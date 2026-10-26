# P7 Jev 路由技术 Spike（等待产品确认）

状态：**Adapter + fake 已完成；真实 Jev 集成暂停。** “Jev”目前没有唯一可识别的产品、库或协议。按开发计划，在获得官方文档前不得猜测依赖、接口、费用或数据边界。

## 已完成的安全边界

- `agent/jev.py` 定义与厂商无关的 `JevAdapter`、严格 `JevDecision`、`FakeJevAdapter` 和默认关闭的 `JevRoutingBoundary`。
- Jev 仅接收当前用户的原始文本，只能返回不可信的意图/路由建议；schema 不包含 `user_id`、风险授权、MFA、approval 或银行事实。
- 确定性 Green 精确规则优先，Jev 不能把请求升级成 `RULE_DIRECT`，因此无法绕过 Planner、Verifier、审批或 Banking Core。
- 低置信度、禁用、不可用、超时、异常和熔断均回退到现有 `RuleRouter`；敏感写操作仍保持 `PLANNER`，未知请求保持 `SAFE_FALLBACK`。
- 真实适配器接入前，不向任何 Jev 服务发送数据。

## 已验证行为

`tests/test_jev_boundary.py` 覆盖：关闭、不可用、超时、异常、连续失败熔断、低置信度、高置信度错误直达、提示注入以及伪造可信字段。当前 4 项测试全部通过。

## 继续真实集成所需信息

请提供所指 Jev 的至少一种唯一标识：官方产品页/文档 URL、包名或仓库 URL。确认后还需锁定版本与许可证、部署方式、输入输出 schema、认证方式、超时/限流、价格以及请求是否外发。随后才会实现真实 adapter，并运行以下四组同集消融：

1. LLM only
2. rule + LLM
3. Jev + LLM
4. rule + Jev + LLM

P7 在这些信息明确前保持“进行中”，且生产默认配置保持 Jev 关闭。
