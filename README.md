# ResearchDesk

ResearchDesk 是一个长期积累的 AI 技术研究知识库：保存论文与技术博客的来源、阅读笔记和研究结论，发现技术趋势，并为微信公众号文章提供可追溯的素材。

当前只建设知识库基础设施。资料收集、阅读、分析和 Git 同步均由人工执行；尚未开发 Research Agent、抓取程序、定时任务或自动发布功能。不使用数据库和 Agent 框架。

## 目录结构

```text
research-desk/
├── config/
│   ├── research_topics.yaml    # 研究方向及启用状态
│   └── legacy_sources.yaml     # 初始化前旧资料的明确兼容清单
├── sources/
│   ├── papers/                # 论文，一篇论文一个 Markdown 文件
│   └── blogs/                 # 技术博客，一篇原文一个 Markdown 文件
├── reports/                   # 跨资料的专题研究、阶段综述
├── insights/                  # 可复用的观点、趋势假设与证据
├── articles/                  # 微信公众号选题、大纲与文章草稿
└── workflows/
    ├── source-schema.md       # 资料字段与状态定义
    ├── maintenance.md         # 去重、更新和人工笔记保护规范
    ├── templates/             # 论文、博客模板；不是真实资料
    ├── requirements.txt       # 仅用于本地校验的 PyYAML 依赖
    └── validate.py            # 只读检查，不收集或修改研究资料
```

主题通过 Frontmatter 的 `topics` 表达，不为多个主题复制同一份资料。`agent-memory` 首先启用，`agent-rl` 为停用的扩展示例；启用主题只表示研究范围，不会触发任务。Obsidian 直接将仓库根目录作为 Vault 打开。

## 录入一份资料

1. 按照[维护规范](workflows/maintenance.md)先检索全库的 arXiv ID、DOI 和原始 URL，确认是否已有记录。
2. 从[论文模板](workflows/templates/paper.md)或[博客模板](workflows/templates/blog.md)复制到相应的 `sources/` 子目录。文件名建议为 `<id>.md`。
3. 生成一个新 ID，填写标题、来源、日期等必填元数据，再写笔记。日期写成带引号的 `YYYY-MM-DD`；未知发布时间写 `null`，不要猜测。
4. 在 `topics` 中选用已配置的主题；用 `related_sources` 连接资料 ID，用 `related_notes` 连接已经存在的研究文件。正文可以补充 Markdown 或 Obsidian 双链，便于跳转。
5. 运行下方检查，通过后再提交。

生成稳定 ID（博客将 `paper-` 换成 `blog-`）：

```sh
python3 -c "import uuid; print('paper-' + str(uuid.uuid4()))"
```

完整字段见 [Markdown Schema](workflows/source-schema.md)。ID 一经建立，不随标题、文件名、研究主题或论文版本变化。正文、分析状态及研究关联由人工维护。更新原文时保留人工笔记，具体操作见[去重和更新规范](workflows/maintenance.md)。

初始化前的 `sources/papers/test.md` 原样保留，暂由 `config/legacy_sources.yaml` 明确豁免 Frontmatter 检查，并在每次校验时提示。新资料不得借用旧资料豁免；旧资料补齐元数据后，移除对应豁免项。

## 本地验证

在仓库根目录执行。需要 Python 3.9+，以及一个 YAML 解析依赖 PyYAML；无需 Obsidian 插件或后台服务。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r workflows/requirements.txt
.venv/bin/python workflows/validate.py
git diff --check
```

环境已具备 PyYAML 时，也可以执行 `python3 workflows/validate.py`。检查覆盖目录、配置和模板的 YAML 语法（含重复键）、主题字段、资料字段类型与状态、日期、全库 ID/来源重复，以及关联资料和研究文件是否存在。检查失败返回非零退出码，成功返回 `0`；旧资料豁免显示为警告。检查器不会联网或写文件，也不判断研究结论的质量。

## GitHub 与 Obsidian 同步

GitHub 保存仓库中的 Markdown、YAML、规范和历史版本；Obsidian 直接编辑同一份本地文件。Obsidian 本身不会把这些文件自动同步到 GitHub。本仓库保留原有 `.git` 和 `.obsidian`，不修改已有远程地址，也不配置自动同步插件。

每次在一台设备开始编辑前，先查看本地是否有未提交改动。在工作区干净时按以下顺序操作；首次使用且未配置远程或分支跟踪关系时，先自行完成 GitHub 仓库连接。

```sh
git status
git pull --ff-only
# 用 Obsidian 编辑资料，然后执行校验
.venv/bin/python workflows/validate.py
git diff --check
git diff
git add README.md .gitignore config sources reports insights articles workflows
git diff --cached
git commit -m "docs: update research notes"
git push
```

其他设备克隆同一仓库后，在 Obsidian 中打开该目录，并在编辑前拉取、编辑后提交并推送。已有未提交改动时先检查并保存自己的改动，再同步；快进拉取失败时，人工处理分支分歧，保留双方笔记内容，重新校验。不要使用强制推送或整文件覆盖来解决笔记冲突。避免多台设备同时编辑同一份资料，也不要让其他云盘服务同时同步该目录。

`.obsidian/` 继续整体忽略，因此本地插件配置、布局、偏好和可能存放其中的令牌留在各设备上。`.gitignore` 同时排除常见密钥、环境变量文件和缓存；它不会自动移除已被 Git 跟踪的敏感内容，提交前仍应检查暂存差异。凭据不要写进研究正文、配置或远程 URL；如曾泄漏，应撤销密钥并单独处理历史记录。
