# 研究工作流

日常阅读从[研究首页](../研究首页.md)和[正式资料索引](../workbench/资料索引.md)开始。本目录保存操作说明、设计与历史验收；历史调用数和时间是当时快照，当前行为以配置与实际回执为准。

## 当前流程

**Research 采集与单篇研究 → 独立审阅 → Insight 历史比较、洞察与选题 → 独立审阅与正式入库 → 用户确认 → Writing 大纲、初稿与候选稿。** 发布公众号另行决定。

| 操作或问题 | 说明 |
| --- | --- |
| 理解三个 Agent 的分工 | [总体架构](three-agent-architecture.md)、[定时 MVP](agent-memory-github-actions-mvp.md) |
| 最近两个月选材、长期综合与简化边界 | [2026-10-30 目标对齐审查](workflow-alignment-2026-10-30.md) |
| 扩展公开博客与保存原文 | [采集覆盖、原文归档与断网重放](source-coverage-and-archive.md) |
| 配置并运行一轮研究 | [Research → Insight 轮次](research-cycle.md)、[配置驱动批次](configurable-research-batch.md) |
| 来源采集、正文阅读与去重 | [真实来源采集](real-source-collection.md)、[论文全文阅读](fulltext-reading.md)、[维护规范](maintenance.md) |
| 登录自己的会员与控制预算 | [本地会员分析](local-membership-analysis.md)、[共享请求预算](membership-budget.md) |
| 部署 Mac 或配置远程执行环境 | [自托管执行器](self-hosted-worker.md) |
| 已审阅研究正式入库 | [正式准入](formal-admission.md) |
| 研究失败、检查点和补跑 | [轮次运行](research-cycle.md)、[关联 Insight 恢复](linked-insight-recovery.md) |
| 确认选题或撤回 | [真实选题确认页](topic-confirmation-mvp.md) |
| 生成与准入三阶段稿件 | [会员 Writing](writing-agent-member.md)、[Writing 正式准入](writing-formal-admission.md) |
| 检查 Markdown 与来源字段 | [资料 Schema](source-schema.md)、[模板](templates/) |
| 阅读与同步 Obsidian | [研究工作台说明](../workbench/README.md) |

研究调度为每周二、周五北京时间 03:00，最终开关见 [automation.yaml](../config/automation.yaml)。个人 Codex 09:00 简报单独读取已有正式结果，不再次启动模型。执行器需要在线；实际成功与失败看工作流和接受回执，不能用历史演练代替。

## 保留的历史记录

以下文档保留实现过程与可复核验收，不需要作为每日操作步骤逐份阅读。

- [Research 离线骨架](offline-research.md)、[早期会员分析设计](chatgpt-analysis-handoff.md)。
- [Insight 测试闭环](insight-agent-test.md)、[引用范围与证据边界](insight-citation-scope.md)。
- [Writing 离线闭环](writing-agent-offline.md)。
- [首次正式入库与调度验收](formal-admission-acceptance-2026-10-19.md)、[首次同步检查](sync-check-2026-10-18.md)。
- [10 月 27 日准入修复调查](admission-investigation-2026-10-27.md)。

`test` 中的运行记录仍用于断点恢复、预算与去重；正式接受证明绑定历史输入输出。不要为精简文档而删改这些文件或将历史测试升级为新研究。
