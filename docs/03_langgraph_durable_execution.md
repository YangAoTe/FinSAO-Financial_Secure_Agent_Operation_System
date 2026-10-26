# P3 LangGraph Durable Execution / P3 LangGraph 可恢复编排

**Status / 状态:** Implemented on 2026-10-26

## English Summary

P3 adds durable Agent sessions, tasks and monotonic events, a LangGraph state machine
with interrupt/resume, PostgreSQL checkpoints, task/status/resume/cancel/takeover APIs,
SSE reconnection, outcome reconciliation, and opt-in rate-limited proactive
suggestions. Financial state remains exclusively in the Banking Core.

PostgreSQL tests prove that a LangGraph interrupt can resume after reconstructing the
runtime, duplicate task resume invokes the commit gateway once, events are monotonic,
and cross-user task reads fail. Real persistent demonstrations completed an RMB 800
Yellow transfer and an RMB 1,500 Red transfer with simulated MFA; refreshing the task
returned `COMPLETED`.

## 中文正文

### 范围与不做事项

本阶段持久化的是 Agent 控制状态，不复制余额、账本或审批真相。MFA code 从不进入
AgentState、task、event 或 checkpoint。authorization reference 只经 resume API 进入可信
ExecutionContext 并立即用于 Core 提交，不放入 Prompt 或公开 event。已入账转账只能查询
状态/合法补偿，cancel 不能伪装回滚。

### 状态图

```mermaid
stateDiagram-v2
    [*] --> ingest
    ingest --> route
    route --> plan
    plan --> validate
    validate --> execute
    execute --> reconcile: Green / completed step
    execute --> authorize: Yellow or Red
    authorize --> authorize: interrupt / persisted checkpoint
    authorize --> reconcile: trusted resume
    reconcile --> respond
    respond --> [*]
```

### 审批序列

```mermaid
sequenceDiagram
    participant UI
    participant Agent
    participant Core
    participant PG
    UI->>Agent: POST /agent/tasks
    Agent->>Core: create_transfer_draft
    Agent->>PG: WAITING_APPROVAL + event
    Agent-->>UI: exact plan + draft id
    UI->>Core: create approval / confirm or MFA
    Core-->>UI: authorization_reference
    UI->>Agent: POST /tasks/{id}/resume
    Agent->>PG: atomic claim WAITING -> RUNNING
    Agent->>Core: commit_transfer(trusted context)
    Core-->>Agent: persisted receipt
    Agent->>PG: COMPLETED + monotonic event
    Agent-->>UI: task result
```

### 持久状态

- `agent_sessions`: server-bound user/session ownership.
- `agent_tasks`: trace, minimal request, validated plan, non-secret result reference,
  status, error/recovery action and optimistic version.
- `agent_events`: `(task_id, sequence)` unique, public JSON payload only.
- `agent_proactive_subscriptions`: explicit opt-in, quiet hours, minimum interval and
  last delivery.
- LangGraph checkpoint tables: managed by fixed
  `langgraph-checkpoint-postgres==3.2.0` official migrations; domain tables use Alembic
  revision `20261026_0008`.

### 恢复策略

| Failure | Recovery |
|---|---|
| Duplicate/concurrent resume | row lock atomically claims only `WAITING_APPROVAL`; later calls return terminal task |
| Commit timeout / `UNKNOWN_OUTCOME` | call `get_transfer_status` with original draft/operation ID before any retry |
| Invalid plan/arguments | deterministic failure; correct plan/input, never execute partial invalid plan |
| Approval expired/replayed | Core rejects; task records error and `REVIEW_OR_RETRY` |
| Provider/Jev unavailable | no banking mutation; use deterministic fallback or human takeover |
| Cancel | stops unexecuted task only; terminal completed task remains completed |

### 主动提醒

`BUDGET_THRESHOLD` 与 `SUBSCRIPTION_RENEWAL` 只有显式 enabled 后才可发出。数据库行锁
实现重复投递频控，quiet hours 支持跨午夜。输出类型固定
`automatic_financial_action=false`；若用户决定取消订阅等敏感操作，仍需重新进入同一
Planner/Verifier/Core 审批链。

## Contracts / 契约

Task statuses: `RUNNING`, `WAITING_APPROVAL`, `COMPLETED`, `FAILED`, `CANCELLED`,
`HUMAN_TAKEOVER`. 事件含 UUID、task ID、从 1 开始的 sequence、event type、UTC 时间和
公开 payload。SSE frame 使用 sequence 作为 `id`，支持 `Last-Event-ID` 精确续传。

Resume request:

```json
{"authorization_reference":"out-of-band-grant-id"}
```

该字段不属于 AgentRequest/TaskPlan/ToolCall。Core 在 commit transaction 内再次校验
actor、operation、payload、expiry 和 single-use。

## Evidence / 证据

```powershell
$env:DATABASE_TEST_URL = "postgresql+psycopg://banking:banking@localhost:5432/banking_test"
.\.venv\Scripts\pytest.exe -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe --no-incremental banking_core agent_tools agent agent_persistence shared scripts tests
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.generate_p3_evidence
```

Results: 63 tests passed (62 full-suite baseline plus the added cross-scenario DAG test);
Ruff passed; strict mypy passed for 86 source files; migration
upgrade passed. PostgreSQL-specific evidence covers restart resume, ownership, event
order, duplicate resume and proactive opt-in/rate limiting. Real demonstrations:

| Scenario | Initial | Core tier | Verification | Final/refreshed |
|---|---|---|---|---|
| CNY 800 | WAITING_APPROVAL | YELLOW | explicit decision | COMPLETED / COMPLETED |
| CNY 1,500 after cumulative spend | WAITING_APPROVAL | RED | simulated MFA | COMPLETED |

Local evidence export contains 2 completed tasks and 4 events; it is demonstration
evidence, not a reliability benchmark.

- `evaluation/reports/p3_tasks.csv`
- `evaluation/reports/p3_events.csv`
- `evaluation/reports/p3_durable_summary.json`

![Task outcomes](../evaluation/figures/p3_task_outcomes.png)

![Event types](../evaluation/figures/p3_event_types.png)

### 已知限制

- 正式身份与 MFA delivery 仍是比赛模拟。
- 当前 SSE 端点回放现有事件后结束；浏览器通过 `Last-Event-ID` 重连。生产长连接的
  heartbeat/pub-sub 可在部署需求明确后增加。
- PostgreSQL checkpoint 使用官方同步 saver，以兼容 Windows；异步 psycopg saver 不支持
  Windows 默认 Proactor event loop。
- 当前 DAG 支持余额读取后创建转账草稿；更广泛跨场景动态 DAG 在数据集/Planner 阶段扩展。

## Decision / 决策

业务 task/event 表由 Alembic 管理，LangGraph 内部 checkpoint 表交给固定版本官方迁移，
避免复制其私有 schema。`agent/` 只依赖 TaskStore Protocol；SQLAlchemy 实现在独立
`agent_persistence/`，不会导入 Banking Core ORM 或直接改金融表。重复 resume 的硬门槛
优先于方便重试，因此先做原子 claim，未知结果先对账。
