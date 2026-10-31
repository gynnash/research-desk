# 运行与维护

本仓库提供 Research、Insight、Writing 三 Agent 框架与配套工具。默认没有研究资料，示例主题停用，自动研究关闭。

## 配置与准备

| 设置 | 文件 |
| --- | --- |
| 研究方向、范围与关键词 | [research_topics.yaml](../config/research_topics.yaml) |
| 来源、窗口、模型、全文策略与阶段预算 | [default.yaml](../config/cycles/default.yaml) |
| 定时开关与补跑范围 | [automation.yaml](../config/automation.yaml) |
| 本地或远程环境 | [runtime.yaml](../config/runtime.yaml)、[远程示例](../config/examples/runtime-remote.yaml) |
| 本地月度请求上限 | [membership_budget.yaml](../config/membership_budget.yaml) |
| 研究准入、选题确认及稿件准入 | [admission.yaml](../config/admission.yaml)、[confirmation-v2.yaml](../config/confirmation-v2.yaml)、[writing_admission.yaml](../config/writing_admission.yaml) |

先把 `example-topic` 换成自己的主题并启用，配置来源、生成模型、不同的审阅模型与预算。研究正式准入默认关闭；需要正式入库时，在 `admission.yaml` 启用并登记自己的主题。按[会员授权](local-membership-analysis.md)和[自托管部署](self-hosted-worker.md)准备自己的执行环境。仅复制配置不会完成账户授权。

## 手动检查与研究

只获取原文时使用[独立采集命令](collection.md)：

```sh
python3 -B scripts/researchdesk_cycle.py collect --config config/cycles/default.yaml --cycle-id example-topic-collect-001
```

该入口在本地运行，先配置并启用研究方向，结果为原文和待研究清单，不需要会员授权。

知乎来源先按[官方 API 接入说明](zhihu-api.md)验证本人凭证、额度和搜索候选。该独立客户端不运行模型、不自动保存资料；搜索摘要不能直接进入全文研究批次。

以下命令需要 GitHub CLI 已授权，且自己的 runner 已准备就绪：

```sh
gh run list --workflow researchdesk-manual.yml --limit 5
gh workflow run researchdesk-manual.yml --ref main -f operation=health -f config=config/cycles/default.yaml
```

`health` 检查授权与模型，不进行推理。配置完成后，使用一个稳定 ID 发起小批研究：

```sh
gh workflow run researchdesk-manual.yml --ref main -f operation=run -f cycle_id=example-topic-manual-001 -f config=config/cycles/default.yaml
```

`discover` 只发现候选；`run` 执行采集、Research、独立审阅、Insight、独立审阅，并按配置正式准入；`admit` 只准入已通过结果，不新增推理。资料目录按需创建，不需要先放入论文样本。

全文模式只研究完整可用正文。论文使用固定版本官方 HTML 或 PDF；博客提取公开主文。获取失败、正文不完整或超预算时跳过，获取记录说明原因。研究正文采用连贯技术文章，证据关联与审阅记录单独保存。

## 定时与恢复

[automation.yaml](../config/automation.yaml) 默认 `enabled: false`。用户完成配置和手动验证后可自行启用；workflow 保留的时间为每周二、周五北京时间 03:00。配置与 workflow 的调度值须保持一致。

失败时复用原 `cycle_id`、配置、检查点和请求账本，不换 ID 重置预算。只差准入时使用 `operation=admit`；按配置补漏使用：

```sh
gh workflow run researchdesk-manual.yml --ref main -f operation=catchup
```

已完成响应复用，结果未知的请求停止并保留预留。来源、模型、配置或人工笔记变化时，不强行复用旧结果。正式研究以 `reports/<topic>/admissions/<cycle_id>/accepted.yaml` 及其配对散列为准，不能仅凭文件存在判断成功。

## 选题确认与 Writing

```sh
python3 scripts/researchdesk_confirmation.py setup
python3 scripts/researchdesk_confirmation.py serve --open-browser
```

在本机 `http://127.0.0.1:8765` 核对选题、角度、读者、篇幅和证据后，亲自保存确认。同步完成后才可在页面启动 Writing。远程部署通过自己的安全端口转发访问，不直接公开页面。

Writing 生成大纲、初稿和候选稿，每阶段独立审阅。文风来自 [writing_style.md](../config/writing_style.md)，用户可在确认时补充真实经历与判断。未提供的个人经历不会自行编造。

已有三阶段结果通过后，可使用已保存的确认 ID 正式准入，不重新生成：

```sh
python3 scripts/researchdesk_writing_admission.py run --approval-id '<真实确认 ID>'
python3 scripts/researchdesk_writing_admission.py verify --topic example-topic --approval-id '<真实确认 ID>'
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
python3 -B scripts/researchdesk_reading.py --check
```

[Schema](source-schema.md)、[模板](templates/)和[维护规范](maintenance.md)定义资料规则。GitHub 保存共享文件与版本；Obsidian 可选，用同一仓库或自己的同步流程阅读 Markdown。授权与 Obsidian 本地设置不进入 Git。
