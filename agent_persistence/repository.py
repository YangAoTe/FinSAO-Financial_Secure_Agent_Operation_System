from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from agent.contracts import AgentRequest, AgentResponse, TrustedAgentContext
from agent.durable import (
    DurableEvent,
    DurableTask,
    TaskStatus,
    new_event_id,
    response_status_to_task,
    utcnow,
)
from agent.proactive import ProactiveSubscription
from agent_persistence.models import (
    AgentEventModel,
    AgentSessionModel,
    AgentTaskModel,
    ProactiveSubscriptionModel,
)


class SqlAlchemyTaskStore:
    def __init__(self, database_url: str | None = None, *, engine: Engine | None = None) -> None:
        if engine is None and database_url is None:
            raise ValueError("database_url or engine is required")
        self._engine = engine or create_engine(cast(str, database_url), pool_pre_ping=True)
        self._sessions = sessionmaker(bind=self._engine, expire_on_commit=False)

    def create_from_response(
        self, *, request: AgentRequest, context: TrustedAgentContext, response: AgentResponse
    ) -> DurableTask:
        now = utcnow()
        with self._sessions.begin() as session:
            existing = session.get(AgentSessionModel, request.session_id)
            if existing is None:
                session.add(
                    AgentSessionModel(
                        id=request.session_id,
                        user_id=context.authenticated_user_id,
                        status="ACTIVE",
                        created_at=now,
                        updated_at=now,
                    )
                )
            elif existing.user_id != context.authenticated_user_id:
                raise PermissionError("session belongs to another user")
            model = AgentTaskModel(
                id=context.task_id,
                session_id=request.session_id,
                trace_id=context.trace_id,
                status=response_status_to_task(response.status).value,
                request_message=request.message,
                plan=response.plan.model_dump(mode="json") if response.plan else None,
                result=response.result,
                error_code=response.error.code if response.error else None,
                recovery_action=None,
                version=1,
                created_at=now,
                updated_at=now,
            )
            session.add(model)
        return self.get_task(task_id=context.task_id, user_id=context.authenticated_user_id)  # type: ignore[return-value]

    def get_task(self, *, task_id: UUID, user_id: UUID) -> DurableTask | None:
        with self._sessions() as session:
            model = session.execute(
                select(AgentTaskModel)
                .join(AgentSessionModel, AgentSessionModel.id == AgentTaskModel.session_id)
                .where(AgentTaskModel.id == task_id, AgentSessionModel.user_id == user_id)
            ).scalar_one_or_none()
            return self._to_task(model, user_id) if model else None

    def claim_waiting(self, *, task_id: UUID, user_id: UUID) -> DurableTask | None:
        with self._sessions.begin() as session:
            model = self._owned_for_update(session, task_id, user_id)
            if model is None or model.status != TaskStatus.WAITING_APPROVAL.value:
                return None
            model.status = TaskStatus.RUNNING.value
            model.version += 1
            model.updated_at = utcnow()
            session.flush()
            return self._to_task(model, user_id)

    def transition(
        self,
        *,
        task_id: UUID,
        user_id: UUID,
        status: TaskStatus,
        result: Any | None = None,
        error_code: str | None = None,
        recovery_action: str | None = None,
    ) -> DurableTask:
        with self._sessions.begin() as session:
            model = self._owned_for_update(session, task_id, user_id)
            if model is None:
                raise KeyError(task_id)
            if model.status in {TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value}:
                return self._to_task(model, user_id)
            model.status = status.value
            if result is not None:
                model.result = result
            model.error_code = error_code
            model.recovery_action = recovery_action
            model.version += 1
            model.updated_at = utcnow()
            session.flush()
            return self._to_task(model, user_id)

    def append_event(
        self, *, task_id: UUID, event_type: str, payload: dict[str, Any]
    ) -> DurableEvent:
        with self._sessions.begin() as session:
            sequence = (
                session.scalar(
                    select(func.coalesce(func.max(AgentEventModel.sequence), 0)).where(
                        AgentEventModel.task_id == task_id
                    )
                )
                or 0
            ) + 1
            model = AgentEventModel(
                id=new_event_id(),
                task_id=task_id,
                sequence=sequence,
                event_type=event_type,
                payload=payload,
                created_at=utcnow(),
            )
            session.add(model)
        return DurableEvent.model_validate(model, from_attributes=True)

    def list_events(
        self, *, task_id: UUID, user_id: UUID, after_sequence: int = 0
    ) -> list[DurableEvent]:
        if self.get_task(task_id=task_id, user_id=user_id) is None:
            raise KeyError(task_id)
        with self._sessions() as session:
            models = session.scalars(
                select(AgentEventModel)
                .where(
                    AgentEventModel.task_id == task_id,
                    AgentEventModel.sequence > after_sequence,
                )
                .order_by(AgentEventModel.sequence)
            ).all()
            return [DurableEvent.model_validate(model, from_attributes=True) for model in models]

    def configure_proactive(
        self,
        *,
        user_id: UUID,
        event_kind: str,
        enabled: bool,
        quiet_start: time | None,
        quiet_end: time | None,
        minimum_interval_minutes: int,
    ) -> ProactiveSubscription:
        with self._sessions.begin() as session:
            model = session.scalar(
                select(ProactiveSubscriptionModel).where(
                    ProactiveSubscriptionModel.user_id == user_id,
                    ProactiveSubscriptionModel.event_kind == event_kind,
                )
            )
            if model is None:
                model = ProactiveSubscriptionModel(
                    id=uuid4(),
                    user_id=user_id,
                    event_kind=event_kind,
                    enabled=enabled,
                    quiet_start=quiet_start,
                    quiet_end=quiet_end,
                    minimum_interval_minutes=minimum_interval_minutes,
                    last_emitted_at=None,
                    created_at=utcnow(),
                )
                session.add(model)
            else:
                model.enabled = enabled
                model.quiet_start = quiet_start
                model.quiet_end = quiet_end
                model.minimum_interval_minutes = minimum_interval_minutes
            session.flush()
            return ProactiveSubscription.model_validate(model, from_attributes=True)

    def reserve_proactive_delivery(
        self, *, user_id: UUID, event_kind: str, now: datetime
    ) -> bool:
        with self._sessions.begin() as session:
            model = session.scalar(
                select(ProactiveSubscriptionModel)
                .where(
                    ProactiveSubscriptionModel.user_id == user_id,
                    ProactiveSubscriptionModel.event_kind == event_kind,
                )
                .with_for_update()
            )
            if model is None or not model.enabled:
                return False
            current_time = now.timetz().replace(tzinfo=None)
            if self._in_quiet_hours(current_time, model.quiet_start, model.quiet_end):
                return False
            if model.last_emitted_at is not None and now - model.last_emitted_at < timedelta(
                minutes=model.minimum_interval_minutes
            ):
                return False
            model.last_emitted_at = now
            return True

    def _owned_for_update(
        self, session: Session, task_id: UUID, user_id: UUID
    ) -> AgentTaskModel | None:
        return session.execute(
            select(AgentTaskModel)
            .join(AgentSessionModel, AgentSessionModel.id == AgentTaskModel.session_id)
            .where(AgentTaskModel.id == task_id, AgentSessionModel.user_id == user_id)
            .with_for_update()
        ).scalar_one_or_none()

    @staticmethod
    def _in_quiet_hours(value: time, start: time | None, end: time | None) -> bool:
        if start is None or end is None:
            return False
        if start <= end:
            return start <= value < end
        return value >= start or value < end

    @staticmethod
    def _to_task(model: AgentTaskModel, user_id: UUID) -> DurableTask:
        return DurableTask(
            id=model.id,
            session_id=model.session_id,
            user_id=user_id,
            trace_id=model.trace_id,
            status=TaskStatus(model.status),
            request_message=model.request_message,
            plan=model.plan,
            result=model.result,
            error_code=model.error_code,
            recovery_action=model.recovery_action,
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
