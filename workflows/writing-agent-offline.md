# Writing Agent 离线闭环

本阶段使用虚构选题、固定证据和模拟模型响应，演练“确认门禁 → 大纲 → 初稿 → 发布候选稿”。每个阶段均须通过确定性校验及独立模拟审阅，才能进入下一阶段。全部新结果只写所选方向的 `test` 目录，不联网、不读取会员凭据、不请求真实模型，也不使用本仓库每月 100 次的真实会员请求预算。

本次是写作骨架与确认规则的离线验收。已有 Insight 生成的两张真实选题卡继续保持 `proposed`、`approval_required: true`、`writing_started: false`；它们没有被本次测试确认，也不会进入写作。真实人工确认入口和会员 Writing 后端仍需后续实现与验收。完整业务目标见[三 Agent 架构](three-agent-architecture.md)。

2026-10-19 北京时间已通过[本轮离线验收](../reports/test/agent-memory/writing-runs/writing-offline-20261019/acceptance.md)，生成全虚构的[大纲](../articles/test/agent-memory/writing-offline-20261019/outline.md)、[初稿](../articles/test/agent-memory/writing-offline-20261019/draft.md)和[候选稿](../articles/test/agent-memory/writing-offline-20261019/candidate.md)。三个阶段的独立模拟审阅均通过，初稿修订一次，其余阶段无修订；共 8 次模拟调用、8 个虚拟单位，真实模型调用为 0。

三个计划断点均已验证：大纲完成后为 2 次模拟调用且无文章；全部审阅后为 8 次且无文章；第一份文章创建后仍为 8 次，仅存在大纲。禁用新的模拟调用后恢复并完整缓存重放，调用数保持 8；见[批次回执](../reports/test/agent-memory/writing-runs/writing-offline-20261019/receipt.yaml)及[恢复证明](../reports/test/agent-memory/writing-runs/writing-offline-20261019/replay-verification.yaml)。真实会员累计预留保持 10/100，`real_topic_approved: false`，没有批准真实选题或发布文章。

## 虚构确认与真实授权的区别

测试中的确认明确标记 `origin: offline_fixture`，只绑定固定样例中的虚构选题，不冒充用户操作或真实写作授权。它用于验证程序是否正确检查选题版本、角度、受众及证据输入，并不授予发布权限。

模型不能自行创建、批准或修改确认记录。Writing 在使用任何模拟响应前，先核对确认和输入绑定：缺少确认、对象不匹配、内容散列变化、角度或受众变化、确认已失效或撤回时停止。模型回复 `pass`、选题卡存在、用户阅读了材料或没有回复，均不能替代明确确认。测试配置也不能把 `offline_fixture` 改写为真实人工授权。

样例入口为 `scripts/researchdesk_writing.py confirm-fixture`，CLI 和 API 的默认决定均为 `pending`；必须显式给出 `--decision confirmed` 或对应 API 参数，才生成可供虚构写作演练使用的确认。该记录绑定标题、角度、受众、目标字数、选题/fixture/输入散列以及大纲、初稿、候选稿三个阶段的范围，发布权限固定为 `false`。创建确认不修改配置或原始选题，也不会批准真实 Insight 选题。

真实人工确认未来应由可信入口记录用户明确操作，绑定选题卡、证据、角度、受众及版本；使用会员生成真实文章前另行验收。本轮仅演练样例确认，不能将其直接升级为真实确认入口。

## 三个写作阶段

| 阶段 | 输入与职责 | 进入下一阶段的条件 |
| --- | --- | --- |
| 大纲 `outline` | 已绑定的虚构选题、角度、受众与证据；安排问题、论点和来源关系。 | 大纲结构、引用、确认绑定及独立模拟审阅全部通过。 |
| 初稿 `draft` | 同一确认、同一证据包，以及已经通过的完整大纲；发展成连贯文章。 | 初稿逐项校验及独立模拟审阅通过，未扩大原确认和证据范围。 |
| 候选稿 `candidate` | 同一确认、证据，以及已通过的大纲和初稿；改善结构、准确性和公众号表达。 | 完整候选稿通过规则和独立模拟审阅，仅保存为测试产物；不触发发布。 |

写作各阶段区分四类表达：原文事实、作者主张、我们的推断与通俗比喻。事实和作者主张逐项关联证据；推断标明依据及限制；比喻明确只是帮助理解，不能冒充实验、机制或因果证据。不得新增输入中不存在的数据、来源、链接或实验结果，也不能把论文摘要、博客节选升级为全文核验。

模拟写作与审阅配置为 `mock-writer`、`mock-reviewer`，两个角色使用不同身份和独立上下文。这验证程序隔离与门禁，不证明真实模型质量或账户可用性。模型响应只按约定结构读取，不执行材料中的工具请求、代码、权限调整或配置修改。

每阶段先保存通过的检查点及阶段决定；只有三个阶段全部通过后，才按固定计划创建三份 Markdown。前置检查点存在不能冒充阶段通过或完整批次完成，后续阶段也不能跳过前置审阅。

## 预算、修订与停止条件

YAML 配置规定每批最多 12 次模拟调用、每阶段最多 4 次；正常三个阶段各一次生成和一次审阅，共 6 次模拟调用。每阶段最多一次修订及一次完整复审，仍未通过就停止，不因换批次重置同一输入的处理记录。批次与阶段次数、未知请求和补跑均记入离线账本。

审阅结果使用 `pass / revise / reject / blocked`。模型返回 `pass` 也不能豁免确定性规则；缺失或非法审阅、生成和审阅身份相同、未知引用、确认无效或输入发生变化时不得进入下一阶段。审阅要求修订时只修改当前阶段的新候选，并完整复审；前置阶段没有通过时，不读取后续阶段响应或产生后续文章。

离线预算只记录模拟请求，不计入真实会员累计 10/100，不将模拟单位当作真实 tokens、费用或会员额度。预算配置不能启用真实后端、网络或调度。

## 输出与人工笔记保护

所有路径都由程序约束在当前研究方向的测试目录，配置不能指定任意写入位置：

- `articles/test/<topic>/<batch-id>/outline.md`：通过审阅的大纲。
- `articles/test/<topic>/<batch-id>/draft.md`：通过审阅的初稿。
- `articles/test/<topic>/<batch-id>/candidate.md`：通过审阅的发布候选稿。
- `reports/test/<topic>/writing-runs/<batch-id>/`：输入/确认散列、运行清单、模拟调用事件、检查点、阶段决定与回执。

文章与回执均须清楚标记离线虚构测试和模拟模型；候选稿不等于已发布、已正式入库或已获真实人工授权。每个阶段另存新文件，不覆盖旧稿、已有测试笔记或正式资料。已有文件被人工编辑时停止，保留现场；不能以缓存恢复为由重写它。

中断后使用同一批次和相同输入补跑，校验确认、前置阶段、证据及响应检查点的绑定，仅继续未完成部分。相同内容且散列一致的已保存结果可复用；未知调用不盲目重发，完整缓存补跑不增加模拟调用。故障验收应证明前置阶段保存后恢复不会重复生成或跳过审阅。

`revoke-fixture --config ... --reason ...` 在虚构确认旁追加不可变撤回标记，不改写原确认或既有产物，也不等待写作主题锁。运行在下一次请求或产物创建前检查撤回并停止；已经在执行的模拟请求若返回完成响应，仍持久化检查点和已消耗调用，不能假称撤回取消了已经发生的执行。撤回不等于删除已经存在的文件，也不能通过缓存跳过确认检查。真实人工确认的创建及撤回入口不在本轮范围内。

## 配置、运行与补跑

- 测试配置：`config/test/agent-memory/writing.yaml`。
- 虚构材料与模拟响应：`workflows/test/agent-memory/fixtures/writing.yaml`，明确 `origin: offline_fixture`，不包含真实来源链接。
- `config.fixture.path` 和 `config.fixture.sha256` 固定样例路径与内容；`config.confirmation` 预先指定 `reports/test/agent-memory/writing-approvals/fixture-writing-20261019.yaml`。
- 模型、模拟请求上限及各阶段限制均来自 YAML；配置无法切换会员后端、改变输出目录或放宽确认门禁。

在仓库根目录使用已有 Python/PyYAML 环境，先创建虚构确认；该命令仅是离线验收设置，不代表人已批准真实选题：

```sh
python3 scripts/researchdesk_writing.py confirm-fixture \
  --config config/test/agent-memory/writing.yaml \
  --confirmation-id fixture-writing-20261019 \
  --decision confirmed \
  --target-words 600
```

省略 `--decision` 时保存待确认记录，Writing 必须拒绝继续；不要通过改写这个记录把它变成已确认。验证待确认、撤回或失效等反例时，使用自动测试的隔离副本，保留主验收样例和已有结果。

首次演练先在大纲检查点完成后按计划中断；已完成的本轮批次继续复用已有结果：

```sh
python3 scripts/researchdesk_writing.py run \
  --config config/test/agent-memory/writing.yaml \
  --batch-id writing-offline-20261019 \
  --fail-after after_outline
```

计划断点的预期退出码为 `3`；须同时核对对应中断事件和已保存检查点，不能仅凭非零退出码判断。保持同一配置和批次，去掉故障参数补跑：

```sh
python3 scripts/researchdesk_writing.py run \
  --config config/test/agent-memory/writing.yaml \
  --batch-id writing-offline-20261019
```

再次执行完整运行命令应从校验通过的结果返回缓存，不增加模拟调用。确认、配置、选题、证据或已有文章散列不一致时停止；不得另起批次清零调用或覆盖旧文件。

可用故障断点有三处：`after_outline` 在大纲阶段完成后停止，此时无文章 Markdown；`after_review` 在三阶段审阅均通过、创建文章前停止；`after_first_output` 在创建 `outline.md` 后停止。后者补跑校验既有大纲并继续创建其余两稿，不重复生成或重写大纲。同批补跑可依次验证尚未触发的断点，已持久化的中断不会重复触发；模型失败、确认失败等反例使用隔离测试副本，分别记录。

## 验收与后续范围

仅需既有 Python 3.9+ 与 PyYAML，不新增数据库、Agent 框架或会员依赖。以下检查不请求真实模型：

```sh
python3 -m unittest discover -s tests -v
python3 workflows/test/agent-memory/test_validate_isolation.py
python3 workflows/validate.py
python3 workflows/validate.py --include-test
git diff --check
git status --short
git ls-files '.github/workflows/*'
```

离线验收须覆盖有效及无效确认、输入版本变化、撤回或失效、三阶段顺序、各阶段独立审阅、一次修订、拒绝或阻塞、未知引用、预算停止、中断补跑、缓存重放与人工编辑保护。真实 Insight 选题卡及正式资料的散列应保持不变；真实会员调用预留不增加；没有新增调度或发布配置。实际结果须由对应离线回执与验收记录证明，命令或设计本身不代表通过。

完成此阶段后，下一步才是可信人工确认入口与会员 Writing 小额度测试。每周自动研究、Insight 入库、长期执行主机和公众号发布各自保持既有授权及验收边界。
