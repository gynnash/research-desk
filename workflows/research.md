# 逐篇 Research

Research 读取已经采集并固定的完整原文，为每篇论文或博客生成详细总结。默认方向是 `agent_memory`，定义在 [research_topics.yaml](../config/research_topics.yaml)，来源、模型和预算使用 [default.yaml](../config/cycles/default.yaml)。

## 原文与总结

```text
collection/
  agent_memory/
    <批次 ID>/
      manifest.yaml
      items/<资料 ID>/original.md
      items/<资料 ID>/original.yaml
summary/
  agent_memory/
    <批次 ID>/<资料 ID>.md
```

`original.md` 是可读原文，`original.yaml` 保留完整抽取内容与研究读取范围，用于离线重放。总结是文章式解读，正文没有逐段内部证据编号，原文链接和本地原文入口放在篇末。

采集清单、模型响应、预算、审阅与补跑账本继续使用已有的 `reports/test/<主题>/` 内部运行目录；它们是运行记录，不作为面向读者的总结。复用这些检查点避免重复调用及大范围迁移。旧批次不会被静默搬迁或改写。

## 按顺序运行

安装依赖并完成自己账号的[会员授权](local-membership-analysis.md)。单独采集不需要模型授权：

```sh
python3 -B scripts/researchdesk_cycle.py collect \
  --config config/cycles/default.yaml --cycle-id agent-memory-manual-001
```

采集成功后，对同一批次逐篇研究：

```sh
python3 -B scripts/researchdesk_research.py \
  --config config/cycles/default.yaml --cycle-id agent-memory-manual-001
```

不传 `--config` 时也使用上述默认配置。自有会员配置需要另外指定时，使用 `--profile` 指向仓库之外的配置文件。CLI 不会用模拟模型冒充真实执行；离线验收只在临时目录显式注入虚构模型响应。

该入口不重新联网采集，不运行 Insight、Writing 或公众号发布。缺少采集批次时给出采集命令；空批次不初始化会员客户端、不调用模型。

## 详细总结的内容

复用现有深读提示词及独立审阅，每篇通常形成1800–3000字、3–5节的技术文章，随原文信息量调整：

- 研究问题、动机及原有方法遇到的具体困难。
- 作者方法的输入、步骤、模块配合与记忆写入、检索、更新过程。
- 原文实际提供的任务、数据、基线、指标、数值和比较条件；博客则解释工程流程与取舍。
- 作者主张、可直接确认的事实，以及我们的解释或应用推断。
- 方法的适用边界、失败案例、待验证问题和本次实际阅读范围。

原文没有实验、基线或数值时直接说明，不补造结果。完整正文抽取也不等于图表、公式与附录均可核对，更不等于已复现实验。

## 审阅、预算与补跑

研究和审阅使用配置中不同的实际模型；每篇正常为研究、审阅两次调用，审阅要求修改时最多修订一次。沿用单批预算和账号月度预算，预算耗尽时保留已完成结果，未完成项不伪装成功。

只有独立审阅通过的完整原文研究才新增到 `summary/<主题>/`。拒绝、待修订或阻塞的输出保留在内部记录，不生成通过标记的总结。

失败时使用原命令与同一个批次 ID；完成的研究、审阅响应复用。调用结果未知时停止，避免重复消耗。原文、总结或人工笔记被修改时保留修改并停止覆盖。修改研究方向、模型或已绑定输入后，应使用明确的新批次，不强行重置旧记录。

## 校验

```sh
python3 -B workflows/validate.py --include-test
PYTHONPATH=tests python3 -B -m unittest test_collection_only test_research_entry test_research_depth -v
git diff --check
```

离线验收仅验证流程，不生成真实研究成果。真实资料需要显式运行采集、Research 命令；启用方向不会自动启动定时任务。
