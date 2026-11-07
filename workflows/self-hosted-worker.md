# 一条命令部署自托管执行器

GitHub Actions 按时派发任务；用户自己的 Mac 执行采集、逐篇 Research 和 Codex Insight。runner、SDK 环境与会员凭据位于仓库及 Obsidian Vault 之外，研究与用量保存在同一个持久工作台中。新版 SDK 当前支持 macOS；远程部署应在目标 Mac 上执行同一流程，自行完成该机器的授权。

## 首次部署

准备 Python 3.12、Git、GitHub CLI、curl/tar，以及自己仓库的 runner 管理权限。在自己的仓库根目录安装初始化依赖，执行 `workbench init` 建立本地配置，然后完成两项授权：

```sh
python scripts/researchdesk_membership.py login
python scripts/researchdesk_membership.py models
gh auth login
```

这里的 `python` 应来自已安装项目依赖的环境。模型以本人账户返回为准；会员授权不借用浏览器、Codex 或其他应用的令牌。详情见[会员授权](local-membership-analysis.md)和[初始化说明](workbench-init.md)。

编辑 `config/local/workbench.yaml` 的模型、研究主题与预算。需要自动研究时，在同一文件中设置：

```yaml
automation:
  enabled: true
admission:
  enabled: true
```

两个开关默认均为 `false`；`admission` 控制真实审阅结果自动正式准入。随后执行：

```sh
python scripts/researchdesk_workbench.py start
```

`start` 自动应用两层配置，检查本机会员授权、配置模型和 GitHub 权限，将 Codex SDK 依赖安装到 `runtime.python.venv`，下载并核对官方 runner 包，注册执行机器并启动用户服务。Mac 使用当前用户 LaunchAgent，按普通用户执行，无需 `sudo`。

注册和 SDK 预检成功、服务实际运行后，命令才在当前仓库设置 Actions Variable `RESEARCHDESK_DEPLOYED=true`。Actions Variable 只保存这个布尔值；个人 YAML、会员凭据与本机路径不写入 GitHub 变量。新下载或 fork 的仓库没有该变量时，定时执行不会排队等待未注册的机器。

命令不擅自修改 `automation.enabled`。设置为 `false` 时可以完成 runner 注册并启动服务，后续研究仍跳过；改成 `true` 后，下一次定时任务重新读取该设置。重复 `start` 不清空用量、去重或检查点，也不重新计算首次部署时间。执行器状态可在仓库的 `Settings → Actions → Runners` 查看。

## 工作台与配置更新

执行器绑定运行 `start` 时的当前工作台目录，不在每次任务中创建新的资料库。仓库外 runner 的 `.env` 只保存工作台和运行解释器指针，以及用户明确提供的代理设置。模型工具不读取这些部署文件。

每轮开始时，调度入口重新加载 `config/local/workbench.yaml` 与 `config/system.yaml`，合并、校验并应用。主题、模型、采集来源、窗口、预算和自动开关等普通研究参数，修改后无需再手工 `apply` 或重启。

本地手改过的 `config/system.yaml` 保留并使用；未手改时，调度入口从 GitHub 最新 `main` 同步系统配置。同步不覆盖用户文件、人工笔记或历史用量。更换基础 venv、runner 注册名称、标签或安装路径属于部署变更，需要重新执行 `start`；已有注册不匹配时明确停止，保留旧执行器。

运行中的批次固定使用开始时的配置和证据快照。失败后使用原批次及检查点恢复；若新配置与未完成批次不一致，会保留现场并阻塞，避免将旧调用和新参数混用。可恢复原设置后继续，或在明确的新批次使用新配置。

## 定时与手动检查

[研究 workflow](../.github/workflows/researchdesk-manual.yml) 的默认时间为每周二、周五北京时间 03:00。用 `./setup` 在「定时研究」创建或更新日程时，向导同时更新 GitHub 触发时间与本地 `automation.weekly`。任务在 Mac 上读取本人配置和授权，使用 `<topic>-YYYYMMDD-HHMM` 稳定批次 ID。首次部署或修改日程时从启用时间起算。已完成或无新资料的轮次复用原批次。

部署完成后，可先手动派发健康检查：

```sh
gh workflow run researchdesk-manual.yml --ref main -f operation=health
```

健康检查不推理。真实 `run` 会消耗会员请求；`collect` 只采集原文。任务排队时检查机器在线、网络、runner 服务和用户会话。Mac 休眠、关机或断网时不能立即执行；GitHub 定时也可能延迟。

## 结果保存与边界

新版执行顺序为采集原文、逐篇 Research、独立审阅、Codex Insight 及独立审阅。采集原文与审阅通过的逐篇总结回存 `collection/`、`summary/`；SDK 原结果与证明保存在测试区。开启 `admission.enabled` 后，真实且通过审阅的结果自动新增到 `insights/<主题>/`、`articles/<主题>/`，保留 test，并回存正式准入回执。模拟产物不能晋级。用户在页面亲自确认正式选题后，才能另行启动 Writing；研究任务不代为确认或发布公众号。

分析 job 使用只读 GitHub token；独立保存 job 复核允许路径、散列和证明后取得写权限，新增文件并普通推送。同名人工修改发生冲突时保留文件并停止覆盖，不强推。会员授权、真实请求账本、SDK 原始会话和个人配置继续留在本机，不随结果导出。

只执行自己信任的 `main`，不在个人主机运行不可信 PR 代码。Obsidian 阅读同一套 Markdown，不复制会员凭据。本次注册、配置更新与回存衔接仅使用离线验收；开发过程未替用户实际执行 `start`、启用线上部署变量或新增会员调用。
