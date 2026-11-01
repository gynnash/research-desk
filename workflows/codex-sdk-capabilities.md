# Codex SDK 能力核实

核实日期：2026-11-01。只下载公开 wheel 到临时目录、校验 SHA-256 并静态检查源文件及类型；未安装到项目或共享环境，未启动 runtime、登录、读取用户凭证或调用模型。

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

## 尚未满足的真实执行条件

当前 `CodexBackend.preflight()` 始终返回 `live_ready: false`；安装 SDK、修改 YAML 布尔值均不能绕过。`start`、修订、查询、恢复与中断均返回明确阻塞结果，不启动 SDK 或读取授权。

1. **会员授权与子进程环境未验收。** 官方支持本应用 SIWC access token 通过 `ACCESS_TOKEN` 加 Responses provider 配置接入，不要求额外 Codex 登录。但 SDK 会继承宿主环境，尚需受控启动隔离，以及工具子进程不能读取 token 的无敏感探针验收。不得复制用户 Codex 或浏览器登录，不回退到 API Key。
2. **文件/工具权限未验收。** `cwd` 和 `Sandbox.read_only` 不能证明只读取任务输入。Beta permission profiles 可以描述读边界，但不能和旧 sandbox 配置混用；需要对所锁定 runtime 与运行平台实际验收。隔离 Codex 状态目录，禁用无关联网工具、MCP 与用户技能，保护 Git、SSH 和其他项目。
3. **逐次推理预算缺口。** 检查的公开 SDK 没有在每次内部模型请求前供宿主预留预算的回调，也没有可靠模型请求计数。一个任务/turn 可能多次推理，不能记为一次调用。token 汇总不能履行已有每月 100 次请求硬上限；在预算方案被明确调整或找到经核实接口前，不接通真实执行。

这三个门槛是未完成的实现与验收条件，不能用配置自我声明通过。当前适配器只提供公开协议、发行元数据预检和显式阻塞，**不宣称已接通会员 Codex**。现有会员客户端与生产流程不受影响。

## 离线契约

`MockCodexBackend` 使用显式 `scripts` 字典，按 `task_id` 优先、其次 `phase` 选择样例；每项提供 `events`、`status`、`final_response`，可另外提供 `usage`、`observed_model`、`model_request_count`。未提供用量即未知，不自动填 1。

模型读取多份文件可用多条 `item/started` / `item/completed` 样例事件演示；这仅验证业务处理，不声称真实 runtime 已读取文件。`status: blocked_unknown` 配合 `inspect_status: completed` 与 `inspect_final_response` 验证断线后核对已完成结果；没有远端状态则继续阻塞。`resume` 只检查原句柄；修订必须显式 `continue_turn`。只有脚本明确 `interrupt_status: interrupted` 才确认中断。

事件接收器抛出异常时立即传播；不会吞掉持久化失败继续运行。真实事件转换保留类型、ID、终态、usage 和模型改路，不持久化私有推理链、环境转储、工具参数或原始错误响应。

## 官方依据

- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)：稳定 Python SDK、版本要求与配套 runtime。
- [SIWC 接入 Codex app-server](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server)：自有 OAuth token、provider、客户端身份和刷新恢复。
- [App-server](https://learn.chatgpt.com/docs/app-server)：事件、线程与明确终态；裸命令/传输仍有实验性限制。
- [Permissions](https://learn.chatgpt.com/docs/permissions)：Beta 文件权限与旧 sandbox 设置的互斥，及本地命令权限的适用范围。

`model/list` 不证明账号具备某模型资格；本轮未做真实推理，模型资格保持未验证。官方 SDK 提供 Agent runtime，但不自动继承 ChatGPT 网页工具与全部连接器。
