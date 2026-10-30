# 论文全文阅读

2026-10-30 补齐论文获取和按实际范围分析的链路。Research v2 与 Insight v3 用于新轮次；旧配置、提示词、摘要报告、测试回执及人工笔记保持原样。本次没有调用真实研究模型。

## 获取与证据

1. 通过官方 Atom 或摘要页核对 arXiv ID、作者、日期及明确版本 `vN`。
2. 获取 `https://arxiv.org/html/<id>vN`，按标题分节，保留正文、附录和参考文献；忽略网页导航。
3. HTML 不可得或无法可靠提取时，获取同版本 `https://arxiv.org/pdf/<id>vN`。使用 `pypdf` 提取文本，按可识别章节分段并保留页码；跨页内容标注 continued，识别不了章节时明确按页定位。
4. 两种全文都获取或抽取失败时，使用已核实摘要，记录每一步失败原因。纯扫描件不做 OCR。身份或版本明确不符直接停止，不静默降级。

论文正文只在内存中用于模型输入，不把整篇 HTML/PDF 或正文副本提交 Git。落盘的是来源、版本、媒介、抽取器 profile、正文和实际输入散列、章节范围与短引文。每份材料的引文共不超过 25 个空格分词、400 字符；章节标题和位置另行登记。

HTML 单次沿用安全抓取器的 2 MB 上限；PDF 为 20 MB、500 页；抽取文本不超过 500,000 字符。超限或解析失败有明确记录。PDF 无字页会使范围降为节选。图像、公式、多栏顺序和排版可能未完整恢复；读过文本不表示复现实验或验证实现。

`S1` 等定位章节或页内分段，`A1` 等定位原文段落。研究模型与独立审阅模型读取相同正文、章节目录、实际范围与定位索引；修订与复审也使用同一证据。Insight v3 继续携带对应原始材料及范围，不将全文获取等同独立验证。

## 配置与预算

默认轮次配置为 [`config/cycles/agent-memory.yaml`](../config/cycles/agent-memory.yaml)：

```yaml
reading:
  mode: full_text_preferred
  paper_max_chars: 120000
```

论文最多提供 120,000 字符的带定位材料，博客仍按原配置最多 6,000 字符。全文全部装入时才标记 `full_text`；超限时在各节间分配预算、保持顺序，并标记 `excerpt`，逐节列出总字符与已提供字符。摘要超限则停止，不能把不完整摘要当完整摘要。

单次实际请求（包括提示词、JSON、候选及证据索引）上限为 500,000 字符，超过时在预留模型请求前停止；不是预先填满上限，也不是模型 token 配额。最多 5 份资料、单来源 2 份、每轮 16 次及每月 100 次请求保持不变。全文输入会增加实际 tokens，用量仍按模型回执记录，不能据此推算官方剩余额度。

指定论文批次可参考 [`research_batch_fulltext.yaml`](../config/examples/research_batch_fulltext.yaml)：使用 `research-batch-v2`，在 arXiv source 下增加 `reading: {mode: full_text_preferred}`，并调整 `evidence_max_chars`。没有该字段的旧 source 仍按摘要获取；不能修改已绑定批次的配置或重用旧 batch ID 来升级。

## 历史更新与补跑

- 同一身份从已审阅摘要升级为正文，生成新批次 `update`；正式准入创建独立 `research_update` 文件，不改原来源、旧摘要报告或人工笔记。
- 同版本、同正文、同实际材料和阅读 profile 再次出现时跳过推理。只有 URL 表达变化不触发重研。
- 已研究过的同一摘要在全文仍不可得时直接去重，避免为更换包装重复调用；后续全文可得时仍能升级。
- 同批补跑、Insight 及准入复核固定原先已审阅的 HTML/PDF/摘要媒介与版本。原文或章节材料改变、固定媒介获取失败时停止；不能换媒介后套用旧审阅。
- 新的阅读策略只适用于新轮次；旧轮次读取原有配置快照和提示词版本。不会自动为所有历史论文发起深读，也不以测试结果冒充已完成的正式深读。

## 验证

在仓库根目录，使用自己的隔离 Python 环境：

```sh
python -m pip install -r workflows/requirements-membership.txt
python -B -m unittest discover -s tests -p 'test_fulltext*.py' -v
python -B workflows/validate.py --include-test
git diff --check
```

仅验证公开原文获取，不调用模型、不创建研究记录：

```sh
python -B scripts/researchdesk_reading_check.py --url https://arxiv.org/abs/2610.22686v1
python -B scripts/researchdesk_reading_check.py --url https://arxiv.org/abs/2610.22668v1 --format pdf
```

输出是获取与阅读范围检查，不是模型研究或正式准入结果。默认尝试 HTML→PDF→摘要；显式 `--format` 只验证所选媒介，失败不会切换。抽取及模拟验收记录保存在 [`reports/test/agent-memory/fulltext-reading-20261030`](../reports/test/agent-memory/fulltext-reading-20261030/README.md)。

官方格式说明：[arXiv HTML](https://info.arxiv.org/about/accessible_HTML.html)、[pypdf 文本提取](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)。
