# 运行与维护

资料从[项目首页](../README.md)进入：`sources` 保存原文，`reports` 保存单篇总结，`insights` 保存本轮与历史材料的深度思考及趋势总结，`articles` 保存公众号选题和稿件。正文由模型根据实际读取材料生成，来源集中列在篇末；证据绑定、审阅与预算记录供程序复核。

Research 采集、去重并分析 → 独立模型审阅 → Insight 综合历史资料并提出选题 → 独立审阅及正式入库 → 用户确认选题 → Writing 生成大纲、初稿和候选稿。不自动发布公众号。

## 配置入口

| 设置 | 文件 |
| --- | --- |
| 研究方向 | [research_topics.yaml](../config/research_topics.yaml) |
| 来源、60 天选材窗口、最多 5 份、180 天历史、模型及每轮预算 | [agent-memory.yaml](../config/cycles/agent-memory.yaml) |
| 周二、周五北京时间 03:00 调度及漏跑补跑 | [automation.yaml](../config/automation.yaml)、[研究 workflow](../.github/workflows/researchdesk-manual.yml) |
| 本地或远程执行环境 | [runtime.yaml](../config/runtime.yaml)、[远程示例](../config/examples/runtime-remote.yaml) |
| 会员请求月度上限 | [membership_budget.yaml](../config/membership_budget.yaml)、[预算说明](membership-budget.md) |
| 正式研究准入、选题确认及稿件准入 | [admission.yaml](../config/admission.yaml)、[confirmation-v2.yaml](../config/confirmation-v2.yaml)、[writing_admission.yaml](../config/writing_admission.yaml) |

当前公开来源为 arXiv、Letta、LangChain、Hugging Face Blog、美团技术团队和阮一峰的网络日志。关注度来自可核实的 Hugging Face / Hacker News 信号；这是候选范围内的排序，不保证全网最热。未接入知乎、X、Reddit 和 Quora。论文优先获取固定版本官方 HTML，缺失时提取 PDF；失败才标为摘要降级。博客实际模型输入范围及完整归档范围分别记录。

## 首次部署

在仓库根目录准备 Python 3.9+ 环境，依次按[会员授权](local-membership-analysis.md)和[执行器部署](self-hosted-worker.md)完成自己的登录与主机配置。授权、runner 工作目录与运行环境均放在仓库和 Obsidian Vault 外。

```sh
python3 -m venv .venv-membership
.venv-membership/bin/python -m pip install -r workflows/requirements-membership.txt
.venv-membership/bin/python scripts/researchdesk_runner.py doctor
```

自托管主机只执行自己信任的 `main`。开源用户使用自己的仓库、授权与配置，不共享维护者凭据。GitHub 托管检查只运行离线校验，会员推理在配置的自托管主机运行。

## 研究状态与补跑

以下命令使用已授权的 GitHub CLI。`health` 检查授权与配置模型，不进行推理；`discover` 只采集发现；`run` 执行有预算的 Research → Insight，并按配置准入；`admit` 仅准入已通过结果，不新增推理。

```sh
gh run list --workflow researchdesk-manual.yml --limit 5
gh workflow run researchdesk-manual.yml --ref main -f operation=health
```

失败恢复沿用原 `cycle_id` 和原配置，不换 ID 重置调用预算。计划槽 ID 为 `agent-memory-YYYYMMDD-0300`；将下列占位符替换为待恢复的实际 ID：

```sh
gh workflow run researchdesk-manual.yml --ref main -f operation=run -f cycle_id='<原 cycle_id>' -f config=config/cycles/agent-memory.yaml
```

只差正式准入时，将上条命令的 `operation=run` 改为 `operation=admit`。按配置补最近漏跑时间槽使用：

```sh
gh workflow run researchdesk-manual.yml --ref main -f operation=catchup
```

已完成响应复用检查点；未知请求保留预留并停止，不能盲目重发。原文、模型、配置或人工笔记变化时不得强行复用。失败现场、调用账本和仍被正式结果引用的证明是运行依赖，不能按历史演练清空。

正式研究以 `reports/<topic>/admissions/<cycle_id>/accepted.yaml` 及配对散列为准。检查同一 `main` 提交中的证明与正文；文件存在或 workflow 单个阶段成功不等于正式入库。个人 Codex 的周二、周五 09:00 简报是独立只读任务，不重新启动研究。

## 确认选题与写作

```sh
python3 scripts/researchdesk_confirmation.py setup
python3 scripts/researchdesk_confirmation.py serve --open-browser
```

在[本地选题页](http://127.0.0.1:8765)核对标题、角度、受众、字数及证据，亲自保存确认；同步完成后，在确认记录中点击“开始 / 继续测试写作”。页面只监听本机环回地址，需保持服务运行。远程部署由用户安全转发端口，不直接公开页面。

新确认默认使用 [Writing v2 配置](../config/confirmation-v2.yaml)与[作者风格](../config/writing_style.md)：围绕具体问题形成判断，章节直接说明问题、方法或取舍，允许删除旁支和重复案例。页面可选填“作者补充”，提供真实经历、个人判断和希望展开的细节；未提供经历时不会自行编造第一人称故事。风格与补充内容随确认冻结，修改后须重新预览确认。

Writer 接收研究结果及其实际审阅范围内的原文节选。大纲选择主线与必要证据，初稿连贯展开，候选稿可删减、合并、重排和调整章节名；独立审阅同时核对事实与表达。新版正文使用简洁来源标注，详细证据关联保留在检查点。旧 [v1 配置](../config/confirmation.yaml)、提示词和稿件继续按原版本核验，不回写旧文章。

Writing 使用 [confirmed Writing workflow](../.github/workflows/researchdesk-writing.yml)。正常三阶段共 6 次请求，每阶段独立模型审阅，通过才继续；最多请求数及一次修订由确认时冻结的配置限制。页面可撤回确认，后续步骤停止，已发请求和稿件保留。仅在笔记上打勾或由模型声称已同意，不能替代用户确认。

已有三稿完整通过时，可用 `max_new_calls=0` 复核与回存，不新增会员请求。正式准入是确定性另存，不重新生成，使用已保存的真实确认 ID：

```sh
python3 scripts/researchdesk_writing_admission.py run --approval-id '<真实确认 ID>'
python3 scripts/researchdesk_writing_admission.py verify --topic agent-memory --approval-id '<真实确认 ID>'
```

正式三稿位于 `articles/<topic>/`，相关确认和准入证明在 `reports/<topic>/`。候选稿入库不授予公众号发布权限。所有阶段只新增文件，已有人工修改产生冲突时停止，不自动覆盖。

## 校验与同步

资料字段和模板见 [Schema](source-schema.md)及[模板目录](templates/)，去重与人工笔记保护见[维护规范](maintenance.md)。提交前执行：

```sh
python3 workflows/validate.py
python3 workflows/validate.py --include-test
git diff --check
```

代码修改按影响范围运行 `tests/` 对应离线测试，再查看 [ResearchDesk checks](../.github/workflows/researchdesk-checks.yml)。测试样例与真实研究分开，不因样例通过声称已运行真实模型。

GitHub 保存共享 Markdown、代码与可恢复状态；Obsidian 使用同一仓库或既有同步方式阅读这些文件。先保存本地笔记，再正常拉取和推送；冲突保留双方内容，不重置 Vault。Obsidian 配置及手机同步沿用用户已有设置。
