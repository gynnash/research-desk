# 工作流目标对齐：离线验收

日期：2026-10-30。基线：`8bd1212`。本记录是代码与流程验收，不是新的论文研究、行业结论或正式准入。

## 结果

- 最近60天滚动发现、arXiv日期过滤和分页、已挑选身份去重、公开关注度排序、同轮冻结补跑通过模拟验收；旧轮次仍沿用原配置。
- 真实组装的离线闭环通过：发现样例 → Research v2正文输入 → 独立审阅 → 180天历史选择 → Insight v4与独立审阅 → 正式准入。模型与公开抓取均为固定样例；隔离临时库中的4次fake请求，不消耗真实会员额度。
- 端到端样例验证两个角色读取相同全文与历史日期、报告披露实际历史跨度、来源卡链接单篇分析且不重复正文、人工历史字节保留、冻结回执未变化。样例中的122天跨度是虚构夹具，不能代表真实知识库积累。
- 关注度、滚动发现、历史综合、索引、来源卡、已有采集与准入测试共90项通过；关联补跑与可信发布传输共47项通过。索引生成异常不能阻断正式研究回存，人工索引不被覆盖或误暂存。
- `workflows/validate.py --include-test`通过：2个主题、13条正式来源、5条测试来源、1条已登记旧资料豁免。正式资料索引`--check`与`git diff --check`通过。

## 可复现检查

在仓库根目录，用安装了`workflows/requirements-membership.txt`的Python环境：

```sh
PYTHONPATH=tests python -B -m unittest test_attention test_rolling_selection test_history_window test_catalog test_source_card test_collection test_admission test_admission_aliases test_admission_timestamp
python -B -m unittest discover -s tests -p 'test_recovery*.py' -v
python -B workflows/validate.py --include-test
python -B scripts/researchdesk_catalog.py --check
git diff --check
```

这些检查不启动真实调研、会员调用或Git发布。普通推送后的GitHub离线检查是另外一次远端验收，其状态以Actions实际运行记录为准。

## 真实资料与未满足目标

真实库按新策略只读选择30份历史文件，涉及13个原始来源，研究/采集日期覆盖2026-10-18至10-30，约12天；不能声称已具备半年观察。

尚未接入知乎、X、Reddit、Quora，博客公开列表不保证两个月穷尽，最多80个候选的排序不等于全网热门榜。原文全文目前仅在内存，Git还没有原文副本归档；新版单篇深读尚未完成真实模型效果验收。具体差距与精简范围见[目标对齐审查](../../../../workflows/workflow-alignment-2026-10-30.md)。

本次未改正式研究、历史摘要报告、人工笔记或`.obsidian`配置，未启动Writing、未调整定时事件或Codex简报，也未发布公众号。首页和正式索引是阅读导航更新，既有手工索引保留在自动区外。
