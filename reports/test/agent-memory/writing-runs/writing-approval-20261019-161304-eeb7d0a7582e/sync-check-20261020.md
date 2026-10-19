# Writing 执行、回存与 Obsidian 同步验收

> TEST：2026-10-20（Asia/Shanghai）。本次只复核已通过的真实 Writing 结果，新增会员调用为 0，未发布公众号。

## 检查与修复

原[零调用复核](https://github.com/gynnash/research-desk/actions/runs/39285266719)的执行日志显示入口失败、未建立回存 context；当时运行状态接口仍显示排队，不能据此认定尚未执行。原三阶段结果、6 次已完成调用和三稿均完整，无未知请求。

修复提交 `0051341`：GitHub 执行步骤显式使用已有的只读 token，Git fetch 采用进程级 credential helper，禁用交互，不保存凭据；失败返回固定认证、网络或超时错误码。`max_new_calls=0` 对已有完整通过批次改为纯确定性复核，完全绕过会员客户端、OAuth 刷新、账户和模型目录查询以及推理。原确认、最新远端撤回、172 项冻结输入、三阶段独立审阅、原笔记和预算门禁继续生效，未修改原提示词、确认配置或调用账本。

0 次模式追加唯一的 test 验证凭据，并由独立保存作业重验源码提交、确认、原回执、三稿散列和零调用字段；旧文件仍采用同字节复用、不同字节停止的规则。

## 远端实测

| 环节 | 结果与证据 |
| --- | --- |
| Writing 复核 | [运行 39287414087](https://github.com/gynnash/research-desk/actions/runs/39287414087) 的 write 步骤全部成功；`test_accepted`、`completed_calls: 6`、`new_model_calls: 0`、`no_membership_contacts: true`、`publish_authorized: false`。 |
| Artifact | 导出 2 个新 test 文件；连同传输 manifest 共上传 3 个文件，artifact ID `12203127945`。 |
| 结果回存 | 独立 save 步骤全部成功；`saved_files: 2`，提交 `244bbe30dfb3712f65207844726d404aa6c6a83f`。与源码提交比较，仅新增验证 YAML 及配对 SHA-256。 |
| 离线 CI | [运行 39287373370](https://github.com/gynnash/research-desk/actions/runs/39287373370) 的 Schema 与 39 项测试通过：轮次 6、URL 查重 7、准入 4、确认页 7、Writing 12、Git 认证刷新 3。全部使用模拟传输，不调用会员。 |

实际结果以步骤和日志、已上传 artifact、已推送文件为证；本次观察到聚合运行状态接口滞后，排队标签不代替执行结果。

验证凭据见 [gha-39287414087-1.yaml](verifications/gha-39287414087-1.yaml)。其 SHA-256 为 `3ad9c9ea666f90a775d95429187ba71c0ddabb88d8fc27ba154ab6e8916a1231`，绑定原 [receipt.yaml](receipt.yaml) 及三稿的完整散列。

## Obsidian 入站验证

远端凭据创建后，保持 Vault 工作区干净，全程未手动对 Vault 执行 fetch、pull 或 merge。既有 Obsidian Git 插件在原拉取周期内，将 Vault 从 `0051341` 自动快进到 `244bbe3`。通过现有 Obsidian HTTPS 接口读回新增 YAML 和校验文件，均与磁盘逐字节相同，YAML 散列与 GitHub 读回值一致。

现有 Git 插件配置散列保持 `b067b12b0b7a4580227ff8b86c62b0f81e2185caa3cd8e888f6e5e59abfd96a5`；每 10 分钟备份、每 5 分钟拉取配置未改。Vault 外确认页面的独立工作副本已更新并重启，页面与 Obsidian 接口读回三稿均与原输出散列相同。

最终复核：完整输入与独立审阅证明仍通过，三个原稿及原回执未改写，正式资料和人工笔记保持原样；共享月度预留仍为 **31/100**，会员新增调用为 **0**。本记录证明本轮“Writing 复核 → GitHub 回存 → Obsidian 自动拉取及读回”成功，不替代后续每轮的实际回执。
