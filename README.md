# ResearchDesk

采集论文和博客，让大模型根据原文完成总结，再结合历史资料形成深度思考、趋势线索和公众号选题。选题由用户确认后交给 Writing 写作。资料以 Markdown 保存到 GitHub，沿现有同步链路在 Obsidian 中阅读。

**从[研究首页](研究首页.md)开始阅读。** 同一个页面列出最新研究、历史批次、全部论文与博客、洞察与趋势线索、公众号选题和已生成文章。链接直接打开具体正文，不需要按 UUID 文件名寻找资料。

## 四类资料

| 目录 | 你会看到什么 |
| --- | --- |
| [sources](sources/) | 原始论文与博客。新采集的原文保存到 `originals/<方向>/`，`papers/`、`blogs/` 保留来源身份和关联信息 |
| [reports](reports/) | 每篇论文、博客的方法、思路、结果与局限；旧格式的清爽正文在 `<方向>/解读/<轮次>/` |
| [insights](insights/) | 本轮与历史资料的比较、洞察、趋势线索和待验证问题；旧批次合并为 `<方向>/综述/` 内的一篇文章 |
| [articles](articles/) | `<方向>/选题/` 展示写作角度与证据缺口；`<方向>/稿件/` 展示已生成大纲、初稿和候选稿 |

资料按研究方向分组，`agent-memory` 是当前方向。新轮次的可读研究、综合和稿件直接链接正式正文；历史旧格式只整理一次，另存为可读笔记，保留原有研究结论和阅读范围。旧正式文件、检查点与回执继续用于核验，不移位、不覆盖。

首页显示每批实际研究的论文/博客标题和数量，区分新研究与旧文更新，也列出库内可打开的原文。仅有摘要、正文节选、完整抽取正文和“已采集、待研究”分别标注；归档一份全文不代表旧摘要研究已完成全文分析。

## 内容怎么生成

Research 接收采集到的原始正文，按提示词解释问题、机制、结论和局限。Insight 接收本轮原文、研究结果和明确选择的历史资料，比较异同，形成有依据的理解和选题。另一模型使用同一材料审阅。

正文应当能直接读懂：连续段落、清楚的技术解释，不显示 R/H/A 编号、逐段脚注、审阅清单或散列。篇末统一列出原文链接和实际阅读范围；作者的结论与我们的推断用自然语言区分。抽取失败、只读摘要、正文截断和重要不确定性不能隐去。

当前配置使用 `presentation: technical_article`。原始材料、证据定位和审阅仍保存在内部执行记录中；改善文字表达不增加模型步骤或调用预算。历史笔记只重排已审阅内容，不补造新的研究结果；派生阅读笔记不重复进入历史证据池。

## 自动运行与写作

每周二、周五北京时间 **03:00**，GitHub Actions 调度配置的自托管执行器。当前运行在 Mac，执行器需要开机、联网且会话可用。个人 Codex **09:00** 简报是另行设置的只读汇报，不随仓库自动安装。

每轮从近 **60 天**的候选中，按可核实的社区关注度最多选 **5 份**，按 URL/arXiv 身份排除历史已挑选资料。已接入 arXiv、Letta、LangChain、Hugging Face Blog、美团技术团队和阮一峰博客；知乎、X、Reddit、Quora 尚未接入。关注度只覆盖实际扫描和可观测信号，不代表全网热榜。

论文优先官方 HTML，缺失时提取 PDF，确实失败才降级为摘要。历史按最多 **180 天**窗口选择，并如实说明实际积累范围；没有足够跨来源、跨时间证据时只提出研究线索，不声称行业趋势。

在[当前 Mac 的选题页](http://127.0.0.1:8765)确认标题、角度、受众和证据后，Writing 才会运行。它生成大纲、初稿和候选稿，独立审阅通过后入库，不自动发布公众号。手机上的 `127.0.0.1` 指向手机自身。

## 除四类资料外，系统还需要什么

四类资料已经足够。自动运行还需要 `.github/`（调度）、`scripts/`（程序）、`config/`（来源、方向、模型与预算），以及必要的依赖、校验和离线测试。这些是运行文件，不是新的资料分类。删除它们会同时取消自动研究能力。

历史离线演练和重复验收文档已清理；仍用于去重、实际用量统计、补跑和选题验证的真实运行记录、接受证明及写作确认继续保留。日常只需研究首页，不增加工作台、数据库或插件。首页在正式准入后自动刷新；正文只新增，已有人工修改发生冲突时保留并停止覆盖。首页生成区以外的个人批注也会保留。[人工研究笔记](insights/agent-memory/我的研究问题.md)与 Obsidian 原有配置保持不变。

## 配置与检查

[研究方向](config/research_topics.yaml) · [采集、模型与阶段预算](config/cycles/agent-memory.yaml) · [月度请求上限](config/membership_budget.yaml) · [运行环境](config/runtime.yaml) · [调度](config/automation.yaml)

用户使用自己的官方 ChatGPT 会员授权，凭据留在仓库和 Vault 外；本地预算不是会员官方剩余额度。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r workflows/requirements-membership.txt
.venv/bin/python -B workflows/validate.py --include-test
.venv/bin/python -B scripts/researchdesk_reading.py --check
PYTHONPATH=tests .venv/bin/python -B -m unittest test_article_presentation
```

需要手动刷新首页时运行 `python3 -B scripts/researchdesk_reading.py`，只整理现有已准入结果，不采集新内容或调用模型。

## GitHub 与 Obsidian

GitHub 保存资料、代码与版本；Actions 调度执行和回存结果。Mac 通过既有 Git 流程接收文件，Obsidian 阅读同一套 Markdown。另行配置的 Obsidian Sync 可将 Mac 的资料同步到 iPhone，不能代替 Git 拉取。没有 Obsidian 也可以直接在 GitHub 阅读。

在 Obsidian 中打开根目录的 `研究首页.md`，使用阅读视图浏览。如果 Vault 本身就是仓库目录，本地修改会直接出现，不需要再复制一套笔记。

模型凭据、API Key、缓存与 Obsidian 本地配置继续由 `.gitignore` 排除。现有 Git 历史保留，未发布任何公众号内容。
