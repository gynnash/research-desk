# 论文与博客 Markdown Schema v1

每个新增的 `sources/papers/**/*.md`、`sources/blogs/**/*.md` 文件必须以 `---` 开始，以第二个独占一行的 `---` 结束 YAML Frontmatter，随后是 Markdown 正文。使用 UTF-8，YAML 键不得重复；字符串日期须加引号。模板中的空字符串必须填写后才能成为正式资料。

## 公共字段

| 字段 | 类型 | 约定 |
| --- | --- | --- |
| `schema_version` | 整数 | 必填，当前为 `1`。 |
| `id` | 字符串 | 必填，`paper-<UUID v4>` 或 `blog-<UUID v4>`，全库唯一且永久稳定。 |
| `kind` | 字符串 | 必填，`paper` 或 `blog`，与所在目录一致。 |
| `title` | 字符串 | 必填，原文标题；译名可写在正文。 |
| `source` | 字符串 | 必填，来源平台、期刊或博客名称，如 `arXiv`。 |
| `source_url` | 字符串 | 必填，原始来源的公开 HTTP(S) URL，不含账号密码。 |
| `authors` | 字符串列表 | 必填，未知时为 `[]`。 |
| `published_at` | 日期字符串或 null | 必填，原文首次发布日期，格式 `YYYY-MM-DD`；未知为 `null`。 |
| `collected_at` | 日期字符串 | 必填，首次录入本库的日期。 |
| `updated_at` | 日期字符串 | 必填，本地记录最后修改日期，不早于 `collected_at`。 |
| `topics` | 字符串列表 | 必填，至少一个 `config/research_topics.yaml` 中的主题 ID。 |
| `status` | 字符串 | 必填，`inbox`、`reading`、`analyzed`、`archived` 之一。 |
| `related_sources` | 字符串列表 | 必填，关联资料的稳定 ID；没有则 `[]`，不得自关联或重复。 |
| `related_notes` | 字符串列表 | 必填，已存在研究文件的仓库相对路径；没有则 `[]`。限 `reports/`、`insights/`、`articles/` 下的 `.md` 文件。 |

`related_notes` 可填写 `reports/example-topic/cycle-summary.md` 这样的仓库相对路径，填写前须创建该文件。它不是 Obsidian 双链语法；正文可另外添加可点击的相对链接。移动文件时同步修改路径引用。`related_sources` 保持 ID 引用，因此移动来源文件不会改变资料身份。

## 论文扩展字段

| 字段 | 类型 | 约定 |
| --- | --- | --- |
| `arxiv_id` | 字符串或 null | 可选；已知时填写去掉 `vN` 的基础编号，支持现代编号和旧式“分类/编号”形式。旧式分类统一小写。 |
| `doi` | 字符串或 null | 可选；已知时填写小写裸 DOI，去掉 `doi:`、`https://doi.org/` 等前缀。 |
| `source_version` | 字符串或 null | 可选；当前阅读的原文版本，如 `"v2"`。不影响记录 ID。 |

博客不使用这三个字段。论文已知 arXiv ID 或 DOI 时应填写，便于跨发布平台去重。没有的信息写 `null` 或省略可选字段；不要编造。新增扩展字段前，应同时修订本规范、模板与校验器，必要时升级 Schema。

## 状态与正文

- `inbox`：已收集，尚未开始阅读。
- `reading`：正在阅读或验证关键结论。
- `analyzed`：已完成一轮分析，记录结论、证据及局限。
- `archived`：暂不继续研究；保留来源、笔记和关联。

这些状态由人工判断，可以回退，不代表自动生成任务。主题停用不会使历史资料失效；不删除仍被资料引用的主题 ID。

正文不设机器维护区：摘要、结论、证据、局限、人工笔记和更新记录全部视为人工内容。模板只提供建议标题，允许调整，不强制固定章节。自动流程只创建独立新材料，并通过绑定输入和独立审阅后准入；本 Schema 不授予覆盖正文、研究状态或关联的权限。

## 离线测试与主题目录

运行产生的新资料按主要研究方向放入 `sources/papers/<primary-topic>/` 或 `sources/blogs/<primary-topic>/`，多主题仍共用一个 ID。测试来源放在 `sources/<papers|blogs>/test/<topic>/<id>.md`，严格使用同一 Schema，`topics` 必须包含所在方向，正文须有统一 TEST 虚构横幅。

测试审阅结果记在运行清单，不增加 Frontmatter 字段；通过模拟门禁的来源仍初始化 `inbox`。正式与测试来源的 ID 全局唯一，身份重复在各自区域分别检查，Frontmatter 的 `related_sources`/`related_notes` 不得跨区。默认校验正式资料，`--include-test` 同时检查测试资料；测试目录不是旧资料豁免。运行与检查入口见[操作说明](README.md)。

真实来源采集测试不标成虚构原文，其统一横幅为 `> TEST：真实来源采集，分析与审阅均为模拟，不可作为正式研究结论。`。原始元数据与模拟分析必须区分，正文只保留必要短证据。

## 原文快照独立类型

`sources/originals/<topic>/<source-id>-<snapshot-sha256>.md`使用`kind: original_snapshot`，保留`schema_version`、标题、`source_id`、`topics`、原文URL、获取时间、内容散列、抽取范围`coverage`与实际研究范围`research_coverage`。可附作者、来源、发表日期与版本。它不分配第二个来源UUID，不参与论文/博客身份重复计数，也不能冒充第二份独立研究证据。

快照由已绑定的原文检查点确定性生成、正式准入仅新增；篡改归档或派生正文会使重放校验失败。兼容模式中的摘要材料必须标明`abstract_only`，不因保存原文而修改实际阅读范围。默认全文模式在获取不完整时跳过。论文优先固定版本官方 HTML，缺失时提取 PDF；归档正文、交给模型的材料和实际研究结果分别记录，不能因保存了完整正文而声称模型已阅读全文。
