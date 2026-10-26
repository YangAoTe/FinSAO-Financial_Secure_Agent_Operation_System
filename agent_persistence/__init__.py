"""Persistence adapters for Agent state; never used for financial state."""

from agent_persistence.repository import SqlAlchemyTaskStore

__all__ = ["SqlAlchemyTaskStore"]
