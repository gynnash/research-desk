# 已审阅研究的正式准入

Research 与 Insight 的真实结果先保存到 `test`。准入程序重新验证身份、证据版本、输入输出散列、不同实际模型的独立审阅、逐项终态与引用，再以确定性转换创建正式文件。它不调用模型、不读取会员凭据，也不把旧测试回执的 `production_accepted: false` 改成 `true`。

已通过 GitHub 完成 7 份 Markdown 的正式回存及 Obsidian 同步：两条来源、两份单来源研究、一份综合报告、一条洞察和一张待确认选题，新增模型调用为 0。部署证据见[实际验收记录](formal-admission-acceptance-2026-10-19.md)；后续状态以远端 `main`、准入清单和 [`automation.yaml`](../config/automation.yaml) 为准。

## 规则与记录

[`config/admission.yaml`](../config/admission.yaml) 控制准入开关、允许的研究方向、独立审阅与既有文件保护。候选必须来自可核实真实会员 Research → Insight 轮次，保留摘要或节选覆盖范围；模拟、未审阅、输入变化、来源身份冲突或未通过产物不能升级为正式结论。

- 新来源只创建在 `sources/papers/<topic>/` 或 `sources/blogs/<topic>/`，初始化人工阅读状态 `inbox`、人工笔记留空。已有正式来源只引用，补充结论另存研究材料，不覆盖旧笔记。
- 单来源研究、综合报告、洞察和选题分别创建到 `reports/<topic>/`、`insights/<topic>/`、`articles/<topic>/`，引用转换为正式路径；原文事实、作者主张、推断及证据限制保持区分。
- `reports/<topic>/admissions/<cycle-id>/plan.yaml` 固定输出、输入散列及 `source_id_map`；`accepted.yaml` 最后写入，记录准入结果与正式输出散列。两者均带散列校验文件，同批补跑验证后复用。
- 若 UUID 已被同身份的旧测试来源占用，计划预留新的正式 UUID，并登记测试 ID → 正式 ID 映射；不修改旧测试来源、既有回执或人工关联。身份识别只依据有效准入映射解析这类别名，不把无关 ID 冲突自动合并。
- 所有已有文件均保护：同字节可复用，不同字节停止并保留现场；创建过程中断时继续原计划，不重新分配 ID，也不重写人工编辑。

本地 `accepted` 表示准入规则完成。共享知识库的正式入库还需受限发布步骤将确切文件提交到远端 `main` 并核实散列；发布失败保留检查点，不因此重新调用模型。旧测试产物仍保留原来的 TEST 状态与历史预算。

首次部署中，两份新来源笔记的机器页脚使用了研究报告的目录层级。此次修正仅将这两条生成链接重定位到来源笔记所在目录，不改变正文、事实、人工笔记或历史证明。原 `plan.yaml`、`accepted.yaml` 逐字节保留；追加的 `link-repair.yaml` 及校验文件绑定它们的散列，并记录每份来源修正前后的散列。只有字节完全符合原计划、且变化严格等于这一机械转换的文件允许修正，任何人工变化都会停止。历史 `output_hashes` 仍描述原准入，`effective_output_hashes` 描述经核实修正后的当前文件。此修复不是日常自动覆盖入口；后续自动准入仍只创建新文件。新计划在创建前检查正式相对链接。

## 操作

本地只生成固定计划，或按同一计划创建新文件：

```sh
.venv-membership/bin/python scripts/researchdesk_admission.py plan \
  --topic agent-memory --cycle-id cycle-agent-memory-gh-20261019
.venv-membership/bin/python scripts/researchdesk_admission.py run \
  --topic agent-memory --cycle-id cycle-agent-memory-gh-20261019
```

准备工作完成后，GitHub 也可只执行已有轮次的准入，不新增推理：

```sh
gh workflow run researchdesk-manual.yml --ref main \
  -f operation=admit -f cycle_id=cycle-agent-memory-gh-20261019 \
  -f config=config/cycles/agent-memory.yaml
```

`run` 研究操作按配置衔接准入；`health`、`discover` 不准入。发布使用独立 Ubuntu job 的受限 Git 权限，分析端使用仓库外会员授权。遇到仓库规则或内容冲突停止，不强推或覆盖。

选题始终保留 `proposed`、要求人工确认且未启动写作。真实用户确认入口与会员 Writing 后端仍待实现；正式准入、定时启用或模型审阅都不授予写作和公众号发布权限。

## 实际部署

2026-10-19 已完成[GitHub 正式回存与 Obsidian 同步验收](formal-admission-acceptance-2026-10-19.md)，随后启用每周二、周五北京时间 09:00 的研究；实际首个定时结果须以运行回执为准。
