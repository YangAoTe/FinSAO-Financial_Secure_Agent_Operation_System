# FinSAO 前端与后端联调

`demo-final/` 是同学提供的零依赖单页前端。本次接入保留了原有视觉和 Banking Core 业务流程，并连接当前仓库的两个后端进程：

```text
浏览器 http://127.0.0.1:5173
  ├─ /api/core/*  → Banking Core http://127.0.0.1:8000
  └─ /api/agent/* → Agent API    http://127.0.0.1:8100
```

前端服务负责同源代理，因此不需要放宽后端 CORS。Jev 未接入、未调用，也不影响现有功能；当前 Agent 继续使用仓库中的 `RuleRouter + BaselinePlanner + PlanVerifier + ToolGateway`。

## 前置条件

- Python 3.11+，仓库依赖已经安装到 `.venv`。
- PostgreSQL 已启动并已执行迁移、种子脚本。
- Node.js 18+；前端没有 npm 依赖，不需要 `npm install`。
- 根目录 `.env` 至少设置：

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+psycopg://banking:banking@localhost:5432/banking
DEVELOPMENT_USER_ID=<演示用户 UUID>
AGENT_DEVELOPMENT_USER_ID=<与 DEVELOPMENT_USER_ID 相同的 UUID>
MOCK_MFA_CODE=123456
BANKING_BASE_URL=http://127.0.0.1:8000
```

生成确定性的 Lin 演示用户 UUID：

```powershell
uv run python -c "from scripts.seed_demo_data import stable_id; print(stable_id('user:lin'))"
```

身份只由 Core/Agent 服务端环境变量注入。浏览器请求不能提交或覆盖 `user_id`、风险等级、MFA、approval 或授权引用。

## 启动顺序

在仓库根目录分别打开三个终端。

### 1. Banking Core

```powershell
uv run alembic upgrade head
uv run python -m scripts.seed_demo_data
uv run uvicorn banking_core.app.main:app --host 127.0.0.1 --port 8000
```

检查：`http://127.0.0.1:8000/health`。

### 2. Agent API

```powershell
uv run uvicorn agent.app:app --host 127.0.0.1 --port 8100
```

检查：`http://127.0.0.1:8100/openapi.json`。

### 3. 前端

```powershell
cd frontend/demo-final
node server.mjs
```

打开 `http://127.0.0.1:5173`。页面顶部应显示“Core 已连接”和“Agent 已连接”。

可覆盖默认地址：

```powershell
$env:CORE_BACKEND_URL = "http://127.0.0.1:8000"
$env:AGENT_BACKEND_URL = "http://127.0.0.1:8100"
$env:PORT = "5173"
node server.mjs
```

兼容旧变量 `BACKEND_URL`，但新配置建议使用含义更明确的 `CORE_BACKEND_URL`。

## 接入行为

- 账户、余额、流水、转账、预算、订阅、卡片、理财及审批/MFA 页面调用真实 Banking Core。
- AI 助手先调用 `POST /api/agent/requests`，请求包含稳定的浏览器会话 UUID，但不包含用户身份或授权字段。
- 当前 Agent 完成请求时，前端展示后端 `TaskPlan`、工具步骤和 Banking Core 结果。
- 当前 Agent 返回 `NEEDS_CLARIFICATION` 时，前端对其尚未覆盖的消费、预算、订阅、卡片和理财意图使用已有的确定性 Core 工作流。
- `WAITING_APPROVAL` 或 `FAILED` 不会自动重放，防止重复草稿或重复写入；用户转到对应业务页面完成显式确认/MFA。
- Agent 不可用时，业务页面仍可使用 Core，助手明确标记回退状态。
- Core 不可用时会进入内置演示模式。演示模式不写数据库，不能当作后端联调成功的证据。

右上角“JSON 日志”显示最多 40 次请求/响应，并隐藏授权引用与六位 MFA 验证码。

## 当前支持范围

| 页面/能力 | 后端来源 | 状态 |
|---|---|---|
| 账户、余额、流水及分类修正 | Banking Core | 已接入 |
| 转账草稿、Yellow/Red 审批、提交及状态查询 | Banking Core | 已接入 |
| 预算、消费分析、订阅与周期扣费线索 | Banking Core | 已接入 |
| 卡片冻结/解冻/挂失/限额 | Banking Core | 已接入 |
| 风险测评、产品比较、申购/赎回 | Banking Core | 已接入 |
| Agent 单轮请求、计划及结果 | Agent API | 已接入 |
| Jev 路由 | 无 | 按要求暂不接入，保持可插拔 |
| 储蓄罐 | 浏览器预览数据 | 后端尚未实现，不产生真实资金操作 |
| 语音 | 无 | 尚未接入 |

## 验证

前端代理和脚本语法测试：

```powershell
node --test frontend/demo-final/server.test.mjs
node --check frontend/demo-final/server.mjs
```

后端相关验证：

```powershell
uv run pytest tests/test_agent_api.py tests/test_agent_routing_planning.py -q
uv run ruff check agent frontend
```

`server.test.mjs` 会启动隔离的 Core/Agent 假服务，验证：页面可读取、查询字符串/请求体原样转发、Core 与 Agent 不串线、Agent OpenAPI 探测路径正确，以及未知前端路由返回 404。

## 常见问题

- **页面显示 Core 演示模式**：确认 8000 端口和 `/health`，并检查 `DEVELOPMENT_USER_ID`。
- **页面显示 Agent 未连接**：确认 8100 端口和 `AGENT_DEVELOPMENT_USER_ID`；它应与 Core 演示用户一致。
- **Agent 能连通但工具调用失败**：检查 `BANKING_BASE_URL` 和 Core/Agent 的 `BANKING_SERVICE_TOKEN` 配置是否一致。
- **Red 操作无法验证**：检查 `MOCK_MFA_CODE`，演示默认使用六位数字 `123456`。
- **Durable task 接口失败**：确认 `AGENT_DATABASE_URL` 指向已迁移的 PostgreSQL；单轮 `/agent/requests` 与持久任务的数据库要求不同。
- **端口已占用**：用 `PORT`、`CORE_BACKEND_URL`、`AGENT_BACKEND_URL` 覆盖默认值。

不要对含有真实银行信息的数据库运行演示重置命令。当前项目只应使用虚构比赛数据。
