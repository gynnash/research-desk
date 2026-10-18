# Insight Agent 真实测试验收

> TEST：2026-10-19；仅验证 Agent Memory 测试闭环，未正式入库。

基于已接受 Research 批次中的 A-MEM 论文摘要、Letta 博客节选，以及显式登记的 MemGPT、Memory Blocks、历史报告和两条洞察，生成以下产物。五份历史笔记仅作为人工基线，未声称本次重新复核历史原文。

- [综合报告](report.md)：记忆组织与上下文管理的评测边界。
- [洞察一](../../../../../insights/test/agent-memory/insight-agent-memory-20261019/insight-1.md)：分阶段检查记忆使用。
- [洞察二](../../../../../insights/test/agent-memory/insight-agent-memory-20261019/insight-2.md)：分别审视动态更新与上下文管理。
- [选题卡一](../../../../../articles/test/agent-memory/insight-agent-memory-20261019/topic-1.md)：记忆系统的考题，不只是“有没有存进去”。
- [选题卡二](../../../../../articles/test/agent-memory/insight-agent-memory-20261019/topic-2.md)：动态更新之外，Agent Memory 还要看谁管理上下文。

## 真实调用与恢复

生成使用 `gpt-6-luna`，独立审阅及格式确认使用 `gpt-6.1-sol`，均为用户自身官方授权的 ChatGPT 会员。实际完成 **4 次请求，43,163 tokens**（输入 37,931，输出 5,232），包含失败响应，未切换付费 API。会员剩余额度和金额无法核实时保持未知。共享月度测试请求累计 **10/10**；后续真实请求会被当前本地预算阻止，不能通过换批次重置。

1. 首次生成完成，但 JSON 顶层对象后多出一个 `}`；原始响应完整保存，未生成研究产物。
2. 使用唯一一次模型修订，第二份响应仍有同样的尾部语法问题。程序仅解析完整对象后的一个多余 `}`，不改动任何字段或值；严格拒绝重复键、NaN/Infinity、多余对象、文字和其他修补。`format_normalized` 事件绑定原始响应及解析候选散列，两份原始检查点均保留。
3. 独立内容审阅读取同一原文证据包、历史基线、候选与原始响应，逐项 `pass`；由于缺少专门的格式确认字段，产物仍未创建。用剩余的一次预算独立核对原始响应与候选，得到 `pass`、`format_normalization_acknowledged: true` 和具体理由。该确认不推翻内容拒绝，也不是第二次模型修订。
4. 两项独立审阅通过并持久化后，主动在写产物前中断，退出码为 `3`。使用禁止新增推理的后端补跑创建五份产物，再完整重放返回缓存。调用预留始终 **4 → 4 → 4**，见[恢复验证](replay-verification.yaml)。这同时包含真实格式失败恢复和一次计划中断验证，不表示服务端故障已被穷尽测试。

## 校验结果

- 257 项单元测试通过，其中 Insight 65 项；另有 14 项资料隔离测试通过，无跳过。
- 正式范围及包含测试范围的两种仓库校验均通过；原有 `sources/papers/test.md` 继续使用已登记的旧资料豁免。
- 五份产物散列、来源关联及本地引用有效，测试元数据不包含凭据字段。
- [275 个原有文件的基线](existing-files-baseline.yaml)逐项校验不变，覆盖正式资料、旧测试结果和已有配置；新文件只创建，不覆盖已有笔记。
- 两张卡均为 `proposed`、`approval_required: true`、`writing_started: false`、`publish_authorized: false`。没有选题确认入口、Writing 执行、定时任务或公众号发布。

机器可读细节见[验收记录](acceptance.yaml)、[运行回执](receipt.yaml)、[产物散列计划](artifact-plan.yaml)、生成/审阅检查点与事件日志。独立审阅仍指出：验证计划需要进一步设计受控对照，当前洞察是研究假设，不是实证效果结论。

## 可复现的离线检查

在仓库根目录使用已安装 `workflows/requirements-membership.txt` 的 Python 环境：

```sh
.venv-membership/bin/python -m unittest discover -s tests -q
.venv-membership/bin/python workflows/test/agent-memory/test_validate_isolation.py
.venv-membership/bin/python workflows/validate.py
.venv-membership/bin/python workflows/validate.py --include-test
git diff --check
```

复核已有文件和输出的内容散列，无需会员登录或模型调用：

```sh
.venv-membership/bin/python - <<'PYCHECK'
import hashlib
from pathlib import Path
import yaml
root = Path.cwd()
base = root / 'reports/test/agent-memory/insight-runs/insight-agent-memory-20261019'
receipt = yaml.safe_load((base / 'receipt.yaml').read_text())
baseline = yaml.safe_load((base / 'existing-files-baseline.yaml').read_text())['files']
for path, expected in {**baseline, **receipt['output_hashes']}.items():
    assert hashlib.sha256((root / path).read_bytes()).hexdigest() == expected, path
print('275 baseline files and 5 outputs unchanged')
PYCHECK
```

需要复核运行绑定与来源重取时，按[Insight 说明](../../../../../workflows/insight-agent-test.md)复用原配置和原批次。完整缓存重放不会新增推理；来源或历史输入变化时会停止，不能改用新批次绕过记录。
