# 共享会员请求预算

[membership_budget.yaml](../config/membership_budget.yaml) 设置工作台的本地月度请求预留上限。它不代表 ChatGPT 官方会员额度、剩余额度或费用。

Research、Insight、Writing 共用真实请求账本与本地锁。成功、失败、结果未知的请求都计入预留，按 UTC 月份累计；模拟调用不计入。更改上限不清零已发生的请求，模型也不能自行调整策略。

每轮还有阶段预算，来自运行 YAML 和写作确认时冻结的配置。为修订保留的余量不足时，不保证每份候选都完成；不能换 ID 绕过限制。归档的历史调用计数可保留在 `config/research_state.yaml`，无需保留论文、URL或生成文章。

## 只读查看

下列命令不登录、不请求模型、不创建研究资料：

```sh
.venv-membership/bin/python -B - <<'CHECK'
from pathlib import Path
import sys
sys.path.insert(0, str(Path('scripts').resolve()))
from researchdesk_batch import monthly_budget
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
