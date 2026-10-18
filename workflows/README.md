# 研究工作流

## 总体架构与定时研究设计

- [Research、Insight、Writing 三 Agent 总体架构](three-agent-architecture.md)：定义最终系统、角色分工、共享知识与独立模型审阅机制。
- [Agent Memory GitHub Actions MVP](agent-memory-github-actions-mvp.md)：每周二、周五北京时间 09:00 触发；独立审阅模型与规则校验通过后，经 PR 自动合并入库，保留人工笔记保护及失败补跑。

以上均为设计文档，尚未实现或启用。首个任务只覆盖来源研究，Insight、Writing 和综合报告自动化留待后续阶段；公众号发布继续停用。

## 离线运行骨架

[离线运行与验收](offline-research.md)说明固定样例、两个独立模拟模型、测试目录、预算记录及中断补跑。

## 真实来源采集与会员分析设计

[真实采集与模拟验收](real-source-collection.md)已接入 arXiv、Letta、LangChain，结果仅保存到各研究方向的 `test` 目录，分析仍为模拟。未来按[ChatGPT 会员分析设计](chatgpt-analysis-handoff.md)评估官方授权后端；当前只生成交接包，没有会员登录或真实推理。GitHub 自动入库和定时执行仍未实现或启用。

## 人工研究流程

1. 在 `config/research_topics.yaml` 确认主题范围。
2. 按[维护规范](maintenance.md)全库检索来源，决定新增还是更新。
3. 从 [templates/paper.md](templates/paper.md) 或 [templates/blog.md](templates/blog.md) 创建一条资料，填写 [Schema](source-schema.md)。
4. 阅读原文并维护状态和笔记；需要时手动整理到 `reports/`、`insights/` 或 `articles/`。
5. 执行 `python3 workflows/validate.py`（在仓库根目录，需 PyYAML），检查差异，再提交并同步。

这里包含设计、约定、模板、只读校验工具及测试样例；`scripts/` 包含受限真实采集器与模拟运行骨架，只写测试目录。没有调度器或自动研究任务。
