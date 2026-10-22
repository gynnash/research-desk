---
schema_version: 1
id: report-agent-memory-agent-memory-20261023-0300
kind: synthesis
title: 智能体记忆：检索、证据组织与容量约束
topic: agent-memory
status: test_accepted
evidence_ids:
- H1
- H2
- R1
- R2
approval_required: false
writing_started: false
publish_authorized: false
input_fingerprint: c3623fd4f06acf6a922171857a0826c5ae865eef4f1d78b6debe0af5cda6690f
---

> TEST：会员真实综合与独立审阅；论文摘要/博客节选及人工历史基线，未正式入库。

# 智能体记忆：检索、证据组织与容量约束

R1、R2仅覆盖论文摘要；H1、H2为未经本次独立原文复核的历史人工笔记。历史笔记中的转述不能视为本次核验事实；来源有关联不构成独立验证，现有材料不足以推断行业趋势、因果关系或跨方法性能排名。

## 综合摘要

R1摘要描述视频编辑中的有界特征缓存、相似性检索传播和多样性更新；R2摘要提出面向长期对话记忆的查询条件证据编译。H1、H2的历史笔记分别记录上下文管理和记忆块的工程描述。它们可用于提出记忆选择与组织的研究问题，但R1并非通用智能体记忆研究，R2结果仅为作者报告，历史笔记也未经本次复核，不能据此确认效果或进行性能比较。

## 比较与证据

- **原文事实**：R1摘要描述在固定预算下缓存前序帧特征、按相似性检索并依据特征多样性更新；该设计属于视频编辑场景，不能直接证明其适用于智能体长期记忆。（[R1](../../research-batches/agent-memory-20261023-0300/items/arxiv-d9523f400d3a/report.md)）
- **作者声称，未独立复现**：R2摘要描述先定位支持材料、再在有限预算内选择互补证据并组织回答上下文；其报告的 LoCoMo 结果未在本次材料中独立核验。（[R2](../../research-batches/agent-memory-20261023-0300/items/arxiv-e05d9eb84420/report.md)）
- **作者声称，未独立复现**：H1历史笔记转述了文件卸载、摘要和按需加载等上下文管理机制；这些描述未经本次原文复核，不能据此确认其当前适用性或效果。（[H1](../../../../../sources/blogs/agent-memory/blog-05c33166-b18e-425e-91e0-36ddd26f21aa.md)）
- **我们的推断**：H2历史笔记记录了以用途、容量等组织记忆块的工程视角；与R2的查询条件证据编译并置，可形成“持久组织”与“任务时组装”的研究问题，但不能据此认定两者互补或孰优孰劣。（[R2](../../research-batches/agent-memory-20261023-0300/items/arxiv-e05d9eb84420/report.md)、[H2](../../../../../sources/blogs/blog-fec9a2e1-6812-425a-83cd-e6a2464a1110.md)）
- **我们的推断**：R1讨论视频帧特征传播，R2讨论长期对话中的回答证据编译；任务与对象不同，现有材料不支持跨领域性能排名。（[R1](../../research-batches/agent-memory-20261023-0300/items/arxiv-d9523f400d3a/report.md)、[R2](../../research-batches/agent-memory-20261023-0300/items/arxiv-e05d9eb84420/report.md)）

## 局限

- R1、R2均仅有摘要，缺少可供本次复核的全文、完整实验设置和独立复现；R2摘要未提供成本指标定义及统计不确定性。
- R1研究视频编辑特征缓存，不直接研究通用智能体的工作记忆或长期记忆。
- H1、H2为历史笔记，未经本次独立原文复核；其中转述的主张不能升格为本次核验事实。
- 材料没有统一任务或评测条件，不支持因果结论、行业趋势或方法排名。

## 待验证问题

- 查询条件证据编译在不同长期对话任务及独立复现中是否仍有收益？
- 记忆预算受限时，如何评估证据的互补性、冗余程度和回答所需的完整性？
- 持久记忆块、文件卸载或摘要与查询时证据编译如何组合，是否会导致信息丢失或冲突？

## 输入与来源

- [H1](../../../../../sources/blogs/agent-memory/blog-05c33166-b18e-425e-91e0-36ddd26f21aa.md)：human_baseline；来源 ID：blog-05c33166-b18e-425e-91e0-36ddd26f21aa。
  - [原始来源](https://www.langchain.com/blog/context-engineering-deep-agents-remember)；覆盖：historical_note。
- [H2](../../../../../sources/blogs/blog-fec9a2e1-6812-425a-83cd-e6a2464a1110.md)：human_baseline；来源 ID：blog-fec9a2e1-6812-425a-83cd-e6a2464a1110。
  - [原始来源](https://www.letta.com/blog/memory-blocks/)；覆盖：historical_note。
- [R1](../../research-batches/agent-memory-20261023-0300/items/arxiv-d9523f400d3a/report.md)：reviewed_research；来源 ID：paper-ef2bb506-9872-4221-8434-03dc4c74646a。
  - [原始来源](https://arxiv.org/abs/2510.13084v2)；覆盖：abstract_only。
- [R2](../../research-batches/agent-memory-20261023-0300/items/arxiv-e05d9eb84420/report.md)：reviewed_research；来源 ID：paper-2fa6f60d-0b98-43ab-b4bb-c2a94bd803dd。
  - [原始来源](https://arxiv.org/abs/2610.23313v1)；覆盖：abstract_only。
