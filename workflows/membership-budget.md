# 共享会员请求预算

之前的“每月 10 次”是 ResearchDesk 为小额度测试自行设置的请求次数限制，保存在单篇入口默认值、Research/Insight 测试 YAML 及对应运行清单中。这个数字不表示 ChatGPT 官方会员额度、剩余额度或费用。单篇测试使用 2 次、Research 批次使用 4 次、Insight 批次使用 4 次，历史累计预留为 10 次。

按用户后续授权，当前统一配置入口为 [`config/membership_budget.yaml`](../config/membership_budget.yaml)：

```yaml
schema_version: 1
backend: chatgpt_plan
month_max_calls: 100
```

本工作台当前为 **已预留 10 次 / 本地月度上限 100 次**。这个修改不请求模型、不清零历史、不返还失败或未知请求，也不证明会员仍有 90 次可用。会员真实剩余额度、官方限流和授权状态仍须以实际服务为准；不可核实时保持未知。

## 配置优先级与保护边界

- 集中配置存在且有效时，`month_max_calls` 是同一工作台真实会员入口的当前共享月度上限，优先于旧运行及已绑定批次配置中的月度值。
- 集中配置缺失时，保留原来的保守规则：使用当前入口配置与本月历史运行月度上限的最小值。配置无效时停止，不当作缺失继续运行。
- 单篇、Research 和 Insight 共用真实请求账本及并发锁；按调用预留事件累计，包括成功、失败或终态不明的请求。当前实现按 UTC 月份记账，跨月不会重置已有批次的调用及修订次数。
- `mock` 和离线虚拟单位预算保持原样，集中配置只作用于 `chatgpt_plan`。单篇/Insight 最多 4 次、Research 批次最多 6 次、单项最多 4 次以及一次修订的限制继续有效。
- 调整月度策略只影响后续请求准入；不得修改已绑定的 Research/Insight YAML、旧清单、检查点、回执或验收说明。历史 `10/10` 是当时的策略快照，继续保留。
- 预算配置由用户或维护者明确调整，模型没有修改权限。文件不含凭据，拒绝重复键、未知字段、无效数值及符号链接；`month_max_calls` 当前允许 2–1000 的整数。

改变本地请求上限不会启用定时任务、自动入库、Writing 或公众号发布，也不会自动发起新一轮研究。

## 只读复核

在仓库根目录执行下列命令，不登录、不请求会员模型、不创建新的研究产物：

```sh
.venv-membership/bin/python -B - <<'PY'
from pathlib import Path
import sys

sys.path.insert(0, str(Path('scripts').resolve()))
from researchdesk_batch import monthly_budget

root = Path.cwd()
reserved, limit = monthly_budget(root, {
    'backend': 'chatgpt_plan',
    'budget': {'month_max_calls': 10},
})
print('本月累计预留请求：', reserved)
print('当前本地月度上限：', limit)
print('会员实际剩余额度：未知')
PY
```

本次变更后预期前两项为 `10`、`100`；以后有新请求时累计值会增加。命令中的 `10` 只用于不存在集中策略时的旧入口回退，存在有效集中配置时不会覆盖 `100`。该检查读取并校验既有账本，记录缺失或散列不匹配时应停止，不能以清空历史恢复额度。

配置和离线回归可通过下列检查复核；这些测试使用隔离样例，不消耗会员推理额度：

```sh
.venv-membership/bin/python -m unittest discover -s tests -v
.venv-membership/bin/python workflows/validate.py
.venv-membership/bin/python workflows/validate.py --include-test
git diff --check
```
