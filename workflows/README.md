# 研究工作流

## 总体架构与定时研究设计

- [Research、Insight、Writing 三 Agent 总体架构](three-agent-architecture.md)：定义自动研究、综合洞察、公众号选题，以及人工确认选题后才启动写作的完整流程；独立模型审阅是三者共用能力。
- [Agent Memory GitHub Actions MVP](agent-memory-github-actions-mvp.md)：拟每周二、周五北京时间 09:00 触发；研究独立审阅与规则校验通过后受限自动入库，再逐步接通 Insight/选题。保留人工笔记保护及失败补跑。

总体流程和正式入库仍按设计分阶段实现。已有真实采集、官方会员本地后端、单篇摘要真实研究审阅及 YAML 驱动的 Research、Insight 测试闭环；当前增加 Writing 的虚构确认及离线模拟写作。真实人工确认入口和会员 Writing 后端留待后续阶段，没有定时任务或公众号发布。

## Writing 离线闭环

[Writing 虚构确认、三阶段审阅与验收](writing-agent-offline.md)使用固定虚构选题与证据，确认记录明确为 `origin: offline_fixture`。大纲、初稿和候选稿各自先通过确定性校验和独立模拟审阅，再进入下一阶段；模型不能自行批准确认。文章只写 `articles/test/<topic>/<batch-id>/`，账本只写 `reports/test/<topic>/writing-runs/<batch-id>/`，不覆盖旧稿。

每批最多 12 次模拟调用，每阶段最多 4 次及一次修订；缺失、失效或被撤回的确认，输入散列变化、审阅失败和预算不足均应停止。使用既有 PyYAML，无网络或真实会员调用，不影响本地会员累计 10/100。当前两张真实 Insight 选题卡保持待确认，未被此演练批准或启动写作。真实结果以离线回执为准，不将样例确认冒称用户授权。

2026-10-19 [虚构样例验收](../reports/test/agent-memory/writing-runs/writing-offline-20261019/acceptance.md)已通过，保存大纲、初稿和候选稿；初稿修订一次，总计 8 次模拟调用、8 个虚拟单位。大纲检查点、全部审阅后及首个文章创建后的中断均恢复成功；禁用新模拟调用后恢复与完整缓存重放仍为 8 次。真实会员调用为 0，累计预算保持 10/100；真实人工确认入口和会员 Writing 后端尚未接通。

## Insight 测试闭环

[Insight 配置、证据与验收](insight-agent-test.md)说明如何读取已通过真实独立审阅的 Research 输入及显式登记的历史资料，生成综合报告、1–2 条洞察和公众号候选选题，再交独立模型审阅。历史资料保留 `human_baseline` 标识，不冒充本轮重新核实的原文；洞察须追溯到至少两个不同的原始来源，相关材料不能当作独立验证。

正常两次会员请求，最多四次，包含一次修订与复审；与单篇分析、Research 批次共享月度请求预算，当前上限为 100，未知调用不自动重发。报告、洞察和选题分别只写各目录的 `test/<topic>/`，既有资料不可覆盖。选题由程序固定为 `proposed`、`approval_required: true`、`writing_started: false`，本轮不提供确认或 Writing 入口；真实通过状态以回执为准。

2026-10-19 [真实验收](../reports/test/agent-memory/insight-runs/insight-agent-memory-20261019/acceptance.md)已通过：综合报告、2 条洞察和 2 张待确认选题卡，生成 `gpt-6-luna`，独立审阅 `gpt-6.1-sol`。共 4 次请求、43,163 tokens，含失败响应、一次模型修订、一次严格语法规范化及额外独立格式确认；恢复和缓存补跑均没有追加推理。回执中的月度 `10/10` 为当时快照；按用户后续授权，上限现为 100，累计预留仍为 10。会员剩余额度保留未知。正式入库、确认入口、Writing 和调度仍未启用。

## 配置驱动的 Research 批次

[批次运行与验收](configurable-research-batch.md)说明如何通过 YAML 配置主题、来源、两个不同模型和预算，以及一篇论文加一篇博客的采集、研究、独立审阅和中断补跑。通用示例供开源用户自行配置并使用自己的官方授权 profile；当前配置只生成 `reports/test/<topic>/research-batches/<batch-id>/` 中的结果。

本轮最多 6 次请求、单项最多 4 次、至多一次修订；共享月度上限现为 100，保留此前会员测试的所有累计预留。未知请求不自动重发；已通过的单项在同批补跑中复用，已有笔记与测试产物不覆盖。真实状态以批次回执为准，配置中启用方向不等于启用定时任务。

## 共享会员请求预算

统一入口为 [`config/membership_budget.yaml`](../config/membership_budget.yaml)，当前 `month_max_calls: 100`。之前的每月 10 次是本项目用于小额度验收的本地策略，并非来自 ChatGPT 官方会员额度。提高本地月度上限只改变后续请求的准入，不清零已有预留，不返还未知请求，也不扩大单篇、单项或批次限制。旧配置、清单与回执保留当时的 10 次策略及结果；当前累计 10/100，会员实际剩余额度未知。其他用户可为自己的工作台配置该文件，凭据仍在仓库外。

[预算配置与只读复核](membership-budget.md)说明集中配置优先级、缺失时的旧策略回退，以及无会员调用的累计账本检查。模拟预算保持原样。

## 离线运行骨架

[离线运行与验收](offline-research.md)说明固定样例、两个独立模拟模型、测试目录、预算记录及中断补跑。

## 真实来源采集与本地会员分析

[真实采集与模拟验收](real-source-collection.md)已接入 arXiv、Letta、LangChain，模拟分析结果继续保留。[ChatGPT 会员分析设计](chatgpt-analysis-handoff.md)说明官方授权边界；[本地会员分析与独立审阅](local-membership-analysis.md)说明本轮后端、登录、账户可用模型核实、预算和补跑。

上一阶段已用一篇已采集 arXiv 论文的完整摘要完成真实研究和独立审阅，使用 2 次请求，另存到 `reports/test/agent-memory/membership/member-arxiv-20261019/`。该单篇入口仍保留默认最多 4 次推理、一次修订；批次入口另读 YAML 限制。两者均不重写已有来源或人工笔记，GitHub 自动正式入库和定时执行仍未实现或启用。

## 人工研究流程

1. 在 `config/research_topics.yaml` 确认主题范围。
2. 按[维护规范](maintenance.md)全库检索来源，决定新增还是更新。
3. 从 [templates/paper.md](templates/paper.md) 或 [templates/blog.md](templates/blog.md) 创建一条资料，填写 [Schema](source-schema.md)。
4. 阅读原文并维护状态和笔记；需要时手动整理到 `reports/`、`insights/` 或 `articles/`。
5. 执行 `python3 workflows/validate.py`（在仓库根目录，需 PyYAML），检查差异，再提交并同步。

这里包含设计、约定、模板、只读校验工具及测试样例；`scripts/` 包含受限真实采集器、模拟骨架、本地官方会员后端及配置驱动的 Research、Insight 测试批次和 Writing 离线演练，产物只写测试目录。没有已启用的调度器、正式自动入库或公众号发布能力。
