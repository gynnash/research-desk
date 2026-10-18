# Research Agent 离线验收记录

> TEST：离线虚构样例，不可作为正式研究证据。

- 验收日期：2026-10-18。
- 输入：[固定虚构样例](../../../../workflows/test/agent-memory/fixtures/offline.yaml)。
- 范围：离线运行骨架、模拟模型审阅、测试目录隔离；不代表真实模型质量、GitHub 自动入库或定时任务已验收。

## 结果

| 检查 | 结果 |
| --- | --- |
| 运行骨架自动验收 | 38 项通过；每项在临时仓库执行。 |
| 资料隔离与校验器验收 | 14 项通过；覆盖测试路径、Schema、引用隔离及旧资料豁免边界。 |
| 固定样例演练 | 2 份 `test_accepted`、1 份 `rejected`；其中博客经历一次修订和复审。 |
| 模拟调用与用量 | 累计 8 次模拟请求、16 个虚拟预算单位；实际模型 API 费用为 0。 |
| 同批重复运行 | ID、已有结果及累计用量保持不变，仅追加编号回执。 |
| 资料与配置保护 | 开始前已跟踪的 18 个资料、配置及模板文件散列不变；正式来源仍为 2 条，原有 legacy 豁免仍为 1 条。 |
| 测试目录 | 8 处 `test/` 均分别保留 `agent-memory/` 与 `agent-rl/`；后者仍停用。 |
| 运行限制 | 没有真实模型适配器、抓取网络请求、正式资料 writer、Git/PR 执行器、GitHub workflow 或公众号发布。 |

[首轮回执](summary-attempt-1.md)与[重复运行回执](summary-attempt-2.md)保留累计账本。测试来源分别位于 `sources/papers/test/agent-memory/` 和 `sources/blogs/test/agent-memory/`，没有加入正式研究资料。

## 可复现命令

在仓库根目录执行：

```sh
python3 -m unittest discover -s tests -v
python3 workflows/test/agent-memory/test_validate_isolation.py
python3 scripts/researchdesk_offline.py --fixture workflows/test/agent-memory/fixtures/offline.yaml --batch-id offline-acceptance-20261018
python3 workflows/validate.py
python3 workflows/validate.py --include-test
git diff --check
```

自动验收覆盖：全库及历史身份冲突、URL 中的 arXiv/DOI、拒绝和更新不重复研究、不同模型及完整审阅输入、一次修订反馈、无效 pass、人工编辑保全、未知费用预留、月度预算和跨批限制、发布前中断/预留后中断补跑、路径越界及符号链接拒绝。模型响应完全来自 fixture，测试不建立网络连接。
