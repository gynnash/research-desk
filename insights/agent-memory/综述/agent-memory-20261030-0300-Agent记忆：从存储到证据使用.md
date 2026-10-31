---
title: Agent记忆：从存储到证据使用
kind: reading_note
editorial: true
topics:
- agent-memory
---

<!-- researchdesk-reading {"derived_from": "reports/agent-memory/agent-memory-20261030-0300-synthesis.md", "original_sha256": "4b7e0fbace69aaa09672c1089fa8e21e5145724876b5fb471560daa9fb5960b0", "presentation": "reviewed_content_reformatted"} -->

[返回研究首页](../../../%E7%A0%94%E7%A9%B6%E9%A6%96%E9%A1%B5.md)

# Agent记忆：从存储到证据使用

检索到了相关记忆，为什么仍然答不完整？本轮材料把问题引向两个环节：分散记录能否组成足够的回答证据，压缩后的记忆能否回到原始经历补齐细节。它们比“存了多少内容”更接近信息如何被使用，但目前都只是值得验证的研究线索。

## 相关记录与充分证据

QEMem 的论文摘要把记忆利用表述为构建查询特定的证据集，而不是只寻找单条相关记忆。历史 Memory Blocks 笔记描述的用途与容量约束，则是在组织记忆单元。两者关注点不同：组织得清楚，不等于已经找到回答当前问题所需的完整支持。

据此可以提出一个假设：组合证据、标注来源并检查充分性，可能更有助于跨记录整合。它尚未经过本轮直接对照，回答表现也可能受模型、查询类型、记忆形成方式或评测口径影响。应固定模型与记忆库，比较单条相关检索和证据集构建，分别评估答案正确性、证据覆盖及来源追溯。

## 压缩以后能否找回细节

MFM 摘要描述将情景、空间、语义、程序性和工作记忆结合，通过文本记录连接原始多模态经历，并在整合后保留回查入口。历史 MemGPT 笔记中的分层记忆与检索，可以帮助提出架构问题，但不能证明两者效果相当。

保留原始入口可能帮助发现摘要遗漏，前提是原始观察仍可用、检索也能成功。回查也可能增加检索成本，原记录自身还可能有噪声或已经过时。需要在受控任务中比较仅摘要与摘要加原始引用，检查细节召回、错误率、追溯率和检索成本，而不是从“有引用”直接推断“记得可靠”。

## 机制描述与效果证据之间

LangChain 节选中的卸载、摘要，与历史 MemGPT 笔记里的调入、编辑、移出信息，提供了不同的上下文管理视角。另一篇设计代理博客只提到受限范围记忆，没有说明写入、检索、访问控制、更新和遗忘机制，无法据此判断可靠性、隐私或安全效果。

接下来应补齐两篇论文全文、基线、样本和统计设置，复核历史机制，追踪压缩后的缺失、冲突和过时内容。新论文在本轮只读摘要，两篇博客只读节选，历史笔记未重新核验原文，未复现实验；现在保存了原文，也不会改变旧轮次的阅读范围。材料不足以给出细节恢复成功率、跨系统排名或因果结论，更不能据此确认行业趋势。

## 来源

- [Multimodal Filesystem Memory For Long-Horizon Embodied Agents](https://arxiv.org/abs/2610.22686v1)
- [From Relevant Memories to Sufficient Evidence: Rethinking Memory Utilization in LLM Agents](https://arxiv.org/abs/2610.22668v1)
- [Context Engineering: How Deep Agents Remember](https://www.langchain.com/blog/context-engineering-deep-agents-remember)
- [How We Built Our Design Agent](https://www.langchain.com/blog/design-agent)
- [Memory Blocks: The Key to Agentic Context Management](https://www.letta.com/blog/memory-blocks/)
- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)
