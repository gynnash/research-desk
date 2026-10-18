# Writing Agent 离线闭环验收

> TEST：2026-10-19；全虚构选题、固定材料、模拟确认与模拟模型，不代表批准真实选题或公众号发布。

完成“虚构确认门禁 → 大纲 → 初稿 → 发布候选稿”的测试闭环。配置使用 `mock-writer` 生成、`mock-reviewer` 独立审阅，只有三个阶段全部通过才创建文章文件：

- [大纲](../../../../../articles/test/agent-memory/writing-offline-20261019/outline.md)
- [初稿](../../../../../articles/test/agent-memory/writing-offline-20261019/draft.md)
- [候选稿](../../../../../articles/test/agent-memory/writing-offline-20261019/candidate.md)

## 运行结果与确认边界

三个阶段均为 `test_accepted`。大纲与候选稿无修订；初稿中“保存后必然正确使用”的过度断言被固定模拟审阅要求修改，完成一次修订与完整复审。共 **8 次模拟调用、8 个虚拟单位，0 次真实会员推理**。虚拟单位不能换算为真实 tokens、成本或模型质量；真实会员本地累计仍为 **10/100**。

[确认记录](../../writing-approvals/fixture-writing-20261019.yaml)显式标记 `origin: offline_fixture`，只针对[虚构样例](../../../../../workflows/test/agent-memory/fixtures/writing.yaml)。确认绑定选题、标题、角度、受众、目标字数、证据与 fixture 散列及三个阶段范围。CLI 与 API 默认均为待确认；必须显式指定 `confirmed` 才能进行虚构演练。已有两张真实 Insight 选题卡保持待确认，既未获批也未启动真实写作。

原始初稿与审阅问题保留在 `checkpoints/draft-writing-0.yaml`、`checkpoints/draft-review-0.yaml`，修订结果另存，不覆盖原响应。各阶段输出区分虚构材料事实、虚构作者主张、我们的推断及解释性比喻，引用由程序指向固定证据。目标字数目前用于确认绑定；短固定样例没有验证真实文章的字数或文风质量。

## 中断、恢复与保护

[恢复记录](replay-verification.yaml)验证三种计划中断，退出码均为 `3`：

| 断点 | 累计模拟调用 | 保存状态 |
| --- | ---: | --- |
| `after_outline` | 2 | 大纲生成、独立审阅及阶段检查点持久化，无文章 Markdown |
| `after_review` | 8 | 三阶段全部审阅通过，尚未创建文章 |
| `after_first_output` | 8 | 仅创建 `outline.md`，其余两稿等待恢复 |

在全部模拟结果保存后，使用禁止任何新增推理的客户端继续完成及完整缓存重放，调用数保持 **8 → 8 → 8**。未知请求不会重发，人工改稿不会被覆盖。确认与撤回在每次请求和文件创建前重验；运行中追加撤回标记不等待主题锁，下一个操作门停止，已完成响应仍保留。撤回路径与未知结果等反例在临时工作台中验证，没有撤回或改写本次主样例。

## 验收检查

- **317 项单元测试通过**，其中 Writing 47 项；另有 **14 项资料隔离测试通过**，无跳过。
- 缺少/待定/拒绝/撤回确认、选题或角度受众变化、无效引用、模型自批准、审阅遗漏、预算停止、未知调用、额外修订、阶段跳跃、账本/模型绑定异常及人工改稿均有离线回归。
- 正式范围及包含测试范围的仓库校验均通过；原有旧资料豁免保留。
- [326 个原有文件基线](existing-files-baseline.yaml)逐项不变，覆盖既有配置、正式资料、真实测试成果和旧验收。
- 三份文章散列与本地来源链接有效，新测试元数据不包含凭据字段。
- 现有 Obsidian 配置保持原样；没有真实模型调用、正式入库、调度或发布。

机器可读明细见[验收记录](acceptance.yaml)、[批次回执](receipt.yaml)、`manifest.yaml`、`events/`、`stages/` 与 `checkpoints/`。真实人工确认入口、会员 Writing 后端及真实文章质量验收仍属后续阶段。

## 可复现的离线检查

需要现有 Python 3.9+ 与 PyYAML。若使用系统 Python，未安装可选 JWT 依赖时会员签名测试会明确跳过；本次完整验收使用已安装 `workflows/requirements-membership.txt` 的环境，317 项均通过。

```sh
python3 -m unittest discover -s tests -v
python3 workflows/test/agent-memory/test_validate_isolation.py
python3 workflows/validate.py
python3 workflows/validate.py --include-test
python3 scripts/researchdesk_writing.py run \
  --config config/test/agent-memory/writing.yaml \
  --batch-id writing-offline-20261019
git diff --check
```

完成样例再次运行应返回 `cached: true`，模拟调用仍为 8。不要改写已绑定的确认或 fixture 强行重用旧批次；无效确认与中断反例用自动测试的隔离工作台演练。详细确认、撤回及初次运行命令见[Writing 离线说明](../../../../../workflows/writing-agent-offline.md)。
