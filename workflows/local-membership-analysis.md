# 本地 ChatGPT 会员分析与独立审阅

本轮将官方 ChatGPT 会员授权接到本地 ResearchDesk，先测试一篇已采集论文的摘要研究。运行资格和结果必须由实际授权及回执证明，本文不预设账户等级、可用模型或审阅结论。上一阶段的模拟测试保持原样。

当前真实验收状态（2026-10-19 北京时间）：官方 OAuth 身份验签与会员推理权限通过，账户目录实际返回 7 个模型。`gpt-6-luna` 研究、`gpt-6.1-sol` 独立审阅均收到完整推理终态，审阅 `pass`，无修订，共 2 次请求、响应合计报告 2,576 tokens。同批补跑返回 `cached: true`，请求数保持 2。详见[摘要研究报告](../reports/test/agent-memory/membership/member-arxiv-20261019/report.md)、[真实回执](../reports/test/agent-memory/membership/member-arxiv-20261019/receipt.yaml)及[验收说明](../reports/test/agent-memory/membership/member-arxiv-20261019/acceptance.md)。会员等级、剩余额度和金额没有可核实结果，保持未知；没有将这些 tokens 换算成额度百分比或费用。

## 范围与前提

- 只分析已采集的 arXiv `2610.22209v1`，论文为 *Beyond Downstream QA: Rethinking How We Evaluate Agent Memory*。[arXiv 原始来源](https://arxiv.org/abs/2610.22209v1)
- 重新取得完整摘要，在内存中分别交给研究模型和独立审阅模型；先核对版本、元数据及摘要散列与旧采集回执一致。仅提供摘要，不能声称已核验论文全文或实验。
- 模型目录来自当前已授权账户，研究与审阅必须使用不同的实际模型 ID；审阅也获得同一份原始摘要，不能只读研究模型的转述。
- 只新增 `reports/test/agent-memory/membership/<batch-id>/` 中的报告、清单、检查点和回执。已有正式资料、测试来源和人工笔记均不覆盖；不迁移旧资料，不修改 Obsidian 配置。
- 不创建或启用定时任务，不调用 Insight/Writing 自动化，不创建自动入库 PR，也不发布公众号。

本地后端使用官方 Sign in with ChatGPT 开源应用授权流程；这与普通 API Key 计费分开，也不借用 Codex、浏览器或其他应用的登录令牌。本地成功不证明 GitHub-hosted runner 或远程托管应用已获授权。[官方适用范围](https://developers.openai.com/siwc/token-sharing-open-source)

## 登录与资格核实

用户在官方浏览器页面完成登录及会员用量授权。后端使用本应用的注册身份与 PKCE，核验回调、ID Token 签名、发行者、受众、有效期及 nonce；身份登录成功后，还必须确认授权包含 `chatgpt.tokens.use.direct`。[官方授权说明](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)

授权文件必须保存在仓库和 Obsidian Vault 之外，限制为当前用户可读写；不可提交、复制进测试回执或上传到 Actions。仓库只保留脱敏资格结果、模型选择和研究运行记录。`.gitignore` 是误操作防御，不能替代仓库外存储。

资格判断依次为：官方登录及令牌验证成功、获得会员推理权限、读取该账户可用模型目录、两个不同模型分别完成真实推理。不能用模型目录可见、文档列出的模型、模型自述或现有 Codex 设置代替最后一步。缺少权限、目录不足两个模型或实际返回身份无法核实都停止；不会自动改用普通付费 API。[官方模型与推理](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)

## 小规模用量限制

| 控制 | 本轮限制 |
| --- | --- |
| 资料 | 一篇已采集论文，只读摘要；摘要最多 10,000 字符 |
| 每次请求输入 | 指令与材料合计最多 16,000 字符 |
| 每批真实推理 | 默认最多 4 次，可调低到 2 次；包含研究、审阅、最多一次修订及重新审阅 |
| 月度累计 | 同一知识库 Agent Memory 真实分析最多预留 10 次；结果未知也占用预留次数 |
| 单次客户端等待 | 最多 120 秒 |
| 单次客户端输出 | 最多 12,000 字符，超过时停止接收并保留未知请求记录 |
| 原文持久证据 | 合计最多 25 个英文单词的摘录、摘要/句子散列与定位；完整摘要只作内存输入 |

会员端使用 `store: false`、`stream: true` 的官方 Responses API，只在收到完整 `response.completed` 终态后使用结果。当前会员预览不支持 `max_output_tokens`；这里的输出字符和时间限制是客户端停止条件，不能保证服务端生成 token 的硬上限，也不能据此承诺会员额度消耗上限。[官方预览限制](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

每次请求前先追加不可变预留事件，成功后保存结果与用量；缺少可核实 token、余额或金额时写未知值。会员用量不按模拟单位或普通 API 价格换算。若授权撤销、限额、网络中断、超时或输出超限导致结果未知，保留预留且停止，不自动重发或切换计费方式。[官方恢复说明](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)

## 运行

在仓库根目录准备独立环境，不需要数据库或 Agent 框架：

```sh
python3 -m venv .venv-membership
.venv-membership/bin/python -m pip install -r workflows/requirements-membership.txt
```

需要 Python 3.9+、PyYAML 和用于官方 ID Token 签名验证的 PyJWT/cryptography。下面使用本机仓库外的授权目录；`--profile-dir` 指目录，不是一个 JSON 文件。先查状态，需要授权时再登录，然后读取当前账户的可用模型：

```sh
researchdesk_profile_dir="$HOME/Library/Application Support/ResearchDesk/chatgpt"
.venv-membership/bin/python scripts/researchdesk_membership.py \
  --profile-dir "$researchdesk_profile_dir" status
.venv-membership/bin/python scripts/researchdesk_membership.py \
  --profile-dir "$researchdesk_profile_dir" login
.venv-membership/bin/python scripts/researchdesk_membership.py \
  --profile-dir "$researchdesk_profile_dir" models
```

`login` 打开系统浏览器并只监听本机回调；用户自行完成官方登录和授权，不向终端、对话或模型提供密码及验证码。未完成时不能继续推理。状态输出中的身份和权限标志仍需结合实际模型目录及推理终态判断，不能当作余额或会员等级证明。

若系统浏览器无法展示授权页，使用 `--manual-browser login` 保持回调监听，由本地应用读取提示的私有 `authorization.json` 并打开其中的官方授权链接。该临时文件权限为 `0600`，只含授权 URL 和有效期，不含 PKCE verifier 或令牌，结束后自动清理；不要复制进仓库。第三方单点登录（例如 Google）由用户自行完成，后端只接收 OpenAI 的最终回调。

确认授权文件位于仓库外，并从该账户目录选择两个不同的实际模型后执行：

```sh
.venv-membership/bin/python scripts/researchdesk_analyze.py \
  --profile "$researchdesk_profile_dir" \
  --receipt reports/test/agent-memory/collections/real-sources-20261018/receipt-attempt-1.yaml \
  --batch-id member-arxiv-20261019 \
  --research-model RESEARCH_MODEL_FROM_ACCOUNT_CATALOG \
  --review-model DIFFERENT_REVIEW_MODEL_FROM_ACCOUNT_CATALOG \
  --max-calls 4
```

分析入口的 `--profile` 同样接收上述授权目录；模型大写占位符需替换为本机已验证的值，示例不会从占位符推断模型可用性。正式试跑前应先核对目录和请求次数上限。

## 结果与补跑

批次目录保存：

- `manifest.yaml`：源采集回执与散列、摘要证据版本、实际账户模型目录、选定模型、提示词版本、预算及已有笔记散列。
- `events/`：请求预留、实际完成身份和可获得的用量，按序追加。
- `checkpoints/`：绑定输入的研究与审阅响应，附完整性散列。
- `report.md`：带 TEST 标识的摘要级研究，区分原文事实、作者声称及我们的推断，保留原文链接与局限。
- `receipt.yaml`：状态、实际模型、修订次数、请求计数、报告散列及已有笔记保护结果；即使审阅通过也保持 `production_accepted: false`。

模型返回 `pass / revise / reject / blocked`，程序再校验结构、每条主张的证据支持、摘要范围和不同模型身份。只有独立审阅及规则校验均通过才记为 `test_accepted`；它只证明这一份摘要级测试通过，不等于正式入库或全文结论成立。

安全补跑沿用相同批次、模型、证据及请求上限，已完成结果从校验过的检查点复用，不重复调用。相同证据不能另起批次重置预算；资料、模型或预算发生变化时旧回执不能复用。若已有未知请求，程序停止并要求核对原批次；本轮不提供自动清除预留或盲目重试。已有文件被人工修改时停止，保留修改内容。

## 可复现校验

以下检查使用模拟传输和固定样例，不调用真实模型：

```sh
.venv-membership/bin/python -m unittest discover -s tests -v
.venv-membership/bin/python workflows/test/agent-memory/test_validate_isolation.py
.venv-membership/bin/python workflows/validate.py
.venv-membership/bin/python workflows/validate.py --include-test
git diff --check
```

真实验收还需检查该批次回执：授权及账户目录已实际核实；研究、审阅返回不同的实际模型；原摘要绑定旧采集回执；请求次数不超限；仅 test 目录新增研究产物；已有笔记散列保持一致。没有登录或完整真实终态时，只能报告后端与离线检查已完成，不能宣称真实会员研究通过。
