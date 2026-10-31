---
title: 'AgentOdyssey: Open-Ended Long-Horizon Text Game Generation for Test-Time Continual
  Learning Agents'
kind: reading_note
topics:
- agent-memory
---

<!-- researchdesk-reading {"derived_from": "reports/agent-memory/agent-memory-20261027-0300-research-paper-bc0d7d05-0ed7-4d63-8a1b-f8552566bf17.md", "original_sha256": "f647377de115a348aab863d58acc15e86f60d66551f7cdd9caa20be63ce133fb", "presentation": "reviewed_content_reformatted"} -->

[返回研究首页](../../../../%E7%A0%94%E7%A9%B6%E9%A6%96%E9%A1%B5.md)

# AgentOdyssey: Open-Ended Long-Horizon Text Game Generation for Test-Time Continual Learning Agents

仅依据论文摘要，AgentOdyssey面向测试时持续学习智能体，提出程序化生成开放式文本游戏的评测框架，并报告了智能体能力与测试时训练方面的实验观察；以下不代表对全文或实验的独立核验。

## 问题、方法与结果

摘要介绍 AgentOdyssey：一个程序化生成开放式文本游戏的评测框架，游戏包含丰富实体、世界动态和长程任务。

摘要称其评测方法除游戏进度外，还涵盖世界知识获取、情景记忆、物体与动作探索、动作多样性及模型成本。

作者称，他们在六款生成的游戏中评估了多种智能体范式，并观察到智能体关键能力的局限及影响其有效规划时域的因素。

作者称，测试时训练的专项研究发现短期记忆有益，但经监督微调训练的智能体仍会发生灾难性遗忘；有效的参数化持续学习仍是未解决的问题。

## 如何理解这些结论

本次只读论文摘要，未核验全文、实验细节、实现或结果；作者报告的发现不应视为独立验证。

材料对记忆的讨论限于摘要中有关情景记忆、短期记忆与灾难性遗忘的概述，未提供记忆机制的详细描述。

## 来源与阅读范围

- [AgentOdyssey: Open-Ended Long-Horizon Text Game Generation for Test-Time Continual Learning Agents](https://arxiv.org/abs/2606.24893v2)：仅阅读摘要，未核验全文或复现实验。
