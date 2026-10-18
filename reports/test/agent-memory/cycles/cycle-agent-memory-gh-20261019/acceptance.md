# GitHub → 当前 Mac → Research / Insight → Obsidian：真实验收

> TEST：2026-10-19 完成手动部署验收；未正式入库，未启用定时、Writing 或公众号发布。

GitHub 派发给当前 Mac 的 `researchdesk-local` 用户服务，使用仓库外的 ResearchDesk 官方 ChatGPT 会员授权。主题、来源、模型、请求预算从 YAML 读取，执行器目录、Python 环境和会员 profile 从 `config/runtime.yaml` 读取；远程主机另有配置示例。runner 的工作副本与 Obsidian Vault 分开。

## 实际结果

- [离线检查通过](https://github.com/gynnash/research-desk/actions/runs/39151834824)：资料规范与 5 个关键轮次检查。
- [Mac 健康检查通过](https://github.com/gynnash/research-desk/actions/runs/39151835213)：官方会员授权有效，7 个可用模型，配置模型均可用；0 次推理。首次健康检查暴露路径空格问题，已为 Mac 脚本路径加引号后验证通过。
- [真实工作流通过](https://github.com/gynnash/research-desk/actions/runs/39151890497)：分析与结果回存两个 job 成功。自动选择一篇新的论文摘要与一篇 LangChain 博客节选，Research 独立审阅均通过，4 次请求；Insight 在本地格式校验失败后进行一次模型修订，独立审阅通过，3 次请求。
- [综合报告](../../insight-runs/cycle-agent-memory-gh-20261019/report.md)、[1 条洞察](../../../../../insights/test/agent-memory/cycle-agent-memory-gh-20261019/insight-1.md)和[1 张待确认选题卡](../../../../../articles/test/agent-memory/cycle-agent-memory-gh-20261019/topic-1.md)已保存。生成模型为 `gpt-6-luna`，独立审阅为 `gpt-6.1-sol`。
- 工作流提交 `5c587a4` 已快进同步回现有 Obsidian Vault。随后禁用所有模型和网络访问，重放相同轮次成功，新增请求与原文获取均为 0；既有笔记散列均保持不变。

此前[本地轮次](../cycle-agent-memory-20261019/acceptance-local.yaml)使用 8 次真实请求，验证了 Research 后中断、继续 Insight 和完整缓存重放。本次部署阶段合计新增 15 次请求；含此前所有测试，本月累计预留为 **25/100**。这是工作台的本地请求账本，会员真实剩余额度未知；后续累计值以预算复核命令为准。

## 范围与恢复

本次每个来源只检查有限候选列表。研究和 Insight 均为 `test_accepted`，整体回执仍为 `partial`、`discovery_complete: false`，不能据此声称全量扫描。延后项保存在 `pending.yaml`，后续轮次优先考虑历史待处理资料，并在模型调用前再次查重；来源更新只生成新结果，不覆盖原笔记。

失败补跑使用原配置和相同轮次 ID。有效 YAML、散列、请求预留及完成事件与报告一同回存；未知请求不会因换批次而释放预算。流程只新增测试文件，已有同字节文件复用，冲突时停止。作业被强杀来不及导出时须保留 worker 现场；不得先清理再换 ID 重试。详见[部署与恢复说明](../../../../../workflows/self-hosted-worker.md)。

当前 Mac 需保持用户登录、在线且唤醒；一次成功不代表长期可用性已得到验证。远程配置提供了部署方式，本次没有验证另一台远程主机。正式自动入库和每周二、周五北京时间 09:00 的调度仍待后续交付；选题保持 `proposed`，没有获准写作或发布。

## 复现

在已授权并安装执行器的仓库中，手动触发同一轮次可验证缓存与回存，不需要另开真实研究：

```sh
gh workflow run researchdesk-manual.yml --ref main \
  -f operation=run -f cycle_id=cycle-agent-memory-gh-20261019
```

真实研究新轮次使用新 ID；中断恢复使用原 ID。规范复核：

```sh
.venv-membership/bin/python workflows/validate.py --include-test
.venv-membership/bin/python -m unittest discover -s tests -p 'test_cycle.py' -v
git diff --check
```

结构化证明与阶段状态见同目录 `acceptance-github.yaml`、`receipt.yaml` 及关联阶段回执。当前工作流仅有手动事件，未配置 `schedule`。
