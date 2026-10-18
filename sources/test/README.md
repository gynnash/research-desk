# 测试资料

测试索引、说明和辅助结果放在 `test/<topic>/`。完整来源记录分别放在 `sources/papers/test/<topic>/<id>.md` 和 `sources/blogs/test/<topic>/<id>.md`，保持正式 Frontmatter Schema，正文明确注明离线虚构样例。

测试与正式资料分别查重，禁止通过 `related_sources` 或 `related_notes` 互链。运行 `python3 workflows/validate.py --include-test` 校验全部来源；默认命令仅校验正式来源。类型目录的 `test/` 内只放来源记录及目录占位，不放说明 Markdown。既有 `sources/papers/test.md` 仍是原有资料，不能当作测试目录豁免。

每份来源只在一个主研究方向目录保留一份；其他方向通过 `topics` 表达，不复制来源。

