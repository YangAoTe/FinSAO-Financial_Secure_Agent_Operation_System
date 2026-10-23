# AI Banking Agent 后端模块说明

> 架构定位：**模块化单体 Banking Core + 独立 Agent Tool Adapter**。目录划分代表代码职责，不代表必须拆成独立微服务。

| 模块 | 核心职责 | 典型内容 | 不应该负责 |
|---|---|---|---|
| `domain/` | 定义银行领域实体、值对象和不变量 | `Account`、`Money`、`Transfer`、账户状态、金额合法性 | HTTP、SQL、LLM 调用 |
| `schemas/` | 定义 API 的输入与输出契约、数据校验 | Pydantic Request/Response、错误响应、字段校验 | 复杂业务流程、数据库操作 |
| `services/` | 编排银行业务用例与事务边界 | `TransferService`、`AccountService`、转账草案和提交流程 | HTTP 路由、直接处理 Agent Prompt |
| `persistence/` | 实现数据访问、ORM 映射、事务及并发控制 | SQLAlchemy Models、Repositories、Unit of Work、行锁 | 决定用户意图、业务权限策略 |
| `security/` | 认证、授权、风险策略、审批及审计 | Identity、Green/Yellow/Red Policy、MFA、Audit | 信任模型生成的 `approved=true` |
| `api/` | 暴露并组织 FastAPI HTTP 接口 | Routes、依赖注入、HTTP 状态和错误映射 | 在路由函数中直接记账 |
| `agent_tools/` | 让 Agent 通过受控、类型化接口调用银行能力 | `BaseBankingTool`、Registry、Gateway、HTTP Client | 直接修改数据库、绕过安全检查 |
| `shared/` | 定义跨组件稳定且最小化的公共契约 | 通用错误代码、跨边界枚举、版本化接口约定 | 放置任意工具函数或 ORM 对象 |

## 典型调用路径

```text
LangGraph Agent
    -> agent_tools/ (typed input + trusted context)
    -> api/ (HTTP + authentication)
    -> security/ (account permission, policy, approval)
    -> services/ (use case orchestration)
    -> domain/ (business invariants)
    -> persistence/ (atomic database transaction)
    -> PostgreSQL
    -> verified result returned along the same boundary
```

> 注意：这是运行时的简化路径；`services/` 会同时使用 `domain/`、`persistence/` 和 `security/`，安全授权还必须在最终资金提交前重新校验。

## 架构设计原则

1. **关注点分离（Separation of Concerns）**：业务规则、业务流程、数据存储、HTTP 接口、AI 工具不混写。
2. **依赖方向明确（Dependency Rule）**：核心 Domain 不依赖 FastAPI、数据库框架或 Agent；依赖外部系统时优先经接口/适配器。
3. **安全边界强制执行**：所有资金写操作在 Banking Core 内完成权限与审批校验，不能只依靠 Agent 提示词。
4. **金融数据一致性**：`Decimal/NUMERIC`、数据库事务、双重记账/可审计流水、幂等键、并发控制。
5. **契约优先（Contract First）**：API Schema 与 Tool Schema 可检查、可版本化、可测试。
6. **适度抽象**：MVP 保持一个 Banking Core 部署单元；不要为每个文件创建空接口或提前拆微服务。

## 推荐实现顺序

1. `domain/` + `schemas/`：定义 `Money`、`Account`、`Transfer` 等数据模型与请求契约。
2. `persistence/`：账户、流水、账本、幂等记录、事务测试。
3. `services/` + `security/`：完成转账草案、审批、事务提交的安全闭环。
4. `api/`：开放经过认证的账户、转账和状态接口。
5. `agent_tools/`：实现 Typed Tool、Registry、Gateway、Client，连接银行 API。
6. `shared/`：只在跨边界复用需求出现时提取稳定契约。

## 最小验收场景

用户请求“查询余额，并给小王转 800 元” → Agent 调用查询及转账草案工具 → Banking Core 检查账户和每日累计额度 → 用户确认 → 重新校验 → 原子转账并生成流水和审计记录 → 返回真实模拟交易结果；重复提交不能重复扣款。
