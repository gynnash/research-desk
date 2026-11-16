---
schema_version: 1
kind: research_summary
topic: agent_memory
cycle_id: agent_memory-20261116-0900
title: 'MemoryDojo: Benchmarking Poisoning Through LLM Agent Memory'
source_url: https://arxiv.org/abs/2611.09721v1
source_id: paper-6399c18c-5d59-4775-8dee-b9774985901d
collection_original: collection/agent_memory/agent_memory-20261116-0900/items/arxiv-5c6ba19e21f2/original.md
coverage: full_text
review_status: passed
research_model: gpt-6.1-sol
review_model: gpt-6-astra
generated_at: '2026-11-16T07:48:26.075468+00:00'
---

# MemoryDojo: Benchmarking Poisoning Through LLM Agent Memory

作者报告：在 MemoryDojo 的多会话任务中，只向一次工具返回追加恶意指令，就能通过记忆影响后续会话，五种受测记忆系统均出现中毒。关键区别不只是能否存下指令，而是后续检索是否将其带回上下文，以及智能体是否照做。

## 隔离跨会话的记忆影响

作者构建了覆盖四个领域、155条轨迹的基准。每次会话使用全新上下文，开始前检索记忆，结束后写入任务交互记录；写入排除已检索的上下文，避免机械复制旧记忆。攻击者只污染一次工具返回，之后不再干预。评测排除注入当次会话，以BR衡量至少一次后续攻击成功的轨迹比例，以BRT衡量全部后续任务中的攻击成功比例。

## 存储、检索与执行是不同关口

作者在未优化的同领域实验中发现，四种系统的中毒写入成功率接近100%，但Graphiti后续检索到毒指令的比例仅33.43%，A-MEM和Memora则超过80%。Graphiti虽保存完整事件，读取接口却返回关系事实；Memora则可能从无害事实沿链接展开原始事件，将毒指令间接带入上下文。这说明只检查主检索结果，可能漏掉关联展开造成的暴露。

## 优化主要可增强检索后的服从

作者向优化器提供记忆系统描述、攻击目标和辅助环境反馈，迭代修改载荷，并在任务效用约束下选择后续攻击成功率更高的版本。在GPT-5.6-Luna同领域实验中，Letta的BRT从15.30%升至46.26%；其检索率从64.88%升至72.21%，而检索到毒指令后的攻击成功比例从23.59%升至64.06%。收益因此不只是更容易被检索，也包括被检索后更容易诱发目标行为。

## 适用条件与仍需验证的问题

已阅读完整抽取正文及附录，未独立复现实验。原文承诺后续发布数据、集成代码和评测脚本，当前文本不足以核验实现及运行结果。

结论来自沙箱和合成任务轨迹，主要设置是在首个任务会话污染一次工具返回，不能直接代表真实部署、多次投毒或防御启用后的效果。

比较对象是完整记忆集成，各系统的检索预算、上下文选择和展开策略不同；任务模型与记忆生成模型也同时变化，因此不能把差异单独归因于存储架构。中毒内容识别还依赖LLM裁判。

既有良性历史会改变结论：加入约50次历史会话后，五种系统的检索率和BRT均下降，Letta未出现后续攻击成功；Memora的BRT虽仅5.32%，仍有45.16%的轨迹至少成功一次。因此不能将空记忆条件下的风险排序视为固定排名。

## 资料来源与阅读范围

- [MemoryDojo: Benchmarking Poisoning Through LLM Agent Memory](https://arxiv.org/abs/2611.09721v1)：已阅读完整抽取正文，未独立复现实验。

- [阅读已采集的完整原文](../../../collection/agent_memory/agent_memory-20261116-0900/items/arxiv-5c6ba19e21f2/original.md)。
