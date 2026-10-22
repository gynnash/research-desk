---
schema_version: 1
id: paper-2fa6f60d-0b98-43ab-b4bb-c2a94bd803dd
kind: paper
title: 'From Memory Hits to Answerable Evidence: Query-Conditioned Memory Compilation
  for Long-Term Agent Memory'
source: arXiv
source_url: https://arxiv.org/abs/2610.23313
authors:
- Li, Shangze
- Yao, Yanyu
- Xu, Derong
- Zheng, Zhi
- Xu, Tong
published_at: '2026-10-16'
arxiv_id: '2610.23313'
source_version: v1
collected_at: '2026-10-23'
updated_at: '2026-10-23'
topics:
- agent-memory
status: inbox
related_sources: []
related_notes:
- reports/agent-memory/agent-memory-20261023-0300-research-paper-2fa6f60d-0b98-43ab-b4bb-c2a94bd803dd.md
- reports/agent-memory/agent-memory-20261023-0300-synthesis.md
---

# From Memory Hits to Answerable Evidence: Query-Conditioned Memory Compilation for Long-Term Agent Memory

> AI 自动研究记录，已通过独立模型审阅；阅读范围及证据限制见正文，未复现实验。

- 来源：[From Memory Hits to Answerable Evidence: Query-Conditioned Memory Compilation for Long-Term Agent Memory](https://arxiv.org/abs/2610.23313v1)。
- 覆盖范围：仅论文摘要，未核验全文或实验数据。
- 研究模型：`gpt-6-luna`；独立审阅：`gpt-6.1-sol`。
- 审阅：`pass`；修订次数：0；原始材料仅在内存中提供给模型。

## 研究概述

本文摘要提出面向长期对话记忆的查询条件证据编译框架 MemCompile；以下仅概述所提供的摘要，不代表对论文全文或实验的独立核验。

## 主张与证据

- **作者声称（未独立核验）**：作者认为，长期智能体记忆需要从分散于多轮对话和多个会话的内容中恢复与回答相关的证据。（[A1](https://arxiv.org/abs/2610.23313v1)）
- **作者声称（未独立核验）**：作者指出，现有系统可能将检索或扩展后的记忆单元直接交给回答模块，导致最终上下文冗余或不完整。（[A2](https://arxiv.org/abs/2610.23313v1)）
- **作者声称（未独立核验）**：MemCompile 将处理分为寻址与证据编译：寻址平面定位支持材料并将不同检索命中映射到稳定的 SourcePacket 身份；证据平面则在有限预算内选择互补材料并组织成面向回答的上下文。（[A3、A4、A5](https://arxiv.org/abs/2610.23313v1)）
- **作者声称（未独立核验）**：摘要报告，MemCompile 在 LoCoMo 上取得 80.52% 的 Judge Accuracy，并称其将经验质量—成本帕累托前沿扩展至更高质量区域。（[A6](https://arxiv.org/abs/2610.23313v1)）
- **作者声称（未独立核验）**：作者称其在 LongMemEval-S 上的表现进一步显示，查询条件编译的收益可推广至其他长期对话记忆基准。（[A7](https://arxiv.org/abs/2610.23313v1)）

## 局限

- 本次材料仅为论文摘要，未核验全文、实验设置、实现细节或结果。
- 摘要未提供评测对照、成本指标定义、统计不确定性或 LongMemEval-S 的具体结果，无法据此独立判断比较幅度或推广范围。

## 独立审阅


正式来源：[paper-2fa6f60d-0b98-43ab-b4bb-c2a94bd803dd](paper-2fa6f60d-0b98-43ab-b4bb-c2a94bd803dd.md)。

准入记录：[输入、审阅与输出散列](../../../reports/agent-memory/admissions/agent-memory-20261023-0300/accepted.yaml)。

## 人工笔记

