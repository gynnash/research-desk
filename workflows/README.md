# 运行与维护

本仓库提供 Research、Insight、Writing 三 Agent 框架与配套工具。当前主题为 `agent_memory`，自动研究关闭。采集原文在 `collection/<主题>/`，逐篇研究总结在 `summary/<主题>/`。

## 配置与准备

先按[工作台初始化说明](workbench-init.md)执行 `python3 -B scripts/workbench.py init`；已有配置用 `init --adopt-existing`。以后只编辑本地 `config/local/workbench.yaml`。手动入口用 `apply` 和 `check`；用 `start` 部署后，每轮定时任务会自动重新应用配置。下表中的兼容文件由工具生成，不另行编辑，也不提交 GitHub。

| 设置 | 统一 YAML 部分 → 生成文件 |
| --- | --- |
| 研究方向、范围与关键词 | `research_topics` → `config/research_topics.yaml` |
| 来源、窗口、模型、全文策略与阶段预算 | `research` → `config/cycles/default.yaml` |
| Codex Insight | `insight` → `config/local/codex-insight.yaml` |
| 定时开关与补跑范围 | `automation` → `config/automation.yaml` |
| 本地或远程环境 | `runtime` → `config/runtime.yaml`；[远程字段示例](../config/examples/runtime-remote.yaml) |
| 本地月度请求上限 | `membership_budget` → `config/membership_budget.yaml` |
| 研究准入、选题确认及稿件准入 | `admission`、`confirmation`、`writing_admission` → 对应兼容 YAML |

`agent_memory` 的研究范围和关键词已配置，可直接调整或新增其他主题。按[会员授权](local-membership-analysis.md)准备自己的实际模型和独立审阅模型；自动运行与旧正式准入仍保持关闭。仅复制配置不会完成账户授权。

[Codex 后端与 Harness 技术方案](codex-backend.md)已接通官方 SDK：当前 Mac 可使用 ResearchDesk 自有 ChatGPT 会员授权，由 Codex 执行文件工具和模型循环。新路径只做内容准确性审阅，文风和结构由生成提示词引导。默认旧后端与定时开关保持不变，Research/Writing 尚未迁移；具体边界见 [SDK 能力核实](codex-sdk-capabilities.md)。

以下命令只做元数据预检或临时目录内的虚构离线验收，不登录、不调用模型，也不需要安装 Codex SDK：

```sh
python3 -B scripts/harness.py preflight --config config/local/codex-insight.yaml
python3 -B scripts/harness.py offline-demo
PYTHONPATH=tests python3 -B -m unittest test_codex_adapter test_codex_inputs test_codex_harness -v
```

`offline-demo` 验证生成、三条洞察、独立审阅、审阅后中断恢复和幂等导出；临时 Vault 退出后删除。完整验收另覆盖一次准确性修订、纯文风意见不拒收、未知请求不重发、人工笔记保护与历史去重。虚构响应只能验证流程，不能证明真实模型的研究准确性。

新入口读取本人生成的 `config/local/codex-insight.yaml`，公开字段可参考[示例](../config/examples/codex-insight.yaml)。`insight --config config/local/codex-insight.yaml --cycle-id <已完成逐篇研究的批次>` 会读取该批在 `summary/<主题>/` 下的总结及其原文与通过回执。没有本批资料时返回 `empty`，未安装 SDK 或不支持当前隔离平台时返回 `blocked`。原始通过结果新增到 `insights/test/<主题>/<批次>/report.md`、`articles/test/<主题>/<批次>/topic-N.md`，候选、准确性审阅和回执在 `reports/test/<主题>/codex-insight/<批次>/`。

真实且已通过独立准确性审阅的结果可以零模型调用正式准入；模拟结果不能准入：

```sh
python3 -B scripts/insight_admission.py admit --topic agent_memory --cycle-id '<已通过审阅的批次>'
python3 -B scripts/insight_admission.py check --topic agent_memory --cycle-id '<已通过审阅的批次>'
```

新生成的正式综合文章在 `insights/<主题>/<核心发现>~<批次ID>/<报告短标题>.md`，选题在 `articles/<主题>/<批次>-topic-N.md`。原 test 文件和旧正式文件保留原路径。准入使用版本 2 的 `reports/<主题>/admissions/<批次>/plan.yaml`、`accepted.yaml` 及配对散列，绑定固定原文、Research 与 SDK 独立审阅证明，不要求把当前私人配置提交到 GitHub。正式选题可以进入已有确认页面及 Writing，旧版选题仍保持兼容。

新旧入口分开：旧 Research/Insight/Writing 的历史提示词和校验仍保持兼容。真实 SDK 目前只验收 macOS；其他平台明确阻塞，旧后端的本地/远程能力保留。安装与显式运行方式如下，需要 Python 3.10+ 及本人已有的[官方会员授权](local-membership-analysis.md)：

```sh
python3.12 -m venv "$HOME/Library/Application Support/ResearchDesk/codex-venv"
"$HOME/Library/Application Support/ResearchDesk/codex-venv/bin/python" -m pip install -r workflows/requirements-codex.txt
"$HOME/Library/Application Support/ResearchDesk/codex-venv/bin/python" -B scripts/harness.py preflight --config config/local/codex-insight.yaml
"$HOME/Library/Application Support/ResearchDesk/codex-venv/bin/python" -B scripts/harness.py insight --config config/local/codex-insight.yaml --cycle-id '<已完成逐篇研究的批次>'
```

`preflight` 不推理，`live_ready` 只表示本机运行条件齐备，不代表账号模型资格已验证。`sdk-smoke --cycle-id <稳定验收ID>` 会执行两项真实模型任务，读取小型本地验收文件并由另一模型核对；它不是论文研究。每任务默认最多 3 次上游请求，首次运行会消耗会员额度，恢复或查询不得创建新 turn。

本人真实 SDK 验收回执保存在本地 `reports/test/<主题>/codex-sdk-smoke/<批次>/`，请求逐次预留在 `reports/test/<主题>/codex-requests/<批次>/`；两者均不提交 GitHub，新工作台不继承维护者用量。实际请求与旧后端共用本地月度上限（模板为 100 次），未知和失败不释放。真实 OAuth 留在父进程，SDK 只接触本机短期 capability，文件工具只读固定输入，禁用工具网络与无关技能。

## 手动检查与研究

只获取原文时使用[独立采集命令](collection.md)：

```sh
python3 -B scripts/cycle.py collect --config config/cycles/default.yaml --cycle-id agent-memory-manual-001
```

该入口在本地运行，结果保存到 `collection/<主题>/`，不需要会员授权。随后对同一批次逐篇 Research：

```sh
python3 -B scripts/research.py --cycle-id agent-memory-manual-001
```

只有独立审阅通过的详细总结会新增到 `summary/<主题>/`。预算、失败补跑与人工修改保护见[Research 说明](research.md)；该入口不执行 Insight 或 Writing。

知乎来源先按[官方 API 接入说明](zhihu-api.md)验证本人凭证、额度和搜索候选。该独立客户端不运行模型、不自动保存资料；搜索摘要不能直接进入全文研究批次。

完成本机 ChatGPT 与 GitHub CLI 授权后，一条命令部署当前工作台：

```sh
python3 -B scripts/workbench.py start
```

它应用两层配置、校验授权和模型、安装 SDK 依赖、注册并启动 runner，并设置非敏感仓库变量 `RESEARCHDESK_DEPLOYED=true`。新下载或 fork 未执行此命令时不会排队研究。要自动研究，先在用户文件设置 `automation.enabled: true`；命令会保留用户开关。执行器绑定当前持久工作台，不另起空克隆，也不上传个人配置或 OAuth。

查看部署并显式手动运行：

```sh
gh run list --workflow researchdesk-manual.yml --limit 5
gh workflow run researchdesk-manual.yml --ref main -f operation=health
gh workflow run researchdesk-manual.yml --ref main -f operation=run -f cycle_id=agent-memory-manual-001
```

`health` 只检查授权、模型和 SDK 环境，不推理；`collect` 只获取原文；`run` 串联采集、逐篇 Research 和 SDK Insight。设置 `admission.enabled: true` 后，真实 Insight 审阅通过即新增正式报告、选题和准入证明，并与原文、总结、test 检查点一同回存；关闭时仍留在测试区。研究任务不启动 Writing，也不发布公众号。

全文模式只研究完整可用正文。论文使用固定版本官方 HTML 或 PDF；博客提取公开主文。获取失败、正文不完整或超预算时跳过，获取记录说明原因。研究正文采用连贯技术文章，证据关联与审阅记录单独保存。

## 定时与恢复

用户 YAML 的 `automation.enabled` 默认 `false`。GitHub 工作流初始时段为每周二、周五北京时间 03:00。通过 `./setup` 的「定时研究」创建日程，可以选择星期、时间和时区。GitHub 保存触发时间，Mac 使用本地配置执行对应批次。

每次新运行自动合并系统默认和用户覆盖；本地用户文件与本地已修改的系统文件直接生效。系统文件未手改时，会安全加载 GitHub 最新 `main` 的系统配置，不拉取覆盖人工笔记。运行中的批次固定快照；未完成旧批次遇到配置变化会停止混用。更换解释器、runner 身份或安装路径时需要重新执行 `start`。

默认调度只处理最近到期槽，重复触发复用稳定 ID。失败恢复可在页面重新运行同 ID，或显式补漏：

```sh
gh workflow run researchdesk-manual.yml --ref main -f operation=catchup
```

`catchup` 只选已部署起点之后、配置回看范围内的一个最早未完成槽。首次启动记录起始时间，不为安装前的历史槽自动消耗会员请求。SDK 明确失败可通过补跑授权受限的一次新 attempt，保留旧失败和已完成阶段；单独执行 Harness 时使用 `--retry-failed` 显式请求重试。未知状态只查询，未核实旧执行结果前不重发。正式准入失败后重跑同 ID 只复用已审阅结果、补齐准入，不重新推理。

Research 与 SDK 在每次真实请求预留前共同检查固定批次的 `research.budget.max_calls_per_cycle`；SDK 还检查 `insight_max_calls`、每任务上限和共享月度预算。失败、结果未知和重试的预留均计入，不因切换后端或重试重置。

已完成响应复用，结果未知的请求停止并保留预留。来源、模型、配置或人工笔记变化时，不强行复用旧结果。正式研究以 `reports/<topic>/admissions/<cycle_id>/accepted.yaml` 及其配对散列为准，不能仅凭文件存在判断成功。

## 选题确认与 Writing

```sh
python3 scripts/confirmation.py setup
python3 scripts/confirmation.py serve --open-browser
```

在本机 `http://127.0.0.1:8765` 核对选题、角度、读者、篇幅和证据后，亲自保存确认。同步完成后才可在页面启动 Writing。远程部署通过自己的安全端口转发访问，不直接公开页面。

确认页面的独立 Git checkout 只绑定持久工作台路径，从原工作台读取私有设置，不复制 OAuth 或要求兼容 YAML 进入 Git。新版 Writing Actions 使用执行器绑定的同一工作台和解释器；云端回存只接收本次已确认任务的证据及审阅检查点，并再次核对确认、撤回状态与内容散列。

Writing 生成大纲、初稿和候选稿，每阶段独立审阅。文风在本地统一 YAML 的 `writing_style` 配置，工具生成 `config/writing_style.md`；用户可在确认时补充真实经历与判断。未提供的个人经历不会自行编造。

已有三阶段结果通过后，可使用已保存的确认 ID 正式准入，不重新生成：

```sh
python3 scripts/writing_admission.py run --approval-id '<真实确认 ID>'
python3 scripts/writing_admission.py verify --topic example-topic --approval-id '<真实确认 ID>'
```

选题确认、模型审阅与正式准入均不授予公众号发布权限。

## 阅读、校验与同步

运行后按四类目录阅读：`sources` 为原文、`reports` 为单篇研究、`insights` 为综合洞察、`articles` 为选题及稿件。正式准入后，`研究首页.md` 可集中列出具体文章。已有个人批注不会自动覆盖，派生阅读笔记不重复进入历史证据池。

```sh
python3 -B workflows/validate.py --include-test
git diff --check
```

已存在正式研究时，可只读校验阅读入口：

```sh
python3 -B scripts/reading.py --check
```

[Schema](source-schema.md)、[模板](templates/)和[维护规范](maintenance.md)定义资料规则。GitHub 保存共享文件与版本；Obsidian 可选，用同一仓库或自己的同步流程阅读 Markdown。授权与 Obsidian 本地设置不进入 Git。
