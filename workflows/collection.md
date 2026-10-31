# 独立采集模块

采集负责把公开来源变成可重放的原文和待研究清单，模型分析由后续 Research 执行。

## 当前能力

| 环节 | 已实现的范围 |
| --- | --- |
| 来源 | arXiv、Letta、LangChain、Hugging Face Blog、美团技术团队、阮一峰博客 |
| 发现与选择 | 按发表时间扫描滚动窗口；默认近60天、最多5份；使用可核实的 Hugging Face / Hacker News 关注度信号 |
| 去重 | URL规范化、arXiv/DOI身份归并、排除历史已选资料；同一论文新版本默认也排除，不自动重研 |
| 完整正文 | 论文官方 HTML → PDF；博客公开页面主文；失败、访问限制或超限时跳过并记录原因 |
| 归档 | Markdown原文、章节与获取记录、内容散列；可离线重建后续模型读取的材料 |
| 恢复 | 同一批次使用固定选择与归档；已有文件修改时停止覆盖 |

来源适配器已在代码和虚构离线样例中验证。本次开发没有对公开网站重新做联网采集；各站点的当前可访问性需要后续小批验收。知乎、X、Reddit、Quora 尚未接入。

窗口、扫描上限和可观察信号都有边界，排序不代表全网热榜。归档保存完整可用的抽取文本；图片、视频、公式版式与不可访问内容不在文字抽取的保证范围内。

## 只运行采集

先编辑 `config/research_topics.yaml`，配置并启用自己的方向，再修改 `config/cycles/default.yaml` 的主题、来源和限额。自动研究开关可以保持关闭。安装采集依赖：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r workflows/requirements.txt
```

使用唯一且稳定的批次ID：

```sh
.venv/bin/python -B scripts/researchdesk_cycle.py collect \
  --config config/cycles/default.yaml \
  --cycle-id example-topic-collect-001
```

此入口要求 `window.mode: rolling`、`reading.mode: full_text_required` 和 `archive: true`。它不验证会员账户，也没有模型调用；采集回执的 `model_calls` 为0，原文状态为待研究。当前仓库的示例方向停用，直接执行会先提示配置方向，保持空框架状态。

不要把 `discover` 当成完整采集：它只发现候选与排名。旧 `researchdesk_collect.py` 保留摘要/节选与模拟分析的兼容流程，新开发使用上面的 `collect` 入口。

## 输出与交接

执行后按需创建：

- `reports/test/<topic>/cycles/<id>/collection.yaml`：采集回执、待研究清单和输入/输出散列。
- 同目录的 `discovery.yaml`、`selection.yaml`：来源扫描范围、筛选与失败原因。
- `reports/test/<topic>/research-batches/<id>/items/<source>/original.md`：可读原文。
- 同目录的 `original.yaml`、`candidate.yaml`：精确重放与下游交接数据。

沿用现有原文目录是为了让后续 Research 直接读取同一份固定归档，避免重新下载。采集本身不产生研究结论，也不创建正式入库证明。`collection.yaml` 的 `discovery_status` 保留扫描是否完整；`empty` 只表示这次扫描没有可采集的资料，不代表全网没有新资料。

补跑使用原配置与同一个批次ID。已成功归档的内容离线复用，损坏或人工修改的原文保留并报错。改主题、来源或研究策略时使用新批次；去重仍遵守历史已选规则。

后续需要执行 Research 和 Insight 时，显式运行同一个批次的 `run` 命令，并准备相应账户授权。GitHub Actions 现有 `discover` 操作仍只发现候选，本次没有新增采集调度或页面。

## 离线验收

```sh
PYTHONPATH=tests python3 -B -m unittest test_collection_only -v
```

测试在临时工作区使用虚构论文与博客，验证全文归档、零模型接触、跨批去重、中断恢复及人工修改保护，仓库本身不保存验收结果。
