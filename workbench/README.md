# 研究工作台使用说明

[研究首页](../研究首页.md) · [正式资料索引](资料索引.md) · [Obsidian 动态视图](动态资料库.md) · [我的研究问题](../notes/我的研究问题.md)

研究首页只提供稳定导航；正式资料索引集中展示综合报告、单篇分析、洞察、选题、稿件、来源卡和原文归档。新轮次正式原文位于`sources/originals/<方向>/`，旧卡片可能尚无快照；归档量与模型实际阅读范围分开记录。普通Markdown链接可在Obsidian、GitHub和手机上阅读，不改动原文件名与身份。

## 一份索引与可选动态视图

`scripts/researchdesk_catalog.py` 只读取本地已接受的 Research/Insight 和 Writing 准入记录，核验计划、历史链接修正和正式文件，生成一个 Markdown 索引。不联网、不研究、不调用模型、不确认选题。只显示本地已同步的正式结果，日期为研究轮次。

```sh
python -B scripts/researchdesk_catalog.py          # 打印预览
python -B scripts/researchdesk_catalog.py --check  # 检查是否最新
python -B scripts/researchdesk_catalog.py --write  # 显式更新固定索引
```

索引中的 `researchdesk:catalog:start` / `end` 注释围住自动区，起始标记保存该区内容散列。生成器只更新自动区；区外文字保持原样，区内人工修改会停止覆盖。需要自己的判断时放到区外或 `notes/`。首个手工索引保留在文件下方的历史快照区，不自动重写。

正常 Research 正式准入后，可信发布步骤会在本地重新生成并随成果回存索引。索引生成失败会保留内容并提示，不阻断已审阅研究保存；手动准入或 Writing 正式准入后可用上面的 `--write` 更新。

现有三个 Obsidian Bases 视图继续作为可选浏览方式：综合报告、洞察、选题。同步新文件后动态读取目录和属性，不做完整准入校验。GitHub 不渲染 `.base`，直接使用 Markdown 索引即可。没有新增阅读网页或插件，也不修改 `.obsidian` 配置。

## 选题与人工笔记

选题卡的 `status: proposed` 是生成时快照，当前确认、撤回和 Writing 执行状态以[当前 Mac 的确认页](http://127.0.0.1:8765)为准。写作必须绑定实际页面确认，正式稿件仍未授权发布公众号。手机上的同一地址指向手机，不能连接 Mac。

在[我的研究问题](../notes/我的研究问题.md)或独立笔记里保存批注，通过链接关联正式研究。已准入资料、历史版本、test 检查点和接受证明保留原样；不要为整理目录而移动它们。可以在文件树折叠测试与回执目录，日常从首页进入。

## Mac 与 iPhone 同步

GitHub 保存成果和版本；Mac 先沿现有 Git 流程收到新文件，再由自行配置的 Obsidian Sync 同步到 iPhone。Sync 不代替 Git 拉取。两端打开 Obsidian 并等待同步完成后再阅读或编辑。

如使用 Bases，可在每台设备启用核心插件 Bases，并按需在 Sync 选择性同步里启用 **Sync all other types（同步所有其他文件类型）**，以同步 `.base`；设置按官方说明逐设备检查。已有社区插件配置保持原样，阅读工作台不要求新增插件。[同步设置](https://obsidian.md/help/sync/settings)

将“研究首页”加入 Obsidian 书签即可作为日常入口。Obsidian 与 Sync 都不承担模型执行；GitHub Actions 和配置的自托管主机负责研究。

## 校验

在仓库根目录、已安装依赖的隔离 Python 环境执行：

```sh
python -B workflows/validate.py --include-test
python -B scripts/researchdesk_catalog.py --check
```

格式与散列通过不代表 Obsidian 界面已经人工验证。现有 Bases 公式和布局可在 App 中查看。
