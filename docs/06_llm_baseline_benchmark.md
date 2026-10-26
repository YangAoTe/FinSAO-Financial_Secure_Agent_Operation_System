# P6 LLM、规则与本地低参数模型基线

状态：**完成（未微调）**。本报告记录 2026-10-26 在冻结数据集 v1.0.0 上的可复现实验。原始 JSONL、聚合 JSON/CSV 和图表位于 `evaluation/`；金融状态仍只由 Banking Core 提供。

## 结论先行

在当前 150 条安全/越权/未实现功能门槛集上，规则、DeepSeek Flash 和 Qwen Plus 五项 exact-match 指标均为 100%。CPU 本地 Qwen3-1.7B-Q8_0 的意图准确率为 42.28%、安全标签准确率为 67.11%，但风险标签为 100%，149/150 次返回可解析。它目前适合作为隐私优先的实验/降级组件，不适合作为唯一安全路由器。

这个 test split 只包含 50 条 Prompt 注入、50 条跨用户数据请求和 50 条计划中储蓄罐请求，并由有限模板确定性改写而来。因此 100% 是窄范围安全门槛结果，不是全银行业务准确率，也不能证明对未见表达的泛化。

## 公平协议与追溯

- 数据：`1.0.0`，test SHA-256 `49c94faaf871b7af066fde1d16746d6be3872cddf132a1e77a8057768e4f1f22`，150 条；人工种子已二次复核并冻结。
- 所有线路使用同一 `scripts/benchmark_p6.py`、同一 `banking_dataset.score`、同一系统任务说明、temperature 0、串行并发 1。
- Rule 跑完整 test 3 次；各模型跑完整 test 1 次。另从三个 test intent 各取 2 条、每条重复 3 次，保存稳定性原始结果；本地 6/6 样本的三次结构化预测完全一致。
- 非流式接口无法分离首 token 延迟，结构化合同没有 confidence 字段，所以这两项如实记为 `null`。分类实验没有 Tool 执行时间；云端总延迟包含网络与 Provider 推理，不能伪称纯模型时间。
- `evaluation/reports/p6_benchmark_consolidated.json` 保存运行文件名、模型配置、token、错误、费用口径和已知限制；`evaluation/manifests/` 保存本地模型和价格快照。

## 完整冻结测试结果

| 线路 | intent macro-F1 / accuracy | 工具序列 | 风险 | 澄清 | 安全 | 平均 / P95 总延迟 | 成功请求 |
|---|---:|---:|---:|---:|---:|---:|---:|
| rules-v1 | 1.000 / 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0 / 0 ms | 450/450（3 次） |
| DeepSeek Flash | 1.000 / 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1,258 / 1,618 ms | 150/150 |
| Qwen Plus | 1.000 / 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1,435 / 1,694 ms | 150/150 |
| Qwen3-1.7B Q8_0（CPU） | 0.234 / 0.423 | 0.423 | 1.000 | 0.792 | 0.671 | 6,803 / 9,075 ms | 149/150 |

意图准确率的 Wilson 95% 区间：前三者 `[0.975, 1.000]`；本地模型 `[0.344, 0.500]`。区间按样本计算，但模板内相关性意味着它仍可能过于乐观。混淆矩阵、准确率、延迟 ECDF、资源与复杂度图分别为：

- `evaluation/figures/p6_accuracy_comparison.png`
- `evaluation/figures/p6_intent_confusion_matrices.png`
- `evaluation/figures/p6_latency_ecdf.png`
- `evaluation/figures/p6_local_resources_and_complexity.png`
- `evaluation/figures/p6_tokens_pareto_and_errors.png`

## Token 与费用口径

| Provider | 输入 token | 输出 token（含 Provider 报告的推理 token） | 价格快照估计 |
|---|---:|---:|---:|
| DeepSeek Flash | 90,795 | 17,222 | USD 0.047905 上界 |
| Qwen Plus | 77,775 | 7,200 | CNY 0.291758 |
| 本地 Qwen3 | 77,556 | 8,554 | API 费用 0；未估电力/折旧/人工 |

费用不是账单：DeepSeek 上界把全部输入视为 cache miss；Qwen 使用国际 Model Studio 当日公开标价。币种不做汇率折算，避免制造虚假精度。来源见 [DeepSeek 官方价格](https://api-docs.deepseek.com/quick_start/pricing) 与 [Alibaba Cloud Model Studio 官方价格](https://www.alibabacloud.com/help/en/model-studio/model-pricing)。

## 本地模型 Model Card 与运行证据

- 模型：[Qwen/Qwen3-1.7B-GGUF 官方模型卡](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF)，Apache-2.0；revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`。
- 文件：官方 `Qwen3-1.7B-Q8_0.gguf`，1,834,426,016 bytes，SHA-256 `061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a`。
- Runtime：[llama.cpp](https://github.com/ggml-org/llama.cpp) release `b11889` / commit `d854d98ba`，CPU x64，8 threads，0 GPU layers，context 2,048，temperature 0，thinking disabled，严格 JSON schema 解码。
- 主机：Intel i7-8700（6C/12T）、39.84 GiB RAM；GPU/NVML 不可用，因此按 CPU-only 运行。模型冷加载 1.347 秒，`llama-server` 峰值 working set 2.09 GiB；模型文件约 1.71 GiB。
- 选择理由：官方中文模型、原生 GGUF、许可证适合展示、1.7B 在当前 CPU/磁盘约束下可复现。没有证据支持默认扩大到 7B Q8 的资源代价。

本地推理迭代遵循 dev-first：最初仅 `json_object` 的 5 条 dev 请求全部格式失败；关闭 thinking、把 Pydantic schema 传给 llama.cpp 做约束解码后 5/5 可解析且 intent 正确。dev 只含理财比较簇，其工具/风险/澄清子字段仍有明显错误，说明它不足以支持通用调参结论。

## 为什么没有微调

未执行 LoRA/QLoRA。原因不是本地基线已经足够，而是 v1 dev 只覆盖理财比较、v1 test 只覆盖安全/OOS，缺少能支持早停、超参数选择和广泛泛化判断的分层验证集。在看过冻结 test 后再据此训练会污染最终评测。下一版应先设计按所有 intent/risk/complexity 分层且模板来源隔离的 v1.1 dev/test，再只用 train 做参数高效微调并建立新的最终 test。

## 复现

先按 manifest 下载并核验模型/llama.cpp，然后启动 OpenAI-compatible 本地服务；云端 key 仅从 `.env` 读取，结果和日志不保存 key。

```powershell
uv run python scripts/benchmark_p6.py --provider rule --split test --repeat 3
uv run python scripts/benchmark_p6.py --provider deepseek --split test --repeat 1
uv run python scripts/benchmark_p6.py --provider qwen --split test --repeat 1
uv run python scripts/benchmark_p6.py --provider local --split test --repeat 1
uv run python scripts/generate_p6_evidence.py
```

当前推荐：明确命中的安全/计划功能规则优先；复杂场景进入确定性验证后的云端 Planner；本地 1.7B 仅作为可关闭实验或离线降级，不得承担身份、授权、风险定级、MFA、银行事实或资金提交。
