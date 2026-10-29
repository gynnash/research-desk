---
schema_version: 1
id: formal-insight-agent-memory-agent-memory-20261027-0300-1
kind: insight
title: 记忆管理可拆成“保留什么”与“如何组织”两类待检验问题
topic: agent-memory
status: accepted
evidence_ids:
- R1
- H2
approval_required: false
writing_started: false
publish_authorized: false
input_fingerprint: a2b9727f130a1831aaf3d3cb7781f9f967e9b476f37be717c854ead1ee3414a3
topics:
- agent-memory
---

> AI 自动研究记录，已通过独立模型审阅；阅读范围及证据限制见正文，未复现实验。

# 记忆管理可拆成“保留什么”与“如何组织”两类待检验问题

## 待验证假设

待验证的研究假设：将任务时记忆子集选择与持久记忆的组织方式分开评测，可能更容易定位记忆系统失效环节；现有材料并未证明这种拆分能提升表现。

依据：[R1](../../reports/agent-memory/agent-memory-20261027-0300-research-paper-e7352648-9e8c-4262-b10b-9681bf24ee23.md)、[H2](../../sources/blogs/blog-fec9a2e1-6812-425a-83cd-e6a2464a1110.md)

## 反例与替代解释

- R1关注决策时充分子集，H2历史笔记描述记忆块组织，两者问题设置不同，未提供直接对照。
- 历史笔记未经本轮复核；记忆组织也可能与检索和写入策略不可分割。

## 局限

- R1仅摘要；H2仅历史笔记，相关主张未重新核对。
- 两项证据来自不同原始来源，不代表独立验证同一效果。

## 验证计划（尚未执行）

- 在统一任务与模型上，分别操纵子集选择和记忆组织方式，比较任务表现、错误类型、检索成本及记忆规模。
- 复核H2所述原文并记录实现细节，再与受控实验结果区分。

## 准入记录

[独立审阅与输入输出散列](../../reports/agent-memory/admissions/agent-memory-20261027-0300/accepted.yaml)。
