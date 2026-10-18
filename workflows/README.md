# 研究工作流

## 总体架构与定时研究设计

- [Research、Insight、Writing 三 Agent 总体架构](three-agent-architecture.md)：定义最终系统、角色分工、共享知识与独立模型审阅机制。
- [Agent Memory GitHub Actions MVP](agent-memory-github-actions-mvp.md)：每周二、周五北京时间 09:00 触发；独立审阅模型与规则校验通过后，经 PR 自动合并入库，保留人工笔记保护及失败补跑。

以上均为设计文档，尚未实现或启用。首个任务只覆盖来源研究，Insight、Writing 和综合报告自动化留待后续阶段；公众号发布继续停用。

## 人工研究流程

1. 在 `config/research_topics.yaml` 确认主题范围。
2. 按[维护规范](maintenance.md)全库检索来源，决定新增还是更新。
3. 从 [templates/paper.md](templates/paper.md) 或 [templates/blog.md](templates/blog.md) 创建一条资料，填写 [Schema](source-schema.md)。
4. 阅读原文并维护状态和笔记；需要时手动整理到 `reports/`、`insights/` 或 `articles/`。
5. 执行 `python3 workflows/validate.py`（在仓库根目录，需 PyYAML），检查差异，再提交并同步。

这里仅包含设计、约定、模板与只读校验工具。没有可执行的研究 Agent、抓取器、调度器或自动研究任务。
