# 采集覆盖与原文归档验收

> TEST：本记录验证采集、归档和模拟链路，不代表新增真实模型研究或正式准入。

日期：2026-10-30。基线：`75439bd`。新增会员调用0次，没有启动Research/Insight/Writing真实推理，也没有修改旧研究、人工笔记、定时事件或Obsidian配置。

## 实际公开来源验收

[覆盖回执](coverage.yaml)保存六个官方入口的请求范围和响应散列：arXiv近60天查询返回5条探针元数据；Letta sitemap列48篇文章，LangChain列548篇；HF Feed894条、美团10条、阮一峰Atom3条。Feed条数不代表完整两个月覆盖，更不是本轮研究数量。

[原文采集回执](../../research-batches/original-archive-check-20261030/collection-only.yaml)保存两个真实快照：

- [MFM论文抽取正文](../../research-batches/original-archive-check-20261030/items/arxiv-original/original.md)：固定arXiv v1，官方HTML抽取88,776字符，带定位的可用阅读材料91,759字符。未调用研究模型。
- [美团技术博客抽取正文](../../research-batches/original-archive-check-20261030/items/meituan-original/original.md)：官网提取13,757字符，模型节选投影6,228字符；这是采集适配样本，不是选中的Agent Memory研究。

两份快照均通过精确重放、内容散列和传输文本检查，只保存到test。归档是Markdown可读抽取正文与YAML重放检查点，不包含PDF二进制、图片或原版式。

## 离线链路

171项针对性检查通过，涵盖RSS/Atom、官方sitemap、滚动选择、多RSS来源限额、归档与传输、历史综合、全文、旧采集、正式准入及可信发布。

真实函数组装的模拟链路完成全文Research、独立审阅、Insight及正式准入；断网时不重取正文、不重复研究。正式ID重映射、原文/来源卡/报告链接、人工保护和重复准入缓存均通过。原文YAML、派生Markdown或正式快照被篡改时拒绝，保留现场。

关联Insight失败恢复在断网下复用原Research和6份原文检查点，仅追加2次fake Insight调用，重跑缓存不再调用。所有fake调用都在临时目录，不消耗会员额度，也不作为正式研究。

公开代码中的短示例与临时路径只在原文可精确重建时免于通用误报，metadata和普通回执检查保持；真实令牌形态在归档前和传输时拒绝。2MB快照与12MB准入计划的界限有固定测试。

## 复现

使用安装了`workflows/requirements-membership.txt`的Python环境：

```sh
PYTHONPATH=tests python -B -m unittest test_archive_admission test_archive_transfer test_archive test_feeds test_blog_archive_discovery test_rolling_selection test_history_window test_catalog test_source_card test_collection test_cycle test_fulltext_cycle test_fulltext_review test_fulltext_recovery test_admission test_admission_aliases test_admission_timestamp test_recovery_job
python -B workflows/validate.py --include-test
python -B scripts/researchdesk_catalog.py --check
git diff --check
```

格式检查通过：2个主题、13条正式来源、5条测试来源和1条已登记旧资料豁免；索引与差异检查通过。推送后的GitHub离线检查状态以Actions实际运行记录为准。

当前边界：知乎/X/Reddit/Quora尚未配置有效访问资格和平台适配器；Feed与最多80篇正文仍是有界覆盖；中文博客缺少HF/HN信号时可能不入选。详见[实施说明](../../../../../workflows/source-coverage-and-archive.md)。
