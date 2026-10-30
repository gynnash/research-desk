# ResearchDesk

一个用 Markdown、YAML、GitHub 和 Obsidian 积累技术研究的工作台。采集论文与博客，完成单篇分析、跨资料比较和历史综合，提炼洞察与公众号选题；用户确认后，再交给 Writing 生成文章。用户使用自己的官方 ChatGPT 会员授权，凭据留在仓库与 Vault 外。

日常阅读从 **[研究首页](研究首页.md)** 或 **[正式资料索引](workbench/资料索引.md)** 开始。索引显示已核验的最新正式成果；[我的研究问题](notes/我的研究问题.md)用于保存自己的批注和判断。

## 工作流程

1. **Research**：按方向发现候选资料，排除已经研究过的来源，读取正文并分析问题、方法、证据和局限；由另一个模型审阅。
2. **Insight**：比较新资料与已保存的历史，形成综合报告、洞察、待验证问题和公众号选题；独立审阅后新增入库。
3. **Writing**：用户在[当前 Mac 的选题页](http://127.0.0.1:8765)确认选题、角度、受众及证据范围后，生成大纲、初稿和候选稿，逐阶段审阅。正式稿件入库不代表公众号发布。

每周二、周五北京时间 **03:00** 由 GitHub Actions 调度当前自托管执行器；配置见 [automation.yaml](config/automation.yaml)。当前 Mac 需要开机、联网，runner 用户会话可用。实际状态查看 [GitHub Actions](https://github.com/gynnash/research-desk/actions/workflows/researchdesk-manual.yml) 与各轮回执。个人 Codex **09:00** 简报是单独配置的只读汇报，不随仓库自动安装。

## 资料保存在哪里

| 目录 | 内容 |
| --- | --- |
| `sources/papers/<方向>/`、`sources/blogs/<方向>/` | 来源卡：原文链接、作者、日期、唯一身份与相关研究；不是原文全文副本 |
| `sources/originals/<方向>/` | 正式原文抽取快照；保留章节、来源、日期和散列，链接实际研究范围 |
| `reports/<方向>/` | 单篇详细研究、更新报告、跨资料综合报告 |
| `insights/<方向>/` | 可复用观点、趋势判断、反例和待验证问题 |
| `articles/<方向>/` | 选题卡、大纲、初稿、候选稿 |
| `notes/` | 人工研究问题、批注和编辑内容 |
| `workbench/` | 一份正式资料索引，以及可选 Obsidian Bases 视图 |
| `config/` | 方向、来源、模型、预算、调度及写作确认配置 |
| `workflows/`、`scripts/`、`tests/` | 操作说明、执行代码和离线检查 |

各资料目录中的 `test` 保存运行检查点和历史演练；`reports/<方向>/admissions/` 保存正式接受证明。日常阅读通过索引进入，不需要逐个翻阅回执。已有目录、历史文件和 Obsidian 配置不因阅读导航调整而移动或删除。

## 当前能力与边界

- 已接入 arXiv、Letta、LangChain、Hugging Face Blog、美团技术团队和阮一峰博客；每轮重新发现近 **60 天发表**的候选，排除已挑选的 URL/arXiv 身份，再按可核实的社区关注度最多选 **5 份**。官方 sitemap 与 RSS/Atom 补充列表发现，扫描上限、Feed不完整和失败仍如实记录。[来源覆盖说明](workflows/source-coverage-and-archive.md)
- 关注度来自 HF 推荐及 Hacker News 讨论，保留指标、观测时间和原始链接。没有信号不凑数；这是已扫描候选中的社区关注度排序，不是全网热榜或质量排名。知乎、X、Reddit、Quora 尚未接入，不能靠增加网址配置就声称支持。
- 论文优先获取同版本的官方 HTML，其次提取 PDF；确实失败时才降级为摘要。按章节、页码保留证据位置；超出输入预算则标记节选。[全文阅读说明](workflows/fulltext-reading.md)
- 新轮次在模型调用前保存完整可用抽取正文与精确阅读检查点，审阅及补跑从快照重放；通过准入后新增可读原文到 `sources/originals/<方向>/`，来源卡、报告和索引互相链接。归档不包含PDF附件、图像或原版式，不能把摘要降级冒充全文。历史摘要报告保留，后续深读另存更新报告。
- 历史综合从过去 **180 天**资料按真实研究日期和月份分布选择，最多 30 份文件（含来源依赖）；报告公开实际覆盖范围。当前资料仅积累十余天，不能据此声称半年行业趋势。发现窗口、数量和预算以 [方向配置](config/cycles/agent-memory.yaml) 为准；旧轮次仍使用冻结配置。
- 原文事实、作者主张与我们的推断分别标注。独立审阅检查是否忠于输入材料，不等于复现实验。正式成果仅新增，人工笔记保留；选题确认与发布授权分别处理。
- 当前 Mac 的真实研究、入库与 Git 同步已有验收；远程主机按[执行器说明](workflows/self-hosted-worker.md)配置。此仓库仍含个人资料与历史演练，尚不是下载即用的干净开源模板。

## 配置与运行

研究方向在 [research_topics.yaml](config/research_topics.yaml) 中定义；采集、阅读、模型和阶段预算在 [cycles/agent-memory.yaml](config/cycles/agent-memory.yaml) 中配置。共享月度请求上限见 [membership_budget.yaml](config/membership_budget.yaml)，它是工作台的本地限制，不表示会员官方剩余额度。模型与账户资格以用户自己的官方授权为准。

在仓库根目录，用隔离环境安装依赖并校验：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r workflows/requirements-membership.txt
.venv/bin/python -B workflows/validate.py --include-test
.venv/bin/python -B scripts/researchdesk_catalog.py --check
```

正式资料索引只读取已有结果，不联网或调用模型。正常 Research 准入后由发布步骤更新；手动维护时默认打印预览，`--check` 只读检查，`--write` 更新固定索引的自动区。区外人工文字保留，区内人工改写会停止覆盖且不阻塞正式研究回存：

```sh
.venv/bin/python -B scripts/researchdesk_catalog.py
.venv/bin/python -B scripts/researchdesk_catalog.py --write
```

真实研究与维护命令见[研究轮次](workflows/research-cycle.md)、[会员授权](workflows/local-membership-analysis.md)、[失败补跑](workflows/linked-insight-recovery.md)及[工作流目录](workflows/README.md)。不要用旧批次 ID 重置已绑定的输入或策略。

## GitHub 与 Obsidian

GitHub 保存资料、代码和版本历史；Actions 负责调度与结果回存，自托管主机负责采集与模型执行。Mac 用现有 Git 流程接收新文件，Obsidian 直接打开仓库根目录作为 Vault，读取同一套 Markdown。

手机可通过另行配置的 Obsidian Sync 接收 Mac 上的文件；Sync 不代替 Git 拉取。Obsidian 是可选阅读与批注工具，没有它也能用 GitHub 和 Markdown。`127.0.0.1:8765` 仅供运行选题服务的设备使用，手机同一地址不会连接 Mac。[阅读与同步说明](workbench/README.md)

现有 `.obsidian` 本地配置、凭据和缓存通过 [.gitignore](.gitignore) 排除；不要提交 API Key、会员 profile 或登录材料。资料字段见 [Schema](workflows/source-schema.md)，去重、更新与笔记保护见[维护规范](workflows/maintenance.md)。

## 设计与历史验收

[本次目标对齐审查](workflows/workflow-alignment-2026-10-30.md)列出已修正、尚未满足和本次精简的部分；没有新增 Agent、数据库或另一套阅读页面。

[三 Agent 架构](workflows/three-agent-architecture.md) · [定时 MVP](workflows/agent-memory-github-actions-mvp.md) · [首次正式准入](workflows/formal-admission-acceptance-2026-10-19.md) · [Insight 验收](workflows/insight-agent-test.md) · [Writing 验收与准入](workflows/writing-formal-admission.md)。历史文档中的调用数、时间和范围是当时快照，当前行为以配置、代码和实际回执为准。
