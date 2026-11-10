# 工作台初始化与两层配置

配置分为系统默认和用户覆盖两层：

| 文件 | 内容 | 是否提交 GitHub |
| --- | --- | --- |
| `config/system.yaml` | 完整系统默认，含内置来源、SDK 和较少调整的参数 | 是 |
| `config/workbench.example.yaml` | 简短的用户配置模板 | 是 |
| `config/local/workbench.yaml` | 从模板复制的本人设置，只写需要覆盖的部分 | 否 |

个人使用只编辑本地 `config/local/workbench.yaml`。工具加载系统默认，再合并本人覆盖，校验后生成旧入口需要的兼容配置。个人副本和生成文件均被 Git 忽略，不需要把本人设置推送到 GitHub 才能运行本地工作台。

首次配置定时研究，在 Mac 的仓库根目录运行 `./setup` 打开本机向导。完成授权后，选择星期、时间和时区，点击「创建」。向导会在健康检查通过后更新 GitHub 工作流日程，并启用本地定时研究与正式准入。首次启用从当前时间起算，配置期间只检查部署。下文保留手动配置、迁移和维护命令，均在仓库根目录运行，并使用已安装项目依赖的 Python。

## 新下载或 fork 的工作台

```sh
python3 -B scripts/workbench.py init
python3 -B scripts/workbench.py check
```

`init` 复制短用户模板，与系统默认合并并生成现有入口需要的配置，按主题准备 `collection/`、`summary/`、`insights/`、`articles/` 目录。新工作台没有维护者的研究资料、实际用量或真实 SDK 验收回执。公开 `config/examples/`、`config/test/` 和虚构测试样例仍可用于离线验收。

默认研究方向为 `agent_memory`，采集窗口为过去 60 天，每轮最多 5 份资料。`membership_budget.month_max_calls` 是用户自己设置的工作台月度请求上限，默认 100，不能代表 ChatGPT 官方剩余额度。模型名为配置示例，使用前应根据本人账户实际可用模型调整。

初始化只准备本地文件，不登录、不调用模型、不安装或启动 runner、不启用定时任务，不创建提交或推送。两层合并后的默认 `automation.enabled` 和 `admission.enabled` 均为 `false`；不会触发研究、写作或公众号发布。

## 授权后，一条命令注册并启动

新版定时执行当前使用 Mac。准备 Python 3.12、GitHub CLI 和本人仓库的管理权限，在执行机器完成 ChatGPT 与 GitHub 授权：

```sh
python scripts/membership.py login
python scripts/membership.py models
gh auth login
```

填好本地模型、主题和预算后，需要自动研究的用户在同一 YAML 设置 `automation.enabled: true`；需要真实 Insight 独立审阅通过后自动正式入库，再设置 `admission.enabled: true`。两个开关默认关闭。随后运行：

```sh
python scripts/workbench.py start
```

命令自动应用配置、校验现有授权、安装 `runtime.python.venv` 需要的 SDK 依赖、注册并启动 runner。它不会推理，也不擅自打开自动研究开关；保留默认 `false` 时只启动执行服务，不自动研究。

成功后仅向当前 GitHub 仓库设置非敏感 Actions Variable `RESEARCHDESK_DEPLOYED=true`，作为新仓库的部署入口开关；个人配置、路径和凭据仍留在本机。runner 绑定当前持久工作台，重复启动不搬迁或清空资料、去重及调用记录。部署细节见[执行器说明](self-hosted-worker.md)。

## 已有工作台

仍使用旧的分散兼容配置、尚无本地统一 YAML 时：

```sh
python3 -B scripts/workbench.py init --adopt-existing
python3 -B scripts/workbench.py check
```

导入读取现有设置，生成本人的差异配置。已有上一版完整 `config/local/workbench.yaml` 时，使用：

```sh
python3 -B scripts/workbench.py migrate
python3 -B scripts/workbench.py check
```

`migrate` 先将完整本地 YAML 备份为 `config/local/workbench.before-layers.yaml`，再压缩为相对系统默认的差异，保留当前有效设置；旧配置缺少的默认来源会记录为禁用，避免迁移意外加入来源。备份同样不提交 Git。已有兼容文件保持原字节，人工笔记、原文和研究结果不改，去重状态、历史用量和实际请求账本不清空。以后只编辑差异配置；已部署的定时入口会在下一轮自动应用。

配置停止 Git 跟踪后，本机原文件仍在。此次不改写 Git 历史，因此此前已提交的非密钥设置仍可从旧提交查到。OAuth 凭据保持原来的仓库外存储位置，初始化不会读取、复制或重置凭据内容。

## 常用设置与合并规则

短用户模板提供 `topic`、`models.generation`、`models.review` 和 `models.writing` 快捷项。`topic` 联动研究、洞察与选题相关阶段；`generation` 配生成模型，`review` 配独立审阅模型，`writing` 配写作模型。模型必须符合本人实际资格，生成与审阅继续使用不同模型。

高级配置按 `config/system.yaml` 的相同路径写局部覆盖即可。字典递归合并；标量和普通列表由用户值替换，例如 `allowed_hosts`、`target_words`、`keywords`、`labels` 不会自动追加。显式阶段配置优先于快捷项。例如只为 Research 选择另一个生成模型：

```yaml
models:
  generation: gpt-6.1-sol
  review: gpt-6-astra
  writing: gpt-6-luna
research:
  models:
    research: gpt-6-luna
```

这里 Research 用显式设置，其余生成阶段继续使用快捷项。模型名仅示范覆盖关系，不保证账户可用。

`research.discovery.sources` 单独按 `id` 合并：同 ID 覆盖对应字段，新 ID 追加；同一层重复 ID 会报错。要禁用默认来源，写 `enabled: false`，不需要改系统文件或删除默认项。空列表 `sources: []` 不会清空默认来源。若变更同 ID 的 `adapter`，该条按用户完整配置替换，需要提供新适配器的全部必需字段。

例如添加一项 RSS，同时禁用内置 Letta 来源：

```yaml
research:
  discovery:
    sources:
      - id: nvidia-blog
        adapter: rss
        publisher: NVIDIA Blog
        entry_url: https://blogs.nvidia.com/feed/
        allowed_hosts:
          - blogs.nvidia.com
      - id: letta
        enabled: false
```

这只示范配置结构；实际来源可访问性、返回格式和正文质量仍需采集验证。覆盖后的配置继续经过现有运行安全规则校验，不能通过用户层绕过来源、模型、预算或文件保护规则。

## 配置与应用

| 本地 YAML 部分 | 用途 | 生成的兼容文件 |
| --- | --- | --- |
| `workbench_id` | 本人工作台标识 | 注入确认页面与 Codex Insight 配置 |
| `topic`、`models` | 主题与模型快捷项 | 联动相应阶段；显式阶段配置优先 |
| `research_topics` | 主题、研究范围、关键词 | `config/research_topics.yaml` |
| `research` | 采集来源、时间窗、全文策略、Research 模型与预算 | `config/cycles/default.yaml` |
| `insight` | Codex SDK、独立审阅、历史窗口与任务限制 | `config/local/codex-insight.yaml` |
| `membership_budget` | 共享月度会员请求上限 | `config/membership_budget.yaml` |
| `runtime` | 本地或远程执行环境与运行目录 | `config/runtime.yaml` |
| `automation` | 定时开关、每周日程与补跑设置 | `config/automation.yaml` |
| `confirmation` | 选题确认页及 Writing 模型与预算 | `config/confirmation-v2.yaml`、旧版兼容配置 |
| `writing_style` | 本人写作偏好 | `config/writing_style.md` |
| `admission`、`writing_admission` | 研究与稿件准入规则 | 对应的准入 YAML |

需要立即检查本地修改，或使用独立手动研究入口时，可运行：

```sh
python3 -B scripts/workbench.py apply
python3 -B scripts/workbench.py check
```

`apply` 加载两层配置，合并并校验后更新兼容配置。`check` 检查两层配置及已应用结果，不修改工作台文件，不登录、不调用模型、不修改 Git。直接手改兼容文件会造成配置分歧，工具会停止并保留文件；先将修改合入用户覆盖，再按提示处理。预算归档和去重状态属于运行状态，继续保存在本地 `config/research_state.yaml`，不放进公共模板或个人配置副本。

已注册的定时任务每轮自动执行合并和应用，无需手工重复这两个命令。本地系统文件有手工修改时保留该版本；未手改时，从 GitHub 最新 `main` 同步系统配置，再合并当前本地用户文件。主题、模型、来源、预算与开关在下一轮生效，不覆盖人工笔记或用户配置。

运行中的批次继续使用固定快照。旧批次尚未完成、当前配置却已改变时，会明确阻塞并保留检查点；恢复原配置再补跑，或在新批次使用新配置，不能混用。基础 venv、runner 注册名称、标签或安装目录变化需要重跑 `start`；这些属于部署设置，普通研究参数无需重启。

旧操作文档里的 `config/research_topics.yaml`、`config/cycles/default.yaml` 等路径仍供执行器读取。将其中的“编辑配置”理解为编辑本地统一 YAML 的对应部分，再执行 `apply`，不要维护两份设置。独立采集与 Research 的默认读取路径不变。

使用 Codex Insight 时，显式传入生成的本人配置：

```sh
python3 -B scripts/harness.py preflight --config config/local/codex-insight.yaml
```

`preflight` 不调用模型。真实执行另按 [Codex 后端说明](codex-backend.md)准备 SDK、隔离环境和本人会员授权；SDK 当前真实验收范围为 macOS。本次初始化不会把 Research 或 Writing 自动切换到 Codex 后端。

## GitHub、运行主机与同步

GitHub 保存框架、模板和研究资料。`config/local/`、生成配置、`config/research_state.yaml`、`reports/test/*/codex-requests/` 和 `reports/test/*/codex-sdk-smoke/` 不提交。后两类文件仍在本地参与用量核算或验收追溯，不应为了“清洁工作台”而删除当前真实记录。

CI 从系统默认和短用户模板初始化通用配置，再执行离线检查，不需要维护者的本地配置或会员授权。定时任务由 GitHub 派发，在绑定的 Mac 工作台直接读取本人配置和会员授权；无需将私人 YAML 交给云端。回存包含原文、逐篇总结与测试区的 SDK 证明；开启准入后还包含正式综合文章和待确认选题。研究任务不自动 Writing 或发布。

新版回存包含原文、逐篇总结、SDK 原结果，以及启用准入后新增的正式综合文章和选题。正式选题通过版本 2 准入回执进入页面；确认与 Writing 复用持久工作台的私有设置和授权，不通过 GitHub 传递整份个人 YAML。注册启动、配置更新及回存有离线验收；首次真实部署仍需在用户自己的机器验证。

Obsidian 继续阅读同一份 Markdown。`.gitignore` 只控制 Git，不能决定 Obsidian Sync 是否同步本地配置；手机只阅读资料时无需运行初始化或复制会员凭据。不要把本地配置误当成 GitHub 与手机必须一致的研究内容。

## 可复现检查

```sh
python3 -B scripts/workbench.py check
python3 -B workflows/validate.py --include-test
git check-ignore config/local/workbench.yaml config/research_topics.yaml config/research_state.yaml
git diff --check
```

这些命令不调用真实模型。检查提交内容时只应看到模板、代码、说明和有意保存的研究资料，不应出现本人本地配置或实际请求账本。
