---
schema_version: 1
id: insight-agent-memory-agent-memory-20261030-0300-2
kind: insight
title: 保留原始经历入口可能有助于检查压缩后的记忆
topic: agent-memory
status: test_accepted
evidence_ids:
- R1
- H4
approval_required: false
writing_started: false
publish_authorized: false
input_fingerprint: a409d2af659ab939cf9d6030a225ae4b2a7f20b71594808456ab99f8d90b7221
---

> TEST：会员真实综合与独立审阅；论文摘要/博客节选及人工历史基线，未正式入库。

# 保留原始经历入口可能有助于检查压缩后的记忆

## 待验证假设

待验证研究假设：若压缩或整合后的记忆保留可回查的原始记录入口，系统可能更容易发现摘要遗漏的细节；但效果取决于检索是否成功及原始观察是否可用。

依据：[R1](../../../../reports/test/agent-memory/research-batches/agent-memory-20261030-0300/items/arxiv-6f0f57c922e8/report.md)、[H4](../../../../sources/papers/paper-4eb3be4b-7189-49aa-bafd-f88f77a972f4.md)

## 反例与替代解释

- R1关于引用原始经历的描述来自论文摘要，未独立核验其实现或效果。
- H4历史笔记描述分层记忆机制，但不是本轮重新审阅的证据。
- 回查原始记录可能增加检索成本，且原始材料自身也可能含噪声或过时信息。

## 局限

- R1为abstract_only，无法据此判断细节恢复成功率。
- H4为historical_note，不能作为独立验证或性能证据。

## 验证计划（尚未执行）

- 审阅R1全文并核实原始经历引用、整合过程和失败案例。
- 在受控任务中比较仅摘要、摘要加原始记录引用两种条件，测量细节召回、错误率、来源追溯率与检索成本。
- 对历史笔记H4所述机制复核原始论文和评测设置后，再决定其可比范围。
