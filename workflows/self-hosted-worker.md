# 自托管执行器

GitHub Actions 负责派发、离线校验和保存结果；会员推理在用户选择的 Mac 或远程主机执行。runner、Python 环境及会员授权均位于仓库和 Obsidian Vault 外，执行目录不能指向 Vault。

## 当前 Mac

[runtime.yaml](../config/runtime.yaml) 配置 runner 标签、外部 Python venv 和会员 profile。`membership.profile: null` 使用本机 ResearchDesk 的既有仓库外授权。完成[会员登录](local-membership-analysis.md)后，在仓库根目录执行：

```sh
.venv-membership/bin/python scripts/researchdesk_runner.py doctor
.venv-membership/bin/python scripts/researchdesk_runner.py setup
```

`doctor` 不读取令牌内容或调用模型；`setup` 安装依赖、校验官方 runner 下载散列、向当前仓库注册并启动用户服务。Mac 使用当前用户 LaunchAgent，无需 sudo。需本机 Python 3.9+、Git、GitHub CLI、curl/tar，以及该仓库 runner 管理权限。注册令牌只在内存传递，不进入参数或仓库。

`setup` 继承该次进程显式设置的代理变量，保存在仓库外 runner `.env`，不打印代理地址。代理变化后重启服务，本机代理也需保持运行；缺失变量不会清除旧设置。

在 GitHub 的 runner 页面确认主机在线，标签包含 `self-hosted` 和 `researchdesk`，再运行无推理健康检查：

```sh
gh workflow run researchdesk-manual.yml --ref main -f operation=health
```

任务排队时先检查机器、网络、runner 服务及用户会话。一次健康检查成功不能证明凌晨始终在线。

## 调度与恢复

[研究 workflow](../.github/workflows/researchdesk-manual.yml) 的 UTC cron `0 19 * * 1,4` 对应每周二、周五北京时间 03:00。启用开关、首次启用边界与补跑范围来自 [automation.yaml](../config/automation.yaml)；当前已启用。调整时间须同时修改配置与 workflow，不能只改说明文字。

周期 ID 使用固定时间槽 `agent-memory-YYYYMMDD-0300`，迟到与补跑复用该 ID、固定输入、检查点与请求账本。最近 14 天内每次最多补 1 个未完成槽，已准入、无新资料及终结决定不重复研究。已有模型完成但保存失败时恢复保存或准入，不另起轮次重做。

```sh
gh workflow run researchdesk-manual.yml --ref main -f operation=catchup
```

其他研究、准入及 Writing 操作见[运行说明](README.md)。GitHub schedule 可能延迟或漏发，Mac 须保持开机、联网、runner 用户会话可用；休眠或关机不能保证准点。个人 Codex 周二、周五 09:00 的只读简报独立配置，不随仓库 cron 部署。

## Git 保存与权限

分析 job 的 GitHub token 为 `contents: read`，不在 checkout 保存凭据，会员 profile 仍在主机外部运行目录。主机本身可能另有用户 GitHub/Keychain 权限，因此仍须只执行可信代码。Research、Insight、Writing 共用 `researchdesk-membership-worker` 串行队列，避免多份副本同时调用同一会员。

分析阶段先保存完整检查点、调用预留及结果，失败后仍尝试导出。独立 Ubuntu 保存 job 取得 `contents: write`，复核白名单、绑定散列、独立审阅及最新 `main`，只新增允许的文件并普通推送；不同内容、基线变化或人工修改时停止，不强推。模型不能自由选择写入路径。

artifact 保留 14 天，runner 保留未保存现场。硬断电或作业强杀可能来不及导出；遇到未同步检查点应恢复原轮次，不能直接清理工作目录。正式证明、真实调用账本和未完成状态是恢复依据，与可删除的历史演练分开。

只有保存到共享 `main` 的有效确认允许启动 Writing。确认、正式准入、模型审阅均不授予公众号发布权限。Obsidian 继续使用既有 Git 同步，不修改插件、Vault 配置或个人笔记。

## 远程主机与开源部署

[远程 runtime 示例](../config/examples/runtime-remote.yaml) 可选长期在线主机。用户通过自己的 SSH 连接、克隆自己控制的仓库并配置 GitHub CLI，在该主机选择配置后执行 `doctor/setup`。ResearchDesk 不自动 SSH、不复制当前 Mac 的令牌；各主机自行完成会员授权。Linux 服务安装需预先安排 `sudo -n`，远程 Mac 使用用户服务。

配置中的路径属于各部署主机，不能把维护者 Mac 的路径作为通用路径。页面仍只监听部署主机环回地址，用户通过自己的安全端口转发访问。

自托管 runner 只运行可信 `main`，不接收不可信 PR 或 fork 代码。开源用户在自己的仓库部署自己的 runner，不共享个人主机或会员授权。当前本地锁按工作副本区分，不是跨主机账户额度锁；统一使用该 workflow 派发，避免多个克隆直接并行调用。
