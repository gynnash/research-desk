---
title: 'Beyond Marginal Influence: Interaction-Aware Memory Selection for LLM Agents'
kind: reading_note
topics:
- agent-memory
---

<!-- researchdesk-reading {"derived_from": "reports/agent-memory/agent-memory-20261027-0300-research-paper-e7352648-9e8c-4262-b10b-9681bf24ee23.md", "original_sha256": "ecf2e7eb08cfef10e0859923d9d97fad183713554023c2aef1d7ce9c9d2ad38a", "presentation": "reviewed_content_reformatted"} -->

[返回研究首页](../../../../%E7%A0%94%E7%A9%B6%E9%A6%96%E9%A1%B5.md)

# Beyond Marginal Influence: Interaction-Aware Memory Selection for LLM Agents

该摘要研究 LLM 智能体按决策选择记忆子集的方法，重点是子集能否保留完整记忆下的行为。以下仅概述所提供的论文摘要，未核验论文全文、实验或实现。

## 问题、方法与结果

作者指出，按相关性或单条记录影响力排序，可能无法找到冗余证据或必须联合使用的证据所构成的充分子集。

摘要称，JointCoreBench 包含九类交互、六个工作流领域、自然语言决策及精确充分集 oracle；JointCore 是按相关性成本排序、先测试记录块再测试单条记录的删除基线。

在摘要所述的 6,912 个精确条件上，JointCore 达到 100.0% 的最低成本充分集恢复率，子集评估次数从 30.00 降至 11.13，并报告 87.8% 的活动记忆节省。

在四类 12B–70B 模型、每个模型 432 项任务的测试中，摘要报告 JointCore 的平均模型查询数为 10.28，低于单例删除基线的 16.00；最低成本恢复率分别为 50.6% 和 43.1%。

作者称，基线在确定性主接口下保留完整记忆行为；其他接口测试显示行为依赖接口，并明确表示该研究尚未证明记忆压缩已可用于部署。

## 如何理解这些结论

材料仅为论文摘要，未核验全文、实验设计细节、统计分析或实现。

结果及其解释均为摘要中的作者报告，不能据此视为独立验证。

摘要未提供接口测试的具体结果，也未说明各测试条件的详细定义。

## 来源与阅读范围

- [Beyond Marginal Influence: Interaction-Aware Memory Selection for LLM Agents](https://arxiv.org/abs/2610.23266v1)：仅阅读摘要，未核验全文或复现实验。
