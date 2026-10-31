---
schema_version: 1
id: topic-agent-memory-agent-memory-20261031-acceptance-1
kind: topic_proposal
title: 待确认选题：Agent明明“记住了”，为什么还是答不出来？
topic: agent-memory
status: proposed
evidence_ids:
- R1
- R2
approval_required: true
writing_started: false
publish_authorized: false
input_fingerprint: a80fafcb7fe8373f64fb8b3cd944f199477407eb10717db54643afa18a81bcde
source_ids:
- paper-4fe5c214-056e-49c9-b5e1-dfd550ee077f
- paper-85eab296-b33a-475c-ab8e-44d8b6a705b0
---

# 待确认选题：Agent明明“记住了”，为什么还是答不出来？

> TEST：运行中间产物，未正式入库。

**待你确认选题、角度与读者后才启动 Writing；当前是选题提案，尚未写作或发布。**

围绕读者疑问“证据已经入库，为什么回答仍失败”，比较提前抽取造成的不可恢复损失与检索后打包造成的不可见损失。用《MemoryTax》的成本与写读交换实验，以及《MOSAIC》中结构化文本超过原生平坦检索的反例，解释为什么不能把问题简化为是否使用记忆模块。讨论重点是完整证据如何进入实际请求，而不是宣称原文搜索或结构化记忆已经胜出。

本批两篇同期论文恰好提供了互补视角：一篇质疑预建记忆的成本与信息上限，另一篇展示记忆组织在交付预算下的局部价值。这种有条件的张力足以支撑技术讨论，但没有资料证明它已成为行业热潮或演进趋势。

## 适合谁读

正在设计Agent记忆、RAG、多模态助手及相关评测体系的工程师和技术负责人。

## 准备回答的问题

- 保存、检索命中和实际交付，为什么是三个不同的成功条件？
- 什么情况下提前结构化会损害未来问题，什么情况下又能改善完整链交付？
- 如何同时核算建库成本、回查费用和证据被预算淘汰的损失？

## 写作前还缺少什么

- 写作前应核实《MOSAIC》关键提示词缺失及局部数值方向表述不一致的问题，避免把文本抽取完整误写成实现配置已完整核查。
- 缺少统一输入、共同阅读器和全周期费用下的直接对照，不能将跨论文结果写成性能排名。
- 混合记忆与链感知打包仍是待验证假设；缺少持续更新、真实私人历史及授权删除机制的实证，不宜写成成熟部署建议。

[本轮深度思考](../../../../reports/test/agent-memory/insight-runs/agent-memory-20261031-acceptance/report.md)

## 资料来源与阅读范围

- [MemoryTax: The Bitter Lesson of Agent Memory](https://arxiv.org/abs/2610.29823v1)：已阅读完整抽取正文，未独立复现实验。
- [MOSAIC: An Omni-Modal Benchmark for Long-Term Memory and Cross-Modal Reasoning in Conversational Agents](https://arxiv.org/abs/2610.29249v1)：已阅读完整抽取正文，未独立复现实验。
