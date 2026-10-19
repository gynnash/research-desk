# 页面确认后的真实 Writing 测试闭环

本入口读取用户在本地页面亲自保存、已提交并同步到 `origin/main` 的确认记录。不会替用户确认选题，也不接受离线样例确认。模型生成首先保存为测试稿；[正式文章准入](writing-formal-admission.md)另行确定性创建正式版本，保留原 test。没有公众号发布接口。

## 日常操作

1. 在本地工作台核对正式选题及证据，调整标题、角度、受众、目标字数，保存写作确认。
2. 确认同步后，在“确认记录”点击“开始 / 继续测试写作”。页面只派发 GitHub 的 `ResearchDesk confirmed Writing`，会员推理在用户配置的本地或远程自托管主机运行。
3. 刷新记录查看阶段、调用次数和三份测试稿。大纲通过审阅后才生成初稿，初稿通过后才生成候选稿，每阶段使用另一个实际模型独立审阅。
4. 如需停止后续写作，在页面撤回确认。已保存内容与调用预留保留，撤回不删除稿件，也不能取消已经发送给服务端的请求。

首次小额验证和页面按钮每次最多新增 6 次请求。GitHub 手动入口可选择 6 次或 0 次，不能突破原确认的总额、每阶段额度及共享月度额度。0 次模式只核验已完整通过审阅的结果，不实例化会员客户端、不查询账户或模型目录、不发送推理；未完成批次不能借此模式继续生成。默认总额最多 12 次、每阶段最多 4 次、每阶段最多修订一次；三个阶段无修订时共 6 次请求。独立审阅不通过时保留结果，不将失败稿作为通过稿。

确认本身只保存授权，开始写作是单独操作；本工作流只有 `workflow_dispatch`，没有新增定时或确认记录 push 自动触发。

## 配置与授权

- 研究方向、可用模型、字数、字符及请求预算沿用 `config/confirmation.yaml` 中用户预览时的固定版本；共享月度上限读取 `config/membership_budget.yaml`。已确认后不直接修改原预览来放大权限。
- 写作模型和审阅模型必须是当前账户实际目录中不同的模型。每次响应核对实际模型身份，不能用同一个模型换提示词自审。
- 采用本应用既有的官方 Sign in with ChatGPT 授权、`chatgpt.tokens.use.direct` 权限及仓库外 profile。不读取浏览器或 Codex 登录态，不共享维护者凭据，不自动切换 API Key 计费。[官方授权流程](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- 主机部署沿用[自托管执行器](self-hosted-worker.md)。GitHub 临时主机只校验和保存测试文件；会员凭据保留在选定的分析主机外部运行目录。会员资格、可用模型及官方限流由实际账户决定。[官方错误与恢复说明](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)

执行前核对真实页面确认、原预览、正式 Research / Insight 的准入证明、完整证据散列及 `main` / 索引 / `origin/main` 的文件字节。每个关键边界只 fetch 最新远端，不自动合并人工文件；撤回、输入变化或未同步立即停止。页面服务与 Vault 使用不同工作目录，通过普通 Git 同步。

自托管 Writing 步骤显式传入该作业已有的 `contents: read` token，Git fetch 只在子进程中使用临时 credential helper，不保存到 Git 配置、不依赖交互式 Keychain。令牌不进入参数、模型输入、检查点或日志。同步失败按固定的认证、网络或超时错误码停止，不能把缺少回执误报为排队或成功。

## 引用与审阅

模型仅返回结构化文本和证据编号，程序建立真实笔记、原始 URL 与确认记录的引用。每段区分“原文直接确认的事实”“原作者声称”“我们的推断”“解释性类比”；历史人工笔记只作背景，不能升格为本次已核实的原文事实。审阅模型逐段检查完整候选、标题、导读、用户角度与阅读范围；程序要求核查覆盖每一段，并拒绝有阻塞问题的 pass。

当前证据可能只有论文摘要、博客节选与未重新核验的历史笔记。文章保留这些范围，不能声称读完全文、复现实验或验证了行业趋势。模型审阅是质量门禁，不构成发表授权。

## 保存与恢复

同一确认使用稳定批次 `writing-<approval-id>`：

```text
reports/test/<topic>/writing-runs/writing-<approval-id>/
  manifest.yaml          # 固定输入、账户指纹、模型、预算与旧笔记散列
  events/                # 请求前预留、完成响应及阶段接受事件
  checkpoints/           # 结构化响应、响应标识及实际 usage
  stages/                # 各阶段候选与独立审阅
  partial/               # 中断快照，不改写旧回执
  artifact-plan.yaml     # 三份稿件的确切输出散列
  receipt.yaml           # 最终状态、用量与输出散列
  verifications/         # GitHub 0 调用复核凭据及配对 SHA-256
articles/test/<topic>/writing-<approval-id>/
  outline.md
  draft.md
  candidate.md
```

所有输出 create-only；同路径同字节可复用，不同字节停止，人工修改不会被覆盖。请求前持久化预留；成功响应缓存后再做后续授权和内容核验。失败及结果未知的请求仍计入共享月度 100 次；未知结果不自动重发。已知完成但格式错误的响应也不隐式修补或重新调用，保留现场处理。补跑同一确认复用完成响应，不能换批次重置预算。

Research、Insight、Writing 的 GitHub 作业共用 `researchdesk-membership-worker` 串行并发组；工作副本还有本地预算锁。其他主机应使用同一派发通道，不同时从多个独立副本直接调用，不能将仓库锁理解为账户级分布式额度锁。

自托管作业无仓库写 token，失败时也导出检查点；独立保存作业检查白名单、散列、原始输入及三阶段审阅，只追加 `test` 文件并普通提交推送。同步失败保留 worker 与 14 天 artifact，不强推、不清理未知请求。

GitHub 0 次模式追加 `verifications/gha-<run-id>-<attempt>.yaml`，绑定源码提交、原确认、原回执、三稿散列及零新增调用。保存作业重验这些字段后才提交；已有大纲、初稿、候选稿和原模型账本保持原字节。这样可验证真实的“执行 → artifact → 回存 → Obsidian 拉取”链路，无需再次请求会员。

## 可复现检查

```sh
python3 -m pip install -r workflows/requirements-membership.txt
python3 workflows/validate.py --include-test
python3 -m unittest discover -s tests -p 'test_writing_member.py' -v
git diff --check
```

上述检查使用模拟传输和临时 Git 仓库，不调用会员。维护者在已部署授权的分析主机上可使用下列真实入口，必须指定已有页面确认：

```sh
python3 scripts/researchdesk_writing_job.py execute \
  --state "$HOME/.local/state/ResearchDesk/writing-attempt-001" \
  --approval-id '<页面保存的真实确认 ID>' --max-new-calls 6
```

每次执行使用新的仓库外 state 目录；同一确认 ID 继续复用仓库内的原批次检查点。不要在多个副本并发运行真实入口。已通过的完整批次再次运行只复核及复用，不新增模型请求。首次真实结果与实际调用数量见该批次的 `receipt.yaml` 及测试验收记录。
