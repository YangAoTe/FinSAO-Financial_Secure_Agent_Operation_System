# FinPilot 后续开发总计划（Codex 自动执行交接版）

> 文档版本：2026-10-26
>
> 适用对象：在一个全新对话中接手本仓库、且不知道任何历史背景的 Codex/开发者
>
> 项目口号：**FinPilot — AI Banking, Built on Trust**
> 本文件只规划后续工作。当前已经完成的 Banking Core 不应被重复实现。

## 0. 新会话必须先读这里

### 0.1 项目目标

本项目面向“AI 代替用户操作银行（安全 + 体验）”比赛。最终系统应能通过中文自然语言或语音理解金融意图，制定可解释、可暂停、可恢复的执行计划，并通过受控工具完成真实的**模拟银行**操作。

项目的核心差异化不是堆叠页面或模型，而是形成一个顺畅、可证明的闭环：

```text
用户中文请求
  -> 规则 / Jev / LLM 路由与规划
  -> LangGraph 可恢复编排
  -> 确定性风险策略（Green / Yellow / Red）
  -> Typed Tool Gateway
  -> Mock Banking Core + PostgreSQL
  -> 可验证结果、审批界面、审计轨迹和实验指标
```

比赛重点按优先级排序：

1. 安全地完成一条端到端主链路，而不是做很多不能闭环的功能。
2. 展示 Goal-Driven Banking：能够理解目标并拆解跨场景任务。
3. 展示 Explainable & Reversible Agent：可查看计划、暂停、恢复和人工接管；已入账资金不能伪装成可任意回滚。
4. 展示 Hybrid Intelligence：规则、可选 Jev、DeepSeek/Qwen 与确定性工具各司其职，并用同一测试集证明准确率、成本和速度差异。
5. 展示 Secure by Architecture：模型无权直接访问数据库、伪造身份、授权或银行执行结果。

### 0.2 开始任何阶段前的必读顺序

每次新会话必须依次阅读：

1. `AGENT.md`：不可违反的工程、安全和完成标准。
2. 本文件 `dev_plan.md`：当前路线、阶段状态和自动推进规则。
3. `README.md`：实际启动、测试、迁移和已知限制。
4. `architecture.md`：总体边界；其中部分内容是规划，不代表已实现。
5. `docs/banking_backend_modules.md`：模块职责和依赖方向。
6. `docs/langgraph_integration.md`：现有 Typed Tool 与未来 Agent 的可信上下文边界。
7. `docs/A_manual.md`：前端布局、JSON 格式、接口、敏感操作流程和支持的用户请求。
8. 当前阶段对应的 `docs/NN_*.md` 报告（若已存在）。
9. 用 `rg --files`、测试和 OpenAPI 检查真实代码；文档与代码冲突时以代码和测试为事实，并修正文档。

### 0.3 当前事实基线（不要重复开发）

截至本计划撰写时，仓库已经具备以下模块：

- FastAPI + Pydantic v2 + SQLAlchemy 2 + PostgreSQL + Alembic 的模块化 Banking Core。
- 账户、余额、流水筛选、收款人解析、转账草稿/提交/状态查询。
- `Decimal/NUMERIC` 金额、原子双重记账、幂等、行锁、不可变账本和真实持久化回执。
- Green/Yellow/Red 策略、累计日限额、精确操作绑定审批、模拟 MFA、安全锁和审计。
- 32 个左右的异步 Typed Agent Tools、Registry、Gateway 和 HTTPX Client；工具不直接访问数据库。
- 消费分析、分类修正、预算、周期扣费线索、订阅提醒和授权取消。
- 银行卡限额/冻结/解冻/挂失，以及虚构理财产品、风险测评、持仓、申购和赎回。
- 迁移 `0001` 至 `0007`、确定性种子、单元/安全/工具/PostgreSQL 集成测试和端到端脚本。
- 本地开发 PostgreSQL 与 `.env` 基础配置；`.env` 中已有 DeepSeek 配置键以及qwen的配置，但任何代码和报告均不得输出密钥。

尚未实现、也是本计划的重点：

- 正式的 Agent Request/Session/Task/Event API。
- DeepSeek/Qwen/本地低参数模型的可替换 Provider、结构化 Planner 和响应生成。
- LangGraph 状态机、PostgreSQL checkpoint、interrupt/resume 和 SSE 事件流。
- Jev 的可插拔路由以及严格对照实验。
- 用于联调和比赛展示的简单中文前端。
- 可复现 JSONL 数据集、统一评测器、成本/延迟/准确率报告。
- 语音、端侧模型、通知读取、青少年模式等扩展能力。

重要边界：当前后端是模拟银行，不连接真实支付网络；认证和 MFA 是比赛演示版本；理财、卡片与客户数据均为虚构内容。

### 0.4 评分标准驱动的系统设计

人工智能赛道评分权重为：**任务完成率 40% + 安全合规性 30% + 创新性及交互体验 30%**。后续开发不能只按功能数量排序，必须让每个评分点都有对应模块、测试数据、可见交互和交付证据。

| 评分项 | 评委关注点 | 对应系统能力 | 量化证据 |
|---|---|---|---|
| 任务完成率 40% | 典型金融任务完成、多步规划合理、工具调用正确 | Slot/Context Tracker、结构化 Planner、Plan Verifier、Typed Tool Gateway、Outcome Reconciler | 端到端任务成功率、计划合法率、工具/参数准确率、状态恢复率 |
| 安全合规性 30% | 防诱导转账、信息窃取、越权和 Prompt 注入；敏感操作确认与风控 | Context & Privacy Guard、Capability Broker、Policy/Approval/MFA、Prompt/Tool Boundary、Audit & Red Team | 攻击阻断率、越权成功率（目标为 0）、敏感数据泄漏率（目标为 0）、审批绕过率（目标为 0） |
| 创新性及交互体验 30% | 场景创新、真实意图深度、多轮追问、主动能力、错误恢复、口语化输入、超范围兜底 | Goal Memory、Clarification Manager、Proactive Event Engine、Recovery Manager、语音/端侧原型、Explainable UI | 多轮任务成功率、澄清有效率、口语鲁棒性、恢复成功率、主动建议接受/误报率、可用性测试 |

在原架构上新增以下 Agent 层模块，原因和边界如下：

1. **Conversation Context & Slot Tracker（会话上下文与槽位追踪）**：保存结构化事实、缺失字段和用户明确选择，解决省略表达、多轮指代和同名收款人问题。它不能保存密钥/MFA，也不能把历史猜测升级为事实。
2. **Goal & Preference Memory（目标与偏好记忆）**：支持“每月留出学习费用”等长期目标。采用显式同意、可查看/可删除、最小保留期和来源标注；金融授权与一次性验证码永不进入长期记忆。
3. **Plan Verifier（计划验证器）**：在执行前检查 DAG、工具白名单、参数来源、前置条件、重复/冲突步骤、风险升级和预算上限。它提高 40% 项中的计划合理性与工具正确率，同时是独立于 LLM 的确定性闸门。
4. **Capability Broker（最小权限能力代理）**：按当前任务、用户、会话和阶段动态下发可见工具集合；模型不能看到或调用无关的敏感工具，从架构上降低越权和工具注入面。
5. **Context & Privacy Guard（上下文与隐私防护）**：对进入外部模型的上下文做数据最小化、字段级脱敏、来源/信任标签和输出泄漏检查；不把简单关键词过滤当成唯一防线。
6. **Prompt/Tool Boundary Guard（提示与工具边界防护）**：将用户内容、检索内容、工具结果和系统指令分区；外部文本一律视为不可信数据，不能改变工具白名单、安全策略或执行权限。
7. **Outcome Reconciler & Recovery Manager（结果对账与恢复）**：遇到超时、断网、结构化输出失败或部分步骤完成时查询持久状态，给出重试、修改、取消或人工接管选项，禁止盲目重复资金操作。
8. **Proactive Event Engine（主动服务引擎）**：只对用户显式订阅的预算超限、订阅续费、可疑支出和目标进度触发建议；默认建议而非自动转账，带静默时段、频率限制、撤销入口和误报反馈。
9. **Safe Fallback & Scope Manager（超范围安全兜底）**：遇到贷款、换汇、真实投资承诺、法律/税务建议或未实现功能时，明确能力边界，提供可执行的安全替代或人工渠道，不捏造工具和结果。

更新后的逻辑架构：

```text
Text / Voice / IM
  -> Input normalization + trust labels
  -> Context & Privacy Guard
  -> Conversation/Goal Memory + Clarification Manager
  -> Rule/Jev/LLM Router + Structured Planner
  -> Plan Verifier + Capability Broker
  -> LangGraph Orchestrator
  -> Policy / Approval / MFA
  -> Typed Tool Gateway -> Banking Core -> PostgreSQL
  -> Outcome Reconciler -> Explainable UI / Safe Fallback

Opt-in Proactive Event Engine -> same Planner/Verifier/Policy path
Audit/Tracing/Red-Team evidence spans every boundary
```

这些模块不能形成第二套授权或金融状态：所有主动任务和恢复任务仍走同一 Planner/Verifier/Policy/Tool/Core 链路。

## 1. Codex 长任务执行协议

### 1.1 状态标记

使用以下状态维护阶段表：

- `[ ]` 未开始
- `[~]` 正在进行
- `[x]` 已完成且通过退出门槛
- `[!]` 阻塞，必须在本文件“执行日志”记录原因和下一步

开始一个阶段时先把它改为 `[~]`；仅当代码、测试、文档、图表和验收均完成时才能改为 `[x]`。不能因为 token 或时间不足而标记完成。

### 1.2 自动推进规则

用户已要求：**一个阶段没有问题后自动执行下一个阶段，直到计划完成。** 因此：

1. 按阶段编号顺序工作，不需要每阶段再次询问许可。
2. 每阶段只做该阶段范围内的变更，先检查工作树并保留用户已有修改。
3. 执行该阶段测试，再执行全量回归、Ruff、mypy 和必要的迁移验证。
4. 更新配套双语报告、本文件状态和执行日志，然后自动进入下一阶段。
5. 可恢复的小问题应自行诊断、修复并继续。
6. 以下情况必须停止并向用户说明，不能自行猜测：需要真实资金/外部账号权限；会删除非测试数据；产品定义会改变安全或资金语义；API/许可证不可获得；同一阻塞经过充分排查仍无法解决。
7. 任何破坏性数据库命令只能针对明确命名的 disposable 测试库。不得对未知数据库执行 downgrade、drop、`docker compose down -v` 等操作。

### 1.3 每阶段固定工作循环

```text
Read -> Inspect -> Baseline -> Design -> Implement -> Test
     -> Experiment -> Plot -> Document -> Review -> Gate -> Next phase
```

每个阶段必须做到：

1. 读取相关源码、已有契约和上一阶段报告。
2. 写出本阶段范围、依赖、风险和“不做什么”。
3. 先补契约/测试，再进行最小兼容实现；不得静默改变现有 REST/Tool Schema。
4. 金额继续使用 Decimal/十进制字符串；模型输出不能成为权威金融结果。
5. 新数据库结构必须带 Alembic migration、upgrade/downgrade 检查和 PostgreSQL 测试。
6. 保存结构化原始实验数据，再由脚本生成图，不手工填写有利数字。
7. 报告必须同时记录成功、失败、异常值、限制和复现命令。
8. 结束时报告修改文件、测试结果、剩余风险；随后按 1.2 自动推进。

### 1.4 通用质量命令

在 Windows PowerShell、已激活 `.venv` 的前提下运行：

```powershell
$env:DATABASE_TEST_URL = "postgresql+psycopg://banking:banking@localhost:5432/banking_test"
python -m pytest -q
ruff check .
mypy banking_core agent_tools shared scripts tests
python -m alembic upgrade head
```

如果后续增加 `agent/`、`evaluation/` 等包，必须同步加入 mypy 检查范围。PostgreSQL 集成测试只能使用可丢弃的 `banking_test`，先校验 URL/数据库名再运行会 downgrade 的测试。

## 2. 文档、实验与产物统一规范

### 2.1 双语文档体系

每个阶段必须创建一个配套 Markdown 到 `docs/`。统一结构为：

1. 标题和状态（Planned / In Progress / Implemented）。
2. `English Summary`：让评委或英文开发者快速理解目标、设计、指标和结论。
3. `中文正文`：完整说明动机、架构、接口、步骤、实验、图表、结果、限制和复现方式。
4. `Contracts / 契约`：输入输出、状态机、错误、兼容性。
5. `Evidence / 证据`：测试命令、结果表、数据路径、图路径。
6. `Decision / 决策`：为什么保留/放弃某方案，不能只给结果。

计划中的文档索引：

| 阶段 | 配套报告 |
|---|---|
| P0 | `docs/00_baseline_and_documentation_index.md` |
| P1 | `docs/01_agent_contracts_and_model_providers.md` |
| P2 | `docs/02_planner_and_safe_routing.md` |
| P3 | `docs/03_langgraph_durable_execution.md` |
| P4 | `docs/04_frontend_integration_and_demo.md` |
| P5 | `docs/05_banking_agent_dataset.md` |
| P6 | `docs/06_llm_baseline_benchmark.md` |
| P7 | `docs/07_jev_router_integration.md` |
| P8 | `docs/08_hybrid_agent_experiments.md` |
| P9 | `docs/09_advanced_experience_prototypes.md` |
| P10 | `docs/10_security_and_competition_readiness.md` |

P0 还要创建 `docs/README.md` 作为总索引，标明文档是“现状”“规范”“实验结果”还是“未来规划”，防止把设计稿误认为已实现功能。已有 `docs/A_manual.md` 保持前端权威契约地位，接口变化必须同步更新它。

### 2.2 实验目录和可复现性

后续允许新增以下目录；命名可以调整，但职责不能混淆：

```text
evaluation/
  schemas/          # JSONL/Pydantic 数据契约
  datasets/         # 无真实 PII 的版本化 train/dev/test
  runners/          # 统一实验执行器
  metrics/          # 正确率、工具参数、计划、安全、成本、延迟
  reports/          # CSV/JSON 原始汇总
  figures/          # seaborn 生成的 PNG/SVG
  manifests/        # 模型、温度、prompt、代码版本、数据 hash
frontend/           # 简单中文演示前端
agent/              # provider、planner、router、graph、API
supporting_materials/ # 全部开发完成后生成的比赛必交材料；开发中不得放未验证结论
```

每次实验必须记录：运行 ID、UTC 时间、数据集版本/hash、代码版本或工作树摘要、Provider、模型、模式、温度、最大 token、重试、样本数、随机种子、并发度、请求/响应 token、首 token/总延迟、错误和费用。无法从 Provider 获得的字段写 `null`，不得估算后冒充实测。

### 2.3 Seaborn 图表要求

用户要求实验阶段使用较多且详细的 seaborn 图表。原则是“图必须回答问题”，同时保留对应 CSV/JSON，不能只贴图。所有图使用可读中文字体或英文标签，标注样本量、单位、误差区间和实验条件，禁止截断纵轴制造夸张差异。

每个实验报告至少选择与该阶段相关的图：

- 意图/工具/风险等级的混淆矩阵热力图。
- 各 Provider/模型/模式的准确率、macro-F1、plan success 分组柱状图。
- 延迟分布 ECDF/箱线图/小提琴图，以及 P50/P95/P99。
- 输入/输出/总 token 分布与任务复杂度关系。
- 单请求成本分布、累计成本曲线、准确率—成本 Pareto 前沿。
- 路由占比、fallback 率、Jev 绕过 LLM 比例、错误路由类型。
- Green/Yellow/Red 分层结果、安全拒绝率、越权攻击成功率。
- 多步任务步骤数与成功率/延迟/token 的关系。
- 多次重复运行的置信区间和失败原因堆叠图。

### 2.4 最终 supporting_materials 必交目录

所有开发、实验和决赛加固完成后，在仓库根目录新建 `supporting_materials/`。它面向评委，不替代 `docs/` 的研发过程报告，而是从最终事实和证据中提炼出的正式提交材料。所有图片同时保留可编辑源文件（Mermaid/Draw.io 等）和导出 PNG/SVG，不得放密钥、真实个人信息、内部 chain-of-thought 或未经验证的宣传数字。

```text
supporting_materials/
  README.md                         # 材料索引、版本、复现入口
  01_technical_documentation.md     # 系统组成、部署、接口、数据流、运行与复现
  02_architecture_and_diagrams.md   # 总体/部署/信任边界/序列/状态/数据架构图
  03_algorithm_description.md       # 路由、规划、验证、Jev/LLM 混合与恢复算法
  04_security_design.md             # 必交：威胁模型、控制、审批、审计、隐私与测试
  05_security_self_assessment.md    # 必交：权限分级说明、已知风险清单和整改状态
  assets/
    diagrams/                       # Mermaid 源文件及 PNG/SVG
    figures/                        # 最终实测图表
    evidence/                       # 脱敏后的测试/实验摘要与 manifest
```

最低内容要求：

- 架构图至少包含：总体逻辑架构、部署架构、数据/信任边界、Yellow/Red 审批序列、LangGraph 中断恢复状态图和实验评测流水线。
- 算法说明至少包含：规则/Jev/云端与本地 LLM 路由、TaskPlan/DAG 生成、Plan Verifier、Capability Broker、风险分级、幂等/对账恢复、本地模型选择/微调及复杂度与降级策略。
- 安全设计至少包含：资产/攻击者/信任边界、Prompt 注入、信息窃取、越权、诱导转账、重放、敏感日志、Provider 数据外发、拒绝服务及对应控制和测试。
- 安全自评必须逐项列出 Green/Yellow/Red 权限与操作、身份与授权来源、数据分类/保留/脱敏、第三方 Provider 边界，以及“风险、影响、可能性、现有控制、剩余风险、责任人/阶段、整改状态”。
- 每个“已实现/已通过/提升 X%”声明都要链接到测试或实验 evidence；规划功能必须标为 Planned/Deferred。

## 3. 总阶段表

| 状态 | 阶段 | 核心交付 | 退出门槛 |
|---|---|---|---|
| [x] | P0 基线与文档治理 | 可复现基线、差距清单、文档索引 | 当前测试/迁移结果有证据，现状与规划不混淆 |
| [x] | P1 Agent 契约与模型 Provider | 安全会话/任务契约、DeepSeek、Qwen、本地模型适配接口 | Provider contract tests 通过，密钥不泄露 |
| [x] | P2 Planner 与安全路由基线 | 上下文/槽位、规则路由、结构化计划、Plan Verifier、Capability Broker | 已支持意图可生成并执行合法工具调用；注入/越权无法扩权 |
| [x] | P3 LangGraph 持久编排 | checkpoint、interrupt/resume、主动事件、对账恢复、SSE | Yellow/Red 可暂停审批并跨进程恢复；主动任务走同一安全路径 |
| [x] | P4 中文演示前端 | 多轮聊天、解释/纠错、可用页面、实验与安全看板 | 遵循 A_manual，核心链路和关键可用性场景通过 |
| [x] | P5 JSONL 数据集 | schema、人工种子、扩展、去重和拆分 | 数据验证/泄漏检查通过，版本与统计完整 |
| [x] | P6 LLM 基线实验 | DeepSeek/Qwen/本地低参数模型及微调前后基线 | 同一数据、同一评分器、重复运行和图表齐全 |
| [~] | P7 Jev 适配与消融 | 可关闭的 Jev Router | 不改变安全边界，失败可 fallback，有独立测试 |
| [ ] | P8 混合方案总实验 | a/b/组合的准确率成本延迟比较 | 结论有统计证据，可复现实验并给出选择 |
| [ ] | P9 高级体验原型 | 储蓄罐优先，语音/端侧按门槛选做 | 至少一个差异化功能形成安全闭环 |
| [ ] | P10 决赛加固与交付 | 安全测试、演示脚本、最终文档 | 全量检查通过，可离线降级，演示可重复 |

## 4. 分阶段详细开发步骤

### P0 — 基线、事实核验与文档治理

目标：给后续所有实验建立可信起点，防止新 Agent 层破坏已经完成的银行核心。

步骤：

1. 检查工作树、Python/依赖版本、环境变量**键名**、PostgreSQL 服务和 Alembic head；绝不打印 `.env` 值。
2. 运行现有 unit/security/tool/PostgreSQL 测试、Ruff、mypy、迁移和种子；记录实际结果，不引用旧对话中的“曾经通过”。
3. 运行 `scripts.demo_tool_calls` 和 `scripts.demo_end_to_end`，记录核心链路、trace ID 和耗时；不得为跑通演示而绕过审批。
4. 从 FastAPI `/openapi.json` 与 Tool Registry 导出当前契约摘要，和 `docs/A_manual.md` 逐项比较。
5. 形成“已实现/部分模拟/未实现/规划中”的能力矩阵和已知技术债；确认 CORS、正式认证、Agent API 尚未实现。
6. 建立 `docs/README.md` 索引及 P0 双语报告。若发现现有文档错误，只做有测试依据的最小修正。

测试与证据：全量质量命令、PostgreSQL 集成测试、seed 幂等、OpenAPI 路径数量、Tool Schema 快照。

图表：测试按模块的数量/耗时、API/Tool 按业务域分布、Green/Yellow/Red 能力覆盖。只有真实采集数据才画图。

退出门槛：基线可以从干净测试库复现；没有密钥/个人信息进入日志；报告准确区分现状和规划。

### P1 — Agent 契约、可信上下文与模型 Provider

目标：先建立可替换边界，再接入任何具体模型，避免 DeepSeek/Qwen SDK 侵入业务代码。

步骤：

1. 新建独立 `agent/` 包；不得把 Planner 放进 `banking_core`，不得让它导入 ORM/repository。
2. 用 Pydantic 定义版本化 `AgentRequest`、`AgentResponse`、`AgentEvent`、`TaskPlan`、`PlanStep`、`ToolCall`、`ConversationMessage` 和错误契约。
3. 明确客户端输入与可信 `ExecutionContext` 的分界：身份、风险级别、`authorization_reference` 只能由服务端注入，永远不进入模型可生成参数。
4. 定义 `ModelProvider` Protocol：结构化生成、流式生成（若需要）、usage、latency、provider error normalization；加入 timeout、有限重试和 request ID。
5. 实现 DeepSeek Provider，读取现有 `DEEPSEEK_API_KEY/BASE_URL/MODEL`；日志只允许出现 Provider/模型/请求 ID。
6. 为 Qwen 预留并实现兼容适配器/配置：`QWEN_API_KEY`、`QWEN_BASE_URL`、`QWEN_MODEL`。没有凭据时明确标记 unavailable，并自动跳过 live test，而不是失败或假数据。
7. 定义 `LocalModelProvider` 接口，兼容本地 OpenAI-style HTTP 服务或进程内推理；上层 Planner 不依赖 Ollama、llama.cpp、Transformers、vLLM 等具体运行时。
8. 本地 Provider 必须返回与云端一致的结构化输出、usage（可获取时）、延迟和错误格式；无法得到 token/能耗字段时使用 `null`，不能伪造。
9. 加入 `MODEL_PROVIDER` 等非秘密配置与启动校验；更新 `.env.example`，不修改或提交真实 `.env`。
10. 用 fake provider 做离线 contract tests；云端 live provider 和本地大模型测试必须带显式 marker，默认测试不能消费 API 额度或自动下载权重。

文档：`docs/01_agent_contracts_and_model_providers.md`，包含 JSON 示例、信任边界、配置表、错误/重试语义和两种 Provider 的差异。

图表：Provider smoke test 的延迟/token 分布仅作为连通性证据，不用于宣称模型优劣。

退出门槛：切换云端/本地 Provider 不改 Planner；无 key 时应用可启动离线模式；日志和异常不含 key；类型检查和 contract tests 通过。

### P2 — 规则优先路由、结构化 Planner 与单轮安全执行

目标：先做不依赖 LangGraph 的单轮垂直切片，得到未来 Jev/LLM 的公平基线。

步骤：

1. 定义统一 `IntentResult`：intent、complexity、confidence、route、reason、required_slots，不包含可信身份/授权。
2. 实现 Conversation Context & Slot Tracker：区分“用户明确提供”“工具验证”“模型推断”三种来源；缺少收款人、账户、金额或币种时先追问，不偷偷补值。
3. 建立确定性 allowlist 规则，只直达非常明确的 Green 查询；不确定、写操作、复合任务进入 Planner。规则无法判断时 fail closed 到更严格路径。
4. 实现 Capability Broker：根据当前已认证用户、任务阶段和风险边界生成最小工具集合；Planner 只能看到该集合的 schema/metadata，不看到数据库、MFA code 或授权 secret。
5. 使用结构化输出生成 `TaskPlan`；Plan Verifier 检查唯一 step ID、依赖存在、无环 DAG、参数来源、前置条件、工具允许性、重复/冲突动作、数量/深度上限和风险升级。
6. 对工具参数执行 Registry 的 Pydantic 验证，不在 prompt 中靠文字保证类型。
7. 建立 Prompt/Tool Boundary：用户输入、外部内容和工具文本都用信任标签隔离；文本中“忽略规则”“调用隐藏工具”等内容不能改变 system policy 或 capability。
8. 实现单轮 Agent Service/API：接收中文消息 -> 追问/路由/规划 -> 验证 -> 执行 Green 工具或返回待确认计划 -> 以工具结果生成模板化反馈。
9. ToolResult 是银行事实的唯一来源；模型不得自行说“转账成功”。未知结果必须调用状态工具恢复。
10. 增加口语、省略、指代、同名收款人、缺少金额、多币种、直接/间接 Prompt 注入、信息套取、诱导转账、虚构工具、越权 user_id、恶意 authorization_ref 等测试。

首个验收场景：“查看余额，然后给小王转 800 元”。此阶段允许生成计划和草稿，但审批恢复在 P3 完成。

文档：`docs/02_planner_and_safe_routing.md`，含 Prompt/结构化 schema 版本、路由决策表、失败案例和安全边界。

图表：规则路由覆盖率、intent/route 混淆矩阵、结构验证失败原因、单轮准确率/延迟/token 基线。

退出门槛：受支持的 Green 请求端到端返回 Core 结果；缺失信息会有效追问；写操作不会未经审批执行；所有模型输出在执行前被确定性验证；不可信内容不能扩大工具能力。

### P3 — LangGraph 可恢复编排与人工审批

目标：实现比赛要求的多步 DAG、持久化、暂停/恢复、人工接管和前端事件流。

步骤：

1. 设计 `AgentState`，只保存完成恢复所需的最小数据：task/session/trace、计划、step 状态、非秘密工具结果引用、审批/授权引用和错误；禁止保存 MFA code。
2. 设计节点：ingest -> route -> plan -> validate -> execute -> authorize/interrupt -> reconcile -> respond；限制循环和重试次数。
3. 使用 PostgreSQL checkpointer；数据库 schema 变化走 Alembic。确认 LangGraph/checkpointer 版本并固定依赖。
4. Green 自动执行；Yellow 在精确操作预览处 interrupt；Red 创建 MFA challenge 后 interrupt。恢复时由可信 API 重新构造 `ExecutionContext`。
5. 授权引用不作为聊天消息或模型参数；提交前 Banking Core 仍重新校验 grant 和业务状态。
6. 定义 Task/Session/Event API 与 SSE：事件有单调序号、版本、时间、task/trace ID；断线支持 `Last-Event-ID` 或等价恢复。
7. 实现 cancel/human takeover。仅取消未执行步骤；已提交资金操作用状态查询和合法补偿，不能宣称数据库回滚。
8. 实现 Outcome Reconciler & Recovery Manager：针对超时、Provider/Jev 故障、参数校验失败、部分步骤成功分别给出“查状态、有限重试、修正计划、取消、人工接管”，并持久化恢复原因。
9. 实现 opt-in Proactive Event Engine 的最小闭环：预算预警或订阅续费事件只生成建议/任务草稿，经过相同 Capability/Plan/Policy 路径；支持静默时段、频率限制和关闭订阅。
10. 增加进程重启、重复 resume、审批过期、grant replay、超时 unknown outcome、SSE 重连、节点失败、并发 resume、主动事件重复投递和用户撤销测试。
11. 完成两条演示：800 CNY Yellow 转账；累计超过 1,000 CNY 的 Red 转账/MFA。再完成一个跨场景只读+写入计划和一个主动提醒但不自动扣款的场景。

文档：`docs/03_langgraph_durable_execution.md`，含状态图、序列图、checkpoint 数据、事件契约、恢复手册和限制。

图表：任务状态转移量、节点耗时、恢复成功率、interrupt 时长、重试/失败原因、不同步骤数下的成功率。

退出门槛：服务重启后任务可恢复；重复事件/resume 不重复扣款；主动事件不越权自动支付；前端可仅凭 API/SSE 呈现完整任务状态和恢复选择。

### P4 — 中文联调与比赛展示前端

目标：做一个真正可用的简单前端，用于开发测试和展示准确率、token、速度与费用；它不是静态原型。

步骤：

1. 先依据 `docs/A_manual.md` 选择轻量 React + TypeScript 技术栈并记录版本；不要引入与目标无关的大型框架。
2. 建立统一 API client、十进制金额处理、snake_case 类型、错误码本地化、trace ID、loading/empty/error/retry 状态和同源代理。
3. 桌面：顶部栏 + 左侧导航 + 主内容 + 底部常驻聊天；移动：顶部栏 + 内容 + 底部导航 + 安全区上方聊天/按键说话入口。
4. 优先页面：总览、账户流水、转账/审批/MFA/回执、消费预算、订阅、银行卡、理财、任务轨迹、实验看板。
5. 聊天抽屉显示计划和可解释的步骤状态，但不要展示隐藏 chain-of-thought；只展示结构化理由、参数来源、工具、风险、审批和已验证结果。
6. 多轮交互必须支持：追问缺失槽位、修改计划中的某一步、返回上一步、拒绝审批、取消未执行步骤、失败后继续、转人工和清除会话记忆。
7. 敏感操作使用“渐进式披露”：普通聊天不展示完整敏感数据；确认页突出收款人、金额、币种、来源账户、风险等级、是否可撤销及审批有效期，避免诱导式按钮和默认勾选。
8. 口语化输入要有转写/理解预览，例如“给小王转八百”先呈现规范化结果；歧义、低置信度和超范围请求给出自然中文澄清与可选下一步。
9. 增加“为什么需要确认”“数据来自哪里”“如何恢复”入口，让用户看到简洁可验证解释，而不是模型思维链。
10. 语音尚未实现时按钮必须明确 disabled/preview，不能伪装已录音执行。
11. 储蓄罐页面可先做清楚标记的 planned/mock 视图，直到 P9 定义正式资金语义和 API。
12. 实验看板读取后端汇总数据，展示任务完成率、安全攻击阻断、准确率、P50/P95、token、费用、错误和 Provider/模式筛选；缺失费用显示“未提供”。
13. 进行小规模可用性走查：首次成功率、完成时间、追问轮数、误触/返回、错误恢复和用户是否理解审批；记录问题而不是只展示截图。
14. 浏览器 E2E 覆盖 Yellow/Red、审批拒绝/过期、刷新恢复、重复提交保护、未知结果恢复、多轮纠错、超范围兜底和移动布局。
15. 若浏览器跨域直连，后端只允许配置明确 origin/header；不能使用生产通配 CORS。

文档：`docs/04_frontend_integration_and_demo.md`，并同步 `docs/A_manual.md` 中所有新增 Agent/SSE 契约与页面状态。

图表：产品实验图使用 evaluation 生成的 seaborn 静态资源或聚合 API；页面本身可用前端图表库交互呈现，但数值来源必须相同。

退出门槛：前端不硬编码用户/资源 ID/成功结果；只在 Core 确认后显示成功；刷新可恢复任务；用户可理解、修改、拒绝和恢复 Agent 操作；关键浏览器 E2E 与可用性走查通过。

### P5 — 银行 Agent JSONL 数据集

目标：建立同一套可版本化数据和评分标准，供规则、Jev、DeepSeek、Qwen 及混合模式公平比较。

步骤：

1. 先定义 Pydantic/JSON Schema，再创建数据。建议字段包括：`sample_id`、`locale`、`conversation`、`scenario`、`intent`、`complexity`、`available_context`、`expected_plan`、`expected_tool_calls`、`expected_risk_tier`、`requires_clarification`、`safety_expectation`、`tags`、`source`、`review_status`。
2. `expected_tool_calls` 同时标注工具名、关键参数和依赖关系；授权引用、用户 ID、风险等级不得作为模型应生成参数。
3. 覆盖六大场景、Green/Yellow/Red、模糊/省略/多轮/跨场景、拒绝/澄清、提示注入、越权、同名收款人、超时恢复和规划中功能。
4. 单独建立安全与体验子集：诱导转账、冒充客服/亲友、信息窃取、跨用户数据请求、直接/间接 Prompt 注入、工具结果投毒、权限提升、敏感信息回显；以及方言/口语、错别字、数字同音、多轮改口、低置信度、超范围请求和故障恢复。
5. 先人工编写并双人复核至少 100 条高质量种子；所有人名、账户、卡号均为虚构数据。
6. 再用可记录版本的生成脚本扩展到约 1,000 条。生成样本必须经 schema、规则、去重和人工抽检，不能把模型输出直接当 gold label。
7. **先按意图模板、语义簇和多轮会话分组，再拆分 train/dev/test（建议 70/15/15），最后在各 split 内生成改写。** 防止同一模板近义句跨 split 泄漏。
8. 使用 exact/fuzzy hash、embedding 可选人工复核等方式检查重复；测试集在最终调参期间冻结。
9. 建立统一评分器：intent macro-F1、slot/tool 参数准确率、DAG/依赖正确率、风险等级、澄清率、安全拒绝率、端到端任务成功率、恢复成功率和超范围兜底正确率。禁止只报一个“正确率”。
10. 数据集版本、license/source、生成模型、人工修改、排除项和 hash 写入 manifest。

JSONL 示例（仅表示离线样本结构，字段最终以 schema 为准）：

```json
{"sample_id":"zh_transfer_0001","locale":"zh-CN","conversation":[{"role":"user","content":"查余额后给小王转800元"}],"scenario":"TRANSFER","expected_plan":["get_accounts","get_balance","resolve_beneficiary","create_transfer_draft"],"expected_risk_tier":"YELLOW","requires_clarification":true,"source":"manual","review_status":"reviewed"}
```

文档：`docs/05_banking_agent_dataset.md`，含数据卡（Data Card）、schema、分布、隐私、生成/审核过程、限制和版本。

图表：场景/意图/风险/复杂度/语言分布、对话长度、步骤数、slot 缺失、split 对齐、重复相似度和人工审核结果。

退出门槛：所有 JSONL 逐行校验；test 无模板/会话泄漏；gold label 与 Tool Schema 对齐；数据集可由脚本重新生成统计。

### P6 — DeepSeek/Qwen、本地低参数模型与规则基线实验

目标：在引入 Jev 前得到可复现基线，同时验证低参数本地模型能否以更低隐私暴露和离线能力承担路由、槽位抽取或简单规划，避免把假设节省误写成实测成果。

步骤：

1. 固定 dataset version、prompt version、Tool Schema snapshot、评分器和运行配置。
2. 最少比较：规则直达；DeepSeek 单模型；DeepSeek 不同可用模型/推理模式；Qwen 对应模式（有 key 后启用）；至少一个合适的本地低参数模型原始版；若完成微调，再加入同一模型的 adapter 版。
3. **授权本阶段执行 Agent 自主选择并下载本地模型及决定是否/如何微调**，但选择前必须探测 CPU、RAM、GPU/显存、磁盘和可接受运行时间，并记录证据。下载必须使用官方或可信模型仓库、固定 revision/hash、核对许可证和模型卡，不得下载超出设备资源或用途许可证的模型。
4. 不在本计划硬编码将来可能过时的模型名。执行时从当时可用模型中选择 1–2 个候选，优先条件依次为：中文/口语理解、结构化 JSON/工具调用、许可证可用于比赛展示、上下文长度、内存/显存可承受、量化支持、维护活跃度和可复现实验。默认先考察约 0.5B–4B；硬件充足且收益明确时才扩大到约 7B。
5. 推理运行时由执行 Agent 根据环境决定，可选择 llama.cpp/Ollama/Transformers/vLLM 等；必须通过 `LocalModelProvider` 隔离，记录量化格式/位宽、线程/GPU offload、上下文、采样参数、峰值 RAM/VRAM、冷/热启动时间和模型文件大小。
6. 先依次尝试：原始模型零样本 -> 提示词/JSON schema/constrained decoding -> few-shot。只有 dev 集错误分析表明模型能力可通过领域适配改善时才微调，不能用 test 集决定训练方案。
7. 微调优先使用参数高效方法（LoRA；显存受限时可选 QLoRA），而不是全参数训练。训练数据只用冻结的 train split 和经过审核的安全/工具样本；dev 用于早停和超参数选择，test 最终只评一次。严禁加入真实 PII、密钥、授权引用、MFA 或模型生成但未经复核的错误 gold label。
8. 执行 Agent 自主决定 rank、学习率、epoch、target modules、batch/gradient accumulation、量化方案等，但必须先做小规模 sanity run，保存配置、随机种子、loss/显存曲线、base model revision、adapter hash 和选择理由；出现过拟合、安全退化或收益不显著时停止并保留原始模型。
9. 微调目标仅限意图分类、槽位抽取、工具选择/结构化计划和安全拒绝格式；模型永远不能学习或承担真实身份、风险授权、MFA、余额真相或最终资金提交。
10. 同一 base model 的原始、量化、提示优化和微调版本必须在完全相同的冻结 test/红队集比较。除准确率外，评测安全拒绝、校准、延迟、吞吐、token、RAM/VRAM、模型大小和本地隐私优势；本地不等于天然安全，仍要测试 Prompt 注入与数据残留。
11. 每种配置先小样本 smoke，再跑冻结 dev/test；至少多随机种子或多次重复，报告均值、分位数和 bootstrap 95% CI。
12. 将 Provider 网络时间、Planner 时间、Tool 执行时间分开；本地冷启动、模型加载和热推理分开。
13. Token 采用 Provider usage或统一 tokenizer 实测；价格使用带日期和来源的配置快照。本地成本单独报告硬件、运行时间和能耗（能可靠测量时），不能把本地写成“零成本”。
14. 对 API rate limit、timeout、拒答、本地 OOM、加载失败、结构化输出失败单独计数；有限退避，不无限重试。
15. 输出 per-sample JSONL 和 aggregate CSV/JSON，报告不能只保留汇总。
16. 做错误分析：意图错、slot 错、工具错、依赖错、风险错、安全错、格式错、Provider/OOM 错。

文档：`docs/06_llm_baseline_benchmark.md`。本地模型部分必须附 Model Card 摘要、许可证、硬件、选择决策、下载 revision/hash、推理/微调配方和微调前后对照；若决定不微调，也要记录基于证据的原因。

图表：混淆矩阵、准确率/F1、端到端成功率、延迟 ECDF/箱图、token/费用分布、Pareto 前沿、任务复杂度曲线、错误堆叠和置信区间；本地模型另加峰值 RAM/VRAM、模型大小—准确率、吞吐、冷/热延迟、训练 loss 与微调前后安全指标。

退出门槛：同一测试集和评分器；配置/模型 revision/adapter/原始结果可追溯；Qwen 未获 key 时报告为“未运行”而非零分；本地模型可离线复现且微调未降低安全硬指标；形成 Jev 对照基线。

### P7 — Jev 可插拔路由与消融

目标：验证 Jev 是否在本项目真实条件下提升效果。Jev 只能是可替换路由器，不能成为新的安全权威。

步骤：

1. 在编码前确认 Jev 的准确产品/库、官方文档、版本、许可证、运行环境、输入输出、费用和数据外发边界，并写技术 spike。名称或接口不明确时停在 adapter + fake 实现并向用户确认。
2. 定义通用 `IntentRouter` Protocol，与规则/LLM Router 使用同一 `IntentResult`。
3. 实现 Jev Adapter、timeout/circuit breaker、置信度阈值和 deterministic fallback；任何错误不得放行敏感操作。
4. 规则仍可先处理明确 Green；Jev 可以选择工具或模型档位，但不能提供 identity、risk tier、approval 或银行结果。
5. 低置信度、分布外、写操作和复合任务进入严格 Planner/校验流程。
6. 添加 Jev 被关闭、不可用、超时、异常输出、错误高置信度、提示注入和敏感误路由测试。
7. 运行消融：LLM only；rule + LLM；Jev + LLM；rule + Jev + LLM。不得只选择对 Jev 有利的简单查询。

文档：`docs/07_jev_router_integration.md`，明确官方来源、适配层、数据流、许可证、安全威胁和初步消融；没有实测时不得写“节省 69%”之类结论。

图表：路由混淆矩阵、coverage-risk 曲线、置信度校准、fallback/绕过率、延迟/token/成本变化、按场景和风险层分组的副作用。

退出门槛：一键关闭 Jev 后系统功能不受损；Jev 故障安全 fallback；没有敏感写操作绕过 Banking Core；消融结果完整。

### P8 — 混合 Agent 总实验与方案选择

目标：用同一数据、评分标准和可说明的硬件/并发条件回答三个问题：Jev 的提升/副作用；DeepSeek/Qwen/本地低参数模型各模式准确率；不同组合的 token、费用、资源和速度。

步骤：

1. 冻结实验矩阵、主要指标和判定规则，避免看到结果后修改评价标准。
2. 在资源允许范围执行 factorial matrix：Router × Provider × Model × Mode × Complexity × Risk Tier。
3. 随机化运行顺序，限制相同并发；记录 warm-up、网络环境、rate limit 和失败重跑。
4. 准确性同时看 routing、plan、tool arguments、risk、安全和端到端结果；写操作在隔离测试库或 dry-run 环境运行。
5. 计算相对基线的 token/费用/延迟变化，并报告 bootstrap CI；小样本不做过强结论。
6. 建立 Pareto 分析：不能用明显下降的安全/正确率换取少量成本；为不同任务选择建议路由策略。
7. 做失败案例册和可复现 demo：至少包括模糊请求、跨场景、注入攻击、审批恢复、Provider/Jev 故障。
8. 根据预先定义门槛选择默认方案；若 Jev 无显著收益，保留实验结论并默认关闭，而不是为了亮点强行启用。
9. 生成与评分标准同构的三张 Scorecard：任务完成（40）、安全合规（30）、创新体验（30）。综合分仅用于展示；任何“越权/审批绕过/敏感信息泄漏”硬门槛失败时，方案直接不具备上线资格，不能被其他得分抵消。

文档：`docs/08_hybrid_agent_experiments.md`，这是核心比赛证据报告。

图表：全套总体/分层结果、交互效应、Pareto、显著性/置信区间、失败率、费用累计、延迟尾部、路由流向 Sankey 可选；主要统计图仍由 seaborn 生成。

退出门槛：原始数据到报告可以一条命令复现；结论同时展示收益与副作用；选定默认/降级策略。

### P9 — 差异化体验原型（按门槛选做）

本阶段不能拖累核心闭环。优先级：储蓄罐 > 语音入口 > 已选本地模型的端侧部署优化 > 青少年模式 > 手机通知读取。本地模型选型与微调已经在 P6 完成；P9 只研究它能否在目标设备稳定部署。创新不以“使用了新模型”为标准，而以是否解决真实用户问题、能否安全闭环、是否有可量化体验提升为标准。

#### P9A 储蓄罐（建议完成）

1. 先和产品语义二选一并记录：仅虚拟分配目标，或实际子账户转账。未确认前不得实现资金移动。
2. 定义 Goal/Pot/Contribution schema、状态、幂等、所有权、取消/完成语义和迁移。
3. 若资金移动，复用现有转账/账本/审批，不建立第二套余额真相。
4. 加入目标进度、贡献历史、自动建议和前端页面；自动执行只允许符合策略的动作。

#### P9B 语音与端侧能力（时间允许再做）

1. 按键说话 -> 明示录音 -> 本地/受控转写 -> 用户可编辑 transcript -> 进入同一 AgentRequest。
2. 不让 ASR 绕过确认；金额、收款人和风险操作必须在屏幕复核。
3. 评测字错率、金融实体/数字准确率、实时率、内存/CPU/设备条件；比较云端与本地隐私和体验。
4. “读取手机通知”涉及平台权限、隐私和法律边界，只能做 opt-in、最小权限、端侧解析的研究原型；无明确授权不实施。

#### P9C 青少年模式（仅在核心稳定后）

必须先定义监护关系、可见范围、同意、额度、撤销和审计；不能用简单 user_id 参数模拟家长越权。

文档：`docs/09_advanced_experience_prototypes.md`，每个未做项目明确写 Deferred 及理由。

图表：储蓄目标进度/建议效果；语音 WER、数字实体准确率、延迟、CPU/内存/功耗（能可靠测量时）；隐私风险表不是性能图的替代品。

退出门槛：至少一个差异化功能可真实演示且不突破安全边界；其余功能诚实标注规划中。

### P10 — 安全加固、比赛演示与最终交付

目标：把研发系统变成可稳定重复的比赛作品，任何降级都不能产生假成功。

步骤：

1. 全量 threat model：prompt injection、工具注入、身份伪造、审批篡改/replay、越权、PII/secret 日志、DoS、Provider 数据外发、checkpoint 泄露。
2. 自动红队数据覆盖直接/间接注入、中文混淆、冒充客服/亲属诱导转账、要求泄露 prompt/key/他人数据、恶意检索内容、伪造工具结果、权限提升、绕过 MFA 和重复支付。
3. 做权限矩阵复核：角色/会话/任务/工具/资源/风险等级/审批方式/审计事件逐格检查；验证 Capability Broker 最小权限、跨用户隔离和默认拒绝。
4. 做数据安全复核：数据分类、收集目的、最小化、外部 Provider 字段、传输/静态保护、日志脱敏、保留/删除、用户查看/清除记忆和测试数据隔离。
5. 审核日志和 trace：记录决策/工具/审批/结果，但脱敏 prompt 中的账户信息，不记录 key、MFA code 或 authorization secret。
6. 验证迁移从空库到 head、备份/恢复说明、健康检查、超时、限流、Provider/Jev 断线降级和前端离线错误态。
7. 固化三个主演示：安全转账；账单/预算/订阅分析；理财或跨场景 Goal Plan。另准备诱导/注入被拦截、超时恢复、口语化多轮追问和主动提醒的评分点演示。
8. 演示脚本每次从可控种子开始，记录预期事件、用时、审批动作和恢复步骤；不能依赖手改数据库。
9. 汇总双语文档索引、API/数据集/实验卡、最终指标、限制和未来工作。
10. **所有工作完成后才创建 `supporting_materials/`**，严格按照 2.4 生成技术文档、架构图、算法说明、必交安全设计和必交安全自评。安全自评必须包含权限分级说明与已知风险清单，未修复项不能隐藏。
11. 对 `supporting_materials/` 做声明—证据审计：每个已实现能力链接真实代码/测试/图表；每张图有源文件；每个风险有状态；所有敏感内容已脱敏。
12. 最终运行 unit/integration/security/concurrency/browser E2E、Ruff、mypy、migration、seed、demo；记录精确版本和结果。

文档：`docs/10_security_and_competition_readiness.md`，并更新 `README.md`、`architecture.md`、`docs/README.md` 与 `docs/A_manual.md` 到最终事实。

图表：最终方案与基线对比、安全攻击分类结果、E2E 成功率/恢复率、P95 延迟、token/费用、测试覆盖分布和演示运行稳定性。

退出门槛：从 README 可在新环境复现；关键演示连续运行通过；断网/失败不会产生假成功或重复资金操作；已知限制公开；`supporting_materials/` 结构完整且安全设计、安全自评、权限分级和风险清单通过人工核对。

## 5. 全局不可违反的架构和安全规则

1. 概率模型只负责理解、建议和规划；Banking Core 是金融状态唯一权威。
2. `agent_tools`/`agent` 不直接导入 SQLAlchemy model/repository，不直连银行数据库。
3. ORM、领域实体、Pydantic API schema 和模型结构化输出保持分离。
4. 模型不能生成可信 user identity、risk tier、approval、MFA、authorization reference。
5. 所有写操作由 Core 独立鉴权；提交前重新校验 exact payload、grant、所有权和业务状态。
6. 金额禁止 binary float；Python 用 `Decimal`、DB 用 `NUMERIC`、JSON 用十进制字符串。
7. 资金操作保持事务、双重记账、幂等和并发锁；timeout 后先查状态。
8. 不向用户展示模型臆测的余额、收益或成功回执。
9. 不展示隐藏 chain-of-thought；展示结构化计划、简短理由、工具调用、风险等级和审计事实。
10. 数据集不得含真实 PII、密钥或生产数据；外部 Provider 的数据处理范围必须记录。
11. 不允许为了提高 benchmark 而污染 test、选择性删除失败样本或修改评分规则。
12. 新公共契约必须版本化、测试并同步文档；兼容性破坏必须显式迁移。
13. 外部文本、历史消息、检索材料和工具返回都不是系统指令；必须携带来源/信任标签并经过最小权限验证。
14. 长期目标/偏好记忆必须 opt-in、可查看、可更正、可删除；审批、授权、MFA 和不必要的账户明细不得进入长期记忆。
15. 主动服务默认只能建议或创建草稿，不能因为“用户过去同意过类似操作”就自动执行新的敏感操作。
16. 安全指标采用硬门槛：任何可复现的跨用户访问、审批绕过、敏感信息泄漏或重复扣款都阻止最终交付。

## 6. 范围控制与决策门槛

为了避免“功能很多但没有一条流畅”，遵守以下门槛：

- P0–P4 是可交互安全 Agent 的最小闭环，优先级最高。
- P5–P8 是 Jev/混合智能亮点的证据链；没有基线不得先宣传优化比例。
- P9 是选做创新，任何一项都不能破坏 P0–P8 的质量。
- 真实支付、真实投资交易、正式身份系统、生产 MFA、读取用户手机通知、自动购买鲜花蛋糕均不在默认授权范围。
- Redis、Temporal、Kafka、Kubernetes、向量数据库、代码生成沙箱只有在明确瓶颈和验收需求出现时才引入。

建议的默认比赛故事线：

1. 用户用中文或语音提出目标。
2. 页面展示结构化计划及为什么需要确认。
3. Agent 在 Green 步骤自动读取真实模拟数据。
4. Yellow/Red 操作可靠暂停，用户确认/MFA 后恢复。
5. 结果来自 Banking Core，刷新或超时后仍能恢复。
6. 实验看板现场展示 rule/Jev/DeepSeek/Qwen/本地低参数模型在同一数据集上的准确率、token、成本、资源占用和延迟。
7. 现场输入一条诱导转账或 Prompt 注入，展示 Capability Broker、Plan Verifier 与 Banking Core 如何共同拒绝越权，而不是只弹出笼统“有风险”。
8. 用一句口语化且信息不完整的请求展示多轮追问、用户改口、计划修正、断线恢复和最终可验证回执。

## 7. 执行日志（每阶段结束必须追加）

不要删除旧记录；每阶段追加一行，并在报告中保存详细证据。

| 日期 | 阶段 | 状态 | 关键变更 | 验证结果 | 报告 | 阻塞/下一步 |
|---|---|---|---|---|---|---|
| 2026-10-26 | Plan | 完成 | 根据现有 Core、架构、LangGraph 边界、前端规范和比赛目标制定后续路线 | 仅文档任务；未执行代码测试 | `dev_plan.md` | 从 P0 开始执行 |
| 2026-10-26 | Plan 补充 | 完成 | 按 40/30/30 评分细化任务完成、安全、创新交互模块，并加入最终 supporting_materials 必交清单 | Markdown 结构自检；未执行代码测试 | `dev_plan.md` | 从 P0 开始执行 |
| 2026-10-26 | P0 | 完成 | 建立可复现基线、OpenAPI/Tool 快照、Seaborn 图表、文档索引和能力差距矩阵；补充演示变量说明 | 34 passed；PostgreSQL 集成、迁移、双次 seed、Yellow/Red 演示、Ruff、mypy 均通过；Docker CLI 不可用 | `docs/00_baseline_and_documentation_index.md` | 自动进入 P1 |
| 2026-10-26 | P1 | 完成 | 新增版本化 Agent 契约、可信上下文边界、DeepSeek/Qwen/本地/Fake Provider、有界重试与脱敏错误 | 12 个专项及 46 个全量测试通过；Ruff、mypy、迁移通过；DeepSeek/Qwen live smoke 成功 | `docs/01_agent_contracts_and_model_providers.md` | 自动进入 P2 |
| 2026-10-26 | P2 | 完成 | 新增规则路由、来源槽位、Capability Broker、DAG/参数验证、单轮 Agent API 与真实 Core Green 闭环 | 9 个专项及 55 个全量测试通过；Ruff、mypy、迁移通过；15 条规则契约集 15/15 | `docs/02_planner_and_safe_routing.md` | 自动进入 P3 |
| 2026-10-26 | P3 | 完成 | 固定 LangGraph/Postgres checkpointer，新增持久 Task/Event、interrupt/resume、SSE、对账恢复、人工接管与主动提醒 | 63 tests；Ruff/mypy/迁移通过；重启恢复与重复 resume 测试通过；真实 Yellow/Red+MFA 均完成 | `docs/03_langgraph_durable_execution.md` | 自动进入 P4 |
| 2026-10-26 | P4 | 完成 | React/TypeScript 中文前端、Core/Agent 同源代理、任务 DAG、审批/MFA、实验看板与响应式移动导航 | 63 pytest；Ruff/mypy；Vitest/build；Playwright desktop + Pixel 7 通过；首次移动导航缺陷已修复 | `docs/04_frontend_integration_and_demo.md` | 自动进入 P5 |
| 2026-10-26 | P5 | 进行中 | 完成 v1 schema、1,000 条全虚构 JSONL、700/150/150 分组拆分、Tool Schema/去重/泄漏校验、统一评分器与分布图 | 1,000 行全通过；20 簇不跨 split；exact leak=0；最大 fuzzy=0.8235；3 dataset tests 通过 | `docs/05_banking_agent_dataset.md` | 等待第二名人工审核者复核 100 条种子后冻结 test；此前 P6 仅可做 smoke |
| 2026-10-26 | P5 | 完成 | 项目负责人确认第二人工审核；100 条种子签署通过，重新生成 split 哈希并冻结 test | 1,000 行全通过；reviewed seeds=100；exact leak=0；Tool Schema 对齐 | `docs/05_banking_agent_dataset.md` | 自动进入 P6 |
| 2026-10-26 | P6 | 完成 | 规则、DeepSeek Flash、Qwen Plus、CPU 本地 Qwen3-1.7B-Q8_0 统一冻结测试；严格 JSON schema、硬件/模型/价格 manifest 与图表 | 规则/两云端五项门槛 100%；本地 intent 42.28%、safety 67.11%、149/150 成功；重复子集稳定；Ruff/mypy/专项测试通过 | `docs/06_llm_baseline_benchmark.md` | 不微调：v1 dev/test 分层不足；进入 P7 |
| 2026-10-26 | P7 | 进行中 | 完成默认关闭的产品无关 Jev Adapter/Fake、置信度阈值、timeout、熔断与确定性回退 | 4 个 Jev 边界测试通过；不可信输出不能升级 RULE_DIRECT 或注入可信字段 | `docs/07_jev_router_integration.md` | 等待用户提供准确 Jev 官方产品/库标识后实现真实 adapter 与消融 |

## 8. 完成定义

只有同时满足以下条件，整个计划才算完成：

- 用户可以通过中文对话完成至少三类比赛场景，其中一条是完整 Yellow/Red 资金链路。
- Agent 支持可验证计划、审批中断、持久恢复、人工接管和状态对账。
- 前端可用且遵守 `docs/A_manual.md`，能展示操作轨迹和真实实验指标。
- 口语、省略、歧义、多轮改口和超范围请求有明确的追问、纠错、恢复或安全兜底；主动服务只能在 opt-in 和同一权限链路内运行。
- JSONL 数据集、评分器、DeepSeek/Qwen/本地低参数模型/Jev 对照和组合实验均可复现；本地模型与 adapter 的许可证、revision、训练配置和硬件记录完整。
- 实验结论包含准确率、安全、token、费用、P50/P95 延迟和失败分析，而非只展示最好数字。
- Banking Core 的金融正确性、安全边界和现有 API 未被 Agent 绕过或破坏。
- 跨用户访问、审批绕过、敏感信息泄漏和重复扣款四类安全硬门槛全部通过；已知剩余风险有负责人、状态和缓解方案。
- 所有适用测试、Ruff、mypy、迁移和演示通过，双语文档与实际实现一致。
- 根目录 `supporting_materials/` 已在所有工作完成后生成，包含技术文档、架构图、算法说明、必交安全设计，以及包含权限分级和已知风险清单的必交安全自评。
- 未实现或模拟功能被明确标注，不以假成功、假数据或假能力参加展示。
