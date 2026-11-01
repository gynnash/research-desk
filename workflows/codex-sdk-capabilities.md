# Codex SDK 能力核实

核实日期：2026-11-01。已核实官方发行包，并在当前 Mac 的独立 Python 3.12 环境真实接通 SDK、自有 SIWC 会员授权和独立模型审阅。真实验收只读取小型本地测试材料，没有采集或研究论文，没有启用定时任务。

可复查的通过回执：[codex-sdk-live-20261101-02](../reports/test/agent_memory/codex-sdk-smoke/codex-sdk-live-20261101-02/accepted.yaml)。本次生成与审阅分别使用 `gpt-6.1-sol`、`gpt-6-astra`，合计 4 次请求；此前未通过的验收另保留 5 次，本轮累计预留 9 次。原线程查询核对通过，新增请求为 0。它们是接入验收，不是研究成果。

## 发行基线

- Python 包：`openai-codex==0.163.0`，要求 Python `>=3.10`。
- 依赖：`pydantic>=2.12`、`packaging>=26.2`、`openai-codex-cli-bin==0.163.0`。使用发行包固定的 runtime，不自动选择已有桌面端可执行文件。
- wheel：`openai_codex-0.163.0-py3-none-any.whl`。
- SHA-256：`d151e3ff8188bc2c07a962855d598b93bf87a49ec3440810e45a5f2e1167d99e`。
- 公开元数据：`https://pypi.org/pypi/openai-codex/0.163.0/json`。PyPI 发行文件用于核实实际签名；产品与授权行为以文末官方文档为准。

## 实际公开接口

静态检查该发行包的 `openai_codex/__init__.py`、`client.py`、`api.py`、`models.py`、`_run.py`、`_approval_mode.py` 与生成类型，确认以下接口存在。这里记录发行包事实，不把假定参数当作 SDK API。

| 能力 | 已核实接口与边界 |
| --- | --- |
| 配置 | `CodexConfig(codex_bin, launch_args_override, config_overrides, cwd, env, client_name, client_title, client_version, experimental_api)`；均为实际 dataclass 字段 |
| 子进程环境 | `env` 是对 `os.environ.copy()` 的覆盖合并，**不是替换**；只传一个精简字典不能消除宿主已有敏感变量 |
| 初始化身份 | `client_name/title/version` 实际映射 `initialize.clientInfo`；SDK 默认身份不是 ResearchDesk，需要显式配置 |
| 创建线程 | `Codex.thread_start(...)` 支持 `model`、`model_provider`、`config`、`cwd`、`developer_instructions`、`sandbox`、`approval_mode` |
| 执行与流式事件 | `Thread.turn(...) -> TurnHandle`；句柄有 `thread_id`、`id`、`stream()`、`run()`、`interrupt()`；`Thread.run(...)` 直接收集结果 |
| 查询/恢复 | `Thread.read(include_turns=True)`、`Codex.thread_resume(thread_id, ...)`。恢复不等同新 turn；适配器不得读取私有 `_client` 实现自管协议 |
| 事件 | `Notification.method/payload`；读取 `turn/completed` 终态、最终 `item/completed`、token usage 和模型改路事件。不能把输出文字视为完成 |
| 返回 | `TurnResult` 有 `status`、`final_response`、`items`、`usage` 等；usage 的 total/last 是 token 统计，不是模型请求计数 |
| 审批 | `ApprovalMode.deny_all` 映射拒绝扩权的 `never`；默认值是 `auto_review`，不能依赖默认配置 |
| 实验能力 | `CodexConfig.experimental_api` 默认 `True`；正式适配应显式评估关闭，不能因 SDK 稳定就宣称启用的所有协议字段稳定 |

## 已实现的真实调用路径

```text
ResearchDesk 固定输入和角色任务
  → 官方 Python SDK / 配套 Codex runtime
  → 本机临时 Responses 网关
  → ResearchDesk 自有 SIWC 授权刷新与官方 /v1/responses
```

SDK 继续负责模型与工具往返循环。网关只做请求验证、逐次预算预留、授权转发和稀疏用量记录，不解析或派发 Agent 工具，不重写模型响应，不提供通用代理。

真实 OAuth 留在父进程。SDK 仅获得每次启动生成的本机 capability；该值不写文件、不进入工具环境，服务退出即失效。上游地址固定为官方 Responses，复用本人已有会员授权，不读取 Codex 桌面端或浏览器登录，不回退 API Key。

每个实际转发请求在共享锁内预留，新旧后端共计月度 100 次上限；失败、结果未知和重试均保留计数。每任务另有请求上限，示例为 3 次。真实模型标识和 token usage 从 `response.completed` 记录，任务数、turn 数、请求数分别保存。

## 已验收的本机权限

目前只支持 macOS。受控 wrapper 用 `/usr/bin/python3 -I` 清理继承环境后执行固定 runtime，支持 SDK venv 路径含空格；设置独立 HOME、CODEX_HOME 和运行目录。真实 OAuth 不进入该进程。

使用 Beta permission profile，而不混用旧 sandbox 设置：工具仅能读取固定输入，不能写入；文件系统其余部分按默认拒绝与最小系统路径配置，禁用工具网络、MCP、浏览器与无关技能。当前 runtime 的内置技能通过公开 `skills.config` 设置完整 `SKILL.md` 路径禁用。

原生 SDK `command/exec` 无模型探针已实际验证：输入可读不可写，合成宿主私有文件与 CODEX_HOME canary 不可读，工具环境没有 capability 或宿主秘密变量；宿主可连接同一本机测试服务，而沙箱工具不能连接。探针不触碰真实凭据文件，不消耗会员推理。

## 恢复边界

`start` 和 `continue_turn` 才能创建新 turn；`inspect/resume` 通过公开 `thread_resume/read` 核对原线程，使用请求上限为 0 的网关，即使误发推理 HTTP 也不能转发。跨实例查询已保存的真实线程，最终响应一致，月度计数保持 9。

当前活跃的 `TurnHandle` 可以请求中断；服务重启后，公开 SDK 无法按旧 turn ID 重新取得活句柄。此时只核对终态，无法确认时返回未知，不伪称已经取消，也不重新发送任务。

`preflight` 不读取授权、不启动进程、不推理；`live_ready` 仅表示版本、模块和本机配置齐备。具体账号模型访问以实际完成的请求为依据。Linux 等其他隔离平台尚未验收，明确阻塞，不降级为全盘权限。默认旧三 Agent 后端和调度开关不变。

## 离线契约

`MockCodexBackend` 使用显式 `scripts` 字典，按 `task_id` 优先、其次 `phase` 选择样例；每项提供 `events`、`status`、`final_response`，可另外提供 `usage`、`observed_model`、`model_request_count`。未提供用量即未知，不自动填 1。

模型读取多份文件可用多条 `item/started` / `item/completed` 样例事件演示；这仅验证业务处理，不声称真实 runtime 已读取文件。`status: blocked_unknown` 配合 `inspect_status: completed` 与 `inspect_final_response` 验证断线后核对已完成结果；没有远端状态则继续阻塞。`resume` 只检查原句柄；修订必须显式 `continue_turn`。只有脚本明确 `interrupt_status: interrupted` 才确认中断。

事件接收器抛出异常时立即传播；不会吞掉持久化失败继续运行。真实事件转换保留类型、ID、终态、usage 和模型改路，不持久化私有推理链、环境转储、工具参数或原始错误响应。

## 官方依据

- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)：稳定 Python SDK、版本要求与配套 runtime。
- [SIWC 接入 Codex app-server](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server)：自有 OAuth token、provider、客户端身份和刷新恢复。
- [App-server](https://learn.chatgpt.com/docs/app-server)：事件、线程与明确终态；裸命令/传输仍有实验性限制。
- [Permissions](https://learn.chatgpt.com/docs/permissions)：Beta 文件权限与旧 sandbox 设置的互斥，及本地命令权限的适用范围。

`model/list` 不证明账号具备某模型资格；上文回执只证明本次访问了对应模型，不能承诺其他用户或未来账号资格。官方 SDK 提供 Agent runtime，不自动继承 ChatGPT 网页工具与全部连接器。
