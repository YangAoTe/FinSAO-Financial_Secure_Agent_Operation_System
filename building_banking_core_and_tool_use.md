# Phase 1 — Foundation, Domain Models and Database

You are building Phase 1 of a Python-only AI Banking Agent backend.

Read `AGENTS.md` first. If it does not exist, create it using the project's established architecture constraints.

## Objective

Create a clean, runnable backend foundation with explicit domain models, database models, migrations, and deterministic seed data.

Do not implement LLM, LangGraph, Jev, Agent Tools, or complete banking business logic in this phase.

## Requirements

### 1. Initialize the project

Use:

- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- PostgreSQL
- Alembic
- pytest
- Ruff
- mypy
- Docker Compose

Create `pyproject.toml`, `.env.example`, `.gitignore`, `Dockerfile`, `docker-compose.yml`, and `README.md`.

Use environment-based configuration with Pydantic Settings.

### 2. Establish package structure

Create:

- `banking_core/app/api/`
- `banking_core/app/domain/`
- `banking_core/app/schemas/`
- `banking_core/app/services/`
- `banking_core/app/persistence/`
- `banking_core/app/security/`
- `agent_tools/`
- `shared/`
- `scripts/`
- `tests/`

Include valid Python package initialization where needed.

### 3. Implement core domain models

Define:

- User
- Account
- Beneficiary
- Transaction
- LedgerEntry
- TransferDraft
- Budget
- Subscription
- Card
- WealthProduct
- AuditEvent

Create clear enum types for account status, transaction status, transfer status, card status, currency and risk tier.

Use Decimal for all monetary amounts.

Separate domain models, API schemas and SQLAlchemy ORM models.

Create reusable `Money` value-object utilities where appropriate.

### 4. Database infrastructure

Implement:

- SQLAlchemy engine and session management
- PostgreSQL connection configuration
- Base ORM model
- Repository interfaces
- Alembic configuration
- Initial migration
- Foreign keys and appropriate unique constraints

Design the schema to support future double-entry accounting.

Ensure consistent UUID or string identifier conventions across all entities.

### 5. Seed data

Create an idempotent `scripts/seed_demo_data.py` script.

Populate:

- At least three fictional users
- Two or more accounts per user
- Beneficiaries
- Three months of sample transactions
- Subscriptions
- Budgets
- Cards
- Mock wealth products

Seed data must be deterministic and safe to rerun.

Use fictional information only.

For initial balances and existing transactions, use a balanced opening-ledger model rather than arbitrary inconsistent balance updates.

### 6. Minimal API

Implement:

- `GET /health`
- `GET /health/db`

Expose OpenAPI documentation.

### 7. Tests

Test:

- Domain model validation
- Decimal precision
- Invalid enum values
- Database creation and migrations
- Seed-data consistency
- Health endpoints

## Constraints

Do not implement transfer execution yet.

Do not introduce unnecessary service abstractions or placeholders.

Do not implement authentication beyond a clearly isolated development stub.

Do not use SQLite as a substitute for PostgreSQL when verifying transaction-related semantics.

## Acceptance Criteria

1. The backend starts successfully.
2. PostgreSQL is accessible.
3. Alembic migrations complete successfully.
4. Seed data can be loaded and rerun without duplicates.
5. Domain, schema and ORM layers are separate.
6. Tests pass.

## Execution Instructions

Inspect the repository, implement the files directly, run available checks and fix failures.

At the end, report:

- Project structure
- Models implemented
- Migration status
- Seed results
- Test results
- Setup and startup commands

Stop after Phase 1. Do not proceed to Phase 2.




# Phase 2 — Banking Core, Double-Entry Ledger and Transfers

Continue development in the existing repository.

Read `AGENTS.md` and inspect the code produced in Phase 1.

Do not regenerate the project or rewrite existing public interfaces unnecessarily.

## Objective

Implement a deterministic, transaction-safe Mock Banking Core covering account queries, transaction history and transfers.

All functionality must work without an AI Agent.

## 1. Domain Services

Implement the following services with clear responsibilities.

### AccountService

Methods:

- `get_accounts(user_id)`
- `get_account(account_id, user_id)`
- `get_balance(account_id, user_id)`
- `get_transactions(account_id, user_id, filters)`

Account ownership must be verified by the backend.

### BeneficiaryService

Methods:

- `list_beneficiaries(user_id)`
- `resolve_beneficiary(user_id, query)`

If multiple beneficiaries match, return an explicit ambiguous result rather than choosing one silently.

### LedgerService

Implement append-only double-entry accounting.

Requirements:

- Every completed transfer creates balanced debit and credit entries.
- Every account balance mutation must be atomic with its ledger entries.
- Ledger records must not be silently modified after posting.
- Verify ledger balance invariants.
- Support opening balance entries created by the seed script.
- Do not use float for money.

### TransferService

Methods:

- `create_transfer_draft(...)`
- `get_transfer_draft(...)`
- `commit_transfer(...)`
- `get_transfer_status(...)`

Define explicit states:

- DRAFT
- PENDING_AUTHORIZATION
- AUTHORIZED
- PROCESSING
- COMPLETED
- FAILED
- CANCELLED
- EXPIRED

Use an explicit state-transition policy. Reject invalid transitions.

## 2. Database Concurrency

Use SQLAlchemy transaction management and PostgreSQL row-level locks or equivalent safe conditional updates.

Ensure that:

- Concurrent transfers cannot overspend an account.
- Locks are acquired in deterministic order.
- All financial mutations happen in one atomic transaction.
- Duplicate transfer requests do not debit twice.
- An insufficient-funds failure leaves balances unchanged.

Implement database-backed idempotency.

For identical idempotency keys and identical request payloads, return the same operation result.

For identical keys and different payloads, reject the request.

Store enough operation state to reconcile a timeout without blindly executing again.

## 3. Temporary Authorization Boundary

Do not make transfer commit publicly executable without authorization.

Phase 3 will implement the complete approval workflow.

For now, define a narrow `TransferAuthorizationVerifier` Protocol and a default fail-closed implementation.

A development-only test implementation may issue explicit test authorizations, but it must not be enabled in normal runtime configuration.

Keep this boundary easy to replace in Phase 3.

## 4. REST APIs

Implement:

- GET `/accounts`
- GET `/accounts/{account_id}/balance`
- GET `/accounts/{account_id}/transactions`
- GET `/beneficiaries`
- POST `/transfers/drafts`
- GET `/transfers/drafts/{draft_id}`
- POST `/transfers/{draft_id}/commit`
- GET `/transfers/{transfer_id}`

Use typed Pydantic request and response schemas.

Keep business logic out of route handlers.

Use a clearly isolated mock-auth dependency with no client-controlled impersonation enabled in normal runtime.

## 5. Testing

Add tests for:

- Authorized account queries
- Cross-user access rejection
- Beneficiary ambiguity
- Draft lifecycle
- Successful transfer
- Insufficient funds
- Duplicate idempotency keys
- Same key with different payload
- Concurrent transfers
- Rollback on database failure
- Balanced ledger entries
- Invalid state transitions
- Unauthorized commit rejection

Tests must assert database state and ledger consistency.

Use real PostgreSQL for concurrency integration tests.

## Acceptance Criteria

A transfer through the domain service correctly modifies sender and recipient balances, creates balanced ledger records, returns a transaction ID, and is safe under concurrent and duplicate requests.

The public API must not expose an authorization bypass.

## Instructions

Implement Phase 2 directly in the existing repository.

Run tests, Ruff and mypy.

Explain key concurrency and idempotency decisions.

Stop after Phase 2. Do not start Phase 3.


# Phase 3 — Security, Policy Engine and Authorization

Continue from Phase 2. Read `AGENTS.md` and inspect existing interfaces before modifying code.

## Objective

Implement the deterministic security and authorization system for the Mock Banking Core.

The security layer must be independently testable and must not depend on LLM decisions.

## 1. Policy Models

Define explicit Pydantic and Enum types:

- `RiskTier`: GREEN, YELLOW, RED
- `PolicyStatus`: ALLOWED, REQUIRES_CONFIRMATION, REQUIRES_MFA, DENIED
- `PolicyDecision`
- `AuthorizationRequest`
- `ApprovalRecord`
- `AuthorizationGrant`
- `SafetyLockState`

Separate risk classification from authorization status.

The LLM must never provide an authoritative risk tier.

## 2. Policy Engine

Implement `PolicyEngine.evaluate(action, actor, resource, context)`.

Competition rules:

GREEN:
- Balance query
- Transaction and bill queries
- Investment-return queries

YELLOW:
- Daily outgoing transfers up to RMB 1,000
- Subscription cancellation
- Virtual-card application

RED:
- Daily outgoing transfers exceeding RMB 1,000
- Password changes
- Card loss reporting
- Wealth subscription

For the competition's RMB transfer threshold, use the user's cumulative daily outgoing amount, including relevant committed and pending/reserved transfers.

Use a documented business timezone and exact daily-boundary policy.

Prevent concurrent requests or split transfers from bypassing the daily threshold.

Where a full function is not yet implemented, define its policy but do not invent a successful business execution.

## 3. Approval Service

Implement:

- Create approval request
- Retrieve pending approval
- Accept or reject confirmation
- Expire approval
- Verify authorization
- Consume single-use authorization

Approval must bind to:

- Actor identity
- Target account
- Recipient or resource
- Operation type
- Exact amount and currency, where relevant
- Canonical operation payload hash
- Expiration time
- Risk tier
- Operation identifier

An approval must not authorize a modified operation.

Use a secure server-generated identifier, not an `approved=true` flag.

Revalidate business conditions before execution.

## 4. Simulated MFA

Implement a mock MFA provider behind an interface.

The mock implementation must support:

- Challenge creation
- Code verification
- Expiration
- Limited attempts
- Replay prevention
- Lockout on repeated failure

Do not log OTP codes or store them in plaintext.

The simulated provider is for competition demonstrations, not production banking authentication.

## 5. Safety Lock and Audit

Implement configurable lockout rules.

Audit events should include:

- Actor
- Action
- Policy result
- Approval result
- Transaction reference
- Timestamp
- Trace ID
- Failure code

Never log secrets.

Ensure rejected and failed actions are recorded.

## 6. Banking Integration

Replace the temporary authorization verifier introduced in Phase 2.

Every sensitive write operation must invoke the security boundary.

Authorization must be rechecked at commit time.

The Banking Core must reject unauthorized requests even if the caller bypasses the Agent Tool Gateway.

## 7. API Endpoints

Implement appropriately authenticated routes for:

- Creating and retrieving approval requests
- Confirming or rejecting an operation
- Creating and verifying a mock MFA challenge
- Querying authorization status

Avoid returning credentials or internal policy secrets to clients.

## 8. Tests

Test at least:

- GREEN automatic read permission
- YELLOW explicit confirmation
- RED MFA
- 800 RMB transfer
- 1,500 RMB transfer
- 600 + 700 RMB cumulative threshold
- Concurrent transfers attempting limit bypass
- Expired approval
- Approval replay
- Payload modification
- Wrong user approving
- Multiple MFA failures
- Locked user
- Cross-user account access
- Unauthorized direct Banking API access

## Acceptance Criteria

A valid Yellow transfer can be committed after confirmation.

A Red transfer can be committed only after the simulated MFA flow.

Unauthorized, expired, replayed or modified operations are rejected.

The complete operation is audited.

## Instructions

Implement and test Phase 3 only.

Preserve Phase 2 transaction and idempotency guarantees.

Run relevant automated checks and report results.

Stop after Phase 3.

# Phase 4 — Typed Agent Tools, Registry and Secure Gateway

Continue from Phase 3 in the existing repository.

Read `AGENTS.md`, inspect the Banking Core API and security contracts, and reuse established types.

## Objective

Implement a clean, strongly typed, asynchronous Agent Tool Layer that exposes Banking Core functionality to a future LangGraph Agent.

Do not implement the LangGraph graph or LLM planner yet.

## 1. Core Interfaces

Implement these components:

### ExecutionContext

A trusted server-generated context containing:

- Authenticated user identity
- Session ID
- Task ID
- Trace ID
- Authorization reference, if applicable

This object must never be constructed from untrusted model arguments.

### BaseBankingTool

Use an ABC or Protocol with generic Pydantic input and output models.

Each tool must define:

- Name
- Description
- Input schema
- Output schema
- Execute method
- Action identifier
- Risk policy reference

Use a clear `execute(input_data, execution_context)` interface.

### ToolRegistry

Responsibilities:

- Register a tool
- Reject duplicate names
- Find a tool
- List allowed tools
- Export input JSON Schema
- Return metadata for a future LLM Planner

Do not expose authorization objects or internal-only parameters as LLM tool arguments.

### ToolGateway

Responsibilities:

1. Resolve the requested tool.
2. Validate model-generated parameters.
3. Attach trusted ExecutionContext.
4. Verify actor permissions.
5. Call the banking adapter.
6. Validate typed output.
7. Return standardized results.
8. Emit audit and tracing events.

The Gateway must never bypass Banking Core authorization.

## 2. Typed Result Models

Implement a type-safe result contract with explicit statuses:

- SUCCESS
- WAITING_APPROVAL
- MFA_REQUIRED
- DENIED
- VALIDATION_ERROR
- EXECUTION_ERROR

Prefer a typed discriminated union or equivalent Pydantic models.

Avoid ambiguous `success=False` results for legitimate approval waits.

Define standardized error codes.

Do not reveal stack traces or sensitive internal information to the model.

## 3. Banking HTTP Client

Implement an asynchronous HTTPX client.

Requirements:

- Typed request and response validation
- Configurable URL and timeout
- Explicit service-to-service authentication interface
- Proper exception mapping
- Trace propagation
- Request-level idempotency keys for mutations
- Correct handling of unknown transfer outcomes after timeout

Do not blindly retry a financial mutation with a new idempotency key.

Use dependency injection for the HTTP client.

## 4. Initial Tools

Implement:

- `get_accounts`
- `get_balance`
- `get_transactions`
- `resolve_beneficiary`
- `create_transfer_draft`
- `get_transfer_status`
- `commit_transfer`

For `commit_transfer`, the authorization must come from a trusted approved operation reference, not a model-generated approval flag.

Implement a separate trusted approval-resume path if necessary.

Prevent the LLM from inventing an authorization token.

## 5. Example Tool Classes

Use explicit types.

Example design:

```python
class GetBalanceInput(BaseModel):
    account_id: str


class GetBalanceOutput(BaseModel):
    account_id: str
    balance: Decimal
    currency: str


class GetBalanceTool(BaseBankingTool[GetBalanceInput, GetBalanceOutput]): ...
```

All tool classes should have clear responsibility boundaries.

## 6. Standalone Demonstration

Create `scripts/demo_tool_calls.py`.

Demonstrate:

1. Construct a trusted mock execution context through the development identity provider.
2. Query account balance through ToolGateway.
3. Query transaction history.
4. Create a transfer draft.
5. Observe WAITING_APPROVAL or MFA_REQUIRED.
6. Complete approval through the trusted approval service.
7. Execute the authorized transfer.
8. Verify balances and transaction receipt.

Do not bypass security for the demonstration.

## 7. Tests

Implement tests for:

- Tool registration
- Duplicate registration
- Unknown tool names
- Input schema validation
- Output validation
- Trusted context handling
- Authorization enforcement
- Invalid approval
- Successful Banking API call
- HTTP timeout
- Upstream banking errors
- Error-result normalization
- Cross-user data access
- Duplicate transfer execution

## Acceptance Criteria

A future LangGraph Agent should be able to call:

```python
result = await tool_gateway.execute(
    tool_name="get_balance",
    arguments={"account_id": "acc_001"},
    context=trusted_context,
)
```

All banking access must pass through the typed Tool Gateway.

The Tool Layer must not import SQLAlchemy repositories or access the Banking Core database directly.

## Instructions

Implement Phase 4 only.

Update documentation with a short guide explaining how a future LangGraph agent should discover and invoke tools.

Run tests, Ruff and mypy.

Stop after Phase 4.

# Phase 5 — Bills, Budgets and Subscription Management

Continue development from Phase 4.

Read `AGENTS.md`. Preserve all existing domain, security and Tool Gateway interfaces.

## Objective

Implement deterministic spending analytics, budget management and subscription management in the Banking Core, and expose them through typed Agent Tools.

## 1. Bill Analysis

Create `BillAnalysisService` with functions for:

- Monthly spending summary
- Category-level spending
- Merchant-level spending
- Transaction filtering
- Unusual spending detection
- Monthly comparison

Use existing transaction ledger data, not LLM-generated amounts.

Distinguish account transfers from actual consumer spending to avoid double-counting.

Create a deterministic transaction categorization mechanism using merchant rules and manually defined mappings.

Unrecognized transactions should have an explicit UNKNOWN category.

Allow manual category correction.

## 2. Budget Management

Implement `BudgetService`.

Functions:

- Create budget
- Update budget
- List budgets
- Calculate current usage
- Calculate remaining allowance
- Estimate month-end spending
- Detect configurable spending threshold exceedance

Budget periods must use a documented timezone.

Separate a virtual budgeting allocation from actual transfer of funds.

Budget changes must not directly modify account balances.

Validate budget ownership and prevent unauthorized updates.

## 3. Subscription Management

Implement `SubscriptionService`.

Functions:

- List subscriptions
- Detect recurring payments
- Estimate next billing date
- Create renewal reminder records
- Cancel supported mock subscriptions
- Track cancellation state

Recurring-charge detection must be based on transaction history and clearly defined heuristics.

Return a confidence indicator and evidence references for inferred subscriptions.

Do not claim a subscription is cancelled merely because the Agent requested cancellation.

Cancellation must change the relevant simulated subscription state through a transactional business operation.

Apply Yellow Tier confirmation to cancellation.

## 4. API Endpoints and Agent Tools

Add REST APIs and matching typed tools for:

- `get_monthly_summary`
- `analyze_spending`
- `categorize_transaction`
- `get_budget_status`
- `create_budget`
- `update_budget`
- `list_subscriptions`
- `detect_recurring_payments`
- `cancel_subscription`

Reuse the existing Tool Registry and Gateway.

Do not create a second tool execution framework.

## 5. Tests

Cover:

- Correct category totals
- Monthly summaries
- Exclusion of internal transfers from spending
- Unknown merchant category
- Budget ownership
- Budget limit calculations
- Date and month boundaries
- Recurring payment detection
- False-positive recurring detection cases
- Subscription cancellation authorization
- Duplicate cancellation requests
- Correct database state after cancellation

## Acceptance Criteria

The user can retrieve spending analysis, configure a monthly budget and safely cancel a mock subscription.

All operations are available through both Banking APIs and typed Agent Tools.

## Instructions

Implement, test and document Phase 5.

Preserve previous functionality.

Stop after Phase 5.

# Phase 6 — Card Management and Mock Wealth Operations

Continue development from Phase 5.

Read `AGENTS.md` and follow established architectural contracts.

## Objective

Implement simulated card management and wealth product operations with deterministic security rules and typed Agent Tools.

Do not integrate real banking or investment providers.

## 1. Card Management

Implement `CardService` with:

- List cards
- Get card details
- Update spending limits
- Freeze card
- Unfreeze card
- Report card lost
- Retrieve card operation status

Define explicit card states and allowed transitions.

Prevent a LOST card from being unfrozen or used through an invalid transition.

Require the authenticated user to own or be explicitly authorized for the associated account.

Apply the competition's permission tiers.

Card loss reporting must require Red Tier verification.

Use fictional card identifiers only. Do not store or generate real payment credentials.

## 2. Wealth Management

Implement `WealthService`.

Functions:

- List available mock products
- Filter by product type and risk
- Compare products
- Retrieve mock holdings
- Conduct a risk-assessment questionnaire
- Check product suitability
- Create a subscription draft
- Execute authorized mock subscription
- Simulate redemption where supported

Define product types such as:

- Money market fund
- Bond fund
- Government bond
- Fixed-income product

Use clearly fictional product information.

The backend must distinguish risk assessment, recommendations, order preparation and execution.

Use deterministic suitability rules.

LLM opinions must not override suitability constraints.

Simulated investment subscription must require Red Tier authorization.

Any balance-changing mock wealth operation must use the existing financial ledger and transaction mechanisms.

## 3. Typed Agent Tools

Implement corresponding tools, including:

- `list_cards`
- `update_card_limit`
- `freeze_card`
- `report_card_lost`
- `list_wealth_products`
- `compare_wealth_products`
- `assess_risk_profile`
- `get_holdings`
- `create_wealth_subscription_draft`
- `commit_wealth_subscription`

Use the existing Tool Gateway, ExecutionContext and Policy Engine.

## 4. Tests

Cover:

- Card state transitions
- Unauthorized card operations
- Card loss MFA enforcement
- Invalid limit values
- Product filtering
- Risk questionnaire validation
- Unsuitable product rejection
- Wealth order approval
- Duplicate subscription requests
- Ledger consistency for balance-changing operations

## Acceptance Criteria

Card operations and fictional wealth operations work through REST APIs and Typed Tools, with appropriate risk-tier enforcement and auditable outcomes.

## Instructions

Implement only Phase 6.

Run relevant tests and static checks.

Stop after Phase 6.

# Phase 7 — Integration, Reliability Testing and Competition Demo

This is the final integration phase for the Python Banking Core and Typed Tool Layer.

Read `AGENTS.md`, inspect all implemented modules and review the repository's actual state.

## Objective

Turn the existing implementation into a reproducible, reliable and well-documented competition backend.

Do not add new banking scenarios or introduce new frameworks.

Prioritize correctness, integration, reproducibility and security.

## 1. Architecture Review

Verify the separation between:

- API routes
- Domain models
- Services
- Repositories
- Security
- Agent Tools
- Banking HTTP Client
- Database

Check that:

- Agent Tools do not access the database directly.
- Financial mutations use the Banking Core.
- Authorization is enforced by the Banking Core.
- Public contracts use explicit typed models.
- There are no circular imports.
- There are no duplicated risk engines or tool registries.

Refactor only when necessary to correct architectural problems.

## 2. API Contract Review

Verify:

- Consistent request and response naming
- Consistent error envelopes
- Stable Enum values
- OpenAPI documentation
- Decimal serialization as strings
- Pagination for transaction queries
- Trace ID propagation
- Idempotency semantics
- Approval-required status responses

Document every exposed banking tool's:

- Name
- Purpose
- Input schema
- Output schema
- Risk requirement
- Possible errors

## 3. End-to-End Demo

Create `scripts/demo_end_to_end.py`.

Use the existing Tool Gateway to demonstrate:

### Scenario A — Green

Read account balances and analyze spending.

### Scenario B — Yellow

Prepare an RMB 800 transfer, wait for explicit confirmation, execute it and return a receipt.

### Scenario C — Red

Prepare an RMB 1,500 transfer, require simulated MFA and execute only after successful verification.

### Scenario D — Cross-Scenario

Retrieve spending data, evaluate an existing budget, detect subscriptions and prepare an authorized subscription cancellation.

Do not fake any business results.

All amounts, balances, transaction IDs and operation outcomes must come from persisted Banking Core data.

## 4. Security and Reliability Tests

Implement or strengthen tests for:

- Unauthorized account access
- Forged identity
- Forged approval
- Invalid MFA
- Expired MFA
- Approval replay
- Payload tampering
- Concurrent transfers
- Split-transfer daily-limit bypass
- Duplicate idempotency keys
- Database failure during transfer
- Timeout after a committed transfer
- Consistent transaction status recovery
- Audit record completeness
- Balance and ledger invariants

Use a real PostgreSQL instance for concurrency tests.

## 5. Quality Checks

Run:

- pytest
- Ruff
- mypy
- Alembic migration upgrade
- Seed-data initialization
- End-to-end demo

Fix any discovered defects.

Do not claim tests passed if they were not executed.

## 6. Docker Compose

Verify that Docker Compose can start the required components.

Keep the deployment minimal:

- Banking Core API
- PostgreSQL
- Optional standalone tool demonstration service only if architecturally necessary

Agent Tools may remain an importable Python package.

Provide working health checks.

Do not add Kubernetes, Kafka or a message broker unless strictly necessary.

## 7. Documentation

Update README with:

- Project overview
- Architecture Mermaid diagram
- Technology stack
- Domain model descriptions
- Installation instructions
- Environment configuration
- Database initialization
- API documentation
- Running tests
- Running demo scenarios
- Security model
- Known limitations

Add `docs/langgraph_integration.md` explaining how a future LangGraph Agent can register tools and invoke ToolGateway.

Do not implement the actual LangGraph Agent in this phase.

## 8. Final Audit

Produce a completion matrix with:

- Feature
- Implemented status
- Main files
- Test coverage
- Remaining issues

Clearly distinguish fully implemented functionality from partial or simulated functionality.

## Acceptance Criteria

The project starts reproducibly, all available tests pass, and the demonstration scenarios run through the same public Tool Gateway that the future Agent will use.

The Banking Core is independently testable and remains the authoritative source of financial state.

## Instructions

Implement required integration fixes, tests, demo scripts and documentation.

Run all available checks.

Provide an accurate final report without claiming unverified success.

Stop after Phase 7.