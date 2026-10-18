# ResearchDesk 双向同步验证记录

日期：2026-10-18（Asia/Shanghai）
仓库：gynnash/research-desk，分支 main。

本文件是同步链路测试记录，不是研究资料或 Research Agent。

## 测试步骤

1. 已审阅初始化后续改动：现有 Vault 自动备份已提交并推送至 `732d451`。
2. 通过 Obsidian 已启用的本地接口创建本文件，核对写入位置为 ResearchDesk 仓库。
3. 已通过现有 Obsidian Git 的 Commit-and-sync 命令提交推送至 `ac70e9b`，并从 GitHub 读取验证原文及标记一致。
4. 已在 GitHub 写入独立回传标记，形成提交 `323873a`；现有 Obsidian Git 于 15:45:46 自动快进到该提交，未手动执行拉取。随后通过 Obsidian 接口读回验证，全文与 GitHub 写入内容一致。

## 验证标记

- Obsidian → GitHub：`researchdesk-sync-20261018-408a472366ff-outbound`
- GitHub → Obsidian：`researchdesk-sync-20261018-408a472366ff-inbound`

## 验证结果

| 项目 | 结果与证据 |
| --- | --- |
| 原有改动审阅 | `732d451` 包含 README 和校验器修复，检查通过，已在 GitHub。 |
| Obsidian → GitHub | 从 Obsidian 创建笔记，调用现有 Commit-and-sync 命令，提交 `ac70e9b`；从 GitHub 读回内容及标记一致。 |
| GitHub → Obsidian | 15:42:11 在 GitHub 回写，15:45:46 被现有插件自动拉取为 `323873a`；Obsidian 接口读回全文一致。 |
| 原有笔记 | `sources/papers/test.md` 与初始化前内容一致，未覆盖人工资料。 |
| 配置保护 | 未修改 Git 远端或 Obsidian 插件设置，插件配置文件的 SHA-256 与测试前一致。 |

本次双向同步实测通过。时间均为 Asia/Shanghai；这里记录一次成功验证，不代表对未来网络和每次定时执行作保证。

## 配置与范围

保留现有远程地址、分支、Obsidian 插件及配置，不开发 Research Agent。
当前插件设置为每 10 分钟备份、每 5 分钟拉取；正向使用现有插件命令主动触发，反向观察现有自动拉取周期，不修改配置。
