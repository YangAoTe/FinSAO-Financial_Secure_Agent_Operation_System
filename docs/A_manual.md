# 首先是当前的架构预期
```mermaid

flowchart TB
    U(["User Request<br/>Text / Voice / IM"])

    A["1. API & Context<br/>FastAPI + PostgreSQL<br/>Input: Request<br/>Output: User Intent + Context"]

    B["2. AI Decision & Planning<br/>Rules / Jev + LLM<br/>Input: Intent + Context<br/>Output: Tool Call / Task DAG"]

    C["3. Agent Orchestration<br/>LangGraph<br/>Input: Task DAG<br/>Output: Next Action + Task State"]

    D["4. Security & Authorization<br/>Policy Engine + MFA<br/>Input: Action + User Permissions<br/>Output: Allow / Confirm / Deny"]

    E["5. Banking Tool Execution<br/>Typed Tools + Mock Banking API<br/>Input: Authorized Action<br/>Output: Verified Result / Receipt"]

    F[("Infrastructure<br/>PostgreSQL + Checkpoints + Audit")]

    U --> A --> B --> C --> D --> E
    E -->|"Tool Result / Continue"| C
    C -->|"Final Result"| A
    A -->|"Response / Events"| U

    A -.-> F
    B -.-> F
    C -.-> F
    D -.-> F
    E -.-> F

    D -->|"Approval Required"| U
    U -->|"Approval / MFA Result"| D

    classDef core fill:#eaf2ff,stroke:#2563eb,color:#1e3a8a
    classDef security fill:#fff4dd,stroke:#d97706,color:#92400e
    classDef execution fill:#e8f7ee,stroke:#16a34a,color:#14532d
    classDef infra fill:#f3f4f6,stroke:#64748b,color:#334155

    class B,C core
    class D security
    class E execution
    class F infra


```
# 实际工程开发中的文件组织和解耦合
参考
[text](banking_backend_modules.md)
具体的工程细节参考为

# 预计开发顺序
1. Infrastructure + Banking Tools
   先建立可验证的银行模拟环境，让业务操作不依赖 LLM。
2. Security & Authorization
   给所有敏感工具加上真正生效的权限检查。
3. API & Context
   把会话、账户身份、工具和审批流程通过统一 API 接起来。
4. LLM Planner + LangGraph
   让用户通过自然语言生成工具调用，并完成可中断的多步执行。
5. Jev + 高级 Agent 优化
   基于已有测试集判断 Jev 能否降低成本、延迟或改善路由。