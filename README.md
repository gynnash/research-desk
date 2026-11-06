# ResearchDesk

ResearchDesk 是一套可配置的三 Agent 研究工作台框架：采集公开资料、阅读原文、形成洞察和选题，再由用户确认是否写作。当前默认研究方向为 `agent_memory`；采集原文放在 [collection/agent_memory](collection/agent_memory/README.md)，逐篇详细总结放在 [summary/agent_memory](summary/agent_memory/README.md)。仓库不预置已收集论文或生成稿件，离线样例均为虚构资料。

| Agent | 职责 | 运行后产物 |
| --- | --- | --- |
| Research | 逐篇读取采集原文，详细解释问题、方法、实验和局限，经独立模型审阅 | `summary/<主题>/` 中的详细技术解读 |
| Insight | 比较本轮与实际存在的历史资料，推导洞察、研究方向和选题 | `insights/<主题>/` 综合文章、洞察与 `articles/<主题>/` 待确认选题卡 |
| Writing | 只处理用户确认过的选题，按配置文风写作 | 大纲、初稿、候选稿 |

生成与独立审阅使用不同的实际模型，并读取同一绑定材料。没有足够跨时间证据时，只提出研究线索；不把单篇论文或同期材料写成行业趋势。稿件不会自动发布公众号。

## 快速开始

在用来执行每周研究的 Mac 上克隆项目，进入仓库目录运行：

```sh
./setup
```

浏览器会打开本机配置向导。根据页面提示完成 **ChatGPT 和 GitHub 授权**，已有有效授权会自动复用。向导准备默认主题、内置来源和独立审阅模型，然后检查仓库、配置 Mac 执行器，并运行 GitHub 健康检查。用于部署的仓库需由当前账号管理，`main` 上需有本版本的工作流。标准的公开上游克隆可在向导创建自己的私有仓库。遇到仓库权限或组织策略限制时，页面会给出对应入口和重试按钮。使用公开仓库需要在页面确认。

健康检查通过后启用**每周二、周五北京时间 03:00** 的采集、逐篇总结、洞察和选题。配置过程只做健康检查，下一次定时触发才开始研究。Mac 需要在执行时开机联网。正式选题回存后，从向导打开确认页，亲自确认后可启动 Writing。

向导也会准备独立的 Obsidian 阅读副本。首次在 Obsidian 选择「打开文件夹作为仓库」，使用向导显示的目录。新版研究和写作工作流回存后会刷新该副本。其他 GitHub 更新可在向导手动拉取。Obsidian 多端同步从该阅读库单独设置，运行目录和个人 Vault 分开使用。

手动部署和已有配置迁移见[初始化说明](workflows/workbench-init.md)和[执行器说明](workflows/self-hosted-worker.md)。

系统默认维护内置来源、SDK 和较少调整的参数；用户配置只保留本人差异。来源按 `id` 合并，可添加 RSS，或用 `enabled: false` 禁用某个默认来源。具体例子与合并规则见[配置说明](workflows/workbench-init.md)。

运行命令、补跑和选题确认见[操作说明](workflows/README.md)。不需要数据库或复杂 Agent 框架。

先使用[独立采集入口](workflows/collection.md)把完整原文保存到 `collection/<主题>/`，不需要会员登录；再用 [Research 入口](workflows/research.md)对同一批次逐篇分析，审阅通过后把详细总结保存到 `summary/<主题>/`。此入口不自动执行 Insight 或 Writing。

[Codex 后端](workflows/codex-backend.md)在 Mac 使用官方 SDK 和用户自己的 ChatGPT 会员授权，复用固定原文与历史总结，只做内容准确性审阅；逐次推理请求与旧后端共用月度、整轮和阶段预算。新版 Actions 串联采集、逐篇 Research 和 Codex Insight，回存原文、总结及审阅证明；开启 `admission.enabled` 后，把真实且通过审阅的 Insight 另存为正式综合文章和待确认选题，保留测试区原结果。选题出现在现有确认页面，用户亲自确认后才能启动 Writing。稿件不会自动发布。可运行 `python3 -B scripts/researchdesk_harness.py offline-demo` 零调用验证流程；离线验收不代表已完成真实论文研究或已部署执行器。

## 框架目录

| 目录                   | 用途                                    |
| -------------------- | ------------------------------------- |
| `scripts/`           | 采集、全文提取、三 Agent 执行、独立审阅、预算、准入、页面与同步工具 |
| `config/`            | 系统默认、短用户模板、通用示例和虚构测试配置；本地覆盖及生成配置不提交 |
| `.github/workflows/` | 离线检查、可选定时执行和结果回存                      |
| `tests/`             | 无真实模型调用的离线回归                          |
| `workflows/`         | 操作说明、资料 Schema、Markdown 模板及虚构样例       |
| `collection/<主题>/`   | 采集到的论文和博客原文，按批次保存                     |
| `summary/<主题>/`      | Research 独立审阅通过的逐篇详细总结                |
| `insights/<主题>/`     | 正式综合文章、洞察、趋势线索与后续研究方向                 |
| `articles/<主题>/`     | 待确认选题，以及人工确认后生成的大纲、初稿和候选稿             |

四个资料目录都按研究方向分组。新版正式综合文章在 `insights/<主题>/<批次>/report.md`，待确认选题在 `articles/<主题>/<批次>-topic-N.md`。`insights/test/`、`articles/test/` 和 `reports/` 中保留原始运行结果、准确性审阅及准入证明；它们供恢复和核验使用。模拟结果始终留在测试区，不能正式入库。已有三 Agent 全轮次及旧准入保持兼容，旧资料不自动迁移。Obsidian 可打开向导准备的阅读副本。

当前框架支持 arXiv、Letta、LangChain、Hugging Face Blog、美团技术团队和阮一峰博客等公开来源适配器；来源和研究范围由 YAML 配置。[知乎官方 API](workflows/zhihu-api.md)提供独立额度查询与搜索候选验证入口，搜索摘要尚未接入全文研究。X、Reddit、Quora 未接入。关注度排序只反映实际扫描和可观测信号。

## 内容与保护规则

默认全文模式优先获取论文官方 HTML，缺失时提取官方 PDF；博客提取公开页面主文。拿不到完整可用正文、遇到访问限制或超出材料预算时跳过，不用摘要冒充全文。图片、视频和公式布局的抽取范围如实说明。

Research 与 Insight 输出可连续阅读的技术文章，具体解释机制、实验条件、观点异同、推理和局限；来源集中在篇末。证据编号、散列和审阅细节留在运行记录中。选题需要用户确认，Writing 才能启动。

已有人工修改不会被生成覆盖；恢复任务复用原轮次与已核实响应。真实请求计入[本地预算](workflows/membership-budget.md)，失败和结果未知的请求也保留计数。本地计数不是 ChatGPT 官方剩余额度或费用。

SDK 明确失败后的重试需要显式授权；补跑 `catchup` 使用受限的失败重试，保留旧 attempt、已完成阶段和预算。未知状态先查询，不盲目发送新请求。已通过审阅但正式准入中断时，只补准入，不重新生成。具体命令见[操作说明](workflows/README.md)。

## 检查与可选同步

```sh
.venv-membership/bin/python -B scripts/researchdesk_workbench.py check
.venv-membership/bin/python -B workflows/validate.py --include-test
PYTHONPATH=tests .venv-membership/bin/python -B -m unittest test_research_depth test_insight_depth test_fulltext_required test_usage_archive
```

GitHub 用于保存代码、公共配置模板和用户后续产生的资料版本。个人设置、用量归档及真实 SDK 请求账本只留在本机；新用户不会继承维护者的用量或测试回执。Markdown 可以在 GitHub 或 Obsidian 阅读。用 Obsidian Sync 多端阅读时，选择独立阅读库作为同步对象。

`.gitignore` 排除本地工作台配置、凭据、API Key、缓存和 Obsidian 本地配置。已有本机文件保留，旧 Git 历史不改写；`.gitignore` 不控制 Obsidian Sync 的同步范围。配置映射、迁移和可复现检查见[工作台初始化](workflows/workbench-init.md)。
