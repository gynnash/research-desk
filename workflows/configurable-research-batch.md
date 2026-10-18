# 配置驱动的 Research 批次

本阶段将真实采集、本应用官方 ChatGPT 会员分析和独立审阅接成一个有限批次，验证开源用户可通过 YAML 配置自己的研究工作台。使用一篇论文与一篇博客，不实现 Insight、自动选题或 Writing；完整业务流程及人工确认边界见[三 Agent 架构](three-agent-architecture.md)。

当前真实批次已验收（2026-10-19 北京时间）：两项均独立审阅 `pass`，无修订，总计 4 次请求，响应报告 6,057 tokens；计划中断后恢复及完整缓存补跑均未重复请求。详见[真实验收](../reports/test/agent-memory/research-batches/configured-research-20261019/acceptance.md)与[批次回执](../reports/test/agent-memory/research-batches/configured-research-20261019/receipt-attempt-1.yaml)。上一阶段的[单篇 arXiv 摘要测试](local-membership-analysis.md)保持原样。

## 配置与用户边界

- 通用示例：`config/examples/research_batch.yaml`。用户复制示例，配置自己的研究方向、来源、模型和预算；示例不包含凭据，不自动运行或启用调度。
- 本轮配置：`config/test/agent-memory/research_batch.yaml`。选择 Agent Memory、[A-MEM arXiv 2502.12110v1](https://arxiv.org/abs/2502.12110v1)和 [Letta：Why Memory Isn't a Plugin](https://www.letta.com/blog/why-memory-isnt-a-plugin/)，分别验证论文摘要与博客正文的处理。
- 模型：当前用户已验证目录中的 `gpt-6-luna` 研究，`gpt-6.1-sol` 独立审阅。其他用户必须从自己的账户目录选择两个不同的实际模型；示例中的 ID 不证明账户可用性。
- 授权：沿用[本地会员登录](local-membership-analysis.md)建立的本应用 profile，由运行参数指定仓库外目录；不得将令牌、账户资料、profile 内容、浏览器 Cookie 或既有 Codex session 写入 YAML、提示词或 Git。
- 写入：仅允许 `reports/test/<topic>/research-batches/<batch-id>/`。主题来自配置且须通过校验；配置不能扩大程序的目录白名单、覆盖规则或权限。正式资料、已有测试来源和人工笔记均保持原样。

研究方向配置与任务配置作用不同：方向定义研究范围，批次配置选择实际运行的方向、资料及限制。修改或启用主题不会自动创建任务。当前来源适配器限 arXiv、Letta 和 LangChain 官方公开站点；增加域名需要受信任代码明确支持，不能在 YAML 放任意 URL 扩大网络权限。

| YAML 字段 | 含义 |
| --- | --- |
| `schema_version`、`mode`、`backend` | 当前为版本 `1`、`research_batch_test`、`chatgpt_plan`；离线测试可显式使用 `mock`，真实错误不自动降级模拟 |
| `topic`、`topics_file` | 稳定方向 ID 及 `config/` 内的方向配置路径；方向必须存在、启用，并给出名称、说明、范围和关键词 |
| `models.research`、`models.review` | 当前用户账户目录中的两个不同模型 slug |
| `sources` | 每项给出稳定 `id`、适配器、资料类型、官方 URL 和 `evidence_max_chars`；本阶段是有限的指定资料批次，不代表已实现定时发现和完整扫描游标 |
| `budget` | 资料数、单项/批次/月度请求数、输入/输出字符、等待秒数和修订次数限制 |
| `prompts.version` | 已实现提示词协议版本 `research-batch-v1`；修改任意版本字符串不能跳过协议校验 |

通用示例使用 `config/examples/research_topics.yaml`，与现有 Agent Memory 配置分开。示例方向的 `enabled: true` 仅表示允许被手动选择，不创建任务；用户运行前应填写自己的方向和来源，核对启用意图，并将两个模型占位符替换为自己账户目录中的实际 slug。配置文件与引用的方向文件均须位于选定工作台的 `config/`，拒绝重复 YAML 键、未知字段、目录穿越及符号链接。配置不能包含 token 或任意执行命令。

## 小额度与审阅

| 控制 | 本轮要求 |
| --- | --- |
| 批次资料数 | 一篇论文加一篇博客，最多两份 |
| 模型身份 | YAML 中配置两个不同模型，并核对账户目录及实际响应身份 |
| 单项请求 | 最多 4 次：研究、审阅，必要时一次修订与一次完整复审 |
| 批次请求 | 最多 6 次；通常 4 次，剩余 2 次仅够一项修订与复审 |
| 月度累计 | 最多预留 10 次，包含此前单篇测试的 2 次；换批次不返还或重置 |
| 输入/输出/等待 | 本轮每次输入最多 20,000 字符、输出最多 10,000 字符、客户端等待最多 120 秒；每项原文证据最多 6,000 字符 |
| 原文范围 | 论文明确标注 `abstract_only`；博客按实际取得的正文范围标注，不把节选当全文 |
| 原文持久化 | 每份最多合计 25 个英文单词且 400 字符的短摘录、定位及散列；完整原文只作为内存输入，不存整页镜像或完整请求 |

每次调用前持久化预留事件；成功后记录实际返回模型和可获得的用量。超时、断流、输出超限或终态不明继续占用预留，不自动重发、不切换付费 API。会员剩余额度、金额无法核实时保持未知，不把调用数或 token 数换算为会员百分比。

输入、输出字符数和等待时间由 YAML 限制并由客户端执行。官方会员预览不支持 `max_output_tokens`；客户端停止接收无法保证服务端生成或会员额度消耗的硬上限。[OpenAI 官方限制](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

研究和审阅使用独立上下文；审阅收到同一原文证据及完整候选，逐项核查事实、作者主张、我们的推断、引用和阅读范围。结果为 `pass / revise / reject / blocked`；硬性规则失败不能由模型豁免。仅格式、证据、模型身份与独立审阅都通过才记 `test_accepted`，始终保持 `production_accepted: false`。

## 去重、保护与恢复

先对正式库、测试来源及历史运行查重，以 arXiv 基础编号、DOI 和保守规范化 URL 匹配，版本和正文散列用于判断内容变化。已存在的来源只关联原 ID 或记录独立更新分析，不复制来源文件，不刷新旧文件的状态或人工笔记。首次从模拟研究升级到真实会员分析可以新增独立测试报告，不能覆盖模拟来源或冒充已正式入库。

同批恢复绑定原 YAML、资料身份、证据、模型、预算、授权身份及受保护文件散列。已经持久化且校验一致的研究/审阅结果复用，缺失或被改动的文件不能静默重建或覆盖。新批次不能绕过同一证据的历史完成、拒绝、待办或未知请求记录。

抓取失败逐项记录，健康项继续；批次状态必须区分全部完成、部分成功、失败和阻塞。来源失败不能计为零新增，也不允许以未核实的旧资料代替原文。已确认完成一项后故意中断，再沿用同一批次补跑，用调用账本确认第一项没有重复请求；未知结果仍需核对，不能通过换批次盲目重发。

## 运行与中断补跑

需要 Python 3.9+ 以及 `workflows/requirements-membership.txt` 中的依赖。安装环境和官方登录步骤见[本地会员分析说明](local-membership-analysis.md)。每位用户独立授权，先查看状态和模型目录；以下 profile 变量仅指仓库外目录，不将任何令牌写进命令：

```sh
researchdesk_profile_dir="$HOME/Library/Application Support/ResearchDesk/chatgpt"
.venv-membership/bin/python scripts/researchdesk_membership.py \
  --profile-dir "$researchdesk_profile_dir" status
.venv-membership/bin/python scripts/researchdesk_membership.py \
  --profile-dir "$researchdesk_profile_dir" models
```

状态不满足要求时先执行同一 profile 的 `login` 并由用户自行完成官方页面。模型 ID 需来自该账户目录；配置错误、资格不足、缺少不同审阅模型或额度不足时停止，不转向其他账户或 API Key。`--profile` 可省略以使用本机默认外部目录；其他安装应明确指定自己的目录。`--root` 可选择另一工作台根目录，配置和输出仍受该根目录内的边界约束。

本轮先在第一项完成并持久化后主动中断，检查第一项的研究与审阅结果已经保存：

```sh
.venv-membership/bin/python scripts/researchdesk_batch.py \
  --config config/test/agent-memory/research_batch.yaml \
  --batch-id configured-research-20261019 \
  --profile "$researchdesk_profile_dir" \
  --fail-after after_first_item
```

该验收中断的预期退出码为 `3`，不是模型失败。随后保持相同批次、配置和 profile，去掉故障参数继续：

```sh
.venv-membership/bin/python scripts/researchdesk_batch.py \
  --config config/test/agent-memory/research_batch.yaml \
  --batch-id configured-research-20261019 \
  --profile "$researchdesk_profile_dir"
```

第一项从散列校验过的结果复用，第二项继续采集及分析。完成后再次执行后一条命令，预期返回 `cached: true`，已有结果不重写，调用预留与实际完成计数不增加；重新读取账户目录不计模型推理调用。真实状态必须以回执证明，命令示例本身不代表已通过。如果第一项未完成或结果未知，不能把退出码或批次存在当成验收成功。

## 产物与验收

本轮目录为 `reports/test/agent-memory/research-batches/configured-research-20261019/`：

- `manifest.yaml`：配置和方向文件散列、原始基线、独立模型、预算、授权身份脱敏标识及已有笔记保护基线。
- `items/<source.id>/candidate.yaml`：稳定来源身份、已有来源关联、元数据、证据范围/定位/散列与处理决定；原文正文不落盘。
- `items/<source.id>/checkpoints/`：绑定请求的研究、修订和审阅结果；`report.md` 为带 TEST 标识的通过报告，`result.yaml` 保存单项决定及产物散列。
- `source-attempts/<source.id>/attempt-N.yaml`：不可变采集尝试；失败只保存错误类型，不泄露可能包含凭据的原始异常。
- `events/`：调用预留、实际完成用量、单项完成和验收中断等追加事件；未知预留继续占用预算。
- `receipt-attempt-N.yaml`：每次产生新状态的批次回执，包括单项结果、实际模型、调用数量、用量及保护结果；完整缓存补跑不新增同内容回执。

各 YAML 与检查点附完整性散列；已有文件发生人工变化时停止并保留现场。批次结果仅为 `test_accepted`，`production_accepted` 必须是 `false`。

本阶段验收需观察两份资料的采集范围与来源核实、实际研究/审阅模型不同、审阅结论、请求与用量记录、首次中断及补跑事件、已有资料散列保护。通常总计 4 次真实请求；发生一次修订与复审时最多 6 次。不能把“部分成功”写成两项均已通过，也不能声称博客节选或论文摘要支持全文结论。

以下离线检查不消耗会员模型额度，在仓库根目录执行：

```sh
.venv-membership/bin/python -m unittest discover -s tests -v
.venv-membership/bin/python workflows/test/agent-memory/test_validate_isolation.py
.venv-membership/bin/python workflows/validate.py
.venv-membership/bin/python workflows/validate.py --include-test
git diff --check
git status --short
git ls-files '.github/workflows/*'
```

最后一项预期无输出；同时核对未跟踪文件，确认没有实际调度配置。验收后可以提交源码、配置、文档和测试回执，凭据不进入仓库。没有正式入库、定时、Insight 或 Writing 验收记录时，不宣称完整研究工作台已经自动运行。
