---
title: 'MemSyco-Bench: Benchmarking Sycophancy in Agent Memory'
kind: reading_note
topics:
- agent-memory
---

<!-- researchdesk-reading {"derived_from": "reports/agent-memory/agent-memory-20261020-0300-recovery-1-research-paper-f5ce4a88-8dda-4ad0-b219-a0abb5a40c21.md", "original_sha256": "7ac58401dcd754ab98fab604f73496f53cb79c8d7da88710b6c71f21bd2acd0e", "presentation": "reviewed_content_reformatted"} -->

[返回研究首页](../../../../%E7%A0%94%E7%A9%B6%E9%A6%96%E9%A1%B5.md)

# MemSyco-Bench: Benchmarking Sycophancy in Agent Memory

仅依据论文摘要节选，MemSyco-Bench 关注记忆对智能体后续推理与决策的影响，尤其是记忆诱发的迎合问题；不能据此判断基准的完整设计或实测效果。

## 问题、方法与结果

作者指出，检索到的记忆可能导致智能体过度迎合用户，从而损害事实准确性或客观推理。

作者称，现有记忆基准主要评估记忆是否被正确存储、检索或更新，而较少关注记忆如何影响后续推理与决策。

作者提出 MemSyco-Bench，用于评估智能体系统中的记忆诱发迎合，并考察何时应让记忆影响决策、以及如何使用有效记忆。

摘要列出五类评测任务：拒绝将记忆当作事实证据、遵守记忆适用范围、处理记忆与客观证据的冲突、跟踪记忆更新，以及使用有效记忆进行个性化。

## 如何理解这些结论

本次仅阅读摘要节选，未核验论文全文、基准数据、实验结果或实现。

节选未提供各任务的具体定义、评测方法、结果或局限，不能据此判断基准的有效性或实际表现。

## 来源与阅读范围

- [MemSyco-Bench: Benchmarking Sycophancy in Agent Memory](https://arxiv.org/abs/2607.01071v3)：仅阅读摘要，未核验全文或复现实验。
