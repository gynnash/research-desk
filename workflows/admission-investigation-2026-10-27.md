# 2026-10-27 正式准入调查与恢复

调查基线：main `101dd35a65d043f29a9b6b61ffbba4635ae1eaa8`。
失败运行：<https://github.com/gynnash/research-desk/actions/runs/40416213363>，analyze job `121899145977`。

## 可复现的程序缺陷

本轮 Research 包含 LangChain 来源 `langchain-9098f9f1ed8c`，候选使用正式 ID `blog-05c33166-b18e-425e-91e0-36ddd26f21aa`。原始来源索引还包含旧测试 ID `blog-be47c817-56d3-4fa5-bb9a-bd19be5c68df`。

`reports/agent-memory/admissions/cycle-agent-memory-gh-20261019/accepted.yaml` 已以 `source_id_map` 明确证明后者映射到前者。`researchdesk_identity.source_index()` 会校验接受回执及其 SHA-256，并折叠这类别名；Research 输入解析已使用它。

`researchdesk_admission._render()` 却调用原始 `store.source_index()`，遇到该数据确定性抛出“正式与测试来源存在多个身份ID，须先显式解决冲突”。这是准入实现与既有身份策略不一致，不需要更改本轮来源或历史回执。

最小修复：渲染器使用同一经过证明的身份解析；计算已占用 UUID 时继续使用原始索引，避免被折叠的旧测试 ID 被重新使用。无证明的冲突与损坏的接受回执仍然拒绝。

## 验证边界

新测试从本轮真实检查点加载候选、审阅结果及来源信息，直接重放确定性渲染边界。使用原始索引复现原异常；使用修复后的索引生成 10 个正式文件的内存内容，验证既有博客仅新增 update 报告、不覆盖来源笔记，所有正式相对链接可解析，既有笔记散列保持不变。没有创建计划或接受标记，也没有调用模型。

新测试另验证删除映射证明及破坏其 SHA-256 时仍拒绝。既有准入测试继续检查真实历史计划的完整离线准入、幂等重放、人工内容冲突及中断续跑。

Actions 日志隐藏子进程异常，只有 exit_code=1、admission=failed；因此历史作业最先触发的具体异常不能从日志还原。上述缺陷是本轮数据已经证实的确定性阻塞。当前测试环境无法解析 arxiv.org，独立 admit 在公开来源重新核验处停止，不能断言它是历史作业唯一故障，也不能声称完整在线准入已经通过。不得绕过原文复核生成 accepted.yaml。

## 测试与恢复操作

```sh
python -m pip install -r workflows/requirements-membership.txt
python workflows/validate.py --include-test
python -m unittest discover -s tests -p 'test_admission*.py' -v
python -m unittest discover -s tests -v
```

修复合入 main 后，在已有可访问公开来源的受信任 runner 上，只执行独立准入：

```sh
gh workflow run researchdesk-manual.yml --ref main \
  -f operation=admit \
  -f cycle_id=agent-memory-20261027-0300 \
  -f config=config/cycles/agent-memory.yaml
```

不要重跑原失败的 run 作业。独立 admit 不调用模型，会重新核验原文、散列、真实模型审阅、身份与引用；如果上游原文已变化则应保留失败现场，不能更新检查点或伪造通过。

如需在受信任本地环境看到准确错误，先在干净独立 checkout 中使用：

```sh
python scripts/researchdesk_admission.py plan \
  --topic agent-memory --cycle-id agent-memory-20261027-0300
python scripts/researchdesk_job.py admit \
  --config config/cycles/agent-memory.yaml --cycle-id agent-memory-20261027-0300
```

本地操作只产生本地准入，远端回存应走既有受限 workflow，而非把整个工作目录提交。

恢复后分别核验：

1. 测试通过：旧 Research/Insight 回执仍为 test_accepted，production_accepted=false，原字节保留。
2. 正式准入：本轮 admissions 下 accepted.yaml 及校验文件有效，production_accepted=true，new_model_calls=0；逐一核对输出散列和正式引用。
3. 远端回存：发布/保存 job 成功，远端 main 存在确切接受标记及产物，散列与计划一致。

准入不授权 Writing 或公众号发布。本次修复不触发二者，不更改测试回执、历史准入证明或人工笔记。
