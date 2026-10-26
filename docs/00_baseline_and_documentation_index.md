# P0 Baseline and Documentation Governance / P0 基线与文档治理

**Status / 状态:** Implemented on 2026-10-26

## English Summary

P0 established a reproducible factual baseline before adding an Agent runtime. On
Windows 11 with Python 3.14.7, all 34 collected tests passed against the explicitly
named disposable `banking_test` PostgreSQL database. Ruff and strict mypy passed,
Alembic was at revision `20261022_0007`, and deterministic seeding succeeded twice.
The current Core exposes 41 OpenAPI paths, 42 operations, 46 schemas and 32 typed
tools. The tool catalog declares 21 Green, 4 Yellow, 5 Red and 2 dynamic
Yellow-or-Red tools.

The Yellow and Red end-to-end transfer paths, Green reads, budget inspection and
authorized subscription cancellation were exercised against a running local API.
No Docker CLI was available, but the already-running PostgreSQL service allowed all
PostgreSQL integration tests and migrations to execute. This is an environment
limitation, not an unverified database claim.

## 中文正文

### 范围、依赖与不做事项

本阶段只核验既有 Banking Core、Typed Tool、迁移、种子、演示和文档契约，不实现
Planner、Provider、LangGraph 或前端，也不改变 REST/Tool 公共契约。依赖本地 Python
虚拟环境及明确命名的可丢弃测试库 `banking_test`。未打印 `.env` 值，只枚举配置键名。

### 实测环境与结果

| 项目 | 实测结果 |
|---|---|
| OS / Python | Windows 11 / Python 3.14.7 |
| Alembic head | `20261022_0007` |
| 测试 | 34 passed；JUnit 用例总耗时 10.732 s；38 条依赖弃用警告 |
| PostgreSQL | 6 个集成用例通过，含迁移、种子、并发、账本不可变、审批/MFA、分析/卡/理财 |
| Ruff | All checks passed |
| mypy | 61 source files，0 issues |
| Seed | 连续运行两次均成功，验证幂等 |
| OpenAPI | 41 paths / 42 operations / 46 schemas |
| Typed tools | 32 tools |
| Docker | CLI 不可用；未执行 Compose 生命周期命令 |

### 能力事实矩阵

| 能力 | 状态 | 事实依据 |
|---|---|---|
| 账户、流水、收款人、转账与双重记账 | 已实现 | API、工具、单元和 PostgreSQL 集成测试 |
| Green/Yellow/Red、精确审批、模拟 MFA | 已实现/比赛模拟 | 安全测试及 Yellow/Red 演示 |
| 预算、消费、订阅 | 已实现 | API、工具、集成测试和演示 |
| 卡与虚构理财 | 已实现/虚构数据 | API、工具和集成测试 |
| 正式身份系统、真实 MFA、真实银行网络 | 未实现 | README 已明确为比赛桩/模拟银行 |
| CORS | 未实现 | `main.py` 未注册 CORS middleware |
| Agent API、Planner、LLM Provider | 未实现 | 无 `agent/` 包或 `/agent` 路由 |
| LangGraph checkpoint/interrupt/SSE | 未实现 | `docs/langgraph_integration.md` 仅定义未来边界 |
| 中文对话前端与实验看板 | 未实现 | 无 `frontend/` 目录 |
| Jev、统一数据集与模型对照实验 | 未实现 | 无对应运行时代码和冻结数据集 |

### 契约核验

`docs/A_manual.md` 的 Method/Path 清单与生成的 OpenAPI 快照一致；当前明确没有
`/chat`、`/voice` 或 `/savings-pots`。Tool Registry 快照显示模型可见参数中不包含
`authorization_reference`；可信身份和授权继续由 `ExecutionContext` 注入。

### 演示异常与恢复

`scripts.demo_end_to_end` 一次完成 Green、Yellow、Red、预算和订阅场景。首次运行
`scripts.demo_tool_calls` 因缺少三个文档未说明的环境变量失败；补齐确定性种子 ID 后，
Lin 用户又因此前演示累计转出进入 Red 而被 Core 正确拒绝普通确认。未重置数据库，改用
另一位虚构种子用户后完成原定 Yellow 流程。README 已补充所需变量和“新业务日/累计额”
前提。这一过程证明安全策略没有为了演示而绕过。

### 已知技术债

1. Python 3.14 下 pytest-asyncio 与测试客户端产生 38 条弃用警告，应在不改变行为的前提下升级适配。
2. `demo_tool_calls` 固定幂等键并假设当日累计额较低，适合作为受控演示，不是可无限重复的 smoke test。
3. 本机无 Docker CLI，无法验证 Compose 启停；数据库功能已通过直连 PostgreSQL 验证。
4. CORS、正式认证、Agent API、Provider、持久编排、前端和评测体系尚未实现，将由后续阶段处理。

## Contracts / 契约

- REST 契约快照：`evaluation/reports/p0_openapi.json`。
- Tool 契约快照：`evaluation/reports/p0_tool_schemas.json`。
- 金额仍为十进制字符串；模型无权提供身份、风险等级或授权引用。
- P0 未改变现有 API 或 Tool schema，仅补充开发依赖、证据生成器和 README 演示说明。

## Evidence / 证据

Reproduce / 复现：

```powershell
$env:DATABASE_TEST_URL = "postgresql+psycopg://banking:banking@localhost:5432/banking_test"
.\.venv\Scripts\pytest.exe -q --junitxml=evaluation/reports/p0_pytest.xml
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe banking_core agent_tools shared scripts tests
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_demo_data
.\.venv\Scripts\python.exe -m scripts.generate_p0_evidence
```

Raw data / 原始数据：

- `evaluation/reports/p0_pytest.xml`
- `evaluation/reports/p0_baseline.json`
- `evaluation/reports/p0_tests.csv`
- `evaluation/reports/p0_api_operations.csv`
- `evaluation/reports/p0_tools.csv`
- `evaluation/reports/p0_openapi.json`
- `evaluation/reports/p0_tool_schemas.json`

Figures / 图表：

![Tests by module](../evaluation/figures/p0_test_counts_by_module.png)

![API operations by domain](../evaluation/figures/p0_api_operations_by_domain.png)

![Tool risk coverage](../evaluation/figures/p0_tool_risk_coverage.png)

## Decision / 决策

保留现有 Banking Core 和 Typed Tool 边界，不为 Agent 重写金融逻辑。后续阶段以生成的
OpenAPI/Tool 快照为兼容性基线。Docker CLI 缺失不阻止 P0 退出，因为所有依赖 PostgreSQL
语义的集成测试、迁移和种子均已对明确测试库真实执行；Compose 生命周期验证仍作为环境
限制公开记录。
