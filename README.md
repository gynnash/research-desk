# ResearchDesk

ResearchDesk 是一套可配置的三 Agent 研究工作台框架：采集公开资料、阅读原文、形成洞察和选题，再由用户确认是否写作。仓库只保留代码、工具、配置模板和虚构离线测试样例，不附带已收集论文、博客或生成稿件。

| Agent | 职责 | 运行后产物 |
| --- | --- | --- |
| Research | 采集、去重，详细解释原文问题、方法、实验和局限 | 原文快照、单篇研究 |
| Insight | 比较本轮与实际存在的历史资料，推导洞察、研究方向和选题 | 综合文章、洞察、待确认选题卡 |
| Writing | 只处理用户确认过的选题，按配置文风写作 | 大纲、初稿、候选稿 |

生成与独立审阅使用不同的实际模型，并读取同一绑定材料。没有足够跨时间证据时，只提出研究线索；不把单篇论文或同期材料写成行业趋势。稿件不会自动发布公众号。

## 快速开始

1. 准备 Python 3.9+、Git 和 GitHub CLI，安装依赖：

   ```sh
   python3 -m venv .venv-membership
   .venv-membership/bin/python -m pip install -r workflows/requirements-membership.txt
   ```

2. 编辑 [研究方向](config/research_topics.yaml)，将停用的 `example-topic` 替换为自己的主题、问题范围和关键词，再启用该主题。编辑 [运行配置](config/cycles/default.yaml)，设置来源、采集窗口、模型和预算。示例主题不是已配置好的真实研究方向。
3. 按[会员授权说明](workflows/local-membership-analysis.md)完成自己的官方登录，查看账户实际可用模型，选择不同的生成与审阅模型。凭据始终留在仓库之外。
4. 配置 [运行环境](config/runtime.yaml)，按[执行器说明](workflows/self-hosted-worker.md)准备自己的本地或远程主机，先检查环境与小批运行。
5. 验证满意后，如需正式入库，在 [admission.yaml](config/admission.yaml) 启用准入并登记自己的主题；如需定时运行，再在 [automation.yaml](config/automation.yaml) 启用定时任务。**默认关闭自动研究**；保留的 workflow 不会因下载或 fork 仓库而自动开始研究。

运行命令、补跑和选题确认见[操作说明](workflows/README.md)。不需要数据库或复杂 Agent 框架。

## 框架目录

| 目录 | 用途 |
| --- | --- |
| `scripts/` | 采集、全文提取、三 Agent 执行、独立审阅、预算、准入、页面与同步工具 |
| `config/` | 用户配置、通用示例和虚构测试配置 |
| `.github/workflows/` | 离线检查、可选定时执行和结果回存 |
| `tests/` | 无真实模型调用的离线回归 |
| `workflows/` | 操作说明、资料 Schema、Markdown 模板及虚构样例 |

首次实际运行时，工具按需要创建四类资料目录：`sources/` 保存原文，`reports/` 保存单篇研究及运行记录，`insights/` 保存综合洞察，`articles/` 保存选题和稿件。资料再按用户配置的研究方向分组。正式准入后可生成 `研究首页.md`，集中浏览文章正文。

当前框架支持 arXiv、Letta、LangChain、Hugging Face Blog、美团技术团队和阮一峰博客等公开来源适配器；来源和研究范围由 YAML 配置。知乎、X、Reddit、Quora 未接入。关注度排序只反映实际扫描和可观测信号。

## 内容与保护规则

默认全文模式优先获取论文官方 HTML，缺失时提取官方 PDF；博客提取公开页面主文。拿不到完整可用正文、遇到访问限制或超出材料预算时跳过，不用摘要冒充全文。图片、视频和公式布局的抽取范围如实说明。

Research 与 Insight 输出可连续阅读的技术文章，具体解释机制、实验条件、观点异同、推理和局限；来源集中在篇末。证据编号、散列和审阅细节留在运行记录中。选题需要用户确认，Writing 才能启动。

已有人工修改不会被生成覆盖；恢复任务复用原轮次与已核实响应。真实请求计入[本地预算](workflows/membership-budget.md)，失败和结果未知的请求也保留计数。本地计数不是 ChatGPT 官方剩余额度或费用。

## 检查与可选同步

```sh
.venv-membership/bin/python -B workflows/validate.py --include-test
PYTHONPATH=tests .venv-membership/bin/python -B -m unittest test_research_depth test_insight_depth test_fulltext_required test_usage_archive
```

GitHub 用于保存代码、配置和用户后续产生的资料版本。Obsidian 是可选阅读工具：把自己的资料仓库作为 Vault，即可阅读同一套 Markdown；手机同步可自行配置 Obsidian Sync。没有 Obsidian 也能直接在 GitHub 阅读。

`.gitignore` 排除凭据、API Key、缓存和 Obsidian 本地配置。部署时使用自己的仓库、授权和运行主机，不复制维护者的登录状态。
