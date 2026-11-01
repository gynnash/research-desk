# ResearchDesk

ResearchDesk 是一套可配置的三 Agent 研究工作台框架：采集公开资料、阅读原文、形成洞察和选题，再由用户确认是否写作。当前默认研究方向为 `agent_memory`；采集原文放在 [collection/agent_memory](collection/agent_memory/README.md)，逐篇详细总结放在 [summary/agent_memory](summary/agent_memory/README.md)。仓库不预置已收集论文或生成稿件，离线样例均为虚构资料。

| Agent | 职责 | 运行后产物 |
| --- | --- | --- |
| Research | 逐篇读取采集原文，详细解释问题、方法、实验和局限，经独立模型审阅 | `summary/<主题>/` 中的详细技术解读 |
| Insight | 比较本轮与实际存在的历史资料，推导洞察、研究方向和选题 | 综合文章、洞察、待确认选题卡 |
| Writing | 只处理用户确认过的选题，按配置文风写作 | 大纲、初稿、候选稿 |

生成与独立审阅使用不同的实际模型，并读取同一绑定材料。没有足够跨时间证据时，只提出研究线索；不把单篇论文或同期材料写成行业趋势。稿件不会自动发布公众号。

## 快速开始

1. 将代码放入自己的 GitHub 仓库并克隆到本机。准备 Python 3.12、Git 和 GitHub CLI，安装初始化工具依赖：

   ```sh
   python3.12 -m venv .venv-membership
   .venv-membership/bin/python -m pip install -r workflows/requirements-membership.txt
   ```

2. 从[用户配置模板](config/workbench.example.yaml)初始化自己的工作台：

   ```sh
   .venv-membership/bin/python -B scripts/researchdesk_workbench.py init
   ```

   这会把短模板复制到被 Git 忽略的 `config/local/workbench.yaml`，与公共[系统默认](config/system.yaml)合并，生成旧入口需要的兼容配置。已有旧兼容配置用 `init --adopt-existing` 导入；已有上一版完整本地 YAML 用 `migrate` 备份并压缩为差异配置。两者都保留资料、去重状态和实际用量。

3. 完成本机 ChatGPT 和 GitHub 授权：

   ```sh
   .venv-membership/bin/python scripts/researchdesk_membership.py login
   .venv-membership/bin/python scripts/researchdesk_membership.py models
   gh auth login
   ```

   用户亲自在浏览器完成会员授权；模型以本人账户实际返回为准，生成与独立审阅选择不同模型。GitHub 账号需有自己仓库的 runner 管理权限。凭据留在仓库之外，不写入 YAML。

4. 编辑本地 `config/local/workbench.yaml`：设置 `workbench_id`、`topic`、`models`、来源和预算。需要每周二、周五北京时间 03:00 自动研究时，合并以下设置：

   ```yaml
   automation:
     enabled: true
   ```

   模板默认仍为 `false`；保留该值可以先注册执行器而不自动研究。其他设置继承[系统默认](config/system.yaml)，显式阶段设置优先于主题和模型快捷项。

5. 一条命令应用配置、校验授权、安装外部 SDK 环境并注册启动执行器：

   ```sh
   .venv-membership/bin/python scripts/researchdesk_workbench.py start
   ```

   当前新版 SDK 调度范围为 macOS。`start` 不进行推理，也不擅自修改研究开关；它会给自己的 GitHub 仓库设置非敏感变量 `RESEARCHDESK_DEPLOYED=true`。执行器绑定当前持久工作台，后续每轮自动重新加载两层配置，普通研究参数无需再次 `apply` 或重启。详细步骤见[初始化说明](workflows/workbench-init.md)和[执行器说明](workflows/self-hosted-worker.md)。

系统默认维护内置来源、SDK 和较少调整的参数；用户配置只保留本人差异。来源按 `id` 合并，可添加 RSS，或用 `enabled: false` 禁用某个默认来源。具体例子与合并规则见[配置说明](workflows/workbench-init.md)。

运行命令、补跑和选题确认见[操作说明](workflows/README.md)。不需要数据库或复杂 Agent 框架。

先使用[独立采集入口](workflows/collection.md)把完整原文保存到 `collection/<主题>/`，不需要会员登录；再用 [Research 入口](workflows/research.md)对同一批次逐篇分析，审阅通过后把详细总结保存到 `summary/<主题>/`。此入口不自动执行 Insight 或 Writing。

[Codex 后端](workflows/codex-backend.md)在 Mac 使用官方 SDK 和用户自己的 ChatGPT 会员授权，复用固定原文与历史总结，只做内容准确性审阅；逐次推理请求与旧后端共用预算。新版 Actions 串联采集、逐篇 Research 和 Codex Insight，回存原文、总结及测试区的洞察和选题；不自动启动 Writing、正式晋级或发布公众号。可运行 `python3 -B scripts/researchdesk_harness.py offline-demo` 零调用验证流程。本次部署衔接使用离线验收，未替用户执行真实 `start` 或新增会员调用；此前小额真实 SDK 验收读取的是本地测试材料，不代表论文研究验收。

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

新采集与逐篇研究使用上述两个资料入口。新版调度的综合洞察在 `insights/test/<主题>/<批次>/`，待确认选题在 `articles/test/<主题>/<批次>/`；`reports/test/<主题>/` 保留研究与审阅证明。已有三 Agent 全轮次及正式准入保持兼容，旧资料不自动迁移。Obsidian 打开同一工作台即可阅读 Markdown。

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
