# FinPilot Documentation Index / 文档索引

This index separates verified implementation facts from specifications and future plans.
本索引用于区分已验证实现、规范和未来规划，避免把设计稿误认为已交付能力。

| Document / 文档 | Type / 类型 | Status / 状态 | Authority / 定位 |
|---|---|---|---|
| `../README.md` | Current state / 现状 | Implemented | Setup, checks, implemented scope and known limits / 启动、检查、已实现范围和限制 |
| `../AGENT.md` | Engineering rules / 工程规范 | Active | Mandatory architecture, finance and security rules / 强制架构、金融与安全规则 |
| `../architecture.md` | Architecture + plan / 架构与规划 | Mixed | Sections may describe future work; verify against code / 部分为未来设计，须以代码核验 |
| `banking_backend_modules.md` | Architecture contract / 架构契约 | Active | Module responsibilities and dependency direction / 模块职责与依赖方向 |
| `langgraph_integration.md` | Integration contract / 集成规范 | Active | Trusted-context and typed-tool boundary; graph runtime is planned / 可信上下文和工具边界；图运行时尚属规划 |
| `A_manual.md` | Frontend/API contract / 前端与接口规范 | Active | Authoritative UI integration contract for current Core / 当前 Core 的前端联调权威契约 |
| `00_baseline_and_documentation_index.md` | Evidence report / 证据报告 | Implemented | P0 reproducible baseline and gap matrix / P0 可复现基线与差距矩阵 |
| `01_agent_contracts_and_model_providers.md` | Phase report / 阶段报告 | Implemented | P1 contracts and provider adapters / P1 契约与适配器 |
| `02_planner_and_safe_routing.md` | Phase report / 阶段报告 | Implemented | P2 safe single-turn routing / P2 安全单轮路由 |
| `03_langgraph_durable_execution.md` | Phase report / 阶段报告 | Implemented | P3 durable tasks, resume and SSE / P3 持久任务、恢复与事件流 |
| `04_frontend_integration_and_demo.md` | Phase report / 阶段报告 | Implemented | P4 live-service React demo and browser evidence |
| `05_banking_agent_dataset.md` | Dataset card / 数据卡 | Implemented | P5 schema, 1,000 reviewed/frozen synthetic rows and validation |
| `06_llm_baseline_benchmark.md` | Experiment report / 实验报告 | Implemented | P6 rule/DeepSeek/Qwen/local frozen-test baseline |
| `07_jev_router_integration.md` | Technical spike / 技术预研 | Partial | P7 safe adapter + fake complete; exact Jev product awaiting confirmation |
| `08_hybrid_agent_experiments.md` | Experiment report / 实验报告 | Planned | P8 |
| `09_advanced_experience_prototypes.md` | Prototype report / 原型报告 | Planned | P9 |
| `10_security_and_competition_readiness.md` | Final readiness report / 决赛报告 | Planned | P10 |

Generated evidence lives under `evaluation/reports/` and figures under
`evaluation/figures/`. Generated evidence never overrides the Banking Core as the
authority for financial state.

生成证据位于 `evaluation/reports/`，图表位于 `evaluation/figures/`。任何实验产物都不能
取代 Banking Core 对金融状态的唯一权威地位。
