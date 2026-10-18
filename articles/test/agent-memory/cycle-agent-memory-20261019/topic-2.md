---
schema_version: 1
id: topic-agent-memory-cycle-agent-memory-20261019-2
kind: topic_proposal
title: 产品说有用户级记忆，可靠性还需要哪些证据？
topic: agent-memory
status: proposed
evidence_ids:
- R2
- H2
approval_required: true
writing_started: false
publish_authorized: false
input_fingerprint: 4f554f655b50a96dc88c5f1c123cd3b185a0b325227afde6ab73bfc8e32c952f
---

> TEST：会员真实综合与独立审阅；论文摘要/博客节选及人工历史基线，未正式入库。

# 产品说有用户级记忆，可靠性还需要哪些证据？

**待用户确认选题、角度与受众；未授权或启动 Writing，不是文章大纲或草稿。**

- 写作角度：以R2节选中的用户级记忆描述为切入，探讨可靠性评估需要核实的保存期限、跨会话行为和更新规则；H2仅作为不同系统的历史评测记录，不作为该产品能力的验证。
- 目标读者：评估Agent产品能力、可靠性与上线风险的技术团队和产品读者
- 选题理由：当前材料包含产品能力描述与另一系统的历史评测记录，可用于区分功能表述和效果证据；不据此推断市场热度或产品成熟度。
- 关联洞察：insight-agent-memory-cycle-agent-memory-20261019-2
- 证据：[R2](../../../../reports/test/agent-memory/research-batches/cycle-agent-memory-20261019/items/langchain-fb2f55573b1a/report.md)、[H2](../../../../sources/papers/paper-4eb3be4b-7189-49aa-bafd-f88f77a972f4.md)

## 拟回答的问题

- R2所述用户级记忆是否跨会话保存，保存期限如何定义？
- 记忆如何写入、更新、处理过时信息或冲突？
- 评估记忆能力时，如何记录任务条件和实际记忆状态？

## 写作前的证据缺口

- 需查验完整产品文档、实现细节、保存与更新规则、部署及隐私安全说明。
- 需重新核验H2所记论文的任务条件；不同系统的结果不能替代同一产品配置下的评测。
