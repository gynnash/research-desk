# 研究工作台使用说明

[打开研究首页](../研究首页.md) · [动态资料库](动态资料库.md) · [普通资料索引](资料索引.md) · [我的研究问题](../notes/我的研究问题.md)

研究首页提供中文导航、最近一轮的导读、洞察、选题和稿件入口。普通 Markdown 链接可在 Obsidian、GitHub 和手机上阅读；原资料的文件名、唯一 ID 与准入证明保持原样，链接显示中文标题即可。

## 固定导读与动态列表

首页导读是整理时的阅读快照，不会因为新文件同步进来而自动重写。导读旁的日期表示其对应轮次；若看到更新轮次，请从下面的列表或正式目录进入。不能把旧导读当成当天新研究。

本目录提供三个 Obsidian Bases 视图，读取当前设备上的 Markdown 属性：

| 视图 | 内容 |
|---|---|
| [研究报告](研究报告.base) | Agent Memory 综合报告，按研究轮次排序 |
| [洞察](洞察.base) | 已保存的洞察与待验证判断 |
| [选题](选题.base) | 正式选题提案的历史卡片 |

文件同步到本机后，Bases 的列表会随本地资料变化。它们是阅读导航，按目录与属性筛选，不会运行完整准入校验，也不会生成、审阅或确认内容。正式入库的依据仍是对应轮次的 `accepted.yaml`、计划、配对散列及其绑定的正式文件；各正式文末保留准入记录链接。

GitHub 不渲染 Bases 视图；首页和普通资料索引保留 Markdown 导读及链接，即使没有 Bases 也能使用。要在 Obsidian 查看动态列表，可自行到“设置 → 核心插件”启用 **Bases**，然后打开[动态资料库](动态资料库.md)或单个 `.base` 文件；本次整理不更改 `.obsidian` 配置。使用方法见 [Bases 官方说明](https://obsidian.md/help/bases)。

首页导读与普通索引目前按整理日期维护，不会由定时研究任务自动改写。现有任务、正式准入与回存范围不变；后续更新可先核对新的正式准入，再整理新的导读快照。

## 选题确认与文章阅读

选题文件里的 `status: proposed` 是生成时的历史状态，不能据此判断它现在是否待确认、已撤回或已经开始写作。当前状态以确认记录、撤回事件和 Writing 执行回执为准；正式候选稿入库也不等于已经发布公众号。

需要确认角度、受众或启动写作时，在当前 Mac 打开[选题确认页](http://127.0.0.1:8765)。这个地址只连接打开浏览器的设备本机：在 iPhone 上点开会指向手机，不能直接访问 Mac 的确认服务。手机可以阅读同步的报告、选题和稿件。

## Mac 与 iPhone 同步

GitHub 保存正式成果和版本历史；Mac 先通过既有 Git 流程收到新文件，再由 Obsidian Sync 同步到 iPhone。Sync 不会代替 Git 拉取。

两端打开 Obsidian 并等待同步完成后再阅读或编辑。要让 `.base` 视图也随 Sync 同步，请在每台设备的“设置 → Sync → 选择性同步”检查 **Sync all other types（同步所有其他文件类型）**，按需启用；修改后按官方说明重启应用。Sync 的选择性同步设置需要逐设备配置，详见[同步设置与选择性同步](https://obsidian.md/help/sync/settings#Selective%20syncing)。保留各设备既有插件配置，不需要为了阅读首页同步社区插件。

可将“研究首页”加入 Obsidian 自带的书签，日常从该页进入；是否设为启动页、调整工作区或外观，由你自行选择。

## 保存自己的研究判断

在 [我的研究问题](../notes/我的研究问题.md) 中记录问题与批注，链接对应报告、洞察或文章，不改动已经绑定散列的正式产物。这些个人笔记当前不自动进入 Insight 输入；后续需要明确登记文件和阅读范围后再用于综合研究，不会因编辑笔记而调用模型。

## 文件校验

在仓库根目录、已安装 `workflows/requirements.txt` 依赖的 Python 环境中执行：

```sh
python workflows/validate.py --include-test
python - <<'PY'
from pathlib import Path
import yaml
from workflows.validate import UniqueKeyLoader

for path in sorted(Path('workbench').glob('*.base')):
    yaml.load(path.read_text(encoding='utf-8'), Loader=UniqueKeyLoader)
    print('YAML OK:', path)
PY
```

这些命令核验资料 Schema 和 Bases 的 YAML 格式，不会启动研究或调用模型；Obsidian 的公式执行及布局仍需在 App 中查看。
