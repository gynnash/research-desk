# Research Agent 离线运行与验收

当前实现是固定样例驱动的运行骨架。它只支持 `mock-*` 模型：没有网络抓取、真实模型客户端、Git/PR 执行器、定时工作流或公众号发布。测试状态为 `test_accepted`，不表示正式 `accepted` 或真实模型审阅通过。

这是纯离线模块的范围；后来新增的[真实采集入口](real-source-collection.md)负责联网取得短证据，再交给同一模拟运行骨架。真实来源使用独立横幅，不标成虚构样例。

实现位于 [researchdesk_offline.py](../scripts/researchdesk_offline.py)，自包含离线配置与虚构证据/模型响应位于 [offline.yaml](test/agent-memory/fixtures/offline.yaml)。仍只依赖 Python 3.9+ 和现有 PyYAML，不增加数据库或 Agent 框架。

## 测试目录和研究方向

GitHub 仓库与 Obsidian Vault 使用同一份本地目录，不需要另建一套 Obsidian 文件夹或改插件配置。以下 `test/` 目录下均保留独立的 `agent-memory/`、`agent-rl/`；后者仍停用，只预留位置。

| 目录 | 用途 |
| --- | --- |
| `config/test/<topic>/` | 后续测试配置位置；当前配置在自包含 fixture，不重复保存另一份参数。 |
| `sources/test/<topic>/` | 来源测试区的方向导航/预留位置。 |
| `sources/papers/test/<topic>/`、`sources/blogs/test/<topic>/` | 按现有 Schema 保存通过离线门禁的虚构来源。 |
| `reports/test/<topic>/<batch>/` | 冻结的批次计划、调用事件、研究/审阅检查点、独立更新建议与验收回执。 |
| `insights/test/<topic>/`、`articles/test/<topic>/` | 后续洞察和文章测试结果位置；本轮只预留，不生成内容。 |
| `workflows/test/<topic>/` | 固定样例与目录隔离验收；运行骨架的其他自动验收在 `tests/`。 |

论文/博客的测试目录不放 README，避免被当成来源文件；说明集中在 [sources/test/README.md](../sources/test/README.md)。测试 Markdown 必须包含 `> TEST：离线虚构样例，不可作为正式研究证据。`，不能通过 legacy 清单豁免 Schema。原来的 `sources/papers/test.md` 原样保留，它与新测试目录无关。

以后每个方向单独建目录。新正式来源拟采用 `sources/<papers|blogs>/<primary-topic>/<id>.md`，报告、洞察和文章采用各自的 `<primary-topic>/`。当前不创建正式研究产物或迁移旧文件。同一来源只保留一个稳定 ID、一个主目录，其余主题使用 `topics` 和关联表达，避免按主题复制。

## 可复现命令

在仓库根目录执行；环境需要现有 `workflows/requirements.txt` 中的依赖。

```sh
python3 -m unittest discover -s tests -v
python3 workflows/test/agent-memory/test_validate_isolation.py
python3 scripts/researchdesk_offline.py --fixture workflows/test/agent-memory/fixtures/offline.yaml --batch-id offline-acceptance-20261018
python3 workflows/validate.py
python3 workflows/validate.py --include-test
git diff --check
```

固定演练预期：2 份虚构来源 `test_accepted`，其中博客经过一次修订；1 份拒绝；累计 8 次模拟请求、16 个虚拟费用单位，真实 API 费用为 0。结果位于 [首批回执](../reports/test/agent-memory/offline-acceptance-20261018/summary-attempt-1.md)。

重复相同命令不会重新调用模型、分配 ID 或覆盖已有资料，会追加编号回执；显示的 8 次/16 单位是累计账本，不是本次新增费用。批次 ID 使用小写字母、数字和连字符。真实定时任务时槽格式仍以 [MVP](agent-memory-github-actions-mvp.md) 为准。

自动验收全部在临时仓库内运行，覆盖发布前中断与预留后中断，测试期间不修改正式资料。可用 CLI 的 `--fail-after after_review` 或 `--fail-after after_reservation` 在独立测试批次复现中断；退出码为 2。去掉该参数，使用同一 fixture 和批次 ID 补跑。已完成的批次不会再次触发故障；不要修改旧 fixture 来强行重用原批次。

正常完整处理返回 0；仍有阻塞/延期返回 1；输入、保护门禁或故障注入返回 2。某份资料被正常拒绝不等于整批运行故障。

## 已实现的边界

- **身份与规划**：先比较 URL、arXiv 基础编号、DOI；显式身份与 URL 提取的身份同时核对。正式库、测试库、历史计划/拒绝及当前批次共同查重，多记录键冲突不猜测合并。调用前将 UUID v4 和固定 fixture 散列保存到不可变 `manifest.yaml`。
- **独立审阅**：研究和审阅使用不同模拟模型 ID、独立输入。审阅输入含原文证据、候选正文/元数据/研究结果；修订输入含上一稿和审阅问题。检查摘要、主张、证据 ID、摘录匹配及逐项支持判断，不能用带阻塞问题或未知严重度的 `pass` 放行。
- **有限修订**：最多一次修订与复审；仍未通过则终结该轮。同一证据、目标版本的拒绝或已完成更新不能通过新批次重新研究。已有付费尝试的延期项需恢复原批次，当前骨架不实现跨批次转移执行账本。
- **预算**：每角色每份最多 2 次、每份最多 4 次、每批最多 12 次。整数虚拟单位在请求前预留；结果未知按预留消耗，不自动返还。月度上限首次持久化，后续 fixture 可收紧，不能抬高绕过；跨月只改变新请求记账月份，批次/角色次数不重置。
- **恢复与保护**：事件、响应和计划只追加/创建，散列旁文件检测误改；补跑复用已有响应和 ID。候选/原文/fixture 或正式资料基线变化使原批次停止；包括已生成测试笔记在内的人工编辑均保留。散列用于检测意外变化，不是防篡改签名或远端持久化保证。
- **输出限制**：writer 只能创建 `sources/<papers|blogs>/test/<topic>/` 与 `reports/test/<topic>/` 文件，拒绝越界和符号链接。正式来源新版仅生成测试区独立更新建议，包含原 ID、路径、散列与版本，不改旧笔记。
- **检查模式**：默认校验正式来源；`--include-test` 同时严格校验测试来源，分区查重和计数，ID 全局唯一，Frontmatter 的研究关联不得跨区。测试回执与独立更新建议不作为正式研究证据。

执行记录是本地离线检查点；本轮由用户要求的普通 Git 提交同步到 GitHub。没有模拟“PR 已合并”，也没有实现线上游标、来源分页、真实计费、token 限制的服务端执行或云端故障恢复。`input_tokens`/`output_tokens` 是固定模拟用量，不能据此推断真实模型成本或质量。

## 后续接入顺序

真实来源采集测试已实现，模型仍为模拟。下一步按[ChatGPT 会员分析设计](chatgpt-analysis-handoff.md)验证官方授权、两个独立模型与用量边界，再考虑真实推理和受限 PR 自动入库。真实验收通过且另获启用授权后，才配置周二、周五北京时间 09:00 的定时入口。Insight、Writing 和公众号发布不在当前范围。
