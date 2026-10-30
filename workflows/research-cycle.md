# Research → Insight 研究轮次

本阶段把资料发现、Research 与 Insight 接成一个本地入口：读取研究方向和来源配置，发现候选并查重，生成研究与独立审阅结果，再以通过的输入生成综合报告、洞察和待人工确认的公众号选题。新执行产物先写各方向的 `test` 目录，通过[正式准入](formal-admission.md)后仅创建新的正式资料。真实运行的完成情况以轮次回执及关联阶段回执为准，命令退出或文件存在不能代替审阅通过。

2026-10-19 已通过[本地断点与缓存验收](../reports/test/agent-memory/cycles/cycle-agent-memory-20261019/acceptance-local.yaml)，并完成[GitHub → 当前 Mac → 测试结果回存 → Obsidian 的真实验收](../reports/test/agent-memory/cycles/cycle-agent-memory-gh-20261019/acceptance.md)。来源扫描是有边界的候选列表；阶段通过不表示全量检索完成。本轮增加受限正式准入与定时入口，实际验收及启用状态以远端配置和回执为准。

本地分析使用用户自己的官方 ChatGPT 会员授权。GitHub 的 `ResearchDesk checks` 只做离线校验；[自托管执行器](self-hosted-worker.md)在当前 Mac 上使用仓库外配置执行健康检查或有限研究轮次，并通过独立发布 job 保存检查点。Research 与 Insight 先写测试区，准入规则通过后仅创建允许的正式新文件。每周二、周五北京时间 03:00 的 cron 由 `automation.yaml` 启用开关控制，正式准入验收后才开启，不启动 Writing 或发布公众号。

## 配置与运行

轮次配置为 [`config/cycles/agent-memory.yaml`](../config/cycles/agent-memory.yaml)。每个方向使用自己的配置及 `test/<topic>/` 输出；模型从该用户当前账户目录选择，生成和独立审阅使用不同的实际模型。授权 profile 保存在仓库及 Obsidian Vault 之外，沿用[本地会员说明](local-membership-analysis.md)的官方登录方式；不复制到 GitHub Secrets 或资料目录。

当前新轮次重新扫描过去 60 天首次发表的资料，每来源最多检查 80 个候选；arXiv 有日期查询与有界分页，博客仍仅扫描公开列表，不能承诺覆盖两个月全部文章。先排除全历史已挑选身份，再按 HF 推荐和 Hacker News 讨论的可核实关注度全局选择最多 5 份，不强制论文与博客配额，也不为凑数选择没有信号的资料。每轮最多 240 次公开关注度查询，与模型预算分开记录。范围、评分与未接入平台见[目标对齐审查](workflow-alignment-2026-10-30.md)。

Research 上限为 12 次（5 份正常研究及审阅共 10 次，另有 2 次修订余量），Insight 上限 4 次，总上限 16 次；不保证每份都能修订，失败或未知请求也占预算。共享月度上限仍为 100 次。单次实际输入上限为 500,000 字符，论文材料最多 120,000 字符、博客节选最多 6,000 字符；超限停止并记录原因，不静默删减审阅依据。历史从过去 180 天按研究日期及月份选择最多 30 份文件，含来源依赖，实际时间覆盖会写入综合报告；配置半年不等于已有半年证据。最大输出与等待时间保持原配置。

查重读取全库来源、真实研究历史与冻结选择，不只比较当前轮次的配置 ID。URL 去掉 fragment 和明确的跟踪参数，保留内容查询参数；arXiv 的 abs/pdf/html 与版本 URL 归同一论文身份。日常滚动发现不再挑选已选身份，失败在原轮次补跑；不消费旧轮次积压队列。定向全文升级或实质更新仍可通过显式批次另存更新研究，不覆盖原来源及人工笔记。已有绑定轮次继续保留原配置快照与提示词，不能将新配置套到旧轮次 ID。

在仓库根目录使用已安装会员依赖的环境运行：

```sh
.venv-membership/bin/python scripts/researchdesk_cycle.py run \
  --config config/cycles/agent-memory.yaml \
  --cycle-id agent-memory-20261019-cycle
```

同一轮次恢复时沿用相同配置和 `cycle-id`，复用已完成的发现、研究和审阅检查点。为了核对 Research 完成后的恢复，可在第一次运行时使用：

```sh
.venv-membership/bin/python scripts/researchdesk_cycle.py run \
  --config config/cycles/agent-memory.yaml \
  --cycle-id agent-memory-20261019-cycle \
  --fail-after after_research
```

随后执行第一条不含中断参数的命令。不要为了补跑改用新的轮次 ID：这不能重置历史处理决定或共享会员预算。`run` 默认使用本机仓库外的 ResearchDesk 授权目录，也可显式传入 `--profile` 指定自己的仓库外目录。`discover` 子命令使用同样的 `--config` 和 `--cycle-id`，只负责资料发现，不启动模型分析；具体参数见 `scripts/researchdesk_cycle.py discover --help`。

## 结果与停止条件

- 发现结果、原文身份与版本、阶段回执及恢复所需清单保存在当前方向的测试区；正式笔记与已有人工批注不覆盖。
- 原文事实、作者主张与研究推断继续区分，明确全文、章节节选或摘要降级范围。新配置按[全文阅读规范](fulltext-reading.md)获取固定版本官方 HTML/PDF；Insight 使用通过独立审阅且输入绑定仍有效的 Research 结果及明确登记的历史基线。
- 同版本且证据未变的资料复用已有判断；定向更新通过独立材料说明，不回写旧笔记。没有合适的新资料时记录发现结果，不能为了完成轮次制造新结论或重复付费研究。
- 部分失败、待修订、拒绝、预算延后和完整通过分别记录。未知请求保留预算预留，不盲目重发；不能把单个阶段成功视为整轮成功。
- 待确认选题保持 `proposed`，用户在现有页面确认选题、角度、受众及证据版本后，才可以派发真实 Writing。模型审阅不能替代该确认，选题卡也不代表发布授权。

本工作台的请求预算来自 [`membership_budget.yaml`](../config/membership_budget.yaml)，按已有累计账本计算；这是本地准入限制，不是官方会员余额。会员实际剩余额度不可核实时保留未知。

## GitHub 验收

[`ResearchDesk checks`](../.github/workflows/researchdesk-checks.yml) 在推送到 `main`、PR 或显式手动触发时运行。它使用 GitHub 托管 Ubuntu 与 Python 3.12，只取得 `contents: read`，检出后不保留 Git 凭据；执行资料规范校验及固定输入的少量关键轮次测试，不连接会员后端、没有仓库写权限，也没有定时事件。安装公开依赖需要网络，研究与模型调用不在这个 workflow 中。

先做对应的本地离线检查：

```sh
.venv-membership/bin/python workflows/validate.py --include-test
.venv-membership/bin/python -m unittest discover -s tests -p 'test_cycle.py' -v
.venv-membership/bin/python -m unittest discover -s tests -p 'test_url_history_dedup.py' -v
.venv-membership/bin/python -m unittest discover -s tests -p 'test_admission.py' -v
git diff --check
```

2026-10-19 容量与查重调整的离线验收：6 项轮次、7 项 URL 历史及 4 项正式准入检查全部通过。新增容量用例使用解析器、真实阶段代码及模拟模型完成 5 份资料的独立审阅与 Insight，实际 Insight 生成/审阅输入为 51,346/52,276 字符，均在 60,000 上限内；不把模拟结果视为新的真实会员研究。正式资料、历史检查点、人工笔记和 Obsidian 配置均未修改，新增真实模型调用为 0。

workflow 提交并推送到默认分支后，可从 GitHub Actions 页面选择 **ResearchDesk checks → Run workflow**，或使用已登录的 GitHub CLI：

```sh
gh workflow run researchdesk-checks.yml --ref main
gh run list --workflow researchdesk-checks.yml --limit 3
gh run view <run-id> --log-failed
```

只有远端运行实际成功才能声称 GitHub 验收通过。`workflow_dispatch` 要求 workflow 已存在于默认分支；权限与触发行为依据 [GitHub workflow 语法](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)及[手动触发说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch)。官方 [checkout](https://github.com/actions/checkout) 与 [setup-python](https://github.com/actions/setup-python) 当前使用 v7。

## 接下来的部署

当前选择用户自己的 Mac，按[自托管部署说明](self-hosted-worker.md)配置 runner、仓库外 venv 与会员 profile；远程长期主机另有配置示例。会员凭据、自动刷新、工作目录、故障恢复和 Git 发布权限分别验收；GitHub 临时 runner 的离线检查通过不证明它已有会员推理资格。

已完成[受限正式入库、Obsidian 同步和定时启用验收](formal-admission-acceptance-2026-10-19.md)；验收当时启用每周二、周五北京时间09:00，现调整为03:00；实际执行结果以运行回执为准。开源用户沿用同一代码，自行配置主题、来源、模型、预算、授权和部署环境；个人授权、账户信息及私有笔记不得随示例分发。
