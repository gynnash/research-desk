---
schema_version: 1
id: paper-4eb3be4b-7189-49aa-bafd-f88f77a972f4
kind: paper
title: "MemGPT: Towards LLMs as Operating Systems"
source: arXiv
source_url: https://arxiv.org/abs/2310.08560
authors:
  - Charles Packer
  - Sarah Wooders
  - Kevin Lin
  - Vivian Fang
  - Shishir G. Patil
  - Ion Stoica
  - Joseph E. Gonzalez
published_at: "2023-10-12"
collected_at: "2026-10-18"
updated_at: "2026-10-18"
topics:
  - agent-memory
status: analyzed
related_sources:
  - blog-fec9a2e1-6812-425a-83cd-e6a2464a1110
related_notes:
  - reports/2026-10-18-agent-memory-memgpt-memory-blocks.md
  - insights/2026-10-18-agent-memory-usable-memory.md
  - insights/2026-10-18-agent-memory-traceable-updates.md
  - articles/2026-10-18-agent-memory-saving-vs-remembering-outline.md
  - articles/2026-10-18-agent-memory-saving-vs-remembering-draft.md
arxiv_id: "2310.08560"
doi: 10.48550/arxiv.2310.08560
source_version: v2
---

# MemGPT: Towards LLMs as Operating Systems

## 来源核验与入选理由

[arXiv 原始记录](https://arxiv.org/abs/2310.08560)核对标题、作者与首发日期；本次阅读 [v2 正文](https://arxiv.org/html/2310.08560v2)，修订于 2024-02-12。[DOI](https://doi.org/10.48550/arXiv.2310.08560)为 arXiv 分配，不代表会议发表。

入选作为分层记忆与自主记忆管理的架构样本，便于后续比较；不以“当前最佳”作为入选依据。

## 摘要

把有限上下文与外部存储分层，通过函数调用调入、编辑和移出信息，配合队列与控制流管理。扩展的是可访问的信息范围，并未扩大模型的实际窗口。[§2](https://arxiv.org/html/2310.08560v2)

## 关键结论与证据

- **机制**：主上下文包含指令、工作区和消息队列；检索结果必须进入窗口才能参与推理。[§2.1–2.4、图3](https://arxiv.org/html/2310.08560v2)
- **作者报告**：跨会话 DMR 任务中，GPT-4 准确率从 32.1% 到加 MemGPT 后的 92.5%。基线使用历史摘要，MemGPT 可检索完整历史；不能脱离此信息条件解释差值。[§3.1.1、表2](https://arxiv.org/html/2310.08560v2)

## 与研究主题的关系

覆盖记忆存储、检索、更新和评测。相关工程表达见 [Memory Blocks 博客笔记](../blogs/blog-fec9a2e1-6812-425a-83cd-e6a2464a1110.md)。

## 局限与待验证问题

原文报告 GPT-3.5 因函数调用能力受限而性能退化，以及检索可能提前停止；文档问答仅取 50 题，并使用模型评审。结果不直接证明真实长期使用的可靠性。[§3.2.1](https://arxiv.org/html/2310.08560v2)

## 人工笔记

本轮为 AI 辅助首轮分析，尚未经用户复核，未复现实验。

本库待验证：什么应长期保存？错误记忆怎样纠正并保留证据？公众号选题线索：为什么“保存过”不等于“需要时能想起”？以上为研究问题，非论文结论。

## 更新记录

- 2026-10-18：核验原始来源、首发日期及 v2；完成首轮分析和博客互链。标记 `analyzed` 仅表示已完成本轮阅读分析，不表示复现成功。
- 2026-10-18：补充首轮报告、两条洞察及公众号大纲的关联，保留原阅读笔记。
- 2026-10-18：补充公众号文章初稿关联，原文事实与写作推断在初稿中分别标示。
