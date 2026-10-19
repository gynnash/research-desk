# 当前 Writing 三稿正式准入验收

日期：2026-10-20（Asia/Shanghai）。本次由用户明确要求将当前已确认、已审阅三稿正式入库，不授予公众号发布权限。

已核验原[页面确认](../../writing-approvals/approval-20261019-161304-eeb7d0a7582e/confirmed.yaml)仍有效、未撤回并已同步；原测试 Writing 三阶段独立审阅均通过，6 个请求均已完成、没有未知请求。准入基于代码提交 `e94d82f`，绑定 229 项原始输入与审阅证明的散列，计划及接受回执见 [plan.yaml](plan.yaml) 和 [accepted.yaml](accepted.yaml)。

以新增文件方式保存三稿：

- [正式大纲](../../../../articles/agent-memory/writing-approval-20261019-161304-eeb7d0a7582e-outline.md)
- [正式初稿](../../../../articles/agent-memory/writing-approval-20261019-161304-eeb7d0a7582e-draft.md)
- [正式候选稿](../../../../articles/agent-memory/writing-approval-20261019-161304-eeb7d0a7582e-candidate.md)

正文只进行测试标识、正式 ID／状态及相对引用的机械转换。原文字句、原始来源 URL、论文摘要／博客节选／历史笔记的阅读范围、作者主张与我们的推断均保留；所有本地正文引用存在且不指向 test。正式稿 `production_accepted: true`，`publish_authorized: false`。

本次实际执行禁用了会员客户端初始化、账户查询、模型查询、推理及资料重采集入口；新增会员调用为 **0**，共享月度预留仍为 **31/100**。原[测试回执](../../../test/agent-memory/writing-runs/writing-approval-20261019-161304-eeb7d0a7582e/receipt.yaml)、全部 test 结果及人工笔记保留：执行前登记的 **684 个既有资料文件逐个 SHA-256 比对未变**。重复准入返回 `cached: true`，新增文件为 0，已生成三稿及机器回执字节均不变。

5 项新增隔离验收通过，覆盖正式三稿与引用、幂等恢复、未同步／撤回／审阅或测试稿变化的拒绝、目标冲突／符号链接／人工改稿保护，以及页面只读展示和历史读取。配置扩展允许方向后，历史正式稿仍可读，不能据此重新绑定旧准入。所有真实会员入口及网络采集在测试中均被禁止。

页面数据接口已验证：原 TEST 三稿保留，另有 3 个通过准入散列核验的正式稿入口；正式稿人工修改后保留文件并停止将其作为原审阅版本展示。部署后在“确认记录”查看“正式稿件 · 已入库，未发布”，说明与命令见[正式准入工作流](../../../../workflows/writing-formal-admission.md)。
