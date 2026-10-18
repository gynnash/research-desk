# 配置驱动 Research 批次真实验收

> TEST：本地会员、指定资料批次验证；未正式入库。

验收日期：2026-10-19（北京时间）；批次：`configured-research-20261019`。

## 实际运行

- 按 [Agent Memory YAML](../../../../../config/test/agent-memory/research_batch.yaml) 选择主题、来源、研究/审阅模型和预算。通用用户示例见 [研究方向](../../../../../config/examples/research_topics.yaml) 与 [批次配置](../../../../../config/examples/research_batch.yaml)；配置不包含凭据。
- 论文：[A-MEM: Agentic Memory for LLM Agents，2502.12110v1](https://arxiv.org/abs/2502.12110v1)，仅摘要；[论文测试报告](items/amem-paper/report.md)。新资料 ID 仅在批次中预留，没有新增或改动来源笔记。
- 博客：[Letta: Why Memory Isn't a Plugin](https://www.letta.com/blog/why-memory-isnt-a-plugin/)，按博客节选范围研究；[博客测试报告](items/letta-memory-blog/report.md)。关联已有测试来源 ID，原模拟笔记保持原样。
- 两份均由 `gpt-6-luna` 真实研究、`gpt-6.1-sol` 在独立上下文读取同一原文材料与候选逐项审阅；实际返回身份相符，均 `pass`，修订次数均为 0。
- 共 4 次真实请求，响应报告输入 4,658、输出 1,399、合计 6,057 tokens；低于本批 6 次上限。共享月度账本累计 6 次，包含此前单篇测试的 2 次，月度上限 10 次。会员剩余额度及金额仍未知。

## 中断与补跑

论文研究与审阅完成后，程序按 `after_first_item` 验收断点主动中断（退出码 3）；此时账本为 2 次完成请求，论文报告及检查点已保存。这是计划内进程中断，不是伪造模型故障。

以相同配置、批次与账户补跑，论文从完整性校验过的结果复用，仅继续博客；最终计数为 4。再次完整补跑返回 `cached: true`，计数仍为 4，未新增模型调用或重写报告。断流后结果未知不盲目重发、来源失败后只恢复缺失项、一次修订、跨方向与旧入口共享预算等分支由离线测试覆盖，未为测试这些故障额外消耗会员额度。

## 检查与边界

- 192 项离线验收与 14 项目录隔离验收通过；正式/测试来源校验及差异格式检查通过。
- 开始工作前的 221 个知识与配置文件散列全部保持一致；本轮研究产物只新增在当前 `reports/test` 批次，已有来源和人工笔记保持只读。
- 凭据沿用本应用在仓库与 Obsidian Vault 外的私有 profile，没有复制进配置、资料、日志或 Git；没有自动退回 API Key。
- 当前为指定来源的小批次，不代表完整扫描游标或已启用自动发现；没有 GitHub 定时任务、正式自动入库、Insight/选题/Writing 执行或公众号发布。

[批次回执](receipt-attempt-1.yaml) · [机器可读验收](acceptance.yaml) · [配置与补跑说明](../../../../../workflows/configurable-research-batch.md)
