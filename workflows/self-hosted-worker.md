# 自托管研究执行器：当前 Mac 与远程主机

研究执行器使用用户自己的官方 ChatGPT 会员，在仓库外保存 Python 环境和授权。GitHub 负责手动派发、离线检查与版本同步。本阶段只支持手动任务，研究结果及失败检查点均属于测试资料，不启用周二、周五北京时间 09:00 的定时任务，不正式入库、不启动 Writing，也不发布公众号。

## 当前 Mac

[`config/runtime.yaml`](../config/runtime.yaml) 选择当前 Mac，分别配置 runner、Python venv 和会员 profile。三者必须在仓库与 Obsidian Vault 之外且互不包含；`membership.profile: null` 沿用本机 ResearchDesk 的既有仓库外授权目录，不读取 Codex 或浏览器凭据。检查与安装入口由 [`researchdesk_runner.py`](../scripts/researchdesk_runner.py) 提供：

```sh
.venv-membership/bin/python scripts/researchdesk_runner.py doctor
.venv-membership/bin/python scripts/researchdesk_runner.py setup
```

`doctor` 不读取令牌内容、不联网或调用模型；`setup` 会在当前主机安装依赖、校验官方 runner 下载散列、向当前 GitHub 仓库注册，并安装/启动用户服务。Mac 使用当前登录用户的 LaunchAgent，无需 sudo。安装要求本机 Python 3.9+、Git、GitHub CLI、curl/tar 可用，且 GitHub CLI 已获该仓库 runner 管理权限；注册令牌只在内存传递，不放在命令参数或仓库中。

## 手动健康检查与研究

[`ResearchDesk manual cycle`](../.github/workflows/researchdesk-manual.yml) 仅有 `workflow_dispatch`，仅允许 `main`；自托管 job 需要 `self-hosted` 与 `researchdesk` 标签。默认 `health` 使用 `runtime.yaml` 的 Python 与 profile，检查官方授权、账户模型目录和配置模型可用性，**不调用推理**，不创建研究产物，也不需要上传 artifact 才能成功。

在 GitHub Actions 页面选择工作流并运行，或在已授权的 GitHub CLI 中执行：

```sh
gh workflow run researchdesk-manual.yml --ref main -f operation=health
```

健康检查实际通过后，可使用 `discover` 只发现资料，或 `run` 执行有预算限制的真实 Research → Insight：

```sh
gh workflow run researchdesk-manual.yml --ref main \
  -f operation=run -f cycle_id=cycle-agent-memory-20261019 \
  -f config=config/cycles/agent-memory.yaml
```

同一输入已完成时复用缓存；恢复失败轮次必须保持相同 `cycle_id` 和配置。省略 ID 使用稳定的 `agent-memory-gh-<GitHub run ID>`，同一次 GitHub 运行的重跑不换 ID。`fail_after=after_research` 仅用于显式断点验收，正常运行保持 `none`。真实状态以实际运行及各阶段回执为准，不预设健康检查或研究已通过。

## 凭据、工作目录与保存

- 自托管分析 job 的 `GITHUB_TOKEN` 只取得 `contents: read`，检出后不保留该 Git 凭据，使用仓库外会员 profile；日志只打印脱敏状态，不打印模型响应、原文、profile 路径或令牌。当前 Mac 的用户环境仍有 GitHub CLI/Keychain 等既有授权，因此不能声称整个主机没有 Git 写权限；可信代码和受控分支仍是必要边界。
- 工作目录是 runner 自己的 `_work/.../researchdesk-worker`，与现有 Obsidian Vault 分开。不得让 checkout 指向 Vault；不删除本地笔记、不修改 Obsidian 配置。运行开始读取 `main` 中全部历史会员请求事件，继续累计预算。
- 每轮只允许新增 `reports/test/<topic>/{cycles,research-batches,insight-runs}/<cycle-id>/`、`insights/test/<topic>/<cycle-id>/` 和 `articles/test/<topic>/<cycle-id>/`。预算预留、未知请求及失败前的有效检查点也在这些目录，不能只保存通过报告而丢弃已消耗请求。
- 研究失败后仍尝试导出有效测试文件，检查 YAML 配对散列、路径、现有文件未变及常见凭据/本地绝对路径泄漏，再保存为保留 14 天的 artifact。硬断电、磁盘损坏或作业被强杀仍可能来不及导出；runner 工作目录保留现场，不能直接清理后换批次重试。
- 单独的 Ubuntu 发布 job 取得 `contents: write`，不接触会员 profile。它对照原有 Git 文件散列检查最新 `main`，只创建新测试文件；已有同字节文件复用，内容冲突或基线变化停止。规范检查通过后普通提交推送，不强推、不修改正式资料或原笔记。
- 推送被仓库保护或并发修改阻止时，保留 artifact 与 runner 工作目录，不绕过规则。发布成功后 Obsidian 按既有 Git 同步拉取。未发布的其他轮次文件会阻止开始新研究，应先恢复原轮次或从 artifact 恢复检查点。

工作流共用单个并发组，运行中不自动取消。当前预算和主题锁按仓库根路径区分，**不能阻止另一个克隆目录同时调用会员**；部署后应统一从这个 workflow 派发，不同时在 Vault、其他克隆或第二台主机启动真实研究。若以后需要多工作台并行，须另做账户级协调，不能把当前配置说成全账户额度硬限制。

自托管 runner 只运行自己信任的 `main` 代码，不运行 PR 或 fork 的代码。开源发布代码时，用户应在自己控制的仓库部署执行器；把个人 Mac 的 runner 暴露给不可信工作流会使本机资料和授权面临风险，详见 [GitHub 自托管安全说明](https://docs.github.com/en/actions/reference/security/secure-use#hardening-for-self-hosted-runners)。标签路由依据[官方 runner 说明](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/use-in-a-workflow)。

## 换成远程主机

[`config/examples/runtime-remote.yaml`](../config/examples/runtime-remote.yaml) 提供长期主机配置。用户先通过自己的 SSH 方式连接主机，克隆自己的仓库、配置 GitHub CLI，再在**该主机**选择 remote 配置并执行 `doctor/setup`。ResearchDesk 不发起 SSH、不复制本地令牌或登录会话；各用户自行在合资格主机完成官方会员授权。远程 Linux 的服务安装/启动需要预先安排 `sudo -n` 权限，远程 Mac 使用用户服务。

代码和轮次配置可共用，runner、venv 和 profile 路径属于各部署主机；不要把当前 Mac 的绝对路径当远程通用配置。部署资格仍应按官方会员适用范围分别核实。本地 Mac 需要登录用户会话、网络和机器在线；休眠、关机或未登录可能让任务排队，不能据健康检查一次通过承诺长期可用。

无人值守运行、故障补跑与同步均验收后，再另外启用每周二、周五北京时间 09:00；当前工作流没有 `schedule`。
