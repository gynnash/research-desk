# 采集覆盖与原文归档

2026-10-30 补齐公开博客发现入口与原文保存。继续使用Markdown、YAML和现有三Agent，不增加数据库、爬虫框架或付费数据服务。新轮次启用；历史配置、摘要报告及人工笔记不回写。

## 当前来源

| 来源 | 发现入口 | 日期与边界 |
| --- | --- | --- |
| arXiv | 官方API，近60天submittedDate查询和有界分页 | 固定vN官方HTML，失败再提取PDF，确实失败才摘要降级 |
| Letta | [官方sitemap](https://www.letta.com/sitemap.xml) | 已核验48篇博客URL；按lastmod优先抓取，最终用正文发表日筛选 |
| LangChain | [官方sitemap](https://www.langchain.com/sitemap.xml) | 已核验548篇博客URL；索引并非日期顺序，不能直接截前80个URL |
| Hugging Face Blog | [官方RSS](https://huggingface.co/blog/feed.xml) | 已核验894条Feed记录；正文缺日期时用已绑定的Feed发布日期 |
| 美团技术团队 | [官方RSS](https://tech.meituan.com/feed/) | 当前Feed仅10条且无发布日期；用文章页面明示日期，不能从URL猜日期 |
| 阮一峰的网络日志 | [官方Atom](https://www.ruanyifeng.com/blog/atom.xml) | 当前Feed仅3条；按已核实文章与Feed元数据处理 |

这些是公开入口的技术验收，不意味着每个来源都有符合Agent Memory的新材料。仍按主题关键词、最近60天、全历史已挑选去重和可核实关注度选最多5份；一般技术博客中的无关文章不进入研究。

关注度仍仅来自HF/HN，中文博客在这些社区缺乏讨论时会少选或不选；已接入Feed不等于已具备各中文平台的热度指标，不用最新日期冒充热门。

每来源最多检查80篇正文，最多12个配置来源。sitemap索引可有界遍历最多5页（配置1–10页），最多5000个URL；正文未全检查、任一抓取失败或索引未穷尽都记录partial。lastmod仅决定抓取优先级，不当首次发表日，也不以旧文章更新时间骗过60天窗口。

RSS/Atom常只列近期部分文章，即使获取成功也不声称完整覆盖两个月。Feed摘要和content字段不直接当网站全文；研究前获取原文HTML，从明确正文容器或Article结构化正文抽取。HTML有可靠日期时优先；缺日期时才允许使用已冻结的官方Feed发布日期，保存Feed URL和响应SHA-256。两处都未知就不编造日期。

## 配置自己的公开博客

在`config/cycles/<方向>.yaml`的`discovery.sources`中增加：

```yaml
- id: my-tech-blog
  adapter: rss
  publisher: My Tech Blog
  entry_url: https://blog.example.org/feed.xml
  allowed_hosts: [blog.example.org]
```

域名必须由维护者明确列入配置；正文或Feed不能自行扩大抓取范围。仅HTTPS，跨域跳转须仍在允许范围，私网地址、凭据URL、超大响应和XML实体拒绝。通用正文提取支持明确article或JSON-LD articleBody；复杂页面可能需要补一个小适配规则，不能承诺配置任意网址就能全文解析。

知乎、X、Reddit、Quora仍未配置有效的平台采集授权/适配器，本次没有假称已接通。X两个月检索需具备[官方完整档案搜索](https://docs.x.com/x-api/posts/search/introduction)访问资格；Reddit依[官方开发者入口](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data)核验可访问范围。知乎与Quora可用官方内容接口尚未核实，不读取个人浏览器登录材料、不绕过登录墙或默认调用付费接口。这些平台不能单凭配置名称被列作已覆盖来源。

## 保存什么原文

默认方向配置新增`archive: true`，生成给Research的source配置冻结`archive: true`。首次采集后、模型请求前，在现有test检查点创建：

```text
reports/test/<方向>/research-batches/<批次>/items/<来源>/
  original.yaml          # 完整抽取正文、章节、元数据、响应散列及精确模型材料
  original.yaml.sha256
  original.md            # 可读原文视图
```

YAML用于精确重放，Markdown用于阅读。正文最多500,000字符，每个快照文件最多2MB，超限停止，不把静默截断内容称全文。论文原文可大于120,000字符的模型节选，博客原文可大于6,000字符的模型节选；归档覆盖与实际模型阅读分开保留。

论文保存固定版本HTML或PDF抽取正文及章节/页码；博客保存明确正文容器中的抽取文本。正文排版整理不改变YAML中的原始抽取值或散列。保留作者、原文日期、URL、获取时间与响应散列。这里没有保存可执行HTML、PDF附件、图片或原版式，图表与公式仍需核对原文；摘要降级也会明确标明。

Research中断恢复、Insight、关联补跑及新准入计划均读取同份归档，重建并核对正文、章节、模型材料、短证据定位与散列。已绑定归档缺失或被改写时停止，不联网换材料掩盖问题。旧候选没有启用归档时继续沿用原先行为，不伪造历史快照。

归档Schema与渲染v1发布后保留兼容，未来抽取、投影或排版改动需另设版本，不重新渲染覆盖已接受的快照。

## 正式保存与阅读

通过已有独立审阅及确定性准入后，以新增文件保存：

```text
sources/originals/<方向>/<source-id>-<snapshot-sha256>.md
```

正式来源卡与研究报告链接对应原文，资料索引增加“原文归档”。原文快照不是第二份来源身份，也不作为额外独立证据计数。不同显式批次可记录各自精确快照，日常研究仍按原始URL/arXiv身份去重；旧原文、旧报告和人工笔记不覆盖。

可信publisher核验正式Markdown与绑定原文一致，仍只接受UTF-8 Markdown/YAML/散列文件，不开放任意二进制上传。包含最多5份原文的准入计划单文件上限12MB，其他传输文件继续2MB；超限不入库。GitHub及Obsidian读取同一份正式原文，手机沿现有Sync配置接收；本次不改`.obsidian`或同步设置。

## 本次验收与命令

一篇arXiv论文与一篇美团博客已真实获取并保存到[测试采集记录](../reports/test/agent-memory/research-batches/original-archive-check-20261030/collection-only.yaml)，分别抽取88,776和13,757字符，精确离线重放通过。美团文章是采集适配验收样本，不是新选中的Agent Memory研究。没有模型调用或正式研究准入。

[六个官方入口的只读覆盖回执](../reports/test/agent-memory/collections/coverage-archive-20261030/coverage.yaml)保存请求范围与响应散列；其中sitemap/Feed条数只是元数据检查，不能当本轮实际研究数量。

完整模拟验收覆盖断网Research/Insight与准入、ID映射、引用、人工保护、缓存、HTML/PDF与摘要降级、归档篡改拒绝；模拟材料不作为真实研究结论。

```sh
PYTHONPATH=tests python -B -m unittest test_feeds test_blog_archive_discovery test_archive test_archive_admission
python -B workflows/validate.py --include-test
python -B scripts/researchdesk_catalog.py --check
git diff --check
```

所有上述校验均不调用研究模型。实际新轮次研究与正式回存效果须看之后Actions运行和对应准入回执，不能用本次公开采集或离线样例代替。
