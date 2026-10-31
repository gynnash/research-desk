# 共享会员请求预算

[membership_budget.yaml](../config/membership_budget.yaml) 设置同一工作台的本地月度请求预留上限，当前为 `month_max_calls: 100`。它是项目的用量控制策略，不代表 ChatGPT 官方会员额度、剩余额度或费用。早期 10 次是历史测试限制，不再作为当前策略。

Research、Insight 和 Writing 共用真实请求账本及本地锁，成功、失败、终态未知的请求都计入预留；按 UTC 月份累计。更改上限不清零旧请求、不返还失败预留，也不会自动启动任何任务。模型没有调整策略的权限。

集中配置存在且有效时优先使用；缺失时回退到旧入口和历史策略的保守最小值，配置无效则停止。当前配置允许 2–1000 的整数，不含凭据。既有运行清单仍保留启动时的历史策略。

每轮还有更严格的预算：当前 Research → Insight 总上限 16 次，其中 Research 最多 12、Insight 最多 4；正常 5 份研究加审阅需要 10 次，余量不足时不能保证每份都完成修订。Writing 原确认通常最多 12 次，每阶段最多 4 次、一次修订；页面单次派发最多新增 6 次。最终以绑定清单和当前策略共同校验，不可换 ID 绕过。

## 只读查看

在仓库根目录执行，不登录、不请求模型、不创建研究资料：

```sh
.venv-membership/bin/python -B - <<'CHECK'
from pathlib import Path
import sys

sys.path.insert(0, str(Path('scripts').resolve()))
from researchdesk_batch import monthly_budget

reserved, limit = monthly_budget(Path.cwd(), {
    'backend': 'chatgpt_plan',
    'budget': {'month_max_calls': 10},
})
print('本月累计预留请求：', reserved)
print('当前本地月度上限：', limit)
print('会员实际剩余额度：未知')
CHECK
```

命令中的 `10` 仅为缺少集中策略时的旧入口回退，不覆盖有效集中配置的 `100`。累计值读取真实账本，不在文档硬编码；散列不匹配、记录缺失或存在未知请求时先核查原轮次，不能通过清空历史恢复额度。离线模拟测试不计入真实会员预算。

本地锁不能协调其他克隆或其他主机的账户请求，执行统一经过[自托管队列](self-hosted-worker.md)，不要从多份副本并行调用。
