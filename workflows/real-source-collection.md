# 真实来源采集与模拟分析验收

> 本文保留早期模拟采集阶段的验收记录。当前论文获取与实际阅读范围以[全文阅读规范](fulltext-reading.md)为准；新轮次已支持官方 HTML/PDF，不再固定为仅摘要。

当前阶段已接入 arXiv、Letta 和 LangChain 的官方公开来源，只写 `test/<topic>`。模型仍为 `mock-*`，没有会员登录、OAuth、真实模型推理、正式研究资料写入、GitHub workflow 或公众号发布。

采集与模型分开：[来源适配器](../scripts/researchdesk_sources.py)负责 HTTPS、解析与正文散列；[采集入口](../scripts/researchdesk_collect.py)负责方向配置、不可变检查点、跨批比较和交接包；[原模拟运行骨架](../scripts/researchdesk_offline.py)负责模拟分析/审阅、身份、预算和测试输出。依赖仍为 Python 3.9+ 标准库和现有 PyYAML。

## 来源与阅读范围

| 来源 | 当前采集方式 | 范围与限制 |
| --- | --- | --- |
| arXiv | 官方 Atom API，主题关键词查询，按更新时间排序；读取标题、作者、首次发表/更新、DOI、基础编号与实际 vN。 | 当前只取摘要，明确标记 `abstract_only`。API 失败时可使用配置中的官方摘要页种子，回执标为降级，不能冒充搜索成功。 |
| Letta | 官方博客列表与文章；当前配置一个明确的验收种子。 | 使用可见作者、发布日期、canonical；不能用网页抓取时间或 HTTP Last-Modified 冒充作者更新时间。 |
| LangChain | 当前官方 `www.langchain.com/blog` 列表与文章；旧 RSS 若返回 HTML 不作 feed。 | 主文章署名优先，排除相关文章卡片作者；区分 datePublished 和 dateModified。 |

采集器暂不做完整时间窗游标、全站历史分页或定时发现。每批最多选 3 份；博客种子用于稳定验证，列表发现数量不等于全部经过研究或覆盖某个时间段。HTML 正文只在内存提取和计算散列，落盘最多 25 个空格分词的词、最多 400 字符的短节选及必要元数据，不保存整页或整篇文章。

解析器可提取完整博客正文，但落盘和传给模拟模型的只是短节选，所以笔记仍标 `excerpt`；`extraction_coverage` 与实际分析输入范围分开。模拟摘要只说明采集状态，不编造论文贡献、实验结果或真实模型审阅意见。

HTTP 只允许固定官方 HTTPS 主机，拒绝凭据 URL、非公共地址、未验证重定向和不支持的内容类型；设置超时、大小和有限重试，arXiv 请求至少相隔 3 秒。布局异常、403/429 等失败保留到每源回执，不能当作“零新增”。参见 [arXiv API 手册](https://info.arxiv.org/help/api/user-manual.html)。

## 配置、产物与查重更新

配置在 [config/test/agent-memory/collection.yaml](../config/test/agent-memory/collection.yaml)。方向必须已登记且启用；`agent-rl` 保持停用。配置强制 `analysis_backend: mock`，`future_analysis_backend: chatgpt_membership` 仅记录下一阶段方向，不会执行会员授权或推理。

- 采集计划、按来源缓存、短证据和回执：`reports/test/<topic>/collections/<batch>/`。
- 模拟运行账本及独立更新建议：`reports/test/<topic>/collect-<batch>-a<n>/`。
- 新测试来源：`sources/<papers|blogs>/test/<topic>/<id>.md`。正文横幅为“真实来源采集，分析与审阅均为模拟”，与原虚构样例区分。
- ChatGPT 交接包：每次采集的 `analysis-bundle-attempt-<n>.md` 和 `analysis-manifest-attempt-<n>.yaml`，记录原文链接、范围、散列及待分析要求；`sent_to_chatgpt: false`。

查重同时比较 arXiv/DOI/保守 URL 规范，读取正式库、测试库和过去的处理记录。已有人工作品首次抓取但没有上游正文基线时，仅建立基线，不将笔记与原文的文字差异当作原文修订。

后续比较规范化正文散列与元数据/明确修订线索，分别记录 `new / unchanged / updated / duplicate / blocked`。正文或元数据变化只产生独立更新建议，保留原 ID、路径、旧文件散列与新旧来源线索；不覆盖旧笔记，不把散列变化断言为作者确认的修订日期。身份键冲突为 `partial`，不能误记全部成功。

同批完整运行可直接复用采集与模拟结果，不再联网或追加模型调用。缓存复用前验证源检查点、输入 fixture、分析清单/事件/终态/摘要与交接包散列；缺失或人工改写会停止并保全现场。失败源补跑只重取失败源；成功源缓存不重抓。模拟运行仍遵守原来的 ID、一次修订与预算规则。

## 可复现命令

在仓库根目录执行：

```sh
python3 -m unittest discover -s tests -v
python3 workflows/test/agent-memory/test_validate_isolation.py
python3 workflows/validate.py
python3 workflows/validate.py --include-test
git diff --check
```

以下命令会访问真实来源；同批已完整完成时使用缓存，新批次才重新读取来源：

```sh
python3 scripts/researchdesk_collect.py --config config/test/agent-memory/collection.yaml --batch-id real-sources-20261018
python3 scripts/researchdesk_collect.py --config config/test/agent-memory/collection.yaml --batch-id real-sources-20261019-check
```

首批 3 份新记录、6 次模拟请求、12 个虚拟预算单位。重新读取三源的第二批识别 3 份 `unchanged`，没有新增测试来源或模拟模型调用；真实模型调用始终为 0。更新识别通过受控正文/修订日期变化样例验证，没有声称观察到本次原文真实修订。实际回执和验收记录保存在相应 `test` 批次中。

## ChatGPT 会员分析方向

未来优先采用官方 **Sign in with ChatGPT** 会员授权后端，详见[会员分析设计](chatgpt-analysis-handoff.md)。当前只导出交接包，没有把它发送到 ChatGPT，也没有读取会员、浏览器或 Codex 登录凭据。

会员账户/客户端资格、可用的两个不同模型、额度与认证恢复、执行主机需要独立验收；GitHub 采集不等于 GitHub-hosted runner 已能调用会员。官方会员预览的参数限制也不同于普通 API，因此不自动回退付费 API，暂不实现或启用真实分析与定时任务。
