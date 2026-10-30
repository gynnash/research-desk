# 让研究成果可以直接阅读

综合报告、洞察和趋势线索应像技术文章一样解释问题、方法、差别与意义。来源标注服务阅读，完整的核验链继续保留。选题卡仍是选题说明，研究正文和历史阅读版不会授权 Writing。

## 正文约定

- 标题说明要讨论什么，导读解释为什么值得读；连续段落讲清机制、判断依据和适用条件，避免把正文排成审核清单。
- 用论文名、方法名、博客标题称呼材料。内部 R/H/A 编号、来源 UUID、字符计数和模型回执不占据主要阅读段落。
- 每个有来源的解释段落在末尾附简洁脚注，篇末写出标题、原文链接、实际阅读范围与研究记录。源码仍是标准 Markdown；不引入网页、插件或数据库。
- 用“作者提出／作者报告”标明原文主张，用“我们据此推测／待验证的可能”标明推断。数字保留评测条件，不能把独立模型审阅说成复现实验。
- 摘要降级、正文截断、重要反例和因果不确定性不能为了流畅而删掉。完整来源与核验细节可移到文末；影响结论的限制要就近说明。
- 综述要比较机制和观点，不能只是串联摘要。跨来源、跨时间证据不足时，明确是研究线索或假设，不能包装成行业趋势。

## 新轮次如何生效

当前 [方向配置](../config/cycles/agent-memory.yaml) 增加：

```yaml
presentation: technical_article
```

配置驱动的新批次使用 `research-batch-v3` 与 `insight-v5`。没有该设置的历史配置继续使用既有版本；已冻结 manifest 与检查点保持原样。旧 Research v1/v2、Insight v1–v4 提示词和正文重放不变。

复用原来的结构化字段：Research 的 summary、claims，Insight 的 summary、comparisons、hypothesis 等改写成完整解释段落。kind 和 evidence_ids 继续驱动独立审阅及脚注，段落衔接和扩写也要在同一次独立审阅中核验。没有新增 Agent、额外润色调用、预算或发布步骤，输出仍受现有字符上限约束。

生成器先保存 test 结果，经现有正式准入流程转为正式正文。脚注定义中使用普通 Markdown 链接，正式准入能够把研究记录链接从 test 重定位到正式目录。选题路径、身份、结构化内容与人工确认门槛不变，Writing 仍须用户确认。

## 历史成果如何阅读

已有正式文件的散列绑定准入证明，不能就地换版。当前另存了一篇 [10 月 30 日阅读版](../workbench/阅读/agent-memory/2026-10-30-memory-evidence.md)，由 Codex 根据已保存结果编辑，不增加原文核验、不重跑研究、不另做模型审阅，也不成为公众号稿件。

历史阅读版放 `workbench/阅读/<方向>/`，Frontmatter 使用 `kind: research_reading`、`status: editorial`、`source_cycle` 和 `derived_from`（依据路径到 SHA-256 的映射）。索引先验证原有接受证明，再检查这些依据仍是同方向已准入文件且散列相同，才提供阅读入口；旁边保留原研究记录。它只校验依据身份与版本，不声称已重新审阅编辑后的文字。

此阶段只提供最新一轮的编辑阅读示例，不批量重写历史、生成第二套历史研究或建立自动润色流水线。未来正文直接在原 Research/Insight 流程内生成，索引自然显示新的正式结果。人工笔记留在 `notes/` 或其他独立笔记中，旧正式记录和 Obsidian 配置保留。

## 离线检查

使用已安装依赖的隔离 Python 环境，在仓库根目录运行：

```sh
python -B workflows/validate.py --include-test
PYTHONPATH=tests python -B -m unittest test_article_presentation test_catalog
python -B scripts/researchdesk_catalog.py --write
python -B scripts/researchdesk_catalog.py --check
```

检查使用固定材料与模拟响应，不联网、不调用真实模型。旧准入证明通过索引校验继续重放；本次整理不启动新的研究、写作或发布。
