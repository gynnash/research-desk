# ResearchDesk

ResearchDesk 是一个以 Markdown、YAML、GitHub 和 Obsidian 为基础的 AI 技术研究工作台：保存论文与技术博客、研究证据和历史判断，发现技术变化，并为微信公众号提供可追溯的选题与文章。框架面向开源，用户可配置自己的研究方向、来源、模型和预算，并使用自己授权的 ChatGPT 会员。

当前已完成知识库基础设施、离线骨架、arXiv/Letta/LangChain 真实采集与本地官方 ChatGPT 会员接入。2026-10-19 已通过 YAML 配置驱动的一篇论文摘要与一篇博客节选研究，两项独立审阅通过，4 次请求，中断补跑未重复调用，详见[批次真实验收](reports/test/agent-memory/research-batches/configured-research-20261019/acceptance.md)。[上一阶段单篇测试](reports/test/agent-memory/membership/member-arxiv-20261019/acceptance.md)和模拟结果继续保留。Research 与 Insight 先写测试区，[正式准入](workflows/formal-admission.md)已实现：核实独立审阅及散列后仅创建新正式文件，保留旧资料和测试回执。定时代码已准备，最终启用值以 [automation.yaml](config/automation.yaml) 为准；远端准入与首个定时执行需看实际回执。未发布公众号，不使用数据库或复杂 Agent 框架，已有 Vault 设置保持原样。

同日已完成 [Insight 真实测试](reports/test/agent-memory/insight-runs/insight-agent-memory-20261019/acceptance.md)：基于上述两份 Research 结果和五份历史基线，生成 1 份综合报告、2 条洞察和 2 张待确认选题卡，实际生成与审阅模型不同。共 4 次会员请求、43,163 tokens，包含格式失败响应、一次模型修订及额外独立格式确认；禁用推理的中断恢复与完整缓存补跑均未增加调用。新产物仍只在 `test`，未启动 Writing。验收时的 `10/10` 保留为历史快照；按用户后续授权，当前本仓库月度请求预算已调为 100，累计值随后续研究增加，以账本复核为准；会员剩余额度未知。

目标流程由三个业务 Agent 完成：每周二、周五北京时间 09:00 自动 **Research 采集、研究与归纳 → Insight 综合历史、提炼洞察和公众号候选选题 → 用户确认选题、角度与受众 → Writing 生成大纲、初稿及候选稿**。各阶段共用独立模型审阅和确定性校验，日常研究、洞察和选题无需人工逐篇审批；写作必须绑定用户明确确认的选题版本，发布由用户另行决定。总体边界见[三 Agent 架构](workflows/three-agent-architecture.md)与[定时研究 MVP](workflows/agent-memory-github-actions-mvp.md)。[Insight 测试闭环](workflows/insight-agent-test.md)已生成待确认选题；[Writing 离线闭环](workflows/writing-agent-offline.md)只演练虚构选题的确认及模拟写作。真实本地选题确认页与[会员 Writing 后端](workflows/writing-agent-member.md)已接通：用户确认并同步后，单独派发三阶段测试写作。

[Research → Insight 研究轮次](workflows/research-cycle.md)按方向发现资料并串联两个阶段。[自托管执行器](workflows/self-hosted-worker.md)支持当前 Mac 及用户配置的远程主机：主机使用自己的会员授权分析，独立作业校验并保存检查点，再按 [admission.yaml](config/admission.yaml) 准入新正式资料；授权与运行环境留在仓库外。`ResearchDesk checks` 单独执行离线检查。调度器支持固定时间槽、14 天范围内每次一个槽的补跑及同槽恢复；`enabled: false` 时不会自动派研究，正式验收后再改为 `true`。

[正式入库与启用验收](workflows/formal-admission-acceptance-2026-10-19.md)已完成：GitHub 自动创建 7 份正式 Markdown 并同步回现有 Obsidian 库，包含两条来源、两份单来源研究、一份综合报告、一条洞察和一张待确认选题，新增模型调用为 0。定时开关已启用，每周二、周五北京时间 09:00；首次计划为 2026-10-20 09:00，实际首个定时执行尚未发生。`reports/<topic>/admissions/<cycle-id>/` 保存计划、身份映射及输入输出散列，原有笔记保持不变；Writing 读取真实页面确认，首次输出继续限定在 test。

当前新研究轮次最多处理 **5 份资料**，每个来源最多 2 份；每个来源最多检查 20 条候选，实际研究数量取决于新资料、来源可用性和剩余预算。正式资料、测试历史及同轮候选按规范 URL、arXiv 基础编号和 DOI 查重；跟踪参数或页内锚点变化不触发重新研究，真实版本或正文变化才生成独立更新材料。Research 最多 12 次请求，Insight 最多 4 次，共享每轮 16 次及月度 100 次上限。历史已绑定配置与回执不改。[真实选题确认入口](workflows/topic-confirmation-mvp.md)已实现本地浏览器页面，供用户核对选题、角度、受众和证据版本，保存真实确认、撤回及同步重试；真实 Writing 只处理用户已在页面确认并同步的选题，先写 test，再通过[Writing 正式准入](workflows/writing-formal-admission.md)新增正式三稿。

## 在浏览器确认选题

本地页面运行后，打开 [选题工作台](http://127.0.0.1:8765)，按“查看选题与证据 → 调整写作要求 → 查看最终预览”操作。页面保留论文摘要、博客节选与人工历史资料的范围和缺口；修改标题或角度不会把新增判断变成已核实事实。核对后自行勾选范围说明，点击“保存写作确认”。确认记录保存并同步后，可点击 **“开始 / 继续测试写作”**，派发 GitHub Writing 作业。确认本身只保存授权；开始按钮每次最多新增 6 次会员请求，仍受原确认与共享月度预算限制。页面可查看阶段、调用数和大纲、初稿、候选稿；不发布公众号。

在“确认记录”中可以撤回；网络或 Git 同步失败时显示待同步状态，使用“重试同步”继续保存同一条记录，不要重复确认。发生冲突会保留现场并停止，不覆盖人工笔记或强推。页面服务与其独立工作目录位于 Vault 外，Obsidian 通过既有 Git 方式收到记录。预览默认 15 分钟有效，服务重启后需要重新预览。首次准备和启动方法见[使用说明与维护附录](workflows/topic-confirmation-mvp.md#维护附录)。

[正式准入](workflows/writing-formal-admission.md)不调用模型，只把有效页面确认且三阶段独立审阅通过的结果，以新文件保存在 `articles/<topic>/`，并在 `reports/<topic>/writing-admissions/` 固定计划和接受回执。原 test 与人工笔记保持原样，页面分别显示 TEST 和正式稿件；正式入库仍未授权公众号发布。

[首个自动发现轮次](reports/test/agent-memory/cycles/cycle-agent-memory-20261019/acceptance-local.yaml)已完成本地真实验收：两份研究、综合报告、两条洞察及两张待确认选题，8 次会员请求；Research 后中断恢复及完整缓存重放没有重复调用。来源仅扫描有限列表，整体回执保留 `partial`，不声称全量覆盖。

[GitHub → Mac → Obsidian 验收](reports/test/agent-memory/cycles/cycle-agent-memory-gh-20261019/acceptance.md)也已通过：手动派发真实研究，7 次会员请求产出两份研究、综合报告、1 条洞察和1张待确认选题，工作流自动提交测试结果并同步回现有 Vault；跨工作副本缓存重放新增调用为 0。配置支持用户在自己的本地或远程主机部署，当前实际验证的是这台 Mac。

可以结合 Codex 维护仓库、配置和校验，使用 ChatGPT Work 辅助论文阅读、研究讨论与文章草稿。两者共用 Markdown/YAML 约定；直接访问本地仓库的能力取决于使用环境和授权。研究成果需明确保存到本仓库并审阅提交，设备间同步沿用下述 Git 流程。[Codex 官方说明](https://developers.openai.com/codex/cli/)与 [ChatGPT Work 官方说明](https://learn.chatgpt.com/docs/get-started-with-work)可供参考。

## 目录结构

```text
research-desk/
├── config/
│   ├── research_topics.yaml    # 研究方向及启用状态
│   ├── membership_budget.yaml  # 本仓库会员调用的共享月度请求预算
│   ├── admission.yaml         # 独立审阅后的受限正式准入
│   ├── writing_admission.yaml # 已确认、已审阅 Writing 三稿的创建式准入
│   ├── automation.yaml        # 定时开关、固定时间槽与补跑范围
│   ├── confirmation.yaml      # 本地确认页、字数及冻结写作范围
│   ├── cycles/                # 按方向配置发现、Research 与 Insight 轮次
│   ├── legacy_sources.yaml     # 初始化前旧资料的明确兼容清单
│   ├── examples/research_batch.yaml # 开源用户的通用 Research 配置示例
│   ├── examples/insight.yaml   # 通用 Insight 与历史输入配置示例
│   └── test/agent-memory/      # Research、Insight 与离线 Writing 测试配置
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
│   ├── researchdesk_batch.py   # 配置驱动研究批次与补跑，只写 test
│   ├── researchdesk_insight_inputs.py # 已审阅输入与历史基线核实
│   ├── researchdesk_insight.py # 综合报告、洞察与待确认选题，只写 test
│   ├── researchdesk_cycle.py   # 方向资料发现及 Research → Insight 轮次
│   ├── researchdesk_admission.py # 只创建新文件的正式准入，不调用模型
│   ├── researchdesk_schedule.py # 固定时间槽、启用门禁和漏跑选择
│   ├── researchdesk_confirmation.py # 本地真实确认、撤回及 Git 保存
│   ├── researchdesk_confirmation_inputs.py # 正式选题证据与冻结预览
│   ├── confirmation_ui/       # 本地浏览器页面，无外部依赖
│   ├── researchdesk_writing_inputs.py # 虚构输入、散列与确认门禁
│   ├── researchdesk_writing.py # 虚构确认与三阶段离线模拟写作
│   ├── researchdesk_writing_member_inputs.py # 真实页面确认与正式证据门禁
│   ├── researchdesk_writing_member.py # 真实会员三阶段写作与独立审阅
│   ├── researchdesk_writing_job.py # 外部会员运行环境与受限测试回存
│   └── researchdesk_writing_admission.py # 三稿正式准入，不调用模型
└── tests/                     # 临时仓库中的自动验收
```

各核心目录均新增 `test/<topic>/`，论文和博客对应 `sources/papers/test/<topic>/`、`sources/blogs/test/<topic>/`；目前分别保留 `agent-memory` 和停用的 `agent-rl` 子目录。测试记录标记 TEST，不作为正式研究依据。结构、演练和验收命令见[离线运行说明](workflows/offline-research.md)。

[真实采集说明](workflows/real-source-collection.md)包含入口、查重与更新识别、短证据和测试回执。[会员分析设计](workflows/chatgpt-analysis-handoff.md)说明官方授权与资料交接边界；[本地会员分析说明](workflows/local-membership-analysis.md)提供登录、账户模型核实、单篇摘要测试、有限修订及补跑流程。单篇入口默认最多 4 次请求；共享月度请求上限统一读取 [membership_budget.yaml](config/membership_budget.yaml)，当前为 100。研究与审阅必须使用账户可用目录中的两个不同实际模型。完整摘要仅作内存输入，研究报告与脱敏回执另存于 `reports/test/agent-memory/membership/<batch-id>/`，不覆盖已有测试来源。

[配置驱动 Research 批次](workflows/configurable-research-batch.md)说明当前的一篇论文加一篇博客测试、通用 YAML 示例及失败补跑。批次读取主题、来源、模型和预算配置，最多 6 次会员请求、单项最多 4 次、至多一次修订；与其他会员入口共享当前月度 100 次上限，不因换批次重置。新结果只写 `reports/test/<topic>/research-batches/<batch-id>/`，不覆盖既有来源。配置和源码改动可提交，个人授权 profile 必须位于仓库与 Vault 外。

[Insight 测试闭环](workflows/insight-agent-test.md)读取散列与真实独立审阅绑定均有效的 Research 结果，以及 YAML 显式登记的 `human_baseline` 历史资料。生成综合报告、1–2 条跨来源洞察和待人工确认的选题卡，分别创建到 `reports/test/<topic>/insight-runs/<batch-id>/`、`insights/test/<topic>/<batch-id>/` 和 `articles/test/<topic>/<batch-id>/`。正常两次请求，允许一次修订与复审，最多四次；与其他会员入口共用月度预算。历史笔记不会被当作本轮重新核实的原文，模型不能批准自己的选题；本阶段不启动写作。

[Writing 离线闭环](workflows/writing-agent-offline.md)已通过[虚构样例验收](reports/test/agent-memory/writing-runs/writing-offline-20261019/acceptance.md)：`origin: offline_fixture` 确认绑定大纲、初稿和候选稿，`mock-writer` 与 `mock-reviewer` 逐级生成、审阅；初稿修订一次，总计 8 次模拟调用，三个断点恢复与缓存补跑未追加调用。文章只写 `articles/test/<topic>/<batch-id>/`，账本只写 `reports/test/<topic>/writing-runs/<batch-id>/`。配置仍限制每批最多 12 次、每阶段最多 4 次及一次修订；不联网、不消费会员预算，也未批准或改写当前两张真实选题卡。真实本地确认入口与[会员 Writing](workflows/writing-agent-member.md)已实现，保留上述离线演练历史；[正式文章准入](workflows/writing-formal-admission.md)只接收真实确认与真实独立审阅结果。

此前的“每月 10 次”是本项目为小额度验收设置的本地请求限制，写在早期入口及测试 YAML 中，并非来自 ChatGPT 官方会员额度。现在由 `config/membership_budget.yaml` 的 `month_max_calls: 100` 集中管理，同一工作台的真实单篇、Research、Insight 和 Writing 请求共用累计账本；修改上限不清零历史消费，失败或未知请求仍占预留。已绑定的测试配置与旧回执保持原样，旧 `10/10` 只表示验收当时的策略。批次、单项和修订次数限制继续有效；会员官方限流及授权状态仍以实际服务为准。

配置优先级、缺失时的保守回退和不调用模型的复核命令见[共享会员请求预算](workflows/membership-budget.md)。模拟与离线虚拟单位预算不受该配置影响。

各用户须自行通过官方会员授权并核实账户可用模型；当前用户本地验证不代表其他账户或 GitHub 临时 runner 已有资格。GitHub 调度、符合资格的本地或自托管会员分析执行器及 Git 发布步骤分开；当前 Mac 已验证手动真实研究，长期在线、远端正式准入及定时实际运行分别验收。[OpenAI 官方适用范围](https://developers.openai.com/siwc/token-sharing-open-source)、[自托管指南](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms)

每个研究方向使用单独目录：正式准入的新来源保存到 `sources/papers/<primary-topic>/` 或 `sources/blogs/<primary-topic>/`，报告、洞察和选题对应 `<folder>/<primary-topic>/`，不迁移或覆盖已有资料。多主题仍通过 Frontmatter 的 `topics` 表达，同一来源只保存一份，以主要方向决定目录。测试 UUID 已被旧测试来源占用时，准入计划登记旧 ID 到新正式 UUID 的映射，保留旧记录；后续身份识别读取有效准入映射。主题启用与定时开关分开，`agent-rl` 继续停用。Obsidian 将仓库根目录作为 Vault，因此 GitHub 和 Obsidian 使用同一套目录。

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
