# 正式入库与每周研究启用验收：2026-10-19

[正式入库工作流](https://github.com/gynnash/research-desk/actions/runs/39153702881)的计划、Mac 准入和 Ubuntu 回存三个 job 均通过。工作流提交 `379bf6d` 已快进同步回现有 Obsidian Vault，既有笔记及原测试回执的散列保持不变。

## 已入库

准入对象为此前已完成真实独立审阅的 `cycle-agent-memory-gh-20261019`，新增 7 份正式 Markdown：

- 2 份来源笔记，保存在 `sources/papers/agent-memory/` 和 `sources/blogs/agent-memory/`，阅读状态为 `inbox`。
- 2 份单来源研究和[1 份综合报告](../reports/agent-memory/cycle-agent-memory-gh-20261019-synthesis.md)，保存在 `reports/agent-memory/`。
- [1 条洞察](../insights/agent-memory/cycle-agent-memory-gh-20261019-insight-1.md)及[1 张待确认选题](../articles/agent-memory/cycle-agent-memory-gh-20261019-topic-1.md)，分别保存在 `insights/agent-memory/` 和 `articles/agent-memory/`。

[正式准入清单](../reports/agent-memory/admissions/cycle-agent-memory-gh-20261019/accepted.yaml)最后落盘，记录输入与输出散列、独立审阅链及身份映射。已有测试博客保留原 UUID，正式博客使用新 UUID；只有已接受的映射才用于后续查重归一，不会把两份笔记误判成互相冲突的新来源。原来源、状态、人工笔记和旧测试回执未覆盖。

本轮复用已审阅结果，**新增模型调用为 0**；账本仍为 25/100 本地月度预留，会员真实剩余额度未知。来源覆盖仍仅为论文摘要和博客节选，来源列表扫描未全量完成；正式准入不等于复现实验或验证行业趋势。

## 关键检查

4 项准入验收通过：正常新建与同轮次零新增、人工目标冲突保留、首个文件创建后恢复、模拟后端或非通过审阅拒绝。测试使用真实证明的临时副本并禁用网络和模型。既有 5 项轮次检查、资料 Schema、YAML 散列和新文件引用也已核对；不以完整旧测试集反复运行代替实际闭环。

入库后，同一博客通过正式身份与历史测试身份映射仍判为 `duplicate`。历史选择仅纳入有 accepted 清单登记的新 AI 文件；未完成入库的半成品不会成为下轮历史。人工修改后的已入库笔记使用当前散列作为未重新核实的历史基线，不覆盖人工修改。

首次远端准入在拉取代码时遇到 Mac 服务缺少终端代理的问题，未进入模型调用；停止后使用同一轮次补跑成功。执行器现从当前主机环境继承代理到仓库外的受保护 `.env`，注册文件兼容官方 UTF-8 BOM，不重新登录或复制会员凭据。此配置遵循 [GitHub 自托管代理说明](https://docs.github.com/en/actions/how-tos/manage-runners/use-proxy-servers)。

入库后的链接核查发现，两份新来源笔记的机器页脚相对路径需要多返回一层目录。已仅修正这两份本轮生成文件的页脚链接，7 份正式 Markdown 的本地引用全部存在；原准入计划、accepted 回执、旧测试记录和受保护笔记的散列均保持不变。[追加的修复记录](../reports/agent-memory/admissions/cycle-agent-memory-gh-20261019/link-repair.yaml)绑定修正前后散列；同一修复重放无变化、无需网络或模型。后续生成已修正目录计算，并在准入前检查链接。

## 定时配置

正式准入与同步通过后，[`automation.yaml`](../config/automation.yaml)设为 `enabled: true`；工作流 cron 为 `0 1 * * 2,5`，对应每周二、周五北京时间 09:00。当前启用时间不包含部署前的时间槽，下一次计划为 **2026-10-20 09:00（北京时间）**。实际首个 schedule 执行尚未发生，GitHub 可能延迟，Mac 需保持联网、唤醒、用户服务及本机所需代理运行。

时间槽使用稳定轮次 ID，最多回看 14 天、每次恢复 1 个未完成槽。已准入、无新资料或已记录终结决定的槽不盲目重复付费；未知请求保留预留。恢复命令与主机配置见[部署说明](self-hosted-worker.md)，正式门槛见[准入说明](formal-admission.md)。

[启用后的补跑计划验收](https://github.com/gynnash/research-desk/actions/runs/39153934408)通过：当前周一没有到期时间槽，计划 job 成功，分析与回存 job 跳过，未新增模型调用。此结果验证了空窗口门槛，不代表首个定时研究已经执行。

选题保持 `proposed`、`approval_required: true`、`writing_started: false`、`publish_authorized: false`。本轮没有确认选题、启动 Writing 或发布公众号。
