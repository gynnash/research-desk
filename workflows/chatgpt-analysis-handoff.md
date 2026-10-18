# ChatGPT 会员分析接入与资料交接设计

核实日期：2026-10-18。状态：设计；本轮仅真实来源采集与模拟模型验收，没有会员登录、真实分析、OAuth 客户端或定时任务。

## 1. 方向与已确认边界

未来优先让 Research、Insight、Writing 及独立审阅使用用户的 ChatGPT 会员能力。采集器只负责发现、身份、原文证据和变更识别；模型后端通过明确接口消费证据，不直接取得 Git 写权限。

- **会员程序接入已有官方路径**：Sign in with ChatGPT 支持符合条件的 Plus/Pro 用户授权参与应用使用会员额度。开源应用可走官方 OAuth 流程，不要求普通 API Key；本项目的账户、应用和工作区资格仍需实际验证。[官方 Quickstart](https://developers.openai.com/siwc/quickstart)
- **不能把会员等同普通 API 余额**：Work 与 Codex 共享会员用量；普通 API 的 token 价格与订阅用量分开。会员授权推理是有单独权限与适用范围的官方路径，不能将普通 API Key 调用记成会员内调用。[官方会员用量说明](https://learn.chatgpt.com/docs/pricing)
- **未来默认后端**：先评估本地或符合条件的自托管开源执行器，通过官方 Sign in with ChatGPT 授权后分析。官方区分本地/开源与付费、远程托管应用；后两类不能仅凭本地成功便认定获准。[官方适用范围](https://developers.openai.com/siwc/token-sharing-open-source)
- **GitHub-hosted runner 尚未确认**：官方已有 self-hosted VM 的凭据管理流程，但这不证明临时 GitHub-hosted runner、刷新令牌持久化和本项目资格已受支持。本轮不导出本机登录态、不上传凭据，也不承诺 Actions 已能直接调用会员。[官方 self-hosted VM 指南](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms)

因此未来可先采用“GitHub 采集与排队 → 获授权的本地会员分析/审阅 → 结果校验 → 受限入库”。Actions 自动触发会员分析的运输、主机可用性和认证生命周期另行验收；当前仍只运行 `mock-*` 后端。

## 2. 采集与模型解耦

后续交接包按 `<topic>/<batch-id>/` 隔离，保留稳定候选 ID 与不可变证据版本；不因切换模型重建身份或重置失败记录。拟定接口如下，本轮不据此启用模型后端：

| 文件/内容 | 必须包含 |
| --- | --- |
| `manifest.yaml` | 包版本、主题、批次、基线 commit、候选身份、原文 URL/版本、文件路径与 SHA-256、采集时间、覆盖范围、提示词版本。 |
| 证据材料 | 规范化元数据、短摘录、章节/段落位置、证据 ID、可回查的原文链接及证据散列；明确 `abstract_only`、节选或全文范围。 |
| 研究请求 | 研究问题、相关历史资料及散列、允许的输出结构、事实与推断区分、证据不足时停止的条件。 |
| 审阅请求 | 同一原文证据、候选全文/散列、研究请求与历史输入；不接受只有研究模型转述的材料。 |

模型只把网页内容当材料；文内指令不能改变权限、来源白名单或输出路径。上传/交接的范围以清单为准，不包含整个 Obsidian 库、密钥或完整第三方文章归档。

## 3. 官方会员后端的实施门槛

1. 后续单独实现官方授权流程：用户在浏览器完成登录、同意会员用量权限；验证身份与授权范围，安全保存应用自己的受保护凭据。身份登录成功本身不能放行推理。当前不读取、复用或逆向浏览器 Cookie、现有 Codex session token 或未公开接口。[官方注册与授权](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
2. 获取所选账户的可用模型目录，选择两个不同的具体 model ID，分别用于生成与独立审阅；记录请求选择和实际返回身份。目录可见不等于本项目已验收，需在用户另行授权后分别验证真实推理；身份未知、模型相同或审阅模型不可用均停止，不能自审。[官方模型与推理](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
3. 该会员路径使用官方 Responses API，要求 `store: false`、`stream: true`，仅完整终态才算完成；当前预览不支持 `max_output_tokens`、持久会话及部分托管工具。不能直接套用普通 API 的参数或令牌硬上限；先设计客户端输入、请求次数、时间与额度控制，明确无法硬限输出的部分。[官方预览限制](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
4. 用量记录区分 `mock`、`chatgpt_plan` 与普通 API。会员实际额度/费用不可观测时保留未知值，不伪造零费用或将模拟单位换算成会员 tokens；沿用请求前预留、有限修订及未知结果保守记账。会员限额、授权撤销、刷新失败进入待补跑，不自动转付费 API。[官方错误与恢复](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)

本轮不选择真实模型、不实现上述客户端，也不验证用户会员等级、余额、授权或真实调用成功。

## 4. ChatGPT / Work 文件交接作为过渡

在官方会员后端接通前，可以在另行授权的实际分析阶段，由用户把清单与材料上传到 ChatGPT 项目，或让具备相应权限的本地 Work 读取限定目录。Work 官方支持文件与插件；项目共享上下文不等于本地文件自动同步，GitHub 连接也须核对实际仓库/提交访问。[Work 能力](https://learn.chatgpt.com/docs/get-started-with-work)、[项目与文件边界](https://learn.chatgpt.com/docs/projects)

该入口是交互分析的过渡，不替代最终定时研究目标，也不能宣称已接通 Actions 无人值守分析。本轮不新建项目、发送分析任务或执行真实分析。

Research、Insight、Writing 分别返回限定格式的分析文件；审阅在独立上下文、不同具体模型下返回 `pass / revise / reject / blocked`、问题及证据 ID。只换对话或提示词不满足不同模型要求；界面未提供可信模型身份时，回执标记 `model_identity_unverified`，不能正式自动入库。

## 5. 返回校验与受限入库

后续结构化回执须绑定包 ID、候选 ID、输入/证据/候选 SHA-256、基线、提示词版本、实际生成与审阅身份、修订次数及可获得的用量。导出文件内自称的身份不是认证证明；来自交互入口的结果需保留可信执行记录，否则仅作为待验证草稿。

入库器先验证结构、完整身份、来源及证据引用、散列、预算、独立审阅和路径白名单；任一不满足即 `blocked`。证据或候选改变使旧审阅失效；已有文件保持只读，更新只生成独立建议，补跑沿用身份、证据版本和已消费额度，不重置一次修订限制。

本轮采集结果、模拟分析和回执只允许进入各研究方向 `test` 目录；`test_accepted` 不等于真实模型审阅通过或正式 `accepted`。正式来源、报告、洞察、文章、Obsidian 配置均不由测试覆盖。未来正式入库仍须满足[总体架构](three-agent-architecture.md)的自动审阅与受限合并门禁，公众号发布另行授权。

验收时分别确认：来源包可重放；正式文件散列未变；模拟用量明确；重复运行不重复研究；新版本只出更新建议。会员资格、真实模型隔离、OAuth 恢复、runner 支持与自动合并是后续独立验收项，本轮结果不作其成功证明。
