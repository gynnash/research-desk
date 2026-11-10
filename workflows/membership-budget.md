# 共享会员请求预算

[membership_budget.yaml](../config/membership_budget.yaml) 设置工作台的本地月度请求预留上限。它不代表 ChatGPT 官方会员额度、剩余额度或费用。

Research、Insight、Writing 共用真实请求账本与本地锁。成功、失败、结果未知的请求都计入预留，按 UTC 月份累计；模拟调用不计入。更改上限不清零已发生的请求，模型也不能自行调整策略。

Codex SDK 通过本机 Responses 网关转发，每一次上游请求（包括 SDK 的重试）都在转发前独立预留，账本位于 `reports/test/<主题>/codex-requests/<批次>/`。旧后端也会统计这部分请求，不把一个 task/turn 算成一次模型调用。SDK 示例每任务另限 3 次，查询原线程使用上限为 0 的网关，不能触发推理；所有计数仍是本地预留，不能替代 ChatGPT 官方用量显示。

每轮还有阶段预算，来自运行 YAML 和写作确认时冻结的配置。自动研究的 `research.budget.max_calls_per_cycle` 限制同一主题、同一批次的 Research 与 SDK 实际请求总数，`insight_max_calls` 额外限制 SDK 阶段；旧请求跨月或进入新 retry attempt 仍占原批次额度。每次预留均检查这些上限以及当前共享月度上限，超过即在发送前停止。Writing 使用人工确认时冻结的独立阶段预算，继续共享月度账本。

为修订保留的余量不足时，不保证每份候选都完成。明确失败的 SDK 请求可显式重试一次，已完成阶段复用；结果未知时先查询旧 turn，不直接重发。所有旧预留保留，不因 retry attempt 改名释放。归档的历史调用计数可保留在 `config/research_state.yaml`，无需保留论文、URL或生成文章。

## 只读查看

下列命令不登录、不请求模型、不创建研究资料：

```sh
.venv-membership/bin/python -B - <<'CHECK'
from pathlib import Path
import sys
sys.path.insert(0, str(Path('scripts').resolve()))
from batch import monthly_budget
reserved, limit = monthly_budget(Path.cwd(), {
    'backend': 'chatgpt_plan',
    'budget': {'month_max_calls': 100},
})
print('本月累计预留请求：', reserved)
print('当前本地月度上限：', limit)
print('会员实际剩余额度：未知')
CHECK
```

有效集中配置优先于命令中的回退值。记录损坏或请求终态未知时先核查原轮次，不自动重发。本地锁不能协调其他克隆或其他主机的请求；部署时通过统一[执行队列](self-hosted-worker.md)运行。
