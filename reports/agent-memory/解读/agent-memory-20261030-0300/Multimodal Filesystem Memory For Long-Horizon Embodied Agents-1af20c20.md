---
title: Multimodal Filesystem Memory For Long-Horizon Embodied Agents
kind: reading_note
topics:
- agent-memory
---

<!-- researchdesk-reading {"derived_from": "reports/agent-memory/agent-memory-20261030-0300-research-paper-1337d0ee-7403-4fe2-8802-f1771af20c20.md", "original_sha256": "9c6ada5ebacaf00435bde246875826d30e750aded8d36785a812e5209c10a26c", "presentation": "reviewed_content_reformatted"} -->

[返回研究首页](../../../../%E7%A0%94%E7%A9%B6%E9%A6%96%E9%A1%B5.md)

# Multimodal Filesystem Memory For Long-Horizon Embodied Agents

本概述仅依据论文摘要，介绍其多模态文件系统记忆架构 MFM 及摘要所报告的任务表现，不代表对完整论文或实验结果的独立核验。

## 问题、方法与结果

作者提出 MFM，将情景、空间、语义、程序性和工作记忆结合起来，分别用于保存经历、关联地点、积累知识与行动方法，以及维持当前计划。

作者称，MFM 通过可搜索的文本记录连接不同记忆表示与底层多模态经历，使智能体能按上下文线索查找经历，并查看原始观察以恢复文本描述中缺失的细节。

作者称，MFM 的整合过程能将经历转化为更高层次的知识与程序，同时保留指向原始经历的引用。

作者报告，使用 GPT-6-Astra 时，MFM 在 Mine Diamond from Scratch 任务中完成目标，在 Ender Dragon 任务中达到 24 个里程碑中的 16 个；摘要称最佳基线为 12.7。

作者报告，MFM 在 CUABench-KiCad 上的平均奖励为 0.440；摘要给出的最佳基线和无持久记忆结果分别为 0.400 和 0.267。

## 如何理解这些结论

本次仅阅读论文摘要，未核验全文、实验设置、实现或结果。

摘要未提供评测细节、统计不确定性或具体基线配置，因此不能据此独立判断所报告差异的稳健性。

## 来源与阅读范围

- [Multimodal Filesystem Memory For Long-Horizon Embodied Agents](https://arxiv.org/abs/2610.22686v1)：仅阅读摘要，未核验全文或复现实验。
