# ResearchDesk

ResearchDesk 是一套可配置的三 Agent 研究工作台框架：采集公开资料、阅读原文、形成洞察和选题，再由用户确认是否写作。当前默认研究方向为 `agent_memory`；采集原文放在 [collection/agent_memory](collection/agent_memory/README.md)，逐篇详细总结放在 [summary/agent_memory](summary/agent_memory/README.md)。仓库不预置已收集论文或生成稿件，离线样例均为虚构资料。

| Agent | 职责 | 运行后产物 |
| --- | --- | --- |
| Research | 逐篇读取采集原文，详细解释问题、方法、实验和局限，经独立模型审阅 | `summary/<主题>/` 中的详细技术解读 |
| Insight | 比较本轮与实际存在的历史资料，推导洞察、研究方向和选题 | 综合文章、洞察、待确认选题卡 |
| Writing | 只处理用户确认过的选题，按配置文风写作 | 大纲、初稿、候选稿 |

生成与独立审阅使用不同的实际模型，并读取同一绑定材料。没有足够跨时间证据时，只提出研究线索；不把单篇论文或同期材料写成行业趋势。稿件不会自动发布公众号。

## 快速开始

1. 准备 Python（推荐 3.12）、Git 和 GitHub CLI，安装依赖：

   ```sh
   python3 -m venv .venv-membership
   .venv-membership/bin/python -m pip install -r workflows/requirements-membership.txt
   ```

2. 从[用户配置模板](config/workbench.example.yaml)初始化自己的工作台：

   ```sh
   .venv-membership/bin/python -B scripts/researchdesk_workbench.py init
   ```

   这会把短模板复制到被 Git 忽略的 `config/local/workbench.yaml`，与公共[系统默认](config/system.yaml)合并，生成旧入口需要的兼容配置。已有旧兼容配置用 `init --adopt-existing` 导入；已有上一版完整本地 YAML 用 `migrate` 备份并压缩为差异配置。两者都保留资料、去重状态和实际用量。

3. 只编辑本地 `config/local/workbench.yaml`，写需要覆盖的设置即可。常用的 `topic`、`models.generation`、`models.review`、`models.writing` 会联动相应阶段，默认主题为 `agent_memory`。需要调整来源或某一阶段时，按 `config/system.yaml` 的相同路径写局部覆盖；显式阶段设置优先于快捷项。修改后应用并检查：

   ```sh
   .venv-membership/bin/python -B scripts/researchdesk_workbench.py apply
   .venv-membership/bin/python -B scripts/researchdesk_workbench.py check
   ```

4. 按[会员授权说明](workflows/local-membership-analysis.md)完成自己的官方登录，核实账户可用模型，再选择不同的生成与审阅模型。模板里的模型名只是示例；凭据继续留在仓库之外，不写入配置 YAML。
5. 按[初始化说明](workflows/workbench-init.md)和[执行器说明](workflows/self-hosted-worker.md)准备自己的运行主机。**模板默认关闭自动研究和正式研究准入**；初始化不登录、不调用模型、不安装 runner、不启用定时任务，也不修改 Git。GitHub 上保留模板和框架，个人配置由各自机器本地管理。

系统默认维护内置来源、SDK 和较少调整的参数；用户配置只保留本人差异。来源按 `id` 合并，可添加 RSS，或用 `enabled: false` 禁用某个默认来源。具体例子与合并规则见[配置说明](workflows/workbench-init.md)。

运行命令、补跑和选题确认见[操作说明](workflows/README.md)。不需要数据库或复杂 Agent 框架。

先使用[独立采集入口](workflows/collection.md)把完整原文保存到 `collection/<主题>/`，不需要会员登录；再用 [Research 入口](workflows/research.md)对同一批次逐篇分析，审阅通过后把详细总结保存到 `summary/<主题>/`。此入口不自动执行 Insight 或 Writing。

[Codex 后端](workflows/codex-backend.md)已在 Mac 接通官方 SDK 和本人 ChatGPT 会员授权，复用固定原文与历史总结，只做内容准确性审阅；逐次推理请求与旧后端共用预算。可以运行 `python3 -B scripts/researchdesk_harness.py offline-demo` 零调用验证流程，或按[运行说明](workflows/README.md)安装独立 SDK 环境后显式运行。已通过的小额真实验收只读取本地测试材料，不代表完成论文研究；默认旧入口与自动开关保持不变。

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

新采集与逐篇研究使用上述两个资料入口。已有三 Agent 全轮次及正式准入保留兼容：`reports/` 保存内部运行记录与原有正式报告，`insights/` 保存洞察，`articles/` 保存选题和稿件；本次不自动运行这些后续阶段或迁移旧资料。Obsidian 打开同一仓库即可看到新目录。

当前框架支持 arXiv、Letta、LangChain、Hugging Face Blog、美团技术团队和阮一峰博客等公开来源适配器；来源和研究范围由 YAML 配置。[知乎官方 API](workflows/zhihu-api.md)提供独立额度查询与搜索候选验证入口，搜索摘要尚未接入全文研究。X、Reddit、Quora 未接入。关注度排序只反映实际扫描和可观测信号。

## 内容与保护规则

默认全文模式优先获取论文官方 HTML，缺失时提取官方 PDF；博客提取公开页面主文。拿不到完整可用正文、遇到访问限制或超出材料预算时跳过，不用摘要冒充全文。图片、视频和公式布局的抽取范围如实说明。

Research 与 Insight 输出可连续阅读的技术文章，具体解释机制、实验条件、观点异同、推理和局限；来源集中在篇末。证据编号、散列和审阅细节留在运行记录中。选题需要用户确认，Writing 才能启动。

已有人工修改不会被生成覆盖；恢复任务复用原轮次与已核实响应。真实请求计入[本地预算](workflows/membership-budget.md)，失败和结果未知的请求也保留计数。本地计数不是 ChatGPT 官方剩余额度或费用。

## 检查与可选同步

```sh
.venv-membership/bin/python -B scripts/researchdesk_workbench.py check
.venv-membership/bin/python -B workflows/validate.py --include-test
PYTHONPATH=tests .venv-membership/bin/python -B -m unittest test_research_depth test_insight_depth test_fulltext_required test_usage_archive
```

GitHub 用于保存代码、公共配置模板和用户后续产生的资料版本。个人设置、用量归档及真实 SDK 请求账本只留在本机；新用户不会继承维护者的用量或测试回执。Obsidian 是可选阅读工具：把自己的资料仓库作为 Vault，即可阅读同一套 Markdown；手机同步可自行配置 Obsidian Sync。没有 Obsidian 也能直接在 GitHub 阅读。

`.gitignore` 排除本地工作台配置、凭据、API Key、缓存和 Obsidian 本地配置。已有本机文件保留，旧 Git 历史不改写；`.gitignore` 不控制 Obsidian Sync 的同步范围。配置映射、迁移和可复现检查见[工作台初始化](workflows/workbench-init.md)。
