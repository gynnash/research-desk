---
title: Agent记忆：从存储到证据使用
kind: reading_note
topics:
- agent-memory
---

<!-- researchdesk-reading {"derived_from": "reports/agent-memory/agent-memory-20261030-0300-synthesis.md", "original_sha256": "4b7e0fbace69aaa09672c1089fa8e21e5145724876b5fb471560daa9fb5960b0", "presentation": "reviewed_content_reformatted"} -->

[返回研究首页](../../../%E7%A0%94%E7%A9%B6%E9%A6%96%E9%A1%B5.md)

# Agent记忆：从存储到证据使用

材料呈现了几类不同的记忆问题：《Multimodal Filesystem Memory For Long-Horizon Embodied Agents》描述多模态记忆与经历整合，《From Relevant Memories to Sufficient Evidence》聚焦针对查询构建充分证据，《Context Engineering》介绍上下文卸载与摘要，《How We Built Our Design Agent》仅提及受限范围记忆而未说明其机制。它们可用于提出架构和评测问题，但摘要与节选不足以证明普遍效果、因果关系或系统间性能优劣。历史基线仅作待复核背景。

## 这些研究有哪些共同点与分歧

《Multimodal Filesystem Memory For Long-Horizon Embodied Agents》摘要描述将情景、空间、语义、程序性和工作记忆结合，并保留通往原始经历的引用；《MemGPT》历史笔记也记录了分层记忆与检索机制。两者可作架构问题的参照，但《MemGPT》未经本轮复核，且不能据此判断架构优劣。

《From Relevant Memories to Sufficient Evidence》摘要将记忆利用表述为构建查询特定证据集，而非只找单条相关记忆；《Memory Blocks》历史笔记描述带用途和容量约束的记忆块。二者涉及不同组织视角，现有材料未给出可比评测。

《Context Engineering》节选描述文件卸载和摘要等上下文管理机制；《MemGPT》历史笔记记录通过调入、编辑和移出信息管理上下文。可比较其关注点，但博客节选与历史笔记均不足以证明实际可靠性或效果。

《How We Built Our Design Agent》节选仅称 Managed Deep Agents 提供受限范围记忆能力，未交代写入、检索或更新机制；《Memory Blocks》历史笔记对记忆块的组织方式作了概述，但未经本轮独立复核。两者不能支持对机制或性能的比较。

## 值得深入研究的线索

以下是基于当前材料提出的研究线索与待验证判断，不能据此确认行业趋势。

### 记忆的关键可能不止是相关性，而是证据是否充分

待验证研究假设：对查询所需证据进行组合、标注来源并检查充分性，可能比只检索单条相关记忆更有助于回答需要跨记录整合的问题；此假设不代表已证明普遍优越。

《From Relevant Memories to Sufficient Evidence》仅为摘要中的方法描述和作者报告，未核验其评测设置或结果。

《Memory Blocks》是未经本轮复核的历史项目笔记，且其记忆块概念不等同于《From Relevant Memories to Sufficient Evidence》的方法。

答案表现也可能受模型、查询类型、记忆形成方式或评测口径影响。

《From Relevant Memories to Sufficient Evidence》为仅摘要，《Memory Blocks》为未经本轮原文复核的历史资料，证据覆盖有限且验证状态不同。

两项来源不构成统一条件下的直接比较。

还需要怎样验证：

- 获取并审阅《From Relevant Memories to Sufficient Evidence》全文与评测配置，确认基线、样本及统计不确定性。
- 在固定模型和同一记忆库上，对比单条相关检索与证据集构建，按跨记录整合题型分别评估准确性、证据覆盖和来源可追溯性。
- 复核《Memory Blocks》对应原文及其记忆块机制，避免把历史概述当作已验证实现。

### 保留原始经历入口可能有助于检查压缩后的记忆

待验证研究假设：若压缩或整合后的记忆保留可回查的原始记录入口，系统可能更容易发现摘要遗漏的细节；但效果取决于检索是否成功及原始观察是否可用。

《Multimodal Filesystem Memory For Long-Horizon Embodied Agents》关于引用原始经历的描述来自论文摘要，未独立核验其实现或效果。

《MemGPT》历史笔记描述分层记忆机制，但不是本轮重新审阅的证据。

回查原始记录可能增加检索成本，且原始材料自身也可能含噪声或过时信息。

《Multimodal Filesystem Memory For Long-Horizon Embodied Agents》为仅摘要，无法据此判断细节恢复成功率。

《MemGPT》为未经本轮原文复核的历史资料，不能作为独立验证或性能证据。

还需要怎样验证：

- 审阅《Multimodal Filesystem Memory For Long-Horizon Embodied Agents》全文并核实原始经历引用、整合过程和失败案例。
- 在受控任务中比较仅摘要、摘要加原始记录引用两种条件，测量细节召回、错误率、来源追溯率与检索成本。
- 对历史笔记《MemGPT》所述机制复核原始论文和评测设置后，再决定其可比范围。

## 当前结论的边界

《Multimodal Filesystem Memory For Long-Horizon Embodied Agents》、《From Relevant Memories to Sufficient Evidence》仅有摘要，实验设计、实现、样本规模和统计不确定性未在材料中充分呈现；其结果均为作者报告。

《Context Engineering》、《How We Built Our Design Agent》仅有博客节选，未提供可独立核验的记忆可靠性、隐私或安全评测。

本轮采用的这些历史笔记是历史人工基线，未经本轮独立复核；其中《Agent Memory》包含旧轮次综合内容，不能把旧引用标记当作本轮证据编号。

材料来自少量、覆盖方式不同的来源，不支持行业趋势、因果结论或跨系统性能排名。

## 接下来值得追问什么

- 多模态原始经历引用、查询特定证据集及上下文摘要分别会如何影响答案的可追溯性与正确性？
- 记忆整合或压缩后，系统能否发现信息缺失、冲突和过时内容，并可靠地回查原始记录？
- 《Multimodal Filesystem Memory For Long-Horizon Embodied Agents》、《From Relevant Memories to Sufficient Evidence》摘要所报结果在完整评测设置、不同模型和独立复现实验中是否成立？
- 《How We Built Our Design Agent》所称受限范围记忆的具体写入、访问控制、更新与遗忘机制是什么？

阅读说明：《Multimodal Filesystem Memory For Long-Horizon Embodied Agents》、《From Relevant Memories to Sufficient Evidence》仅覆盖论文摘要，《Context Engineering》、《How We Built Our Design Agent》仅覆盖博客节选；本轮采用的这些历史笔记为未经本轮独立复核的人工历史基线。历史笔记中的主张不视为新核验事实；来源关联不构成独立验证。

## 来源与阅读范围

- [Multimodal Filesystem Memory For Long-Horizon Embodied Agents](https://arxiv.org/abs/2610.22686v1)：仅阅读摘要，未核验全文或复现实验。
- [From Relevant Memories to Sufficient Evidence: Rethinking Memory Utilization in LLM Agents](https://arxiv.org/abs/2610.22668v1)：仅阅读摘要，未核验全文或复现实验。
- [Context Engineering: How Deep Agents Remember](https://www.langchain.com/blog/context-engineering-deep-agents-remember)：仅阅读正文节选，未覆盖全部原文；历史资料，未经本轮原文复核。
- [How We Built Our Design Agent](https://www.langchain.com/blog/design-agent)：仅阅读正文节选，未覆盖全部原文。
- [Memory Blocks: The Key to Agentic Context Management](https://www.letta.com/blog/memory-blocks/)：历史资料，未经本轮原文复核。
- [Hy-Memory-30B-A3B: Attributed Reinforcement Learning for Long-Term Memory Writing](https://arxiv.org/abs/2610.22196)：历史资料，未经本轮原文复核。
- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)：历史资料，未经本轮原文复核。
