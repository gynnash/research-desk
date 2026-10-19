# Writing 结果正式准入

正式准入把用户已在页面确认、三阶段独立审阅均通过的 Writing 结果，确定性地保存为新的正式稿件。它不重新生成文字，不接触会员客户端，不发布公众号。原 test 文件、原确认与原模型回执保持原字节；用户本次明确要求的正式准入与原测试写作范围分别记录，不改写历史确认来扩大授权。

## 保存位置与含义

同一确认使用稳定的 `writing-<approval-id>`，正式稿件和测试稿件拥有不同 ID：

```text
articles/<topic>/writing-<approval-id>-outline.md
articles/<topic>/writing-<approval-id>-draft.md
articles/<topic>/writing-<approval-id>-candidate.md
reports/<topic>/writing-admissions/writing-<approval-id>/
  plan.yaml
  plan.yaml.sha256
  accepted.yaml
  accepted.yaml.sha256
```

大纲、初稿和候选稿仍是三个独立版本。`production_accepted: true` 表示已保存到正式知识库，`publish_authorized: false` 始终保留；候选稿不等于已发表文章。

`config/writing_admission.yaml` 控制允许的方向、原确认配置路径及保留既有文件的规则；独立审阅是不可跳过的校验。列入方向不会触发模型、定时任务或公众号发布，本次没有新增自动准入触发器。后续使用同一确定性入口准入新的合格批次。

## 校验与机械转换

准入前核验真实页面确认仍有效、未撤回、已完整同步 main / 索引 / origin/main；复核正式 Research / Insight 证明、全部冻结输入、原 Writing manifest 和请求绑定、实际生成与独立审阅模型身份、完整账本及三阶段逐段审阅。原稿件必须与已审阅结构化结果的程序渲染字节一致，仅有一个 `pass` 标签不足以准入。

正文不改写模型表述。只转换测试标识、正式 ID 与状态，并把原引用机械重定位到新文件所在目录；原始来源 URL、事实／作者主张／推断的区分、阅读范围与局限原样保留。正式稿件引用正式研究资料及确认、准入记录，不以 test 稿件作为正文证据。测试产物路径与散列保留在准入计划中，便于追溯。

先固定计划、检查全部目标冲突，再按计划仅创建新文件，最后写接受回执。目标已有同字节文件时复用；已有不同内容、人工修改或符号链接时停止并保留文件。补跑同一确认沿用原计划，不换批次、不覆盖旧稿，也不追加会员预留。

## 页面与人工笔记

“确认记录”保留原 TEST 三稿，并另列已正式入库的大纲、初稿和候选稿，只读查看的文件须通过准入回执与输出散列核验。正式稿件人工修改后原文件保留，页面提示完整性变化，不把修改后的版本冒充原审阅版本。后续撤回写作确认不会删除历史正式稿件，也不会授予发布权限；撤回后不能继续准入或恢复模型执行。

正式文件与证明普通提交推送后，Vault 外的页面工作目录刷新，Obsidian 使用既有 Git 同步读取。目录与插件配置保持原样。

## 可复现检查

在仓库根目录运行，检查及准入均不请求会员：

```sh
python3 -m pip install -r workflows/requirements.txt
python3 workflows/validate.py --include-test
python3 -m unittest discover -s tests -p 'test_writing_admission.py' -v
git diff --check
```

实际准入与只读核验，使用已经保存的真实页面确认 ID：

```sh
python3 scripts/researchdesk_writing_admission.py run \
  --approval-id '<页面保存的真实确认 ID>'
python3 scripts/researchdesk_writing_admission.py verify \
  --topic agent-memory --approval-id '<页面保存的真实确认 ID>'
```

命令行准入会刷新远端，不自动合并文件；保持原确认、证据和已审阅测试结果不变。重复执行只验证与复用同一批次，正式稿件由用户编辑后不得自动重置到旧版本。
