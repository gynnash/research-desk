---
schema_version: 1
id: insight-agent-memory-agent-memory-20261030-0300-1
kind: insight
title: 记忆的关键可能不止是相关性，而是证据是否充分
topic: agent-memory
status: test_accepted
evidence_ids:
- R2
- H2
approval_required: false
writing_started: false
publish_authorized: false
input_fingerprint: a409d2af659ab939cf9d6030a225ae4b2a7f20b71594808456ab99f8d90b7221
---

> TEST：会员真实综合与独立审阅；论文摘要/博客节选及人工历史基线，未正式入库。

# 记忆的关键可能不止是相关性，而是证据是否充分

## 待验证假设

待验证研究假设：对查询所需证据进行组合、标注来源并检查充分性，可能比只检索单条相关记忆更有助于回答需要跨记录整合的问题；此假设不代表已证明普遍优越。

依据：[R2](../../../../reports/test/agent-memory/research-batches/agent-memory-20261030-0300/items/arxiv-908b50ae0f65/report.md)、[H2](../../../../sources/blogs/blog-fec9a2e1-6812-425a-83cd-e6a2464a1110.md)

## 反例与替代解释

- R2仅为摘要中的方法描述和作者报告，未核验其评测设置或结果。
- H2是未经本轮复核的历史项目笔记，且其记忆块概念不等同于R2的方法。
- 答案表现也可能受模型、查询类型、记忆形成方式或评测口径影响。

## 局限

- R2为abstract_only，H2为historical_note，证据覆盖有限且验证状态不同。
- 两项来源不构成统一条件下的直接比较。

## 验证计划（尚未执行）

- 获取并审阅R2全文与评测配置，确认基线、样本及统计不确定性。
- 在固定模型和同一记忆库上，对比单条相关检索与证据集构建，按跨记录整合题型分别评估准确性、证据覆盖和来源可追溯性。
- 复核H2对应原文及其记忆块机制，避免把历史概述当作已验证实现。
