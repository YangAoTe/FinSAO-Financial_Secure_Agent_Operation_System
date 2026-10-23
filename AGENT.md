# Banking Agent Backend Development Rules

## Project Goal

Build a type-safe, deterministic Mock Banking Core and Typed Agent Tool Layer for an AI Banking Agent competition.

This repository implements banking business logic and agent-facing tools. It does not implement the LLM Planner, Jev, LangGraph orchestration, or frontend.

## Technology Stack

please make a .venv 
- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- PostgreSQL
- Alembic
- HTTPX
- pytest and pytest-asyncio
- Ruff and mypy
- Docker Compose

Avoid adding frameworks without a concrete need.

## Architecture Boundaries

Maintain the following separation:

1. `domain/`: domain entities, value objects, enums, business invariants.
2. `schemas/`: API request and response contracts.
3. `services/`: application-level banking business logic.
4. `persistence/`: SQLAlchemy models, repositories, database transactions.
5. `security/`: identity, authorization, policies, approvals and auditing.
6. `api/`: FastAPI routes and dependencies.
7. `agent_tools/`: typed tool interfaces, registry, gateway and HTTP client.
8. `shared/`: stable contracts shared between components.

Do not mix ORM models, Pydantic API schemas and domain entities into one class.

Do not allow Agent Tools to access the banking database directly.

## Financial Correctness

- Never use binary floating-point types for money.
- Use Decimal and PostgreSQL NUMERIC.
- Use atomic database transactions for state-changing financial operations.
- Use double-entry accounting for transfers.
- Enforce idempotency for operations that can move funds.
- Apply database-level concurrency control.
- Never return a fake success response.
- The Banking Core is the sole authority for financial state.

## Security

- Never trust model-generated user identity, authorization or risk tier.
- ExecutionContext must come from trusted server-side code.
- Financial write operations require deterministic authorization checks.
- Green: authenticated read-only operations.
- Yellow: explicit user confirmation.
- Red: strong verification, simulated only in the competition backend.
- Daily transfer limits must use cumulative amounts, not merely per-transfer amounts.
- Approval must be bound to the exact operation.
- Recheck authorization before committing a financial mutation.
- Prevent unauthorized cross-user data access.
- Do not log secrets or sensitive authentication credentials.

## Implementation Style

- Use clear, small classes with well-defined responsibilities.
- Prefer composition over inheritance.
- Use type annotations for public methods.
- Use Protocol or ABC for replaceable interfaces.
- Use Pydantic for data validation.
- Use dependency injection for services and repositories.
- Use stable enums and error codes.
- Avoid circular imports.
- Avoid placeholder implementations when functional code is expected.
- Avoid broad exception swallowing.

## Development Workflow

For every new task:

1. Inspect the existing repository and this file.
2. Summarize the scope and relevant existing interfaces.
3. Implement only the requested phase.
4. Add or update appropriate tests.
5. Run available tests, Ruff, and mypy.
6. Report modified files, test results, and remaining issues.

Do not rewrite previously completed modules without a justified compatibility or correctness reason.

Do not silently change public API contracts.

If a change requires migration or compatibility updates, implement them explicitly.

## Definition of Done

A phase is complete only if:

- The requested functionality is implemented.
- Its tests exist.
- Relevant tests pass.
- Database migrations are consistent.
- Public interfaces are documented.
- No unrelated functionality was broken.

If Docker, PostgreSQL, or other services cannot run in the current environment, report exactly which checks could not be performed.

Do not claim that unexecuted tests passed.