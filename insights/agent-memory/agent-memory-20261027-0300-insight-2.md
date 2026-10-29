---
schema_version: 1
id: formal-insight-agent-memory-agent-memory-20261027-0300-2
kind: insight
title: 长时程记忆评测或需同时检查行为保留与信息取用
topic: agent-memory
status: accepted
evidence_ids:
- R2
- H4
approval_required: false
writing_started: false
publish_authorized: false
input_fingerprint: a2b9727f130a1831aaf3d3cb7781f9f967e9b476f37be717c854ead1ee3414a3
topics:
- agent-memory
---

> AI 自动研究记录，已通过独立模型审阅；阅读范围及证据限制见正文，未复现实验。

# 长时程记忆评测或需同时检查行为保留与信息取用

## 待验证假设

待验证的研究假设：除评估智能体能否保留经历外，还应测试其在长时程任务中能否检索并正确使用相关信息；这只是由不同材料提出的评测方向，不是已证实的改进方案。

依据：[R2](../../reports/agent-memory/agent-memory-20261027-0300-research-paper-bc0d7d05-0ed7-4d63-8a1b-f8552566bf17.md)、[H4](../../sources/papers/paper-4eb3be4b-7189-49aa-bafd-f88f77a972f4.md)

## 反例与替代解释

- R2摘要没有提供记忆机制的详细描述，H4是未经本轮复核的历史架构笔记。
- 长时程任务失败可能来自探索、规划、接口或模型能力，而非记忆本身。

## 局限

- R2仅摘要；H4仅历史笔记，无法支持两者之间的因果关系。
- 现有材料没有统一评测或可直接比较的数据。

## 验证计划（尚未执行）

- 设计分阶段长时程任务，分别测量经验保留、相关记忆检索、使用正确性与最终任务表现。
- 设置记忆机制关闭或替换的对照，并控制模型、工具和任务难度。

## 准入记录

[独立审阅与输入输出散列](../../reports/agent-memory/admissions/agent-memory-20261027-0300/accepted.yaml)。
