# Deterministic Mock Banking Core and Typed Agent Tools

Python-only competition backend implementing an independently usable Banking Core, deterministic security policy, PostgreSQL double-entry ledger, and an asynchronous typed tool gateway for a future LangGraph agent. No LLM or LangGraph runtime is included.

## Architecture

```mermaid
flowchart LR
    FutureAgent[Future LangGraph Agent] -->|typed arguments| Gateway[ToolGateway]
    Gateway --> Registry[ToolRegistry]
    Registry --> Tools[Typed Banking Tools]
    Tools -->|HTTP + trace + idempotency| API[FastAPI Banking Core]
    API --> Policy[Policy / Approval / MFA]
    API --> Services[Banking Services]
    Services --> Repositories[SQLAlchemy Persistence]
    Policy --> PostgreSQL[(PostgreSQL)]
    Repositories --> PostgreSQL
    Services --> Audit[(Audit Events)]
```

`agent_tools` has no SQLAlchemy or persistence imports. Financial writes occur only inside Banking Core database transactions. Domain entities, Pydantic API schemas, SQLAlchemy models, services, security, and routes are separate modules.

## Technology

Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL 16, Alembic, HTTPX, pytest, Ruff, mypy, and Docker Compose.

## Implemented domain

- Users, customer/system accounts, beneficiaries, transactions and append-only ledger entries.
- Transfer drafts with explicit lifecycle, row locking and database idempotency.
- Budgets, transaction categories, spending summaries and recurring-payment evidence.
- Subscriptions with authorized cancellation state.
- Cards with state transitions and Red-tier loss reporting.
- Fictional wealth products, risk assessments, suitability, holdings, subscriptions and supported redemptions.
- Approvals, single-use grants, salted/hashed simulated MFA challenges, safety locks and audits.

All identifiers are UUIDs. Money uses `Decimal` and PostgreSQL `NUMERIC(18,2)`; API money inputs reject binary floats. Every balance-changing operation writes balanced debit/credit entries atomically. PostgreSQL rejects updates and deletes to posted ledger entries.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose up -d db
python -m alembic upgrade head
python -m scripts.seed_demo_data
uvicorn banking_core.app.main:app --reload
```

For a host-run API, set `DATABASE_URL` to use `localhost`; inside Compose use hostname `db`. Set `DEVELOPMENT_USER_ID` to a seeded user only in development. The deterministic Lin demo user ID can be printed with:

```powershell
.\.venv\Scripts\python.exe -c "from scripts.seed_demo_data import stable_id; print(stable_id('user:lin'))"
```

The identity dependency reads this server environment value and does not accept a user ID from request or model arguments.
`MOCK_MFA_CODE` is the out-of-band development code for the simulated provider. Each
challenge stores only a salted hash; the code is never returned by the API or logged.

## API

OpenAPI and Swagger UI are available at `/openapi.json` and `/docs`.

- Health: `/health`, `/health/db`.
- Accounts and transfers: `/accounts`, balances, paginated transactions, beneficiaries and transfer drafts/status/commit.
- Security: `/security/approvals`, decisions, MFA creation/verification.
- Analytics: monthly summaries, category correction, budgets and recurring-payment detection.
- Subscriptions: list and authorized cancellation.
- Cards: list/details, limits, freeze/unfreeze and authorized loss reporting.
- Wealth: products/comparison, assessment, holdings, order status, authorized subscriptions and supported redemptions.

All errors use `{ "code": "...", "message": "..." }`. Decimal response values are JSON strings. `X-Trace-Id` is accepted and returned. Mutation clients preserve idempotency keys and report an unknown outcome after a timeout instead of retrying with a new key.

## Security model

- Green: authenticated reads.
- Yellow: explicit confirmation, including daily CNY outgoing transfers up to 1,000 and subscription cancellation.
- Red: simulated MFA, including cumulative daily outgoing transfers above CNY 1,000, card loss, wealth subscription and redemption.

The daily boundary uses `Asia/Shanghai`. Pending/reserved and completed transfers count toward the cumulative threshold, and the user row is locked while an approval is classified. Grants bind actor, operation, accounts/resource, exact amount/currency and canonical payload hash. Grants expire and are single-use. Business conditions and payload hashes are checked again inside the commit transaction.

Mock MFA stores only a PBKDF2 hash plus random salt, limits attempts, prevents replay and creates a timed safety lock. It is demonstrational, not production authentication.

## Seed data

`python -m scripts.seed_demo_data` is deterministic and idempotent. It creates three fictional users, two accounts each, beneficiaries, three months of transactions, subscriptions, budgets, fictional cards and mock wealth products. Opening balances and history are balanced postings against a system settlement/equity account.

## Checks and demonstrations

```powershell
.\.venv\Scripts\pytest.exe
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe banking_core agent_tools shared scripts tests
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_demo_data
.\.venv\Scripts\python.exe -m scripts.demo_tool_calls
.\.venv\Scripts\python.exe -m scripts.demo_end_to_end
```

The transfer tier scenarios assume a fresh demo database for the current business day. To replay
the exact Yellow-then-Red sequence with Compose, recreate only the disposable demo volume with
`docker compose down -v`, then start the stack again. Never use that command for a database volume
containing valuable data.

Concurrency, migration, ledger immutability and seed integration tests require a disposable real PostgreSQL database:

```powershell
$env:DATABASE_TEST_URL = "postgresql+psycopg://banking:banking@localhost:5432/banking_test"
.\.venv\Scripts\pytest.exe -m postgres
```

These tests downgrade the target to Alembic `base`; never use a valuable database.

## Completion matrix

| Feature | Status | Main files | Coverage |
|---|---|---|---|
| Domain and PostgreSQL foundation | Implemented | `domain/`, `persistence/models.py`, migrations 0001–0007 | Domain, migration and seed tests |
| Double-entry transfers | Implemented | `services/transfers.py`, `services/ledger.py` | Idempotency, ownership, balance, concurrency and ledger tests |
| Policy, approvals and MFA | Implemented/simulated | `security/` | Tier, hash, expiry, replay and lock paths |
| Typed Tool Gateway and HTTP client | Implemented | `agent_tools/` | Registry, validation, HTTP and normalization tests |
| Bills, budgets and subscriptions | Implemented | `services/analytics.py` | Categorization plus PostgreSQL integration paths |
| Cards and fictional wealth | Implemented/simulated | `services/cards_wealth.py` | State, schema, registry and integration paths |
| End-to-end scenarios | Implemented | `scripts/demo_end_to_end.py` | Requires running API and PostgreSQL |

## Known limitations

- Authentication and MFA delivery are competition stubs, not production identity systems.
- Wealth products, holdings, card identifiers and all customer data are fictional.
- No real payment network, investment provider, LLM planner or LangGraph orchestration is included.
- PostgreSQL-specific concurrency and trigger semantics cannot be verified without PostgreSQL; SQLite is intentionally not used as a substitute.

See [LangGraph integration](docs/langgraph_integration.md) for tool discovery and invocation.

