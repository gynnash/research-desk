---
title: 'Edit-Your-Interest: Efficient Video Editing via Feature Most-Similar Propagation'
kind: reading_note
topics:
- agent-memory
---

<!-- researchdesk-reading {"derived_from": "reports/agent-memory/agent-memory-20261023-0300-research-paper-ef2bb506-9872-4221-8434-03dc4c74646a.md", "original_sha256": "c29cc56cb8f4e88e3182e6dc9953b7bcc5dad65d831298eadf9db63430442629", "presentation": "reviewed_content_reformatted"} -->

[返回研究首页](../../../../%E7%A0%94%E7%A9%B6%E9%A6%96%E9%A1%B5.md)

# Edit-Your-Interest: Efficient Video Editing via Feature Most-Similar Propagation

仅依据论文摘要，概述 Edit-Your-Interest 在视频编辑中使用有界特征记忆与相似性检索传播的设计；材料涉及记忆缓存、检索和更新，但不直接研究通用智能体记忆。

## 问题、方法与结果

摘要称，时空特征记忆库（SFM）在固定内存预算下缓存前序帧的空间注意力特征。

作者称，SFM维护代表性候选池，以减少对完整序列进行时空建模的计算开销。

摘要称，特征最相似传播（FMP）依据相似度检索相关缓存令牌，并将其传播至当前帧；SFM更新算法则依据特征多样性维护记忆的代表性和非冗余性。

作者称，SFM与FMP的设计改善了时间一致性并减少模糊和马赛克状伪影；摘要还称实验中该方法在效率和视觉保真度方面优于当时的先进方法。

## 如何理解这些结论

本次仅覆盖论文摘要，未核验全文、实验细节、实现或结果。

材料讨论的是视频编辑方法中的特征缓存与检索，不能据此推断其适用于通用智能体的工作记忆或长期记忆。

摘要未提供可用于独立评估记忆更新策略、内存预算大小或比较实验的具体细节。

## 来源与阅读范围

- [Edit-Your-Interest: Efficient Video Editing via Feature Most-Similar Propagation](https://arxiv.org/abs/2510.13084v2)：仅阅读摘要，未核验全文或复现实验。
