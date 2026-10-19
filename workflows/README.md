# 研究工作流

## 总体架构与定时研究设计

- [Research、Insight、Writing 三 Agent 总体架构](three-agent-architecture.md)：定义自动研究、综合洞察、公众号选题，以及人工确认选题后才启动写作的完整流程；独立模型审阅是三者共用能力。
- [Agent Memory GitHub Actions MVP](agent-memory-github-actions-mvp.md)：每周二、周五北京时间 09:00 的计划入口已准备；按启用配置派发 Research → Insight，独立审阅与规则校验通过后受限正式准入，保留人工笔记保护及失败补跑。

真实采集、官方会员后端、Research → Insight 与 GitHub 到 Mac 的手动轮次已验收；正式准入已实现并通过 7 份 Markdown、0 新增模型调用的远端验收。每周两次调度已启用，最终开关以 [`automation.yaml`](../config/automation.yaml) 为准，定时成功需看实际回执。真实本地确认页现已实现；[会员 Writing](writing-agent-member.md)已接通真实页面确认、三阶段独立审阅及受限测试回存，不发布公众号。

## Research → Insight 研究轮次

[轮次入口与 GitHub 验收](research-cycle.md)按方向串联发现、查重、Research 独立审阅和 Insight 选题，先保存测试检查点，再按规则正式准入。GitHub 的 `ResearchDesk checks` 只执行离线检查；[自托管执行器](self-hosted-worker.md)使用当前 Mac 或用户配置的远程主机研究；Ubuntu 计划步骤处理固定时间槽，独立发布步骤只接纳允许的新文件。

## 正式准入

[准入规则与操作](formal-admission.md)说明 [`admission.yaml`](../config/admission.yaml)、准入计划、有效 `accepted` 清单、测试 UUID 到正式 UUID 的映射及人工笔记保护。准入不再调用模型，不修改旧测试回执；`admit` 只处理已有已审阅轮次，选题仍为待人工确认。定时开关与准入配置分开，正常研究入库不增加人工审批门槛。

## 真实选题确认与 Writing

[真实选题确认入口](topic-confirmation-mvp.md)已实现本地浏览器页面：查看正式选题及证据、调整标题/角度/受众/字数、核对固定预览后，由用户勾选并点击“保存写作确认”。页面也提供只读证据笔记、确认记录、撤回和待同步记录的重试。保存确认后可单独点击“开始 / 继续测试写作”，通过 GitHub 派发到用户配置的会员主机；确认本身不自动调用模型。状态及测试稿在“确认记录”中查看。

[Writing 正式准入](writing-formal-admission.md)把已确认且三阶段独立审阅通过的真实结果，新增到 `articles/<topic>/`；保留原 test、来源引用与人工笔记，固定计划和接受回执，不调用会员。页面分别展示 TEST 与已正式入库的三稿，正式入库仍不代表公众号发布。

确认服务使用 Vault 外的独立工作目录，只追加确认与撤回记录并普通提交推送。网络失败显示 `pending_sync` 或 `revocation_pending_sync`，保留本机记录；冲突时停止，既有资料不覆盖。短时预览仅保存在进程内存，服务重启后需要重新预览。用户日常在浏览器操作，准备与启动命令见[维护附录](topic-confirmation-mvp.md#维护附录)。

[Writing 虚构确认、三阶段审阅与验收](writing-agent-offline.md)使用固定虚构选题与证据，确认记录明确为 `origin: offline_fixture`。大纲、初稿和候选稿各自先通过确定性校验和独立模拟审阅，再进入下一阶段；模型不能自行批准确认。文章只写 `articles/test/<topic>/<batch-id>/`，账本只写 `reports/test/<topic>/writing-runs/<batch-id>/`，不覆盖旧稿。

每批最多 12 次模拟调用，每阶段最多 4 次及一次修订；缺失、失效或被撤回的确认，输入散列变化、审阅失败和预算不足均应停止。使用既有 PyYAML，无网络或真实会员调用，不增加本地会员累计预留。当前两张真实 Insight 选题卡保持待确认，未被此演练批准或启动写作。真实结果以离线回执为准，不将样例确认冒称用户授权。

2026-10-19 [虚构样例验收](../reports/test/agent-memory/writing-runs/writing-offline-20261019/acceptance.md)已通过，保存大纲、初稿和候选稿；初稿修订一次，总计 8 次模拟调用、8 个虚拟单位。大纲检查点、全部审阅后及首个文章创建后的中断均恢复成功；禁用新模拟调用后恢复与完整缓存重放仍为 8 次。真实会员调用为 0，验收当时累计预算保持 10/100；此为离线阶段的历史记录；当前真实写作入口另见[会员 Writing](writing-agent-member.md)，不会升级虚构确认。

## Insight 测试闭环

[Insight 配置、证据与验收](insight-agent-test.md)说明如何读取已通过真实独立审阅的 Research 输入及显式登记的历史资料，生成综合报告、1–2 条洞察和公众号候选选题，再交独立模型审阅。历史资料保留 `human_baseline` 标识，不冒充本轮重新核实的原文；洞察须追溯到至少两个不同的原始来源，相关材料不能当作独立验证。

正常两次会员请求，最多四次，包含一次修订与复审；与单篇分析、Research 批次共享月度请求预算，当前上限为 100，未知调用不自动重发。报告、洞察和选题分别只写各目录的 `test/<topic>/`，既有资料不可覆盖。选题由程序固定为 `proposed`、`approval_required: true`、`writing_started: false`；Insight 批次不批准选题或启动 Writing，正式准入后由独立的本地页面提供用户确认。

2026-10-19 [真实验收](../reports/test/agent-memory/insight-runs/insight-agent-memory-20261019/acceptance.md)已通过：综合报告、2 条洞察和 2 张待确认选题卡，生成 `gpt-6-luna`，独立审阅 `gpt-6.1-sol`。共 4 次请求、43,163 tokens，含失败响应、一次模型修订、一次严格语法规范化及额外独立格式确认；恢复和缓存补跑均没有追加推理。回执中的月度 `10/10` 为当时快照；按用户后续授权，上限现为 100，该阶段历史累计预留为 10，后续轮次继续累计。会员剩余额度保留未知。此处为该阶段的历史记录；当前准入、调度及真实确认入口见上文，会员 Writing 当前入口见[真实写作闭环](writing-agent-member.md)。

## 配置驱动的 Research 批次

[批次运行与验收](configurable-research-batch.md)说明如何通过 YAML 配置主题、来源、两个不同模型和预算，以及一篇论文加一篇博客的采集、研究、独立审阅和中断补跑。通用示例供开源用户自行配置并使用自己的官方授权 profile；当前配置只生成 `reports/test/<topic>/research-batches/<batch-id>/` 中的结果。

本轮最多 6 次请求、单项最多 4 次、至多一次修订；共享月度上限现为 100，保留此前会员测试的所有累计预留。未知请求不自动重发；已通过的单项在同批补跑中复用，已有笔记与测试产物不覆盖。真实状态以批次回执为准，配置中启用方向不等于启用定时任务。

## 共享会员请求预算

统一入口为 [`config/membership_budget.yaml`](../config/membership_budget.yaml)，当前 `month_max_calls: 100`。之前的每月 10 次是本项目用于小额度验收的本地策略，并非来自 ChatGPT 官方会员额度。提高本地月度上限只改变后续请求的准入，不清零已有预留，不返还未知请求，也不扩大单篇、单项或批次限制。旧配置、清单与回执保留当时的 10 次策略及结果；累计预留以账本复核命令为准，会员实际剩余额度未知。其他用户可为自己的工作台配置该文件，凭据仍在仓库外。

[预算配置与只读复核](membership-budget.md)说明集中配置优先级、缺失时的旧策略回退，以及无会员调用的累计账本检查。模拟预算保持原样。

## 离线运行骨架

[离线运行与验收](offline-research.md)说明固定样例、两个独立模拟模型、测试目录、预算记录及中断补跑。

## 真实来源采集与本地会员分析

[真实采集与模拟验收](real-source-collection.md)已接入 arXiv、Letta、LangChain，模拟分析结果继续保留。[ChatGPT 会员分析设计](chatgpt-analysis-handoff.md)说明官方授权边界；[本地会员分析与独立审阅](local-membership-analysis.md)说明本轮后端、登录、账户可用模型核实、预算和补跑。

上一阶段已用一篇已采集 arXiv 论文的完整摘要完成真实研究和独立审阅，使用 2 次请求，另存到 `reports/test/agent-memory/membership/member-arxiv-20261019/`。该单篇入口仍保留默认最多 4 次推理、一次修订；批次入口另读 YAML 限制。两者均不重写已有来源或人工笔记；当时尚未提供正式准入和调度，当前实现见上文。

## 人工研究流程

1. 在 `config/research_topics.yaml` 确认主题范围。
2. 按[维护规范](maintenance.md)全库检索来源，决定新增还是更新。
3. 从 [templates/paper.md](templates/paper.md) 或 [templates/blog.md](templates/blog.md) 创建一条资料，填写 [Schema](source-schema.md)。
4. 阅读原文并维护状态和笔记；需要时手动整理到 `reports/`、`insights/` 或 `articles/`。
5. 执行 `python3 workflows/validate.py`（在仓库根目录，需 PyYAML），检查差异，再提交并同步。

这里包含设计、约定、模板、只读校验工具及测试样例；`scripts/` 包含受限真实采集器、模拟骨架、本地官方会员后端及配置驱动的 Research、Insight 测试批次和 Writing 离线演练，产物只写测试目录。正式准入与时间槽调度已有实现，启用状态及远端成功以配置和实际回执为准；没有公众号发布能力。

## 正式入库与定时启用验收

[2026-10-19 实际回执](formal-admission-acceptance-2026-10-19.md)：GitHub 创建首批 7 份正式资料并同步 Obsidian，0 次新增模型调用；每周二、周五北京时间 09:00 的开关随后启用，首个计划为 2026-10-20。选题仍待人工确认，Writing 和公众号发布未启动。
