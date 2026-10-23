# Future LangGraph integration

The future planner should receive only metadata exported by `ToolRegistry.list_allowed()`. It must not construct identity or authorization fields.

```python
from uuid import uuid4

from agent_tools import ExecutionContext, ToolGateway, ToolRegistry
from agent_tools.client import BankingHttpClient, StaticServiceAuthenticator
from agent_tools.tools import register_default_tools

client = BankingHttpClient(
    "http://banking-core:8000",
    StaticServiceAuthenticator("service-secret-from-secret-store"),
)
registry = ToolRegistry()
register_default_tools(registry, client)
gateway = ToolGateway(registry)

# Constructed by trusted session middleware, never from LLM arguments.
context = ExecutionContext(
    authenticated_user_id=authenticated_user.id,
    session_id=session.id,
    task_id=uuid4(),
    trace_id=uuid4(),
)

schemas = registry.list_allowed()
result = await gateway.execute(
    tool_name="get_balance",
    arguments={"account_id": "..."},
    context=context,
)
```

When a mutation returns `WAITING_APPROVAL`, interrupt the graph and use the Banking Core approval API. Resume with a newly constructed trusted context whose `authorization_reference` is the returned grant ID. Never add that reference to LLM-visible tool arguments. A Red approval requires the simulated MFA flow before a grant exists.

## Tool catalog

| Tool | Purpose | Risk | Important errors |
|---|---|---|---|
| `get_accounts` | List owned accounts | Green | identity, upstream |
| `get_balance` | Read owned balance | Green | not found, cross-user |
| `get_transactions` | Paginated history | Green | validation, cross-user |
| `resolve_beneficiary` | Exact deterministic resolution | Green | ambiguous/not found result |
| `create_transfer_draft` | Reserve transfer intent | Yellow/Red | idempotency conflict, currency |
| `get_transfer_status` | Reconcile transfer outcome | Green | not found, cross-user |
| `commit_transfer` | Commit approved transfer | Yellow/Red | approval, MFA, funds, unknown outcome |
| `get_monthly_summary`, `analyze_spending` | Ledger-derived spending | Green | validation |
| `categorize_transaction` | Manual category correction | Green | ownership |
| `get_budget_status`, `create_budget`, `update_budget` | Virtual budget operations | Green | ownership, validation |
| `list_subscriptions`, `detect_recurring_payments` | Subscription evidence | Green | upstream |
| `cancel_subscription` | Persist cancellation | Yellow | approval/replay |
| `list_cards`, `get_card_status`, `update_card_limit`, `freeze_card`, `unfreeze_card` | Card management/status | Green/Yellow | ownership/state |
| `report_card_lost` | Irreversibly mark lost | Red | MFA/approval/state |
| `list_wealth_products`, `compare_wealth_products` | Fictional product research | Green | validation |
| `get_wealth_recommendations` | Deterministic suitability-filtered product list | Green | empty until assessed |
| `assess_risk_profile`, `get_holdings` | Suitability/holdings | Green | questionnaire |
| `create_wealth_subscription_draft` | Prepare mock order | Red at commit | suitability/idempotency |
| `commit_wealth_subscription` | Balance-changing mock order | Red | MFA/funds/replay |
| `create_wealth_redemption_draft`, `commit_wealth_redemption` | Supported fictional redemption | Red | MFA/holding/replay |
| `get_wealth_order_status` | Reconcile a wealth mutation outcome | Green | not found, ownership |

Every tool publishes its input/output JSON Schema, action identifier and risk policy. Results use `SUCCESS`, `WAITING_APPROVAL`, `MFA_REQUIRED`, `DENIED`, `VALIDATION_ERROR` or `EXECUTION_ERROR`. Stack traces and credentials are never returned to the planner.

On `UNKNOWN_OUTCOME`, call the relevant status tool with the original operation identifier. Do not generate a new idempotency key and blindly repeat the mutation.

