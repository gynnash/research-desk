# 自托管执行器

GitHub Actions 负责派发、离线校验和结果回存；会员推理在用户选择的 Mac 或远程主机执行。runner、Python 环境与授权目录位于仓库及 Obsidian Vault 外。

## 本地或远程部署

先完成[会员授权](local-membership-analysis.md)，再编辑 [runtime.yaml](../config/runtime.yaml) 的路径、runner 标签与会员 profile。远程主机可参考[配置示例](../config/examples/runtime-remote.yaml)，自行在该主机登录，不复制其他主机令牌。

```sh
.venv-membership/bin/python scripts/researchdesk_runner.py doctor
.venv-membership/bin/python scripts/researchdesk_runner.py setup
```

`doctor` 检查环境，不调用模型；`setup` 安装依赖、校验 runner 下载散列、注册并启动服务。Mac 使用当前用户 LaunchAgent；Linux 服务安装需要预先安排相应权限。运行主机需要 Python 3.9+、Git、GitHub CLI、curl/tar 及自己仓库的 runner 管理权限。

配置代理时，setup 可将显式代理变量保存在仓库外 runner 环境中；修改后需重启服务。执行器状态以自己的 GitHub runner 页面为准。

```sh
gh workflow run researchdesk-manual.yml --ref main -f operation=health -f config=config/cycles/default.yaml
```

健康检查不进行推理。任务排队时检查机器、网络、runner 服务及用户会话。一次成功不能保证休眠、关机或断网时仍可运行。

## 可选调度

[automation.yaml](../config/automation.yaml) 默认停用自动研究。[研究 workflow](../.github/workflows/researchdesk-manual.yml) 保留每周二、周五北京时间 03:00 的时间槽，用户完成配置和手动验证后才自行启用。

周期 ID 使用 `<topic>-YYYYMMDD-0300`，迟到与补跑复用相同 ID、固定输入、检查点和请求账本。补跑范围由 YAML 配置；已准入、无新资料或终结决定不重复研究。已完成但保存失败时恢复保存或准入，不另起轮次重做。

## 保存与权限

分析 job 使用只读 GitHub token，会员授权留在主机外部目录。独立保存 job 复核白名单、绑定散列和审阅结果后，才取得写权限新增文件并普通推送。Research、Insight、Writing 共用串行队列，避免同一部署重复调用。

失败后保留原始响应、调用预留和可恢复现场。结果未知时停止，不盲目重发。模型不能自由选择文件路径；人工修改冲突时保留文件并停止覆盖，不强推。

只运行自己信任的 `main`，不在个人主机执行不可信 PR 或 fork 代码。开源用户使用自己的仓库、主机、授权与配置。可选 Obsidian 同步只处理 Markdown 文件，不代替 Git 拉取，也不复制凭据。
