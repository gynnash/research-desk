# 工作台初始化与本地配置

公共入口是 `config/workbench.example.yaml`。每位用户从模板建立自己的 `config/local/workbench.yaml`，以后只编辑这一个本地文件。个人副本和自动生成的兼容配置均被 Git 忽略；不需要把本人设置推送到 GitHub 才能运行本地工作台。

以下命令均在仓库根目录运行；使用已安装项目依赖的 Python。

## 新下载或 fork 的工作台

```sh
python3 -B scripts/researchdesk_workbench.py init
python3 -B scripts/researchdesk_workbench.py check
```

`init` 复制模板并生成现有入口需要的配置，按主题准备 `collection/`、`summary/`、`insights/`、`articles/` 目录。新工作台没有维护者的研究资料、实际用量或真实 SDK 验收回执。公开 `config/examples/`、`config/test/` 和虚构测试样例仍可用于离线验收。

模板保留 `agent_memory` 研究方向，采集窗口为过去 60 天，每轮最多 5 份资料。`membership_budget.month_max_calls` 是用户自己设置的工作台月度请求上限，默认 100，不能代表 ChatGPT 官方剩余额度。模型名为配置示例，使用前应根据本人账户实际可用模型调整。

初始化只准备本地文件，不登录、不调用模型、不安装或启动 runner、不启用定时任务，不创建提交或推送。模板的 `automation.enabled` 和 `admission.enabled` 均为 `false`；不会触发研究、写作或公众号发布。

## 已有工作台

```sh
python3 -B scripts/researchdesk_workbench.py init --adopt-existing
python3 -B scripts/researchdesk_workbench.py check
```

迁移读取现有设置，生成统一的本地副本。现有兼容配置、人工笔记、原文和研究结果保留；去重状态、历史用量和实际请求账本不清空。已有统一配置时不会再覆盖它；以后直接编辑该文件并执行 `apply`。

配置停止 Git 跟踪后，本机原文件仍在。此次不改写 Git 历史，因此此前已提交的非密钥设置仍可从旧提交查到。OAuth 凭据保持原来的仓库外存储位置，初始化不会读取、复制或重置凭据内容。

## 配置与应用

| 本地 YAML 部分 | 用途 | 生成的兼容文件 |
| --- | --- | --- |
| `workbench_id` | 本人工作台标识 | 注入确认页面与 Codex Insight 配置 |
| `research_topics` | 主题、研究范围、关键词 | `config/research_topics.yaml` |
| `research` | 采集来源、时间窗、全文策略、Research 模型与预算 | `config/cycles/default.yaml` |
| `insight` | Codex SDK、独立审阅、历史窗口与任务限制 | `config/local/codex-insight.yaml` |
| `membership_budget` | 共享月度会员请求上限 | `config/membership_budget.yaml` |
| `runtime` | 本地或远程执行环境与运行目录 | `config/runtime.yaml` |
| `automation` | 定时开关与补跑设置 | `config/automation.yaml` |
| `confirmation` | 选题确认页及 Writing 模型与预算 | `config/confirmation-v2.yaml`、旧版兼容配置 |
| `writing_style` | 本人写作偏好 | `config/writing_style.md` |
| `admission`、`writing_admission` | 研究与稿件准入规则 | 对应的准入 YAML |

编辑 `config/local/workbench.yaml` 后运行：

```sh
python3 -B scripts/researchdesk_workbench.py apply
python3 -B scripts/researchdesk_workbench.py check
```

`apply` 先校验再更新兼容配置，`check` 只读检查。直接手改兼容文件会造成配置分歧，工具会停止并保留文件；先将修改合入统一入口，再按提示处理。预算归档和去重状态属于运行状态，继续保存在本地 `config/research_state.yaml`，不放进公共模板或个人配置副本。

旧操作文档里的 `config/research_topics.yaml`、`config/cycles/default.yaml` 等路径仍供执行器读取。将其中的“编辑配置”理解为编辑本地统一 YAML 的对应部分，再执行 `apply`，不要维护两份设置。独立采集与 Research 的默认读取路径不变。

使用 Codex Insight 时，显式传入生成的本人配置：

```sh
python3 -B scripts/researchdesk_harness.py preflight --config config/local/codex-insight.yaml
```

`preflight` 不调用模型。真实执行另按 [Codex 后端说明](codex-backend.md)准备 SDK、隔离环境和本人会员授权；SDK 当前真实验收范围为 macOS。本次初始化不会把 Research 或 Writing 自动切换到 Codex 后端。

## GitHub、运行主机与同步

GitHub 保存框架、模板和研究资料。`config/local/`、生成配置、`config/research_state.yaml`、`reports/test/*/codex-requests/` 和 `reports/test/*/codex-sdk-smoke/` 不提交。后两类文件仍在本地参与用量核算或验收追溯，不应为了“清洁工作台”而删除当前真实记录。

CI 从公共模板初始化通用配置，再执行离线检查，不需要维护者的本地配置或会员授权。运行主机需要自行初始化、配置和授权；本机修改不会通过 Git 自动送到远程 runner。云端缺少个人配置时保持安全关闭；如以后部署定时运行，需要另外设计并配置受信任的配置交付，本次不启用它。

Obsidian 继续阅读同一份 Markdown。`.gitignore` 只控制 Git，不能决定 Obsidian Sync 是否同步本地配置；手机只阅读资料时无需运行初始化或复制会员凭据。不要把本地配置误当成 GitHub 与手机必须一致的研究内容。

## 可复现检查

```sh
python3 -B scripts/researchdesk_workbench.py check
python3 -B workflows/validate.py --include-test
git check-ignore config/local/workbench.yaml config/research_topics.yaml config/research_state.yaml
git diff --check
```

这些命令不调用真实模型。检查提交内容时只应看到模板、代码、说明和有意保存的研究资料，不应出现本人本地配置或实际请求账本。
