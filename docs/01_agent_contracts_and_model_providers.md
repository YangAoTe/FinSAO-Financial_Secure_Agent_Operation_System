# P1 Agent Contracts and Model Providers / P1 Agent 契约与模型 Provider

**Status / 状态:** Implemented on 2026-10-26

## English Summary

P1 adds a standalone `agent/` package with strict versioned Pydantic contracts and a
provider-neutral structured-generation protocol. Client/model payloads cannot contain
trusted identity, risk, approval, MFA or authorization fields. DeepSeek, Qwen and a
local OpenAI-compatible endpoint share the same result, usage, latency and normalized
error contract. Missing credentials produce an explicit unavailable state and offline
startup remains the default.

Twelve focused contract tests and the full 46-test suite pass. One minimal live
connectivity smoke succeeded for both configured cloud providers. It returned fixed
JSON only and did not call banking tools. The single-sample token and latency values
are connectivity evidence, not a model-quality comparison.

## 中文正文

### 范围、依赖、风险与不做事项

本阶段建立可替换边界，不实现意图路由、Planner、工具执行 API 或 LangGraph。
`agent/` 不导入 ORM/repository，不直连银行数据库。外部 Provider 风险包括凭据泄漏、
超时、限流、异常 JSON 和数据外发；当前通过 `SecretStr`、最小日志、有界重试、统一异常
及显式可用性控制。P2 之前模型输出不会触发工具。

### 可信边界

```text
Untrusted client/model                         Trusted server
AgentRequest(message, session_id)              authenticated_user_id
ConversationMessage + trust label              trace_id / task_id
TaskPlan -> ToolCall(arguments)                 authorization_reference
        |                                       risk / approval / MFA truth
        +-- forbidden trusted field validator --+
```

`TrustedAgentContext` 是普通服务端对象，不是 Pydantic 输入模型，不能从
`AgentRequest` 反序列化。`ToolCall.arguments` 确定性拒绝 `user_id`、`risk_tier`、
`approved`、`mfa_code` 和 authorization 字段。

### Provider 设计

| Provider | 接口 | 无凭据行为 | 上层差异 |
|---|---|---|---|
| DeepSeek | OpenAI-compatible HTTP | `available=false`，调用返回 `PROVIDER_UNAVAILABLE` | 无 |
| Qwen | OpenAI-compatible HTTP | 同上 | 无 |
| Local | 本地 OpenAI-compatible HTTP | 只要求配置模型名，不要求云端 key | 无 |
| Fake | 进程内确定性 fixture | 始终可用 | 仅测试/离线开发 |

统一结果含 Provider、模型、request ID、经 Pydantic 验证的结构化对象、可空 token
usage 和整数毫秒延迟。Provider 无 usage 时字段为 `null`，不估算。HTTP 429、5xx、
timeout/transport error 只做有限指数退避；同一次重试保留 request ID。

### 配置

| Key | Secret | Default / semantics |
|---|---|---|
| `MODEL_PROVIDER` | No | `offline`; `deepseek`, `qwen`, `local` 可选 |
| `MODEL_TIMEOUT_SECONDS` | No | 30，范围 0–300 秒 |
| `MODEL_MAX_RETRIES` | No | 2，最大 5 |
| `DEEPSEEK_API_KEY` / `QWEN_API_KEY` | Yes | 缺失时 unavailable |
| `*_BASE_URL`, `*_MODEL` | No | Provider endpoint/model |
| `LOCAL_MODEL_BASE_URL`, `LOCAL_MODEL_NAME` | No | 本地兼容服务；模型名缺失时 unavailable |
| `LOCAL_MODEL_API_KEY` | Optional secret | 仅供需要认证的本地网关 |

日志只记录 provider、model、request ID。异常不包含响应正文、请求头或密钥。

## Contracts / 契约

### Agent request example

```json
{
  "schema_version": "v1",
  "request_id": "0d33262a-0cfe-43df-a4c1-7069ff0d7e7b",
  "session_id": "8287fed6-29be-4eb4-9980-58aaab1a530f",
  "message": "查余额后给小王转800元",
  "conversation": [],
  "locale": "zh-CN"
}
```

### Task plan example

```json
{
  "schema_version": "v1",
  "plan_id": "73a5b70f-f024-4d2e-8709-c04cc4b1af9c",
  "goal": "查询余额并准备转账",
  "steps": [
    {
      "step_id": "balance",
      "purpose": "读取本人账户余额",
      "depends_on": [],
      "tool_call": {"tool_name": "get_balance", "arguments": {"account_id": "..."}},
      "requires_user_input": false
    }
  ]
}
```

计划中的 tool arguments 仍是不可信候选参数；P2 的 Capability Broker、Plan Verifier
及 Registry 校验后才能执行。模型不能声明可信风险等级。

### Normalized errors / 统一错误

- `PROVIDER_UNAVAILABLE`: no credential/model or deliberately offline; not retryable.
- `PROVIDER_TIMEOUT`: final timeout after finite retries; retryable at a higher boundary.
- `PROVIDER_RATE_LIMITED`: HTTP 429; retryability retained.
- `PROVIDER_UPSTREAM_ERROR`: transport/HTTP failure.
- `PROVIDER_INVALID_RESPONSE`: malformed JSON/schema; not executed or treated as truth.

## Evidence / 证据

```powershell
.\.venv\Scripts\pytest.exe -q tests/test_agent_contracts_providers.py
$env:DATABASE_TEST_URL = "postgresql+psycopg://banking:banking@localhost:5432/banking_test"
.\.venv\Scripts\pytest.exe -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe --no-incremental banking_core agent_tools agent shared scripts tests
.\.venv\Scripts\python.exe -m scripts.provider_smoke  # explicit live call
```

Results / 结果：

| Check | Result |
|---|---|
| Focused contracts | 12 passed |
| Full regression | 46 passed |
| Ruff | passed |
| strict mypy | 69 source files, 0 issues |
| DeepSeek smoke | success; 44 provider-reported tokens; 1080 ms |
| Qwen smoke | success; 26 provider-reported tokens; 1013 ms |

Raw smoke record: `evaluation/reports/p1_provider_smoke.json`.

![Provider connectivity smoke](../evaluation/figures/p1_provider_smoke.png)

限制：两个 live 数字分别只有一个相同固定 JSON 请求，受网络波动、Provider tokenizer
和服务端负载影响，不能排序模型质量、稳定性或成本；正式比较在 P6/P8 使用冻结数据集和
重复运行。

## Decision / 决策

使用轻量 HTTP 兼容适配层而非把具体 Provider SDK 引入 Planner，使 DeepSeek、Qwen 和
本地服务可以无上层变更切换。应用默认 `offline`，避免无意消费额度。结构化输出在适配层
立即通过目标 Pydantic 类型验证；失败时返回统一错误，绝不把未验证文本传给银行工具。
