---
title: 'From Relevant Memories to Sufficient Evidence: Rethinking Memory Utilization
  in LLM Agents'
kind: reading_note
topics:
- agent-memory
---

<!-- researchdesk-reading {"derived_from": "reports/agent-memory/agent-memory-20261030-0300-research-paper-f794b398-b1d9-451d-89a0-03897daeede2.md", "original_sha256": "1a11d7814811fdda4ef4ce7886e55ce1aa813076e54cd6ac9898ead6ba190a95", "presentation": "reviewed_content_reformatted"} -->

[返回研究首页](../../../../%E7%A0%94%E7%A9%B6%E9%A6%96%E9%A1%B5.md)

# From Relevant Memories to Sufficient Evidence: Rethinking Memory Utilization in LLM Agents

材料仅提供论文摘要，介绍 QEMem 如何将记忆利用从检索单条相关记忆转向构建针对查询的证据集；以下效果数据均为摘要中的作者报告，未独立核验。

## 问题、方法与结果

作者指出，检索到相关记忆并不必然意味着证据足以回答问题；信息可能分散在多条记录中、被抽象掩盖，或缺少推理所需的关联。

作者提出 QEMem，将记忆利用表述为构建查询特定的证据集，以集体证据支持取代对单条记忆相关性的侧重。

摘要称，QEMem 包含查询引导的多粒度证据发现、带来源引用及证据角色的结构化 ViewCards，以及按证据充分性选择性补回缺失信息的机制。

摘要称，在不修改既有记忆形成方式、并使用共享记忆存储的设定下，QEMem 配合 Claude Opus 4.5 在 LoCoMo 上取得 91.43% 的 LLM judge 准确率；作者报告其较最强评测基线 MemR$^3$ 高 7.6 个百分点，较 NEMORI 高 10.7 个百分点。

作者报告，进一步分析显示 QEMem 提高了证据覆盖率，并在需要整合跨会话证据的问题上表现较强。

## 如何理解这些结论

本次仅依据论文摘要，未核验全文、实验细节、实现或结果。

摘要未提供基线配置、评测样本与统计不确定性等细节，因此不能据此判断报告差异的稳健性或适用范围。

## 来源与阅读范围

- [From Relevant Memories to Sufficient Evidence: Rethinking Memory Utilization in LLM Agents](https://arxiv.org/abs/2610.22668v1)：仅阅读摘要，未核验全文或复现实验。
