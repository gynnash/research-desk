---
schema_version: 1
id: formal-insight-agent-memory-agent-memory-20261023-0300-2
kind: insight
title: 容量受限时，记忆选择与更新规则值得独立评测
topic: agent-memory
status: accepted
evidence_ids:
- R1
- H2
approval_required: false
writing_started: false
publish_authorized: false
input_fingerprint: c3623fd4f06acf6a922171857a0826c5ae865eef4f1d78b6debe0af5cda6690f
topics:
- agent-memory
---

> AI 自动研究记录，已通过独立模型审阅；阅读范围及证据限制见正文，未复现实验。

# 容量受限时，记忆选择与更新规则值得独立评测

## 待验证假设

待验证研究假设：容量受限的记忆若结合查询相关性与冗余控制，可能在预算内保留更多有用信息。R1描述视频特征多样性更新，H2历史笔记描述有容量约束的记忆块；这些材料不能证明策略可迁移至智能体记忆或能提升实际效果。

依据：[R1](../../reports/agent-memory/agent-memory-20261023-0300-research-paper-ef2bb506-9872-4221-8434-03dc4c74646a.md)、[H2](../../sources/blogs/blog-fec9a2e1-6812-425a-83cd-e6a2464a1110.md)

## 反例与替代解释

- 视频特征的多样性不等同于对话事实的价值、时效性或可信度。
- 固定容量和去冗余可能丢弃低频但关键的信息；容量限制本身也不保证记忆质量。
- H2是未经本次复核的历史项目方博客笔记，不构成性能证据。

## 局限

- R1是视频编辑摘要，不是智能体记忆实验；H2是历史笔记。
- 当前材料没有针对记忆写入、遗忘、冲突更新及长期正确性的共同评测。

## 验证计划（尚未执行）

- 在长期对话任务中比较不同容量、相关性选择与冗余控制策略，并保持检索和回答组件一致。
- 分别测量重要信息保留、过时或冲突记忆处理、最终回答正确性及存储成本。
- 使用跨会话、跨任务测试及人工核验的事实来源标签，检查稳定性并识别误删风险。

## 准入记录

[独立审阅与输入输出散列](../../reports/agent-memory/admissions/agent-memory-20261023-0300/accepted.yaml)。
