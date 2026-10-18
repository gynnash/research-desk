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

`related_notes` 示例：`["reports/2026-10-18-agent-memory-survey.md"]`，填写前须创建该文件。它不是 Obsidian 双链语法；可在正文另加 `[研究综述](../../reports/2026-10-18-agent-memory-survey.md)` 方便点击。移动文件时同步修改路径引用。`related_sources` 保持 ID 引用，因此移动来源文件不会改变资料身份。

## 论文扩展字段

| 字段 | 类型 | 约定 |
| --- | --- | --- |
| `arxiv_id` | 字符串或 null | 可选；已知时填写去掉 `vN` 的基础编号，如 `"2501.12345"` 或 `"hep-th/9901001"`。此处数字仅示范格式。旧式分类统一小写。 |
| `doi` | 字符串或 null | 可选；已知时填写小写裸 DOI，去掉 `doi:`、`https://doi.org/` 等前缀。 |
| `source_version` | 字符串或 null | 可选；当前阅读的原文版本，如 `"v2"`。不影响记录 ID。 |

博客不使用这三个字段。论文已知 arXiv ID 或 DOI 时应填写，便于跨发布平台去重。没有的信息写 `null` 或省略可选字段；不要编造。新增扩展字段前，应同时修订本规范、模板与校验器，必要时升级 Schema。

## 状态与正文

- `inbox`：已收集，尚未开始阅读。
- `reading`：正在阅读或验证关键结论。
- `analyzed`：已完成一轮分析，记录结论、证据及局限。
- `archived`：暂不继续研究；保留来源、笔记和关联。

这些状态由人工判断，可以回退，不代表自动生成任务。主题停用不会使历史资料失效；不删除仍被资料引用的主题 ID。

正文不设机器维护区：摘要、结论、证据、局限、人工笔记和更新记录全部视为人工内容。模板只提供建议标题，允许调整，不强制固定章节。未来如引入自动化，必须先制定单独的写入规则和审核流程；不得根据本 Schema 推定可以覆盖正文、研究状态或关联。
