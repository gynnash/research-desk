# 真实来源采集验收记录

> TEST：真实来源采集，分析与审阅均为模拟，不可作为正式研究结论。

验收日期：2026-10-19。首批 ID 沿用启动时的 `real-sources-20261018`，实际采集时间以各条 UTC `captured_at` 为准。当前只验证采集和模拟流程，不代表 ChatGPT 已完成研究或独立审阅。

## 真实采集

| 来源 | 本次原文 | 保存范围 |
| --- | --- | --- |
| arXiv | [Beyond Downstream QA: Rethinking How We Evaluate Agent Memory](https://arxiv.org/abs/2610.22209)，v1，首次发布 2026-10-15。 | 官方 API 摘要；`abstract_only`。 |
| Letta | [Why Memory Isn't a Plugin](https://www.letta.com/blog/why-memory-isnt-a-plugin/)，Sarah Wooders，2026-04-03。 | 提取正文计算散列，保存短节选；无可靠原文修订日期。 |
| LangChain | [Context Engineering: How Deep Agents Remember](https://www.langchain.com/blog/context-engineering-deep-agents-remember)，Jess Weng，2026-10-14。 | 提取正文计算散列，保存短节选；dateModified 与首次日期分开。 |

首批三源均成功：arXiv API 返回 5 条候选、选取 1 条；Letta 列表解析 28 个链接、LangChain 解析 19 个链接，各用一个已配置的稳定验收种子。列表数量不是完整扫描或研究数量。

## 验收结果

- 84 项运行/采集自动验收通过，另有 14 项正式/测试隔离验收通过，共 **98 项**；自动验收使用固定传输和临时仓库，不依赖模型或网络。
- 首批新增 3 份测试记录，6 次模拟请求、12 个虚拟单位；真实模型调用为 0。
- 新批次重新读取三源，识别 3 份 `unchanged`，0 新来源、0 新增模拟请求。见[第二批回执](../real-sources-20261019-check/summary-attempt-1.md)。
- 两个已完成批次均使用禁止网络的传输对象复跑成功，验证缓存复用不重新抓取或调用模拟模型。
- 正文和 dateModified 的更新识别由受控样例验证：变化只产生独立更新建议，旧记录字节保持不变。本次两轮真实抓取未观察到原文变化，没有人为修改正式或已采集资料来伪造真实修订。
- 删除或改写采集检查点、分析清单/事件/摘要、交接包时会停止，不把缺失的分析链当作缓存成功。
- 正式来源仍为 2 条、legacy 豁免仍为原来的 1 条；原有正式研究资料、主题配置、模板和既有测试资料保全。无 GitHub workflow、真实模型、会员授权或公众号发布。

来源元数据、短证据及散列见[采集回执](receipt-attempt-1.yaml)；后续可用的[ChatGPT 交接包](analysis-bundle-attempt-1.md)仍标记待分析，没有发送给任何真实模型。

复现命令与边界见[真实采集说明](../../../../../workflows/real-source-collection.md)。会员接入优先评估官方 Sign in with ChatGPT；账户/应用资格、两个模型、主机与额度限制另行验收，本轮不作其已开通的证明。
