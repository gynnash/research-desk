# 自托管研究执行器：当前 Mac 与远程主机

研究执行器使用用户自己的官方 ChatGPT 会员，在仓库外保存 Python 环境和授权。GitHub 负责派发、离线检查与版本同步。本轮增加受限正式准入和每周二、周五北京时间 09:00 的计划入口：Research → Insight 产物先保存在测试区，只有独立审阅与准入规则均通过的新文件才能进入正式目录，失败检查点仍保留在测试区。不启动 Writing，也不发布公众号。正式准入验收及定时启用状态以远端配置、提交和运行回执为准。

## 当前 Mac

[`config/runtime.yaml`](../config/runtime.yaml) 选择当前 Mac，分别配置 runner、Python venv 和会员 profile。三者必须在仓库与 Obsidian Vault 之外且互不包含；`membership.profile: null` 沿用本机 ResearchDesk 的既有仓库外授权目录，不读取 Codex 或浏览器凭据。检查与安装入口由 [`researchdesk_runner.py`](../scripts/researchdesk_runner.py) 提供：

```sh
.venv-membership/bin/python scripts/researchdesk_runner.py doctor
.venv-membership/bin/python scripts/researchdesk_runner.py setup
```

`doctor` 不读取令牌内容、不联网或调用模型；`setup` 会在当前主机安装依赖、校验官方 runner 下载散列、向当前 GitHub 仓库注册，并安装/启动用户服务。Mac 使用当前登录用户的 LaunchAgent，无需 sudo。安装要求本机 Python 3.9+、Git、GitHub CLI、curl/tar 可用，且 GitHub CLI 已获该仓库 runner 管理权限；注册令牌只在内存传递，不放在命令参数或仓库中。

每台主机的 `setup` 仅继承该次进程显式设置的代理变量，保存在仓库外的 runner `.env`，保留其他配置；代理变化时重启服务，本机代理需保持运行，缺失变量不会清除已有设置，地址不会写入仓库或诊断输出。

## 手动健康检查与研究

[`ResearchDesk research cycle`](../.github/workflows/researchdesk-manual.yml) 支持定时和 `workflow_dispatch`，仅允许 `main`；自托管 job 需要 `self-hosted` 与 `researchdesk` 标签。手动入口默认 `health`，使用 `runtime.yaml` 的 Python 与 profile，检查官方授权、账户模型目录和配置模型可用性，**不调用推理**，不创建研究产物，也不需要上传 artifact 才能成功。

在 GitHub Actions 页面选择工作流并运行，或在已授权的 GitHub CLI 中执行：

```sh
gh workflow run researchdesk-manual.yml --ref main -f operation=health
```

健康检查实际通过后，可使用 `discover` 只发现资料，或 `run` 执行有预算限制的真实 Research → Insight，并按准入配置接纳审阅通过的产物：

```sh
gh workflow run researchdesk-manual.yml --ref main \
  -f operation=run -f cycle_id=cycle-agent-memory-20261019 \
  -f config=config/cycles/agent-memory.yaml
```

同一输入已完成时复用缓存；恢复失败轮次必须保持相同 `cycle_id` 和配置。显式手动运行省略 ID 时使用该 GitHub run 的稳定 ID，同一次运行的重跑不换 ID。`fail_after=after_research` 仅用于显式断点验收，正常运行保持 `none`。真实状态以实际运行及各阶段回执为准，不预设健康检查或研究已通过。

对已有且已通过独立审阅的轮次，可仅执行准入，不启动推理：

```sh
gh workflow run researchdesk-manual.yml --ref main \
  -f operation=admit -f cycle_id=cycle-agent-memory-20261019 \
  -f config=config/cycles/agent-memory.yaml
```

`health` 和 `discover` 不准入。`admit` 不把待确认选题变成已确认，也不改写原有正式来源、历史报告、人工批注或既有文章。准入规则来自 [`config/admission.yaml`](../config/admission.yaml)，通过的确切文件及散列由准入回执记录。

## 每周两次与漏跑恢复

工作流使用 UTC cron `0 1 * * 2,5`，对应每周二、周五北京时间 09:00。计划 job 在 GitHub 托管 Ubuntu 上读取 [`config/automation.yaml`](../config/automation.yaml)，不读取会员凭据；启用开关、启用时间、研究配置、准入配置和补跑范围均来自该文件。实际 cron 写在 workflow 中，修改时间时必须同时调整 YAML 配置与 workflow，保持一致。

正式准入验收前配置保持 `enabled: false`，此时 cron 事件不会派发真实研究。验收后将其改为 `true` 并推送默认分支，自动流程才生效；该开关不撤销已发请求，也不删除历史检查点。

`activated_at` 限制首次部署不追溯补跑启用前的旧时间槽。随后在最近 14 天内优先恢复未完成或已通过但未准入的到期时间槽，每次最多 1 个。周期 ID 由研究方向与固定的北京时间日期/09:00 槽生成，不使用实际开始时间；迟到和同槽补跑仍复用同一 ID、证据绑定、调用账本及未知请求预留。没有待执行槽时计划 job 正常结束，不启动会员分析。 未启动过的漏跑槽以首次实际启动时间建立发现窗口；已经建立清单的槽沿用固定窗口。资料源仅检查有界列表，因此补跑不代表完整恢复历史归档。

已准入、无新资料以及已记录终结决定的轮次不会仅因下次触发就重新研究。模型完成但保存失败时优先恢复原槽和发布，不换 ID 重做；未知请求不能因为出现新 GitHub run 就自动重发。超出自动补跑窗口、配置变化或内容冲突的记录保留，需明确恢复原轮次后再继续。

需要立即按到期时间槽补跑时：

```sh
gh workflow run researchdesk-manual.yml --ref main -f operation=catchup
```

若已知应恢复的 `cycle_id`，可按上方 `operation=run` 手动派发同一 ID；若只差准入，使用 `operation=admit`。多个漏跑槽由后续定时或逐次手动补跑处理，单次不会集中消耗所有积压预算。

09:00 是计划时间，GitHub 可能延迟或遗漏 schedule，且只在默认分支运行，参见 [GitHub schedule 文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。Mac 必须保持开机、联网且 runner 用户会话可用；休眠或关机时不能保证准点，恢复后使用同槽补跑，不能把一次健康检查通过当作长期在线保证。

## 凭据、工作目录与保存

- 自托管分析 job 的 `GITHUB_TOKEN` 只取得 `contents: read`，检出后不保留该 Git 凭据，使用仓库外会员 profile；日志只打印脱敏状态，不打印模型响应、原文、profile 路径或令牌。当前 Mac 的用户环境仍有 GitHub CLI/Keychain 等既有授权，因此不能声称整个主机没有 Git 写权限；可信代码和受控分支仍是必要边界。
- 工作目录是 runner 自己的 `_work/.../researchdesk-worker`，与现有 Obsidian Vault 分开。不得让 checkout 指向 Vault；不删除本地笔记、不修改 Obsidian 配置。运行开始读取 `main` 中全部历史会员请求事件，继续累计预算。
- 研究阶段先在 `reports/test/<topic>/{cycles,research-batches,insight-runs}/<cycle-id>/`、`insights/test/<topic>/<cycle-id>/` 和 `articles/test/<topic>/<cycle-id>/` 生成独立产物。预算预留、未知请求及失败前的有效检查点也在这些目录，不能只保存通过报告而丢弃已消耗请求。正式准入另按 `admission.yaml` 的白名单仅创建新文件，不能由模型自由选择写入位置。
- 研究失败后仍尝试导出有效测试文件，检查 YAML 配对散列、路径、现有文件未变及常见凭据/本地绝对路径泄漏，再保存为保留 14 天的 artifact。硬断电、磁盘损坏或作业被强杀仍可能来不及导出；runner 工作目录保留现场，不能直接清理后换批次重试。
- 单独的 Ubuntu 发布 job 取得 `contents: write`，不接触会员 profile。它对照原有 Git 文件散列检查最新 `main`，只接纳允许的新测试检查点及通过正式准入的新文件；已有同字节文件复用，内容冲突或基线变化停止。规范检查通过后普通提交推送，不强推、不覆盖正式资料或原笔记。选题保持待确认，不能把准入当作写作或发布授权。
- 推送被仓库保护或并发修改阻止时，保留 artifact 与 runner 工作目录，不绕过规则。发布成功后 Obsidian 按既有 Git 同步拉取。未发布的其他轮次文件会阻止开始新研究，应先恢复原轮次或从 artifact 恢复检查点。

工作流共用单个并发组，运行中不自动取消。当前预算和主题锁按仓库根路径区分，**不能阻止另一个克隆目录同时调用会员**；部署后应统一从这个 workflow 派发，不同时在 Vault、其他克隆或第二台主机启动真实研究。若以后需要多工作台并行，须另做账户级协调，不能把当前配置说成全账户额度硬限制。

自托管 runner 只运行自己信任的 `main` 代码，不运行 PR 或 fork 的代码。开源发布代码时，用户应在自己控制的仓库部署执行器；把个人 Mac 的 runner 暴露给不可信工作流会使本机资料和授权面临风险，详见 [GitHub 自托管安全说明](https://docs.github.com/en/actions/reference/security/secure-use#hardening-for-self-hosted-runners)。标签路由依据[官方 runner 说明](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/use-in-a-workflow)。

## 换成远程主机

[`config/examples/runtime-remote.yaml`](../config/examples/runtime-remote.yaml) 提供长期主机配置。用户先通过自己的 SSH 方式连接主机，克隆自己的仓库、配置 GitHub CLI，再在**该主机**选择 remote 配置并执行 `doctor/setup`。ResearchDesk 不发起 SSH、不复制本地令牌或登录会话；各用户自行在合资格主机完成官方会员授权。远程 Linux 的服务安装/启动需要预先安排 `sudo -n` 权限，远程 Mac 使用用户服务。

代码和轮次配置可共用，runner、venv 和 profile 路径属于各部署主机；不要把当前 Mac 的绝对路径当远程通用配置。部署资格仍应按官方会员适用范围分别核实。本地 Mac 需要登录用户会话、网络和机器在线；休眠、关机或未登录可能让任务排队，不能据健康检查一次通过承诺长期可用。

正式准入验收通过后，将启用配置及 workflow 推送到默认分支，才生效为每周二、周五北京时间 09:00 的计划任务。实际首个定时执行仍需以运行回执确认；代码或配置存在不证明任务已经按时完成。
