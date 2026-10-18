# ResearchDesk

ResearchDesk 是一个以 Markdown、YAML、GitHub 和 Obsidian 为基础的 AI 技术研究工作台：保存论文与技术博客、研究证据和历史判断，发现技术变化，并为微信公众号提供可追溯的选题与文章。框架面向开源，用户可配置自己的研究方向、来源、模型和预算，并使用自己授权的 ChatGPT 会员。

当前已完成知识库基础设施、离线运行骨架，以及 arXiv、Letta、LangChain 的真实资料采集测试。2026-10-19 已通过本地官方 ChatGPT 会员授权、账户模型目录核实，以及单篇 arXiv 摘要研究与独立模型审阅，详见[真实验收](reports/test/agent-memory/membership/member-arxiv-20261019/acceptance.md)。模拟分析继续保留，所有新研究结果只写各方向的隔离测试目录。正式资料保持原样；没有定时任务、自动 PR 入库或公众号发布，不使用数据库和复杂 Agent 框架；已有 Vault 备份设置保持原样。

目标流程由三个业务 Agent 完成：每周二、周五北京时间 09:00 自动 **Research 采集、研究与归纳 → Insight 综合历史、提炼洞察和公众号候选选题 → 用户确认选题、角度与受众 → Writing 生成大纲、初稿及候选稿**。各阶段共用独立模型审阅和确定性校验，日常研究、洞察和选题无需人工逐篇审批；写作必须绑定用户明确确认的选题版本，发布由用户另行决定。总体边界见[三 Agent 架构](workflows/three-agent-architecture.md)与[定时研究 MVP](workflows/agent-memory-github-actions-mvp.md)。Insight、选题确认和 Writing 自动执行仍待实现，定时仅保留设计。

可以结合 Codex 维护仓库、配置和校验，使用 ChatGPT Work 辅助论文阅读、研究讨论与文章草稿。两者共用 Markdown/YAML 约定；直接访问本地仓库的能力取决于使用环境和授权。研究成果需明确保存到本仓库并审阅提交，设备间同步沿用下述 Git 流程。[Codex 官方说明](https://developers.openai.com/codex/cli/)与 [ChatGPT Work 官方说明](https://learn.chatgpt.com/docs/get-started-with-work)可供参考。

## 目录结构

```text
research-desk/
├── config/
│   ├── research_topics.yaml    # 研究方向及启用状态
│   ├── legacy_sources.yaml     # 初始化前旧资料的明确兼容清单
│   ├── examples/research_batch.yaml # 开源用户的通用批次配置示例
│   └── test/agent-memory/research_batch.yaml # 两份资料的受限测试配置
├── sources/
│   ├── papers/                # 论文，一篇论文一个 Markdown 文件
│   └── blogs/                 # 技术博客，一篇原文一个 Markdown 文件
├── reports/                   # 跨资料的专题研究、阶段综述
├── insights/                  # 可复用的观点、趋势假设与证据
├── articles/                  # 微信公众号选题、大纲与文章草稿
├── workflows/
│   ├── source-schema.md       # 资料字段与状态定义
│   ├── maintenance.md         # 去重、更新和人工笔记保护规范
│   ├── templates/             # 论文、博客模板；不是真实资料
│   ├── requirements.txt       # 离线运行及校验的 PyYAML 依赖
│   ├── requirements-membership.txt # 本地会员后端的签名验证依赖
│   └── validate.py            # 只读检查，不收集或修改研究资料
├── scripts/
│   ├── researchdesk_offline.py # 固定样例与模拟模型的离线运行骨架
│   ├── researchdesk_sources.py # 官方公开来源的受限抓取与解析
│   ├── researchdesk_collect.py # 真实采集与模拟分析，只写 test
│   ├── researchdesk_membership.py # 本应用官方 OAuth 与会员推理
│   ├── researchdesk_analyze.py # 单篇摘要研究与独立审阅，只写 test
│   ├── researchdesk_batch_inputs.py # YAML 配置及批次采集输入
│   └── researchdesk_batch.py   # 配置驱动研究批次与补跑，只写 test
└── tests/                     # 临时仓库中的自动验收
```

各核心目录均新增 `test/<topic>/`，论文和博客对应 `sources/papers/test/<topic>/`、`sources/blogs/test/<topic>/`；目前分别保留 `agent-memory` 和停用的 `agent-rl` 子目录。测试记录标记 TEST，不作为正式研究依据。结构、演练和验收命令见[离线运行说明](workflows/offline-research.md)。

[真实采集说明](workflows/real-source-collection.md)包含入口、查重与更新识别、短证据和测试回执。[会员分析设计](workflows/chatgpt-analysis-handoff.md)说明官方授权与资料交接边界；[本地会员分析说明](workflows/local-membership-analysis.md)提供登录、账户模型核实、单篇摘要测试、有限修订及补跑流程。单篇入口默认最多 4 次请求、月度最多预留 10 次；研究与审阅必须使用账户可用目录中的两个不同实际模型。完整摘要仅作内存输入，研究报告与脱敏回执另存于 `reports/test/agent-memory/membership/<batch-id>/`，不覆盖已有测试来源。

[配置驱动 Research 批次](workflows/configurable-research-batch.md)说明当前的一篇论文加一篇博客测试、通用 YAML 示例及失败补跑。批次读取主题、来源、模型和预算配置，最多 6 次会员请求、单项最多 4 次、至多一次修订；月度 10 次上限与此前单篇会员测试共享，不因换批次重置。新结果只写 `reports/test/<topic>/research-batches/<batch-id>/`，不覆盖既有来源。配置和源码改动可提交，个人授权 profile 必须位于仓库与 Vault 外。

各用户须自行通过官方会员授权并核实账户可用模型；当前用户本地验证不代表其他账户或 GitHub 临时 runner 已有资格。GitHub 定时与任务记录、符合资格的本地或自托管会员分析执行器及 Git 发布步骤在架构上分开，长期主机及自动入库仍待验收。[OpenAI 官方适用范围](https://developers.openai.com/siwc/token-sharing-open-source)、[自托管指南](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms)

以后每个研究方向使用单独目录：新正式来源拟保存到 `sources/papers/<primary-topic>/` 或 `sources/blogs/<primary-topic>/`，报告、洞察和文章对应 `<folder>/<primary-topic>/`；当前不写入这些正式目录，也不迁移已有资料。多主题仍通过 Frontmatter 的 `topics` 表达，同一来源只保存一份，以主要方向决定目录，不为多个主题复制文件。主题启用不触发任务；`agent-rl` 继续停用。Obsidian 直接将仓库根目录作为 Vault 打开，因此 GitHub 和 Obsidian 使用同一套目录。

## 录入一份资料

1. 按照[维护规范](workflows/maintenance.md)先检索全库的 arXiv ID、DOI 和原始 URL，确认是否已有记录。
2. 从[论文模板](workflows/templates/paper.md)或[博客模板](workflows/templates/blog.md)复制到相应的 `sources/` 子目录。文件名建议为 `<id>.md`。
3. 生成一个新 ID，填写标题、来源、日期等必填元数据，再写笔记。日期写成带引号的 `YYYY-MM-DD`；未知发布时间写 `null`，不要猜测。
4. 在 `topics` 中选用已配置的主题；用 `related_sources` 连接资料 ID，用 `related_notes` 连接已经存在的研究文件。正文可以补充 Markdown 或 Obsidian 双链，便于跳转。
5. 运行下方检查，通过后再提交。

生成稳定 ID（博客将 `paper-` 换成 `blog-`）：

```sh
python3 -c "import uuid; print('paper-' + str(uuid.uuid4()))"
```

完整字段见 [Markdown Schema](workflows/source-schema.md)。ID 一经建立，不随标题、文件名、研究主题或论文版本变化。正文、分析状态及研究关联由人工维护。更新原文时保留人工笔记，具体操作见[去重和更新规范](workflows/maintenance.md)。

初始化前的 `sources/papers/test.md` 原样保留，暂由 `config/legacy_sources.yaml` 明确豁免 Frontmatter 检查，并在每次校验时提示。新资料不得借用旧资料豁免；旧资料补齐元数据后，移除对应豁免项。

## 本地验证

在仓库根目录执行。需要 Python 3.9+，以及一个 YAML 解析依赖 PyYAML；无需 Obsidian 插件或后台服务。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r workflows/requirements.txt
.venv/bin/python workflows/validate.py
git diff --check
```

环境已具备 PyYAML 时，也可以执行 `python3 workflows/validate.py`。检查覆盖目录、配置和模板的 YAML 语法（含重复键）、主题字段、资料字段类型与状态、日期、全库 ID/来源重复，以及关联资料和研究文件是否存在。检查失败返回非零退出码，成功返回 `0`；旧资料豁免显示为警告。检查器不会联网或写文件，也不判断研究结论的质量。

默认检查正式来源；使用 `python3 workflows/validate.py --include-test` 同时严格检查测试来源，分别查重计数，禁止正式与测试互相引用。离线验收执行 `python3 -m unittest discover -s tests -v` 和 `python3 workflows/test/agent-memory/test_validate_isolation.py`。

会员后端另用 `workflows/requirements-membership.txt` 安装 PyJWT/cryptography 等签名验证依赖，再运行同样的离线验收；这些测试不会调用真实模型。实际登录及小规模试跑命令见[本地会员分析说明](workflows/local-membership-analysis.md)。授权文件必须放在本仓库和 Obsidian Vault 之外，不能交给 GitHub 同步；会员余额、金额或用量无法核实时保留未知值，不自动切换普通付费 API。

## GitHub 与 Obsidian 同步

GitHub 保存仓库中的 Markdown、YAML、规范和历史版本；Obsidian 直接编辑同一份本地文件。Obsidian 本身不会把这些文件自动同步到 GitHub。本仓库保留原有 `.git` 和 `.obsidian`，不修改已有远程地址，也不配置自动同步插件。

如果已启用 Obsidian Git 等备份插件，继续按原配置管理提交与同步；在其他设备编辑前确认资料已同步。下方提供不依赖插件的手动流程。

每次在一台设备开始编辑前，先查看本地是否有未提交改动。在工作区干净时按以下顺序操作；首次使用且未配置远程或分支跟踪关系时，先自行完成 GitHub 仓库连接。

```sh
git status
git pull --ff-only
# 用 Obsidian 编辑资料，然后执行校验
.venv/bin/python workflows/validate.py
git diff --check
git diff
git add README.md .gitignore config sources reports insights articles workflows
git diff --cached
git commit -m "docs: update research notes"
git push
```

其他设备克隆同一仓库后，在 Obsidian 中打开该目录，并在编辑前拉取、编辑后提交并推送。已有未提交改动时先检查并保存自己的改动，再同步；快进拉取失败时，人工处理分支分歧，保留双方笔记内容，重新校验。不要使用强制推送或整文件覆盖来解决笔记冲突。避免多台设备同时编辑同一份资料，也不要让其他云盘服务同时同步该目录。

`.obsidian/` 继续整体忽略，因此本地插件配置、布局、偏好和可能存放其中的令牌留在各设备上。`.gitignore` 同时排除常见密钥、环境变量文件和缓存；它不会自动移除已被 Git 跟踪的敏感内容，提交前仍应检查暂存差异。凭据不要写进研究正文、配置或远程 URL；如曾泄漏，应撤销密钥并单独处理历史记录。
