---
title: 'From Memory Hits to Answerable Evidence: Query-Conditioned Memory Compilation
  for Long-Term Agent Memory'
kind: reading_note
topics:
- agent-memory
---

<!-- researchdesk-reading {"derived_from": "reports/agent-memory/agent-memory-20261023-0300-research-paper-2fa6f60d-0b98-43ab-b4bb-c2a94bd803dd.md", "original_sha256": "3924a6a394547717c5c850e25bd4f448a6c10fb5f9a7ec8ffb9a246a2c2e371e", "presentation": "reviewed_content_reformatted"} -->

[返回研究首页](../../../../%E7%A0%94%E7%A9%B6%E9%A6%96%E9%A1%B5.md)

# From Memory Hits to Answerable Evidence: Query-Conditioned Memory Compilation for Long-Term Agent Memory

本文摘要提出面向长期对话记忆的查询条件证据编译框架 MemCompile；以下仅概述所提供的摘要，不代表对论文全文或实验的独立核验。

## 问题、方法与结果

作者认为，长期智能体记忆需要从分散于多轮对话和多个会话的内容中恢复与回答相关的证据。

作者指出，现有系统可能将检索或扩展后的记忆单元直接交给回答模块，导致最终上下文冗余或不完整。

MemCompile 将处理分为寻址与证据编译：寻址平面定位支持材料并将不同检索命中映射到稳定的 SourcePacket 身份；证据平面则在有限预算内选择互补材料并组织成面向回答的上下文。

摘要报告，MemCompile 在 LoCoMo 上取得 80.52% 的 Judge Accuracy，并称其将经验质量—成本帕累托前沿扩展至更高质量区域。

作者称其在 LongMemEval-S 上的表现进一步显示，查询条件编译的收益可推广至其他长期对话记忆基准。

## 如何理解这些结论

本次材料仅为论文摘要，未核验全文、实验设置、实现细节或结果。

摘要未提供评测对照、成本指标定义、统计不确定性或 LongMemEval-S 的具体结果，无法据此独立判断比较幅度或推广范围。

## 来源与阅读范围

- [From Memory Hits to Answerable Evidence: Query-Conditioned Memory Compilation for Long-Term Agent Memory](https://arxiv.org/abs/2610.23313v1)：仅阅读摘要，未核验全文或复现实验。
