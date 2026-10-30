---
title: Agent 记忆：从把信息存下来，到为问题组织证据
kind: research_reading
topic: agent-memory
source_cycle: agent-memory-20261030-0300
status: editorial
derived_from:
  reports/agent-memory/agent-memory-20261030-0300-synthesis.md: 4b7e0fbace69aaa09672c1089fa8e21e5145724876b5fb471560daa9fb5960b0
  reports/agent-memory/agent-memory-20261030-0300-research-paper-1337d0ee-7403-4fe2-8802-f1771af20c20.md: 9c6ada5ebacaf00435bde246875826d30e750aded8d36785a812e5209c10a26c
  reports/agent-memory/agent-memory-20261030-0300-research-paper-f794b398-b1d9-451d-89a0-03897daeede2.md: 1a11d7814811fdda4ef4ce7886e55ce1aa813076e54cd6ac9898ead6ba190a95
  reports/agent-memory/agent-memory-20261030-0300-update-blog-05c33166-b18e-425e-91e0-36ddd26f21aa.md: 948473f78edfee4051a458065149f9c118bdb25378b73da87e245b70026adc04
  reports/agent-memory/agent-memory-20261030-0300-research-blog-2c7372dc-2b55-40b2-bdbf-8cf136b56cd0.md: acf4716ad1d7d6d73ea207fdc089858833c799088bb650ef79550286207da671
  insights/agent-memory/agent-memory-20261030-0300-insight-1.md: 2e6282b5ccfe3c4f0f9a0297aa2c6b7942dd7a933da137fc2e7c9abe160366fa
  insights/agent-memory/agent-memory-20261030-0300-insight-2.md: 2e6a8eb2e8c683dd41b315d3ee099a037c5edf788f574b4fee3ecbe5b741c3c9
---

# Agent 记忆：从把信息存下来，到为问题组织证据

讨论 Agent 的长期记忆时，我们容易先问：信息该存在哪里？但读完这轮资料，会发现还有两个值得分开讨论的问题：存下来的经历如何被组织，面对一个具体问题时，又如何判断找回的信息已经足够回答？

10 月 30 日的研究涉及两篇论文和两篇技术博客。下面沿着“组织经历—使用证据—管理上下文”这条线索解释它们的关系。**这是一篇基于已有研究记录整理的阅读版：论文当时只读了摘要，博客只读了节选；文中的效果均为作者报告，尚未独立复现。**

## 两篇论文，分别处理记忆的组织与使用

MFM（Multimodal Filesystem Memory）讨论的是长时程具身 Agent 如何组织多模态经历。作者在摘要中描述了一套结合情景、空间、语义、程序性和工作记忆的架构，并保留通往原始经历的引用。这里值得关注的设计是：整合后的记忆仍然留下回到原始材料的入口。[^1]

QEMem 则从另一个问题出发：检索到了相关记忆，是否就有足够证据回答问题？作者指出，回答所需的信息可能分散在多条记录中，也可能被抽象过程掩盖，或者缺少连接这些信息的关联。它因此把记忆利用表述为构建“针对当前查询的证据集”。[^2]

在摘要描述的机制里，QEMem 先做查询引导的多粒度证据发现，再用带有来源引用和证据角色的 ViewCards 组织信息，并根据证据是否充分，选择性地补回缺失内容。由此可以看出两篇论文关注点的差别：MFM 着重组织经历，QEMem 着重把已有记忆组织成回答问题所需的证据。它们没有在本轮材料中进行直接对比，不能据此排列优劣。[^1][^2]

作者报告，QEMem 在共享记忆存储、且不修改既有记忆形成方式的设定下，配合 Claude Opus 4.5，在 LoCoMo 上取得了 91.43% 的 LLM judge 准确率。这个结果值得进一步检查，但目前记录只有摘要，尚未核对完整基线配置、评测样本和统计不确定性。因此，它提供了深读的理由，还不足以支撑普遍有效的判断。[^2]

## 工程里还有一个约束：上下文窗口装不下所有内容

LangChain 的《Context Engineering: How Deep Agents Remember》节选从上下文管理切入。它描述了两类做法：控制哪些信息进入窗口，以及管理已经进入窗口的信息。具体机制包括文件卸载、摘要、按需加载技能、子代理和长期记忆。[^3]

例如，节选称工具结果超过约 20,000 个 token 时，会先写入文件，模型收到简短预览和路径；默认上下文使用量达到窗口的 85% 后，摘要中间件会压缩较早消息，同时保留最近消息原文。这些是该博客当时描述的机制和默认阈值，并非对所有 Agent 都适用的配置建议。[^3]

我们据此作出的解释是：卸载应对单次大输入，摘要应对长任务中的持续累积。它们解决不同时间尺度的上下文负担。至于压缩后能否可靠找回必要细节，节选没有提供足够评测来回答。这也让“保留原始材料入口”与“判断证据是否充分”成为值得联动研究的问题。[^3][^5]

另一篇《How We Built Our Design Agent》描述了设计技能、检查项和团队偏好如何进入 Content Studio 的工作过程。不过，当前节选只是提及 scoped agent memory，没有展开其写入、检索、更新或遗忘机制。它能够提供应用背景，无法单独验证某种长期记忆架构的效果。两篇博客同属 LangChain，也不能当作两份独立实验的交叉验证。[^4]

## 可以提出两条研究判断，但还不能叫行业趋势

第一条判断是：**记忆检索的目标，可能需要从“找相关内容”进一步走向“组织足以回答问题的证据”。** 这条假设来自 QEMem 的方法描述，也是本轮已保存洞察的核心。它尤其值得放到需要跨记录整合的问题里检验。但表现差异也可能来自模型、题型、记忆形成方式或评测口径，不能只凭方法描述就认定它一定更好。[^2][^5]

第二条判断是：**压缩或整合后的记忆，如果保留可回查的原始记录入口，可能更便于检查被省略的细节。** MFM 的摘要提供了这样的设计线索，工程博客里的卸载与摘要则说明了信息压缩的使用场景。不过，入口存在不等于回查成功：检索本身有成本，原始观察也可能包含噪声或过时信息。当前资料没有给出细节恢复成功率的独立证据。[^1][^3][^5]

这两条判断适合作为后续研究问题。它们尚不能升级成“行业已经转向某种记忆架构”的趋势结论：本轮原文覆盖有限，历史资料也没有形成经过充分核验的长期时间序列。

## 下一次深读，应该核实什么

对 QEMem，优先核实证据充分性如何判定、ViewCards 如何构建，以及在相同模型和记忆库下，收益是否确实来自证据组织。对 MFM，优先检查原始经历引用如何保留、何时触发回查，以及失败案例。对上下文工程实践，则需要区分“减少窗口占用”与“提高答案可靠性”这两个不同目标。[^5]

现阶段最有价值的收获，是把这些不同层次的问题分开：经历如何保存和组织，证据如何被找到和组合，以及有限上下文如何承载当前任务。接下来的验证应当说明某个机制改善了哪一层、在什么条件下成立。

## 来源与延伸阅读

[^1]: [Multimodal Filesystem Memory For Long-Horizon Embodied Agents](https://arxiv.org/abs/2610.22686v1)。本轮实际范围：论文摘要。[已准入单篇研究](../../../reports/agent-memory/agent-memory-20261030-0300-research-paper-1337d0ee-7403-4fe2-8802-f1771af20c20.md)。
[^2]: [From Relevant Memories to Sufficient Evidence: Rethinking Memory Utilization in LLM Agents](https://arxiv.org/abs/2610.22668v1)。本轮实际范围：论文摘要；数值为作者报告。[已准入单篇研究](../../../reports/agent-memory/agent-memory-20261030-0300-research-paper-f794b398-b1d9-451d-89a0-03897daeede2.md)。
[^3]: [Context Engineering: How Deep Agents Remember](https://www.langchain.com/blog/context-engineering-deep-agents-remember)。本轮实际范围：博客节选。[已准入更新研究](../../../reports/agent-memory/agent-memory-20261030-0300-update-blog-05c33166-b18e-425e-91e0-36ddd26f21aa.md)。
[^4]: [How We Built Our Design Agent](https://www.langchain.com/blog/design-agent)。本轮实际范围：博客节选。[已准入单篇研究](../../../reports/agent-memory/agent-memory-20261030-0300-research-blog-2c7372dc-2b55-40b2-bdbf-8cf136b56cd0.md)。
[^5]: 本文判断与待验证方向据[综合报告](../../../reports/agent-memory/agent-memory-20261030-0300-synthesis.md)、[证据充分性洞察](../../../insights/agent-memory/agent-memory-20261030-0300-insight-1.md)及[原始记录回查洞察](../../../insights/agent-memory/agent-memory-20261030-0300-insight-2.md)整理，属于推断与建议，尚未执行验证。

---

本文由 Codex 编辑已有正式结果，未重新获取原文，也未另做独立模型审阅；不作为新一轮研究、公众号稿件或写作确认。原始记录及其[准入证明](../../../reports/agent-memory/admissions/agent-memory-20261030-0300/accepted.yaml)保留。文首属性记录所依据文件及散列，便于发现依据变化。

[研究首页](../../../研究首页.md) · [全部正式资料](../../资料索引.md) · [我的研究问题](../../../notes/我的研究问题.md)
