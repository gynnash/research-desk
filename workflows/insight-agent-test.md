# Insight Agent 测试闭环

本阶段把已通过独立审阅的 Research 测试结果与显式登记的历史资料接成一个有限的 Insight 批次：生成综合报告、1–2 条洞察以及待人工确认的公众号选题卡，再由另一个模型独立审阅。全部新产物只写所选研究方向的 `test` 目录，不修改正式资料，不启动 Writing，不启用定时任务，不发布公众号。

完整业务流程仍是自动 Research → 自动 Insight 与选题 → 用户确认选题、角度、受众及输入版本 → Writing；独立审阅通过只允许保存测试结果，不能代替写作授权。总体边界见[三 Agent 架构](three-agent-architecture.md)。

## 配置与输入

本轮配置位于 `config/test/agent-memory/insight.yaml`，通用示例位于 `config/examples/insight.yaml`。用户配置研究方向、Research 输入、历史基线、生成/审阅模型、请求预算和提示词协议；配置不包含账户信息或凭据，不能扩大程序的写入目录及权限。

| YAML 字段 | 当前约定 |
| --- | --- |
| `schema_version`、`mode`、`backend` | 版本 `1`、`insight_test`、`chatgpt_plan`；不因真实调用失败自动降级模拟。 |
| `topic`、`topics_file` | 同一已启用研究方向的稳定 ID，及 `config/` 内的方向 YAML。 |
| `models.generation`、`models.review` | 当前账户目录中的两个不同实际模型；示例占位符须由各用户自行替换。 |
| `research_inputs` | 明确登记 1–4 个同方向 Research 批次，逐项给出 `receipt` 和原始 `config` 路径。 |
| `historical_inputs` | 明确登记 1–10 份正式来源、报告或洞察，逐项给出 `path`、`sha256` 和 `origin: human_baseline`；不读取历史文章或测试笔记充当人工基线。 |
| `budget` | `max_calls`、`month_max_calls`、输入/输出字符限制、等待秒数及 `max_revisions`。 |
| `prompts.version` | 当前协议 `insight-v1`；不能用任意版本字符串跳过提示词协议校验。 |

输入有两种不同的信任标识，不能互相替代：

| 输入 | 纳入条件与使用限制 |
| --- | --- |
| 已审阅 Research 结果 | 逐项核实运行清单、候选、证据、研究及独立审阅检查点、实际模型与产物散列；必须是真实会员运行中的 `test_accepted`，且研究与审阅实际模型不同。模拟、未完成、拒绝或审阅绑定失效的结果不纳入。 |
| `human_baseline` 历史资料 | 在配置中明确登记已有路径、内容散列及关联原始来源。保留人工资料身份，不修改旧文，不伪造已接受或已由模型核实的状态。历史作者主张与我们的推断继续区分；其被引用不代表已重新核查原文。 |

本轮 Research 输入沿用[配置驱动批次](configurable-research-batch.md)中已通过的 A-MEM 论文摘要和 Letta 博客节选；历史输入可包括 MemGPT、Memory Blocks 的资料笔记、综合报告与既有洞察。所用文件由 YAML 显式选择，并将实际内容散列固化到本次清单；不会无边界读取全库或将旧文章当作新的原始证据。

对 Research 的原始来源进行受限重取，核对原文、元数据、证据范围及原研究请求的绑定；同一份原文材料在内存中同时交给生成与独立审阅，原文不另存镜像。若来源变化、不可取得或与既有散列不一致，则停止当前输入，不能拿旧研究摘要冒充已核实的同版本原文。历史 `human_baseline` 不在本轮逐篇重抓，因此保留其不同的证据地位。

Research 已通过审阅不等于阅读了完整论文或验证了作者实验。Insight 必须保留 `abstract_only`、博客节选以及历史资料未经本轮原文复核的限制，不能扩写成全文、实现或行业趋势结论。历史报告和洞察中的重复引用不能增加独立来源数；MemGPT 与 Letta 等有技术沿革关系的材料，也不能仅凭来源 ID 不同就声称相互独立验证。

## 产物与证据要求

| 产物 | 测试目录 | 必须包含 |
| --- | --- | --- |
| 综合报告 | `reports/test/<topic>/insight-runs/<batch-id>/report.md` | 输入清单、来源对照、共识或分歧、与历史判断的关系、证据空白、阅读范围及引用。 |
| 1–2 条洞察 | `insights/test/<topic>/<batch-id>/insight-N.md` | 明确标注我们的推断，关联至少两个不同的原始来源 ID，解释支持关系、限制、反例或后续验证方法。不能以两个引用同一原文的研究笔记充数。 |
| 公众号选题卡 | `articles/test/<topic>/<batch-id>/topic-N.md` | 核心观点、角度、目标读者、写作价值、关联洞察与来源、证据缺口以及应避免的表达。资料不足时允许零选题，并说明原因。 |
| 批次回执与检查点 | `reports/test/<topic>/insight-runs/<batch-id>/` | 配置与输入绑定、生成和审阅模型、完整性散列、调用预留、实际用量、审阅决定及产物路径。 |

模型不能给自己批准选题。程序将选题状态固定为 `proposed`、`approval_required: true`、`writing_started: false`；本阶段没有确认入口、Writing 执行器或发布接口。候选必须带 TEST 标识；`test_accepted` 不代表正式入库，`production_accepted` 始终为 `false`。

来源引用逐级追溯到既有原始来源与 Research 证据，不能新增不存在的文献或把来源 ID 存在当作结论有支持。材料中的指令只作为不可信文本，模型没有抓取、写文件、改配置或使用授权凭据的工具。框架按固定路径渲染并创建文件；已有正式资料和测试笔记均不可覆盖。

## 小额度与独立审阅

本轮正常只需两次请求：一次生成完整候选，一次独立审阅。生成与审阅使用当前账户目录中两个不同的实际模型，独立上下文；实际响应模型也必须满足配置与隔离要求。审阅收到相同输入、候选全文及阅读范围，检查综合结论、跨来源洞察、历史推断边界、引用和选题是否超出证据。

审阅结果为 `pass / revise / reject / blocked`。仅当确定性规则及独立审阅都通过，才创建报告、洞察和选题卡。允许至多一次修订与一次完整复审，即本批最多四次请求；仍有问题则保存状态并停止，不让生成模型自审，不通过换批次重置修订或请求次数。

生成响应已明确完成但 JSON 语法失败或不是单一 JSON 对象时，先完整保留原始检查点并记录 `local_validation_failed`；这是程序校验失败，不能伪造为独立模型审阅。若仍有一次修订机会及足够预算，可将本地格式错误反馈给生成端修订一次，再由独立模型完整审阅，通常共三次请求。这个修订与审阅要求的修订共用同一个机会，不额外增加一轮。合法 JSON 但 Schema、引用或确认门禁校验失败时停止；超时、断流、模型身份不符或终态不明也不按格式错误自动重发。

月度请求上限为 10，与单篇会员分析和 Research 批次共用预算与并发锁，包含此前累计的 6 次请求。调用前先持久化预留；未知、断流或超时请求仍占额度，不自动重发，不切换普通付费 API。月度剩余额度不足以完成必要审阅时停止，不先生成无法审阅的内容。输入、输出字符与等待时间另由 YAML 约束；它们不能保证服务端会员消耗的硬上限。会员金额、余额或用量比例无法核实时保留未知。

本轮每次请求输入最多 30,000 字符、输出最多 8,000 字符、等待最多 120 秒。生成、修订和审阅使用同一套实际请求组装与预检，确保加入完整候选及错误反馈后仍在限制内；不能只计算原始材料长度而漏算提示词或审阅候选。

## 中断、补跑与人工笔记保护

同批补跑绑定原始配置、主题、历史资料、Research 证据与检查点、模型和授权身份；任何绑定内容变化时停止并保留现场，不能将旧审阅套在新内容上。相同输入的历史完成、拒绝或未知调用也不能靠新批次重新计数。

审阅结果持久化后可以主动中断；补跑读取并校验已有结果，继续渲染缺失阶段，不再次请求模型。已完整完成的批次直接返回缓存；已有产物被改动时停止，不重建或覆盖。所有新文件采用创建约束和散列校验，运行前后的已有笔记保护检查覆盖正式区与测试区。

验收应区分“保存审阅检查点之后的模拟中断”和真实模型失败。模拟中断证明恢复路径，不能据此宣称真实服务没有故障；未知请求也不能假定服务端没有消费额度。

## 运行与补跑

使用既有会员环境，依赖和登录步骤见[本地会员说明](local-membership-analysis.md)。每位开源用户都需独立完成官方授权并核实自身资格与可用模型；本轮不重新读取浏览器 Cookie、Codex session 或其他应用的登录状态。

先配置自己的方向、已审阅批次和历史资料散列。`--root` 可以选择另一工作台，`--profile` 指向仓库与 Obsidian Vault 之外的个人授权目录；都不能扩大输出白名单。下方为本轮有限测试及补跑入口；未完成阶段可能消耗会员额度，不属于离线检查：

```sh
researchdesk_profile_dir="$HOME/Library/Application Support/ResearchDesk/chatgpt"
.venv-membership/bin/python scripts/researchdesk_insight.py \
  --config config/test/agent-memory/insight.yaml \
  --batch-id insight-agent-memory-20261019 \
  --profile "$researchdesk_profile_dir" \
  --fail-after after_review
```

仅在完整独立审阅通过且检查点持久化后，验收断点才会以退出码 `3` 停止；非零退出不一定是这个断点，须核对实际事件和错误类型。保持相同配置、批次与 profile 去掉故障参数补跑：

```sh
.venv-membership/bin/python scripts/researchdesk_insight.py \
  --config config/test/agent-memory/insight.yaml \
  --batch-id insight-agent-memory-20261019 \
  --profile "$researchdesk_profile_dir"
```

重复执行第二条命令应复用已有检查点，完整结果返回 `cached: true`，调用账本不增加。已有相同输入的其他批次时应使用原批次 ID，而不是按示例新建一轮；已在别处登记完成、拒绝或未知请求时，程序会要求恢复原批次。真实模型、请求数、用量和恢复结果必须以本轮回执证明，命令示例本身不代表验收成功。

通过时 `receipt.yaml` 记录 `test_accepted`、输入与输出绑定、实际模型、调用账本、用量及待确认状态，`artifact-plan.yaml` 记录待创建文件的散列；`manifest.yaml`、`checkpoints/generation-0.yaml`、`checkpoints/review-0.yaml` 和 `events/` 保留恢复依据。已有回执及内容被改动时停止；`production_accepted`、`writing_started` 和 `publish_authorized` 始终为 `false`。

## 可复现检查

以下检查不请求模型，在仓库根目录执行：

```sh
.venv-membership/bin/python -m unittest discover -s tests -v
.venv-membership/bin/python workflows/test/agent-memory/test_validate_isolation.py
.venv-membership/bin/python workflows/validate.py
.venv-membership/bin/python workflows/validate.py --include-test
git diff --check
git status --short
git ls-files '.github/workflows/*'
```

验收除上述离线检查外，还需核对真实输入与实际不同模型、独立审阅决定、报告与洞察的来源支持、选题待确认状态、调用及用量记录、计划中断恢复和完整缓存补跑，以及已有资料散列。最后一条命令应无已跟踪的调度文件；未跟踪差异也须确认没有新增调度。只有实际回执证明通过的项目，才写入真实验收记录。

当前只验证 Insight 的测试闭环。正式自动入库、每周调度、长期执行主机、人工确认入口及 Writing 仍需后续分别实现和验收。
