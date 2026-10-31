---
title: 'Hy-Memory-30B-A3B: Attributed Reinforcement Learning for Long-Term Memory
  Writing'
kind: reading_note
topics:
- agent-memory
---

<!-- researchdesk-reading {"derived_from": "reports/agent-memory/cycle-agent-memory-gh-20261019-research-paper-2d89084b-a1b1-4a27-b298-a660ef434e61.md", "original_sha256": "dc9bbeb260b478b94ebe7919a7e6c4ab10238ba49fdb14a987b803035af3e5d2", "presentation": "reviewed_content_reformatted"} -->

[返回研究首页](../../../../%E7%A0%94%E7%A9%B6%E9%A6%96%E9%A1%B5.md)

# Hy-Memory-30B-A3B: Attributed Reinforcement Learning for Long-Term Memory Writing

本次仅依据所提供的论文摘要，概述 Hy-Memory-30B-A3B 的研究动机、训练方法及作者报告的基准结果；不代表对论文完整内容或结果的独立核验。

## 问题、方法与结果

作者指出，外部记忆系统的质量依赖模型如何写入记忆，包括保留什么、如何表述，以及如何依据新证据更新持久状态；现有框架通常使用由框架专属提示驱动的通用大模型，带来服务成本与协议迁移问题。

作者介绍 Hy-Memory-30B-A3B，将其描述为在 Mem0、MemOS 和 Hy-Memory 上训练的紧凑型长期记忆写入模型。

摘要称，其训练方法包括在学生模型生成的状态上学习框架专属写入协议的 Memory On-Policy Distillation，以及通过分块探测、跨块归因奖励、过度存储控制和 chunk-level GRPO 优化下游可回答性的 Memory RL；训练中还跨窗口沿用策略写入的记忆库。

作者报告，在固定的 20% 基准子样本上，该模型在四个评测 harness 中均排名第一（包括留出的 EverMemOS），宏平均为 55.49%，Claude Opus 5 为 54.62%。

## 如何理解这些结论

本次只读论文摘要，未核验全文、实验设计、实现或结果。

基准结论及数值仅为摘要中的作者报告；材料未提供各评测 harness 的细节、样本规模或统计不确定性。

材料不足以判断模型在其他数据、框架或部署条件下的表现。

## 来源与阅读范围

- [Hy-Memory-30B-A3B: Attributed Reinforcement Learning for Long-Term Memory Writing](https://arxiv.org/abs/2610.22196v1)：仅阅读摘要，未核验全文或复现实验。
