---
schema_version: 1
kind: original_snapshot
title: 'Memory Tax: Dissecting the Net Value of Agent Memory'
source_id: paper-bc2516cd-42b2-41d1-ace2-36b96b38f624
source: arXiv
authors:
- He, Xuan
- Zhoubian, Sining
- Yang, Ruozhen
- Wen, Yuhao
- Wang, Zhineng
- Hu, Yuyang
- Yang, Ke
- Zhang, Yuyu
- Nie, Ping
- Han, Jiawei
- Zhai, ChengXiang
published_at: '2026-10-25'
source_version: v1
topics:
- agent_memory
source_url: https://arxiv.org/abs/2610.34073v1
captured_at: '2026-11-08T14:58:55.078801+00:00'
content_sha256: 41b43bc8086cf03fbb3b6c52b817dde1302c1963d4831a6ba248a0319958e765
coverage: full_text
research_coverage: full_text
---

# Memory Tax: Dissecting the Net Value of Agent Memory

> 原文抽取归档，用于阅读及重放，内容不代表已核实的研究结论。

- [打开来源原文](https://arxiv.org/abs/2610.34073v1)。
- 原文归档保存完整可用抽取文本；绑定的模型材料范围为 `full_text`，可小于本归档。
- 归档自身不表示已经执行研究或审阅；实际执行与审阅状态以对应研究回执为准。
- 不保存可执行网页、PDF 版式或图片，不保证公式和图表的抽取完整性，未复现实验。
- 抽取方式：`html`；抽取范围：`full_text`。
- 抽取限制：Text extraction does not verify figures, layout, or faithful mathematical rendering.
- 取材：html / success / extracted。

## 获取记录

- [text/html](https://arxiv.org/abs/2610.34073v1)；响应 SHA-256：`1b6b7d9303fce2b7d7557f875d1922eef4bf7720f834e1ff5a2519edeabd7f17`；抓取时间：2026-11-08T14:58:32.425763+00:00。
- [text/html](https://arxiv.org/html/2610.34073v1)；响应 SHA-256：`c0080c542596c6a458549d9140805bcb0f7b96b9283fd3aa363a94ebce855552`；抓取时间：2026-11-08T14:58:35.587657+00:00。

## 抽取正文

### S1 · Memory Tax : Dissecting the Net Value of Agent Memory

[原文定位](https://arxiv.org/html/2610.34073v1)

Xuan He

Affiliation: University of Illinois Urbana Champaign

Sining Zhoubian

Affiliation: Tsinghua University

Ruozhen Yang

Affiliation: University of Illinois Urbana Champaign

Yuhao Wen

Affiliation: Tsinghua University

Zhineng Wang

Affiliation: University of Illinois Urbana Champaign

Yuyang Hu

Affiliation: Renmin University of China

Ke Yang

Affiliation: University of Illinois Urbana Champaign

Yuyu Zhang

Affiliation: Verdent.ai

Ping Nie

Affiliation: University of Waterloo

Jiawei Han

Affiliation: University of Illinois Urbana Champaign

ChengXiang Zhai

Affiliation: University of Illinois Urbana Champaign

### S2 · 1 Introduction

[原文定位](https://arxiv.org/html/2610.34073v1#S1)

Memory has become an important component of long-horizon LLM agents, supporting recall across interaction histories and reuse of prior experience (Wang et al., 2023; Xie et al., 2024; Gur et al., 2024; Hu et al., 2025a).

Recent work has introduced increasingly diverse memory representations and management mechanisms (Chhikara et al., 2025a; Kang et al., 2025; Fang et al., 2026a; Hu et al., 2026b; Jiang et al., 2026a), aiming to make relevant information easier to preserve and utilize, but often incur additional computation over the original context.

As memory systems grow more complex, it remains unclear how much these operations improve over a straightforward alternative, such as directly retrieve from the raw history.

Surveying prior works, it shows many memory designs primarily compare against other memories, while naive RAG is often overlooked, and when included, its setup is also not always fully specified (Appendix B.2).

Without a retrieval baseline, the value of building memory remains entangled with the value of direct evidence retrieval, leaving its marginal or net value underexamined.

So this suggests a gap between the growing complexity of memory design and our understanding of whether and where that complexity actually helps, motivating us to revisit a fundamental question:

To study this question, we start from a common setting, personal-agent conversational memory.

We evaluate representative memory designs across several benchmarks and model backbones, using naive RAG as a reference to assess the net value of memory. The results show that naive RAG remains a strong baseline and many memory systems underperform it across diverse settings, indicating a negative net value in these cases.

But a closer query-level comparison shows memory is not uniformly worse. It does solve some queries RAG misses, where organization or restructuring may help, while losing others that RAG already solves. We refer to the former as memory benefit and the latter as memory tax. When the tax outweighs the benefit, memory falls below RAG overall.

These gains and losses suggest a different view of memory.

Memory goes far beyond a purely beneficial augmentation as often treated in prior works, and can be better understood as a double-edged process that changes how information from raw history is structured and accessed. We view such changes as inevitable deviations from the raw history.

These deviations give memory its dual nature.

They are originally designed and intended to better serve the task, e.g., by organizing scattered facts, distilling preferences, etc., yet some may also have unintended harmful effects due to particular design choices, such as losing or obscuring evidence.

Memory benefit and tax thus capture the two sides, and their balance defines the net value of memory, reflected in the external performance.

Memory benefit reflects the intended gains of memory design, such as reorganization or abstraction, which is expected. So we focus more on how the memory tax emerges. We first examine faithfulness for how well the information survives memory process, and then accessibility for how easily the preserved information can be recalled or accessed. We further study robustness for reliability of memory across backbone changes.

These dimensions characterize memory tax from system side, and its balance with memory benefit also highly depends on the task setting.

Across more personal-agent memory benchmarks, we find naive RAG already achieves high absolute scores, suggesting a retrieval-friendly task setting with limited benchmark headroom for memory to deliver more benefit and thus making the tax more visible.

Moreover, the benefit-tax view is generalizable and not tied to particular memory forms, as nontrivial memory operations can introduce both beneficial and harmful deviations from the source. We further examine this in experiential memory and world-model memory. Finally, we derive some design implications from the perspective of memory deviations and benefit-tax trade-offs. We focus on simple changes that can be applied to existing memories without introducing new architectures.

We hope that the notion of memory tax can shift more attention from standalone memory performance to the net value of memory and its dissection into benefit and tax, thus informing more reliable memory design and evaluation.

Our contributions are as follows:

Reassess the net value of long-term memory over direct retrieval holistically.

Dissect the net value into memory benefit and memory tax, and systematically analyze the source of memory tax.

Generalize the benefit-tax view to broader settings and derive general design implications.

### S3 · 2 Preliminary

[原文定位](https://arxiv.org/html/2610.34073v1#S2)

Long-term memory for agents maintains information from past interactions and selectively exposes it to the model at query time.

Let the interaction history be \mathcal{H}=\{h_{1},\ldots,h_{T}\} , where each h_{t} may contain user/agent messages, observations, or other types of content.

A memory system processes this history into a persistent memory \mathcal{M}=I(\mathcal{H}) , where I denotes the memory ingestion process. Given a task query q , it retrieves relevant memory units \mathcal{C}=R(q,\mathcal{M}) and generates an answer \hat{y}=G(q,\mathcal{C}) . Different systems instantiate \mathcal{M} as summaries, extracted facts, structured records, episodic entries, or other representations.

Naive chunk-based RAG provides a natural reference under this formulation.

It keeps raw history with minimal processing and retrieves relevant chunks directly.

We use it throughout this work as the comparison reference for assessing the net value of memory, and measured memory benefit and memory tax are thus relative to this reference.

### S4 · 3.1 Setup

[原文定位](https://arxiv.org/html/2610.34073v1#S3.SS1)

Table 1: Main results. Scores are judge accuracy (%). We highlight the best and the second best per column. Cells are shaded in proportion to how far they fall below or rise above RAG (2rd). Q3.5-4B, Q3.6-27B and 5.6-luna denote the Qwen3.5-4B, Qwen3.6-27B and GPT-5.6 Luna (low) backbones, respectively.

Category

Method

LongMemEval-s§

PersonaMem-v2§

MINT-Eval§

Q3.5-4B

Q3.6-27B

5.6-luna

Q3.5-4B

Q3.6-27B

5.6-luna†

Q3.5-4B

Q3.6-27B

5.6-luna

Vanilla

No Context

9.0

9.0

17.6

20.9

25.6

28.5

2.3

3.8

8.5

Full Context

58.6

68.4

84.0

30.1

45.4

43.6

26.9

28.7

39.7

Gold Context

73.4

84.6

92.8

58.7

72.9

69.7

–

–

–

Retrieval-only

RAG (1rd)

70.2

77.6

82.0

37.2

46.8

45.1

25.8

28.6

29.9

RAG (2rd)

72.2

81.4

90.0

36.2

48.7

48.4

26.1

33.1

34.5

Flat store

A-Mem

70.4 ( - 1.8)

79.4 ( - 2.0)

84.0 ( - 6.0)

33.7 ( - 2.5)

48.4 ( - 0.3)

41.8 ( - 6.6)

24.4 ( - 1.7)

24.4 ( - 8.7)

27.1 ( - 7.4)

MemOS

62.0 ( - 10.2)

76.6 ( - 4.8)

78.0 ( - 12.0)

37.2 (+1.0)

50.2 (+1.5)

41.7 ( - 6.7)

18.0 ( - 8.1)

19.7 ( - 13.4)

30.3 ( - 4.2)

SimpleMem

60.2 ( - 12.0)

73.6 ( - 7.8)

84.0 ( - 6.0)

34.7 ( - 1.5)

46.7 ( - 2.0)

45.1 ( - 3.3)

18.6 ( - 7.5)

19.9 ( - 13.3)

22.9 ( - 11.6)

Hier/Lifecycle

MemoryOS

64.6 ( - 7.6)

73.4 ( - 8.0)

80.0 ( - 10.0)

37.0 (+0.9)

48.2 ( - 0.5)

43.0 ( - 5.4)

19.0 ( - 7.2)

26.3 ( - 6.9)

33.2 ( - 1.3)

LightMem

57.6 ( - 14.6)

78.8 ( - 2.6)

77.0 ( - 13.0)

36.4 (+0.2)

47.0 ( - 1.7)

45.9 ( - 2.5)

20.8 ( - 5.4)

23.0 ( - 10.2)

25.2 ( - 9.3)

OpenViking

31.8 ( - 40.4)

58.8 ( - 22.6)

63.0 ( - 27.0)

31.3 ( - 4.9)

38.7 ( - 10.1)

38.2 ( - 10.2)

10.2 ( - 15.9)

18.6 ( - 14.6)

24.2 ( - 10.3)

Graph-based

HippoRAG2

68.8 ( - 3.4)

78.2 ( - 3.2)

81.0 ( - 9.0)

33.9 ( - 2.3)

46.5 ( - 2.3)

45.3 ( - 3.1)

24.6 ( - 1.5)

23.5 ( - 9.6)

27.8 ( - 6.7)

MAGMA

60.8 ( - 11.4)

68.2 ( - 13.2)

76.0 ( - 14.0)

33.1 ( - 3.1)

40.5 ( - 8.3)

40.6 ( - 7.8)

23.7 ( - 2.4)

27.0 ( - 6.2)

29.5 ( - 5.0)

PlugMem

68.0 ( - 4.2)

75.8 ( - 5.6)

70.0 ( - 20.0)

35.0 ( - 1.2)

45.2 ( - 3.5)

39.8 ( - 8.6)

21.5 ( - 4.7)

33.3 (+0.1)

37.8 (+3.3)

Trained Policy

Mem-T

71.0 ( - 1.2)

75.0 ( - 6.4)

78.0 ( - 12.0)

32.1 ( - 4.1)

42.1 ( - 6.6)

41.0 ( - 7.4)

27.0 (+0.9)

30.4 ( - 2.7)

38.4 (+3.9)

Memory-R2

65.8 ( - 6.4)

73.0 ( - 8.4)

79.0 ( - 11.0)

38.2 (+2.0)

48.4 ( - 0.3)

44.2 ( - 4.2)

21.3 ( - 4.8)

21.5 ( - 11.6)

22.9 ( - 11.6)

§LongMemEval is relatively retrieval-friendly, while the other two involve more complex demands, see §4.5.

†Interestingly, on PersonaMem-v2, 5.6-luna usually scores lower than Q3.6-27B, opposite of the other two benchmarks, see A.5.

Figure 1: Pareto plot of Accuracy vs. Token-cost. Bubble size is the memory store size in tokens.

Memory is increasingly used across different scenarios. We begin with its common application, personal agent memory or conversational memory, and later extend to more domains (§5.1 and §5.2).

Benchmarks.

We evaluate on LongMemEval-s (Wu et al., 2025), PersonaMem-v2 (Jiang et al., 2025b), and MINT-Eval (Lee et al., 2026). Due to cost constraints, we evaluate 20% of PersonaMem-v2 and 10% of MINT-Eval. All subsets are selected with stratified sampling over question types. These benchmarks span direct recall to more complex queries involving aggregation or multi-interference reasoning. Appendix A.1 shows the full details.

Baselines.

We group the memory systems by how they organize what they store, and take open-source representatives of each group.

Flat store: A-Mem (Xu et al., 2026a),

SimpleMem (Liu et al., 2026b),

MemOS (Li et al., 2025b).

Hier/Lifecycle: MemoryOS (Kang et al., 2025), LightMem (Fang et al., 2026a), OpenViking (Volcengine, 2026).

Graph-based:

HippoRAG2 (Gutiérrez et al., 2025),

PlugMem (Yang et al., 2026a), MAGMA (Jiang et al., 2026a).

Trained policy: Mem-T (Yue et al., 2026), Memory-R2 (Yan et al., 2026b).

We use RAG over the raw corpus as the main memory-free baseline, with both single-round (1rd) and two-round (2rd) variants. We also include several vanilla references, including No Context, Gold Context, etc. Appendix A.2 shows the full details.

Implementation details.

We run every system on three backbones, Qwen3.5-4B, Qwen3.6-27B and GPT-5.6-luna(low), sharing the same embedding model, Qwen3-Embedding-0.6B. Answers are scored by an LLM-as-Judge backed by Qwen3.6-27B, with judge prompts in Appendix F.2. Alongside accuracy we report several cost metrics including token cost, end-to-end wall-clock time, number of LLM calls, and memory storage size.

Since memory granularity and storage capacity vary substantially across systems, a fixed top- k can correspond to very different amounts of retrieved information. For a fair comparison, we align retrieval budgets using Retrieval Scope (RS), defined as the tokens in the memory units exposed to the LLM from retrieval through answering, normalized by the total tokens within the system’s retrievable store. We tune top- k for each system (increasing it from the default in most cases) so its Retrieval Scope is roughly no lower than that of RAG (1-round), while roughly comparable across systems. The exception includes systems that contain only a few memory units, which retains a fixed top- k .

See full details in Appendix A.3 and A.4.

Figure 2: Venn plot for per-query correction comparison between memory system and RAG (1rd).

Figure 3: Original performances vs. w/ gold memory units (bars), and the memory tax (quantified in scores) before and after having gold memory units (boxed numbers).

### S5 · 3.2 Results

[原文定位](https://arxiv.org/html/2610.34073v1#S3.SS2)

Table 1 reports the results of all the baselines on three benchmarks, and Figure 1 plots the cost-performance trade-off more directly. Appendix E.1 to E.3 gives the full result. Given the surprisingly strong performance of naive RAG, we further validate our baseline setup in Appendix B.1 to B.3, including ablations on the RAG, reviewing RAG baselines in prior works, and validating the fairness of memory configurations. Overall, many memory systems fail to beat RAG in many cases, motivating a closer analysis in the next section.

### S6 · 4.1 Overview

[原文定位](https://arxiv.org/html/2610.34073v1#S4.SS1)

§3.2 shows many memory systems underperform the naive RAG despite substantially higher costs. Since RAG accesses the same raw history with minimal processing, it provides a reference for assessing the net value of building memory.

We dissect this net value through a per-query comparison with RAG (1rd) (Figure 3). Memory does solve some queries RAG misses, benefiting from additional organization or processing, while losing others that RAG already solves, where evidence may become lost, obscured, or harder to access after memory processing.

These two outcomes can be understood through the inevitable deviations introduced by memory from the raw history, as any nontrivial memory process can change how information is structured, preserved, or accessed.

These deviations give memory its dual nature.

They are originally intended to better serve the tasks, yet may also have unintended harmful effects due to particular design choices, giving rise to Memory Benefit and Memory Tax.

Their balance determines the net value of memory, and for the above cases, the tax outweighs the benefit.

These quantities are reference-dependent, and throughout this work are defined relative to the naive RAG.

Table 2:

Annotations for degree of information loss for sampled facts (%): no loss (NL), partial loss (PL), major loss (ML), and no memory unit (NU).

Method

NL

PL

ML

NU

Method

NL

PL

ML

NU

MemOS

85.8

9.0

2.4

2.8

OpenViking

39.4

9.6

13.0

38.0

SimpleMem

65.6

27.6

2.2

4.6

MAGMA

93.6

6.2

0.2

0.0

MemoryOS

98.4

0.0

0.0

1.6

PlugMem

79.6

10.8

5.2

4.4

LightMem

76.2

13.6

0.6

9.6

Memory-R2

72.6

14.8

6.0

6.6

We further provide representative benefit and tax cases in Appendix D. Memory benefit often appears when extraction, aggregation, preference inference or additional processing helps as shown in several typical types in Appendix D.1, it largely aligns with the intended value of memory, while memory tax is underexplored. Its effects are visible in failed queries, but these outcomes do not explain how the losses arise within the memory. We next examine internal factors behind the memory tax.

### S7 · 4.2 Memory Tax - Faithfulness: How Well Is the Information Preserved?

[原文定位](https://arxiv.org/html/2610.34073v1#S4.SS2)

To trace where memory tax comes from, the first place to look is how well the memory system preserves past information. Memory operations like restructuring and compression may discard or distort evidence before retrieval begins, and such loss can not be recovered later, so we first investigate the faithfulness for a memory system, at both the macro level and micro level.

Figure 4: Retrieval rounds replayed for the evidence to be fully retrieved, under raw chunks vs. memory units.

Figure 5: Similarity comparison of (query, gold raw turn) vs. (query, gold memory unit), with overall distribution shift (left) and point-wise similarity difference (right).

For each query, we denote the raw conversation turns or steps with the evidence as gold raw turns, and the corresponding constructed memory units as gold memory units (null if the evidence is lost after construction). At the macro level, we replay QA with only the gold raw turns and, separately, only the gold memory units. Gold memory units remove retrieval failures, so the remaining memory tax reflects the losses introduced in memory construction, as shown by the red boxes in Figure 3. At the micro level, we sample some atomic facts from the raw corpus and trace each fact to its corresponding memory units, annotating the degree of information loss, as shown in Table 2 and information loss does exist in many systems. Appendix C.2 and D.2 have more details and case studies.

However, the reduced tax after having oracle memory also indicates degradation arises beyond construction. The performance shows a similar signal. Some systems (MAGMA, LightMem) achieve gold-mem scores close to gold-raw-turn scores, yet far above their original, suggesting the preserved evidence may become harder to access.

### S8 · 4.3 Memory Tax - Accessibility: How Easily Can Stored Information Be Accessed?

[原文定位](https://arxiv.org/html/2610.34073v1#S4.SS3)

§4.2 examines how much information survives memory construction. However, preserved information is useful only if it remains accessible at query time. So next we measure the accessibility of memory from both macro and micro levels.

At the macro level, we replay retrieval iteratively for multiple rounds over the constructed memory and record how many rounds are needed to recover all gold memory units for a given query.

Evidence lost in construction is marked as not retrievable.

As shown in Figure 5, Memory systems recover fewer queries than RAG in the first round, suggesting that some relevant evidence is buried deeper after memory construction.

To understand why preserved evidence becomes harder to access, we further inspect some cases as the micro level analysis (Appendix D.3).

We observe several recurring patterns where evidence is fragmented across multiple memory units, diluted with unrelated information, or rephrased, weakening its accessibility compared with raw history.

To visualize this effect more broadly, we compare the (query, gold raw turn) similarity with the (query, gold memory unit) similarity, reporting the point-wise changes and overall drift in Figure 5.

Since each system retrieves within its own memory store, absolute similarity values across systems are only indicative, the main signal is how memory construction shifts the query alignment of the same evidence.

Appendix C.3 provides more results.

### S9 · 4.4 Memory Tax - Robustness: How Robust Is the Memory Across Backbones?

[原文定位](https://arxiv.org/html/2610.34073v1#S4.SS4)

The above analyses examine memory under a fixed backbone setting. However, long-lived agents may construct memory with one model and later consume it with another, making backbone robustness another important property. We construct memory independently with three backbones and evaluate each memory with different QA backbones.

Two patterns emerge. First, with the QA backbone fixed, changing the construction model leads to noticeable score variation. This is expected since many intermediate operations rely heavily on the backbones and can produce different memory items from the same raw history. More interestingly, with the construction fixed, changing the QA backbone causes larger performance variation than naive RAG for many systems, as shown in Figure 7. This suggests many memory mechanisms can introduce additional fragility beyond the raw-history retrieval. In this sense, memory tax is reflected not only in point-wise performance loss, but also in the reduced robustness to backbone changes.

See Appendix C.4 for more details.

Figure 6: Each row fixes the construction model, while different marker shapes denote different QA models. The segment shows Acc drop, red if the drop exceeds that of RAG (grey) and green otherwise.

Figure 7: Results of retrieval baselines on more memory benchmarks with Q27B. Details are in Appendix C.5.

### S10 · 4.5 Benchmark Headroom Further Exposes the Memory Tax

[原文定位](https://arxiv.org/html/2610.34073v1#S4.SS5)

The analysis so far focuses on how memory tax arises within a memory system. Yet the balance between memory benefit and tax also depends on the task settings. Some tasks naturally favor direct recall from raw history, while others may benefit more from abstraction or distillation. To examine this evaluation-side effect, we run several naive baselines across a broader set of long-term memory benchmarks, including No Memory, IDF-keyword, a lexical matching baseline based on the keyword rarity, RAG-Emb, and RAG-Hybrid. Details are in Appendix C.5.

Figure 7 shows that simple retrieval baselines already performs quite well on some of the benchmarks, including some widely-used ones. For example, the extremely simplified IDF-keyword based method can even achieve more than 50% in absolute score on some of them, while RAG-Hybrid reaches about 70%. Such results suggest some current evaluation settings are relatively retrieval-friendly, leaving quite limited headroom for heavy memory to improve over naive retrieval.

This also helps explain why some systems with lightweight or even no explicit memory construction can achieve strong performance and efficiency (Yan et al., 2025b; Yu et al., 2026b; Xiao et al., 2026; Xu et al., 2026b; Zhang et al., 2026b; Wu et al., 2026b). When naive retrieval already provides a strong baseline, they “inherit” much of that performance while introducing little memory tax, so lightweight design can be particularly competitive under limited benchmark headroom.

On the other hand, many real-world queries are also naturally retrieval-friendly, making such accurate recall tasks essential and meaningful in its own right.

Current benchmarks contain a large share of such queries, and future evaluations could complement them with harder settings.

Moreover, reporting memory systems alongside naive RAG can make remaining improvement room more explicit, which also helps clarify the contribution of built memory. RAG scores can also serve as a reference for calibrating difficulty and leaving meaningful room for more reliable evaluations.

### S11 · 5 Generalizing Memory Tax

[原文定位](https://arxiv.org/html/2610.34073v1#S5)

Memory serves a wide range of application scenarios beyond personal-agent memory. We next examine whether the same benefit-tax view extends to two substantially different settings.

### S12 · 5.1 Experiential Memory

[原文定位](https://arxiv.org/html/2610.34073v1#S5.SS1)

In this setting, agents accumulate experience from past task traces to guide future ones. We evaluate on several agentic scenarios covering embodied tasks (ALFWorld), web (WebShop, Mind2Web), coding (BigCodeBench) and tool use (AppWorld, \tau^{2} -Bench), with Qwen3.5-4B as backbone. Experience is accumulated on the training split and evaluated on the test split with memory frozen. We compare Memp (Fang et al., 2026b), ReasoningBank (Ouyang et al., 2026), G-Memory (Zhang et al., 2025a) and SkillPro (Mi et al., 2026) against a ReAct agent without memory and a naive RAG baseline, which retrieves the most similar past tasks by their descriptions and places the trajectories into the context, details are in Appendix C.6.1.

Figure 8 shows the effect of memory varies across task domains. In web-based tasks, distilling long traces into workflows or strategies can outperform naive RAG, while for tool-use, several memory methods fall behind it, suggesting memory tax also emerges in experiential memory, but its magnitude depends strongly on the task settings.

### S13 · 5.2 World-Model Memory

[原文定位](https://arxiv.org/html/2610.34073v1#S5.SS2)

Long-horizon world models need to retain information about past environment states to maintain temporal and scene consistency (Zhang et al., 2026e; Li et al., 2026; He et al., 2026; Chen et al., 2026f; Chen et al., 2026d; Chen et al., 2026c). Existing approaches have explored diverse memory representations and mechanisms, including raw frames, visual latents, and KV caches. We evaluate representative methods on two settings for long-horizon consistency: Context-as-Memory (Yu et al., 2025; King et al., 2026) and MemoBench (Chen et al., 2026b). Full details are in Appendix C.6.2.

A similar pattern appears in these settings (Table 3). Directly retrieving and reinjecting past observations achieves strong consistency, while latent- or cache-based memories do not consistently outperform this simpler alternative. This suggests that memory tax can also arise in world-model memory, where additional memory operations may introduce losses that offset their intended benefits. It also motivates exploration of more unified memory carriers in video world models.

Figure 8: Experiential memory results on agent task benchmarks, memory baselines are green when above RAG and red otherwise. See full version with memory tax part plotted in Appendix C.6.1.

Moreover, we also expect memory benefit/tax to extend beyond above settings along other axes (Hu et al., 2026b), like omni-modality, latents, parameters, etc. We leave the exploration for future work.

Table 3: Long-horizon consistency of world models with different memory representations and mechanisms.

Method

Mem.

Form

C-as-M-eval

MemoBench

SSIM \uparrow

1 - LPIPS \uparrow

SSIM \uparrow

1 - LPIPS \uparrow

I3DM

naive frames

.560

.704

.430

.476

WorldKV

raw KV

.372

.459

.379

.420

ReWorld

learned KV

.378

.510

.387

.422

MagicWorld

visual latents

.388

.341

.433

.412

FramePack

visual latents

.217

.312

.279

.303

HyDRA

mem. tokens

.320

.319

.355

.326

Figure 9: Example frame sequences from three evaluation scenes for testing long-horizon scene consistency.

### S14 · 6 Design Implications

[原文定位](https://arxiv.org/html/2610.34073v1#S6)

In this section, we derive some simple yet effective design implications for reducing or compensating for the memory tax. We focus on improvements that can be used on existing memory systems without introducing another new architecture, and deliberately exclude common test-time scaling techniques like retrieval depth / width expansion, query refinement, using stronger backbones, etc.

As we discussed above, building memory can introduce changes and deviations from the raw history about how information is preserved and accessed through diverse memory operations. While no single design can predict and fit all tasks needs, and the harmful deviations are difficult to eliminate entirely, a more promising way to reduce memory tax is to make such deviations recoverable, preserving a lightweight path back to the source history when memory becomes insufficient.

As a simple proof of concept, we retrieve from source history alongside normal memory retrieval and jointly rerank them before QA. This lightweight recovery path can restore evidence lost during construction or missed in access. Results in Table show consistent improvements and reduction of memory tax across several memory systems.

Memory tax can only be visible in actual use, when relevant evidences become harder to access and are recovered only after deep search. Such retrieval experience directly reflects the harmful deviations memory introduced, and can in turn provide feedback to improve future memory access, creating a recursive loop between memory access and construction.

Inspired by progress on recursive self-improvement (RSI) (Zhang et al., 2026c; Karten et al., 2026; Zhang et al., 2026d), where a system is expected to “improve how it improves”, memory can similarly “remember how it remembers”.

Past queries, evidences, and retrieval paths can themselves be source materials for memory, and this is particularly useful for multi-round retrieval, since evidence found in deeper rounds can then be accessed directly by similar information needs.

It also offers a new dimension of test-time scaling at query-side, allowing inter-query scaling beyond a single query.

As a simple proof of concept, we treat past queries and retrieved evidence as additional inputs into memory store, making them available for future retrieval. Results in Table also validate its effectiveness.

Many methods build memory ahead of time (AoT) before future queries come. As we discussed before, memory makes deviations on the raw history, with the intention of better serving task queries, but may also add implicitly harmful effects. Without knowing future demand accurately, it is unclear what kind of deviations will be beneficial. To cover a broader range of possible queries, AoT systems may need to process more information in more elaborate ways, making it increasingly expensive.

The opposite is just-in-time (JiT) memory (Yan et al., 2025a; Zhou et al., 2026b; Yan et al., 2026a), which delays memory operations until queries arrive. With query already known, JiT can choose more targeted forms and directions of deviation to maximize the memory benefit and minimize the memory tax, but moves computation to the online part and increases user-facing latency, to which the users are highly sensitive.

A middle ground is to model the future demand.

In personal agent settings, task queries are not purely random.

Past interests, habits, and access patterns provide a prior over what information is likely to matter, and hence what kinds of deviations that memory introduces are likely useful.

Such signals may help construction allocate effort more selectively, and reduces harmful deviations, without paying the full online cost of JiT. From this view, memory can partly be seen as an implicit recommendation system that estimates future relevance of past information.

Exploring this perspective in real-world personal-agent settings may be a promising direction for future exploration.

### S15 · Long-Term Agent Memory.

[原文定位](https://arxiv.org/html/2610.34073v1#S7.SS0.SSS0.Px1)

Long-term memory has become an important component for long-horizon agents, supporting the retention of specific information, past interactions, and task experience. Existing systems explore a variety of memory representations, including relatively flat stores (Liu et al., 2026b; Yang et al., 2026b; Meng et al., 2026), hierarchical organizations, from short-/long-term memory layers (Kang et al., 2025; Fang et al., 2026a) to filesystem-tree designs in recent industrial systems (Volcengine, 2026; Tencent-Cloud, 2026), and graph-based representations (Jiang et al., 2026a; Yang et al., 2026a). Another line of variation lies in how memory operations are governed. Some systems rely on predefined harness for writing, updating, and using memories, while others allow an LLM agent to decide these operations dynamically (Wang and Chen, 2025; Xu et al., 2026a; EverMind-AI, 2026) or explore learned memory policies (Yan et al., 2026c; Yu et al., 2026a; Yan et al., 2026b).

In this work, we study these memory systems through the lens of their net value, examining the gains and the losses introduced by memory operations.

### S16 · Empirical Studies of Agent Memory.

[原文定位](https://arxiv.org/html/2610.34073v1#S7.SS0.SSS0.Px2)

Recent empirical studies examine agent memory from different perspectives, including how memory systems are designed and deployed, their performance-cost trade-offs, and where computation and time are spent (Jiang et al., 2026b; Omri et al., 2026; Zhou et al., 2026a; Huang et al., 2026; Wolff and Bennati, 2026). These works mainly characterize existing memory designs and their empirical behavior, but our work focuses on the net value introduced by memory processing itself. We introduce memory tax to characterize its losses relative to direct retrieval, analyze how such losses arise from both system and evaluation sides, and derive system-agnostic design implications.

### S17 · 8 Conclusion

[原文定位](https://arxiv.org/html/2610.34073v1#S8)

We revisit the agent memory by studying its net value over direct retrieval from raw history.

Across the evaluation on three benchmarks with many retrieval-friendly queries alongside some complex ones, many memory methods underperform naive RAG, indicating a negative net value in these settings.

We dissect this net value into memory benefit and tax, showing memory can improve how past information is organized and used, but may also have harmful effects.

We analyze memory tax from both system sides and evaluation settings, and generalize it to broader scenarios like experiential memory and world-model memory.

We hope memory tax can shift more attention from standalone performance to the net value of memory, and encourages more reliable memory design and evaluation.

### S18 · Limitations

[原文定位](https://arxiv.org/html/2610.34073v1#Sx1)

Given the rapid development of this field, our baseline selection is representative rather than exhaustive. We also follow official configurations wherever possible, though further system-specific tuning may yield better performance.

Our benchmarks are primarily static, offline, and English-language, leaving long-lived deployments with interleaved queries and multilingual interactions underexplored. Extending the analysis to other forms of memory, such as omnimodal, latent, and parametric memory, is also left for future work.

Our evaluation is limited by computational and API-calling cost. We do not include stronger frontier models beyond GPT-5.6 Luna (low), and use stratified subsets for some benchmarks (20% of PersonaMem-v2, 10% of MINT-Eval, and 20% LongMemEval-s questions for GPT-5.6 Luna).

### S19 · References

[原文定位](https://arxiv.org/html/2610.34073v1#bib)

Barres et al. (2025)

Victor Barres, Honghua Dong, Soham Ray, Xujie Si, and Karthik Narasimhan. 2025.

\tau^{2} -bench: Evaluating conversational agents in a dual-control environment.

Preprint, arXiv:2506.07982.

Bei et al. (2026)

Yuanchen Bei, Tianxin Wei, Xuying Ning, Yanjun Zhao, Zhining Liu, Xiao Lin, Yada Zhu, Hendrik Hamann, Jingrui He, and Hanghang Tong. 2026.

Mem-gallery: Benchmarking multimodal long-term conversational memory for mllm agents.

Preprint, arXiv:2601.03515.

Bian et al. (2026)

Haonan Bian, Zhiyuan Yao, Sen Hu, Zishan Xu, Shaolei Zhang, Yifu Guo, Ziliang Yang, Xueran Han, Huacan Wang, and Ronghao Chen. 2026.

Realmem: Benchmarking llms in real-world memory-driven interaction.

Preprint, arXiv:2601.06966.

Chen et al. (2026a)

Ding Chen, Simin Niu, Kehang Li, Peng Liu, Xiangping Zheng, Bo Tang, Xinchi Li, Feiyu Xiong, and Zhiyu Li. 2026a.

Halumem: Evaluating hallucinations in memory systems of agents.

Preprint, arXiv:2511.03506.

Chen et al. (2026b)

Haoyu Chen, Kaichen Zhou, Hang Hua, Kaile Zhang, Jingwen Qian, Wufei Ma, Haonan Chen, Chunjiang Liu, Yizhou Zhao, Xiaoyuan Wang, et al. 2026b.

Memobench: Benchmarking world modeling in dynamically changing environments.

In European Conference on Computer Vision, pages 658–676. Springer.

Chen et al. (2026c)

Harold Haodong Chen, Rongjin Guo, Disen Lan, Wen-Jie Shu, Hongfei Zhang, Hanzhe Hu, Shengtao Yao, Zixin Zhang, Guibin Zhang, Zhefan Rao, et al. 2026c.

The past frames the future: Memory for autoregressive video generation.

arXiv preprint arXiv:2609.28466.

Chen et al. (2026d)

Kaijin Chen, Dingkang Liang, Xin Zhou, Yikang Ding, Xiaoqiang Liu, Pengfei Wan, and Xiang Bai. 2026d.

Out of sight but not out of mind: Hybrid memory for dynamic video world models.

arXiv preprint arXiv:2603.25716.

Chen et al. (2026e)

Tiantian Chen, Jiaqi Lu, Ying Shen, and Lin Zhang. 2026e.

Es-memeval: Benchmarking conversational agents on personalized long-term emotional support.

In Proceedings of the ACM Web Conference 2026, page 5810–5821. ACM.

Chen et al. (2026f)

Zhifei Chen, Luozhou Wang, Guibao Shen, Dongyu Yan, Shuai Yang, Tianshuo Xu, Yihua Du, Wei Wang, Tianyi Gui, Lianghua Huang, et al. 2026f.

Reworld: An interactive world model with long-horizon memory.

arXiv preprint arXiv:2608.23565.

Chhikara et al. (2025a)

Prateek Chhikara, Dev Khant, Saket Aryan, Taranjeet Singh, and Deshraj Yadav. 2025a.

Mem0: Building production-ready ai agents with scalable long-term memory.

arXiv preprint arXiv:2504.19413.

Chhikara et al. (2025b)

Prateek Chhikara, Dev Khant, Saket Aryan, Taranjeet Singh, and Deshraj Yadav. 2025b.

Mem0: Building production-ready ai agents with scalable long-term memory.

Preprint, arXiv:2504.19413.

Deng et al. (2023)

Xiang Deng, Yu Gu, Boyuan Zheng, Shijie Chen, Samuel Stevens, Boshi Wang, Huan Sun, and Yu Su. 2023.

Mind2web: Towards a generalist agent for the web.

Preprint, arXiv:2306.06070.

Eslami et al. (2026)

Sedigheh Eslami, Maksim Gaiduk, Markus Krimmel, Louis Milliken, Bo Wang, and Denis Bykov. 2026.

Diffusion-pretrained dense and contextual embeddings.

Preprint, arXiv:2602.11151.

EverMind-AI (2026)

EverMind-AI. 2026.

EverOS: One portable memory layer for every ai agent: local-first, markdown-native, user-owned, and self-evolving across apps, tools, and workflows.

https://github.com/EverMind-AI/EverOS.

Fang et al. (2026a)

Jizhan Fang, Xinle Deng, Haoming Xu, Ziyan Jiang, Yuqi Tang, Ziwen Xu, Shumin Deng, Yunzhi Yao, Mengru Wang, Shuofei Qiao, et al. 2026a.

Lightmem: Lightweight and efficient memory-augmented generation.

In International Conference on Learning Representations, volume 2026, pages 98706–98729.

Fang et al. (2026b)

Runnan Fang, Yuan Liang, Xiaobin Wang, Jialong Wu, Shuofei Qiao, Pengjun Xie, Fei Huang, Huajun Chen, and Ningyu Zhang. 2026b.

Memp: Exploring agent procedural memory.

Preprint, arXiv:2508.06433.

Gur et al. (2024)

Izzeddin Gur, Hiroki Furuta, Austin Huang, Mustafa Safdari, Yutaka Matsuo, Douglas Eck, and Aleksandra Faust. 2024.

A real-world webagent with planning, long context understanding, and program synthesis.

In International Conference on Learning Representations, volume 2024, pages 52690–52717.

Gutiérrez et al. (2025)

Bernal Jiménez Gutiérrez, Yiheng Shu, Weijian Qi, Sizhe Zhou, and Yu Su. 2025.

From rag to memory: Non-parametric continual learning for large language models.

arXiv preprint arXiv:2502.14802.

He et al. (2026)

Xuan He, Cong Wei, Yuhao Cheng, Linrui Ma, Yuxuan Zhang, Zuojun Li, Yuhao Wen, Zeyi Liu, Yuren Hao, Songcheng Cai, et al. 2026.

Vgi-bench: Probing visual intelligence in video generation models.

arXiv preprint arXiv:2608.19583.

Hu et al. (2026a)

Chuanrui Hu, Tong Li, Xingze Gao, Hongda Chen, Yi Bai, Dannong Xu, Tianwei Lin, Xiaohong Li, Yunyun Han, Jian Pei, and Yafeng Deng. 2026a.

Evaluating long-horizon memory for multi-party collaborative dialogues.

Preprint, arXiv:2602.01313.

Hu et al. (2025a)

Mengkang Hu, Tianxing Chen, Qiguang Chen, Yao Mu, Wenqi Shao, and Ping Luo. 2025a.

HiAgent: Hierarchical working memory management for solving long-horizon agent tasks with large language model.

In Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), pages 32779–32798, Vienna, Austria. Association for Computational Linguistics.

Hu et al. (2025b)

Yuanzhe Hu, Yu Wang, and Julian McAuley. 2025b.

Evaluating memory in llm agents via incremental multi-turn interactions.

Preprint, arXiv:2507.05257.

Hu et al. (2026b)

Yuyang Hu, Shichun Liu, Yanwei Yue, Guibin Zhang, Boyang Liu, Fangyi Zhu, Jiahang Lin, Honglin Guo, Shihan Dou, Zhiheng Xi, Senjie Jin, Jiejun Tan, Yanbin Yin, Jiongnan Liu, Zeyu Zhang, Zhongxiang Sun, Yutao Zhu, Hao Sun, Boci Peng, and 28 others. 2026b.

Memory in the age of ai agents.

Preprint, arXiv:2512.13564.

Huang et al. (2026)

Wei-Chieh Huang, Weizhi Zhang, Yuchen Wu, Yankai Chen, Eric Hanchen Jiang, Wooseong Yang, Yiwei Yang, Henry Peng Zou, Hanrong Zhang, Ying Nian Wu, Haolun Wu, Kai-Wei Chang, Philip S. Yu, Xue Liu, and Aylin Caliskan. 2026.

Harness the memory: A holistic evaluation of memory substrates in memory agents.

Preprint, arXiv:2608.15008.

Jiang et al. (2025a)

Bowen Jiang, Zhuoqun Hao, Young-Min Cho, Bryan Li, Yuan Yuan, Sihao Chen, Lyle Ungar, Camillo J. Taylor, and Dan Roth. 2025a.

Know me, respond to me: Benchmarking llms for dynamic user profiling and personalized responses at scale.

Preprint, arXiv:2504.14225.

Jiang et al. (2025b)

Bowen Jiang, Yuan Yuan, Maohao Shen, Zhuoqun Hao, Zhangchen Xu, Zichen Chen, Ziyi Liu, Anvesh Rao Vijjini, Jiashu He, Hanchao Yu, Radha Poovendran, Gregory Wornell, Lyle Ungar, Dan Roth, Sihao Chen, and Camillo Jose Taylor. 2025b.

Personamem-v2: Towards personalized intelligence via learning implicit user personas and agentic memory.

Preprint, arXiv:2512.06688.

Jiang et al. (2026a)

Dongming Jiang, Yi Li, Guanpeng Li, and Bingzhe Li. 2026a.

Magma: A multi-graph based agentic memory architecture for ai agents.

In Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), pages 36848–36865.

Jiang et al. (2026b)

Dongming Jiang, Yi Li, Songtao Wei, Jinxin Yang, Ayushi Kishore, Alysa Zhao, Dingyi Kang, Xu Hu, Feng Chen, Qiannan Li, and Bingzhe Li. 2026b.

Anatomy of agentic memory: Taxonomy and empirical analysis of evaluation and system limitations.

Preprint, arXiv:2602.19320.

Kang et al. (2025)

Jiazheng Kang, Mingming Ji, Zhe Zhao, and Ting Bai. 2025.

Memory os of ai agent.

In Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing, pages 25972–25981.

Karten et al. (2026)

Seth Karten, Alex L. Zhang, Kevin Thomas, Sebastian Müller, Elie Bakouch, Daniel Auras, Mika Senghaas, Fares Obeid, Konstantin Dunas, Johannes Hagemann, and Sami Jaghouar. 2026.

Prime agent: A self-improving rlm harness.

Preprint, arXiv:2608.23552.

King et al. (2026)

Wayne King, Zeyue Xue, Yuxuan Bian, Jie Huang, Haoran Li, Yaowei Li, Yaofeng Su, Yuming Li, Haoyu Wang, Shiyi Zhang, et al. 2026.

Echo-memory: A controlled study of memory in action world models.

arXiv preprint arXiv:2606.09803.

Lee et al. (2025)

Chankyu Lee, Rajarshi Roy, Mengyao Xu, Jonathan Raiman, Mohammad Shoeybi, Bryan Catanzaro, and Wei Ping. 2025.

Nv-embed: Improved techniques for training llms as generalist embedding models.

Preprint, arXiv:2405.17428.

Lee et al. (2026)

Hyunji Lee, Justin Chih-Yao Chen, Joykirat Singh, Zaid Khan, Elias Stengel-Eskin, and Mohit Bansal. 2026.

Minteval: Evaluating memory under multi-target interference in long-horizon agent systems.

Preprint, arXiv:2605.18565.

Li et al. (2025a)

Guangyuan Li, Bo Li, Jinwei Chen, Xiaobin Hu, Lei Zhao, and Peng-Tao Jiang. 2025a.

Magicworld: Towards long-horizon stability for interactive video world exploration.

arXiv preprint arXiv:2511.18886.

Li et al. (2026)

Jia Li, Han Yan, Yihang Chen, Siqi Li, Xibin Song, Yifu Wang, Jianfei Cai, Tien-Tsin Wong, and Pan Ji. 2026.

I3dm: Implicit 3d-aware memory retrieval and injection for consistent video scene generation.

arXiv preprint arXiv:2603.23413.

Li et al. (2025b)

Zhiyu Li, Shichao Song, Hanyu Wang, Simin Niu, Ding Chen, Jiawei Yang, Chenyang Xi, Huayi Lai, Jihao Zhao, Yezhaohui Wang, Junpeng Ren, Zehao Lin, Jiahao Huo, Tianyi Chen, Kai Chen, Kehang Li, Zhiqiang Yin, Qingchen Yu, Bo Tang, and 3 others. 2025b.

Memos: An operating system for memory-augmented generation (mag) in large language models.

Preprint, arXiv:2505.22101.

Liu et al. (2026a)

Chengzhi Liu, Yuzhe Yang, Sophia Xiao Pu, Yepeng Liu, Lin Long, Yichen Guo, Nuo Chen, Zhaotian Weng, Elena Kochkina, Simerjot Kaur, Charese Smiley, Xiaomo Liu, James Zou, Sheng Liu, Yuheng Bu, Songyou Peng, and Xin Eric Wang. 2026a.

Worldmemarena: Evaluating multimodal agent memory through action-world interaction.

Preprint, arXiv:2605.29341.

Liu et al. (2026b)

Jiaqi Liu, Yaofeng Su, Peng Xia, Siwei Han, Zeyu Zheng, Cihang Xie, Mingyu Ding, and Huaxiu Yao. 2026b.

Simplemem: Efficient lifelong memory for llm agents.

Preprint, arXiv:2601.02553.

Liu et al. (2025)

Zheng Liu, Chaofan Li, Shitao Xiao, Yingxia Shao, and Defu Lian. 2025.

Llama2vec: Unsupervised adaptation of large language models for dense retrieval.

Preprint, arXiv:2312.15503.

Ma et al. (2026)

Wenquan Ma, Jiayan Nan, Wenlong Wu, and Yize Chen. 2026.

What deserves memory: Adaptive memory distillation for llm agents.

Preprint, arXiv:2508.03341.

Maharana et al. (2024)

Adyasha Maharana, Dong-Ho Lee, Sergey Tulyakov, Mohit Bansal, Francesco Barbieri, and Yuwei Fang. 2024.

Evaluating very long-term conversational memory of llm agents.

Preprint, arXiv:2402.17753.

Meng et al. (2026)

Xuanyu Meng, Jiashuo Sun, Jash Rajesh Parekh, and Jiawei Han. 2026.

Ensi-rag: Entity-structure-indexed retrieval-augmented generation for long-document question answering.

arXiv preprint arXiv:2608.21252.

Mi et al. (2026)

Qirui Mi, Zhijian Ma, Mengyue Yang, Haoxuan Li, Yisen Wang, Haifeng Zhang, and Jun Wang. 2026.

Skill-pro: Learning reusable skills from experience via non-parametric ppo for llm agents.

Preprint, arXiv:2602.01869.

Omri et al. (2026)

Yasmine Omri, Ziyu Gan, Zachary Broveak, Robin Geens, Zexue He, Alex Pentland, Marian Verhelst, Tsachy Weissman, and Thierry Tambe. 2026.

Agent memory: Characterization and system implications of stateful long-horizon workloads.

Preprint, arXiv:2606.06448.

Ouyang et al. (2026)

Siru Ouyang, Jun Yan, I-Hung Hsu, Yanfei Chen, Ke Jiang, Zifeng Wang, Rujun Han, Long T. Le, Samira Daruki, Xiangru Tang, Vishy Tirumalashetty, George Lee, Mahsan Rofouei, Hangfei Lin, Jiawei Han, Chen-Yu Lee, and Tomas Pfister. 2026.

Reasoningbank: Scaling agent self-evolving with reasoning memory.

Preprint, arXiv:2509.25140.

Packer et al. (2024)

Charles Packer, Sarah Wooders, Kevin Lin, Vivian Fang, Shishir G. Patil, Ion Stoica, and Joseph E. Gonzalez. 2024.

Memgpt: Towards llms as operating systems.

Preprint, arXiv:2310.08560.

Rasmussen et al. (2025)

Preston Rasmussen, Pavlo Paliychuk, Travis Beauvais, Jack Ryan, and Daniel Chalef. 2025.

Zep: A temporal knowledge graph architecture for agent memory.

Preprint, arXiv:2501.13956.

Shridhar et al. (2021)

Mohit Shridhar, Xingdi Yuan, Marc-Alexandre Côté, Yonatan Bisk, Adam Trischler, and Matthew Hausknecht. 2021.

Alfworld: Aligning text and embodied environments for interactive learning.

Preprint, arXiv:2010.03768.

Tencent-Cloud (2026)

Tencent-Cloud. 2026.

TencentDB-Agent-Memory: Tencentdb agent memory is a team-level memory hub for ai agents - turning conversations, docs, and code into four reusable memory assets (chat memory, skill, llm-wiki, code-graph) that are governed, shared, and equipped across agents and frameworks..

https://github.com/TencentCloud/TencentDB-Agent-Memory.

Trivedi et al. (2024)

Harsh Trivedi, Tushar Khot, Mareike Hartmann, Ruskin Manku, Vinty Dong, Edward Li, Shashank Gupta, Ashish Sabharwal, and Niranjan Balasubramanian. 2024.

Appworld: A controllable world of apps and people for benchmarking interactive coding agents.

Preprint, arXiv:2407.18901.

Volcengine (2026)

Volcengine. 2026.

OpenViking: An open-source context database for ai agents.

https://github.com/volcengine/OpenViking.

Wang et al. (2025)

Feng Wang, Yuqing Li, and Han Xiao. 2025.

jina-reranker-v3: Last but not late interaction for document reranking.

Preprint, arXiv:2509.25085.

Wang et al. (2023)

Guanzhi Wang, Yuqi Xie, Yunfan Jiang, Ajay Mandlekar, Chaowei Xiao, Yuke Zhu, Linxi Fan, and Anima Anandkumar. 2023.

Voyager: An open-ended embodied agent with large language models.

arXiv preprint arXiv:2305.16291.

Wang et al. (2020)

Wenhui Wang, Furu Wei, Li Dong, Hangbo Bao, Nan Yang, and Ming Zhou. 2020.

Minilm: Deep self-attention distillation for task-agnostic compression of pre-trained transformers.

Preprint, arXiv:2002.10957.

Wang and Chen (2025)

Yu Wang and Xi Chen. 2025.

Mirix: Multi-agent memory system for llm-based agents.

Preprint, arXiv:2507.07957.

Wolff and Bennati (2026)

Benedict Wolff and Jacopo Bennati. 2026.

Cost and accuracy of long-term memory in distributed multi-agent systems based on large language models.

In 2026 IEEE 50th Annual Computers, Software, and Applications Conference (COMPSAC), page 11–21. IEEE.

Wu et al. (2025)

Di Wu, Hongwei Wang, Wenhao Yu, Yuwei Zhang, Kai-Wei Chang, and Dong Yu. 2025.

Longmemeval: Benchmarking chat assistants on long-term interactive memory.

Preprint, arXiv:2410.10813.

Wu et al. (2026a)

Tingyu Wu, Zhisheng Chen, Ziyan Weng, Shuhe Wang, Chenglong Li, Shuo Zhang, Sen Hu, Silin Wu, Qizhen Lan, Huacan Wang, and Ronghao Chen. 2026a.

Knowme-bench: Benchmarking person understanding for lifelong digital companions.

Preprint, arXiv:2601.04745.

Wu et al. (2026b)

Yuqian Wu, Wei Chen, Zhengjun Huang, Junle Chen, Qingxiang Liu, Kai Wang, Xiaofang Zhou, and Yuxuan Liang. 2026b.

Back to basics: Let conversational agents remember with just retrieval and generation.

Preprint, arXiv:2604.11628.

Xiao et al. (2024)

Shitao Xiao, Zheng Liu, Peitian Zhang, Niklas Muennighoff, Defu Lian, and Jian-Yun Nie. 2024.

C-pack: Packed resources for general chinese embeddings.

Preprint, arXiv:2309.07597.

Xiao et al. (2026)

Yilin Xiao, Zhehan Zhu, Yujing Zhang, Jin Chen, Zijin Hong, Luyao Zhuang, Qinggang Zhang, Shengyuan Chen, Xiaocao Ouyang, Lingfei Ren, and Xiao Huang. 2026.

Zero-mem: Zero-token memory operations for llm agents.

Preprint, arXiv:2607.29377.

Xie et al. (2024)

Tianbao Xie, Danyang Zhang, Jixuan Chen, Xiaochuan Li, Siheng Zhao, Ruisheng Cao, Toh J Hua, Zhoujun Cheng, Dongchan Shin, Fangyu Lei, et al. 2024.

Osworld: Benchmarking multimodal agents for open-ended tasks in real computer environments.

Advances in Neural Information Processing Systems, 37:52040–52094.

Xu et al. (2026a)

Wujiang Xu, Zujie Liang, Kai Mei, Hang Gao, Juntao Tan, and Yongfeng Zhang. 2026a.

A-mem: Agentic memory for llm agents.

Advances in Neural Information Processing Systems, 38:17577–17604.

Xu et al. (2026b)

Xiucheng Xu, Bingbing Xu, Xueyun Tian, Zihe Huang, Rongxin Chen, Yunfan Li, and Huawei Shen. 2026b.

Chain-of-memory: Lightweight memory construction with dynamic evolution for llm agents.

Preprint, arXiv:2601.14287.

Yan et al. (2025a)

B. Y. Yan, Chaofan Li, Hongjin Qian, Shuqi Lu, and Zheng Liu. 2025a.

General agentic memory via deep research.

Preprint, arXiv:2511.18423.

Yan et al. (2026a)

Bingyu Yan, Chaofan Li, Hongjin Qian, Shuqi Lu, Chaozhuo Li, and Zheng Liu. 2026a.

Just-in-time agent memory with runtime agentic research.

Preprint, arXiv:2609.34385.

Yan et al. (2025b)

BY Yan, Chaofan Li, Hongjin Qian, Shuqi Lu, and Zheng Liu. 2025b.

General agentic memory via deep research.

arXiv preprint arXiv:2511.18423.

Yan et al. (2026b)

Sikuan Yan, Ahmed Bahloul, Ercong Nie, Susanna Schwarzmann, Riccardo Trivisonno, Volker Tresp, and Yunpu Ma. 2026b.

Memory-r2: Fair credit assignment for long-horizon memory-augmented llm agents.

arXiv preprint arXiv:2605.21768.

Yan et al. (2026c)

Sikuan Yan, Xiufeng Yang, Zuchao Huang, Ercong Nie, Zifeng Ding, Zonggen Li, Xiaowen Ma, Jinhe Bi, Kristian Kersting, Jeff Z. Pan, Hinrich Schütze, Volker Tresp, and Yunpu Ma. 2026c.

Memory-r1: Enhancing large language model agents to manage and utilize memories via reinforcement learning.

Preprint, arXiv:2508.19828.

Yang et al. (2026a)

Ke Yang, Zixi Chen, Xuan He, Jize Jiang, Michel Galley, Chenglong Wang, Jianfeng Gao, Jiawei Han, and ChengXiang Zhai. 2026a.

Plugmem: A task-agnostic plugin memory module for llm agents.

arXiv preprint arXiv:2603.03296.

Yang et al. (2026b)

Ruozhen Yang, Yucheng Jiang, Yueqi Jiang, Priyanka Kargupta, Yunyi Zhang, and Jiawei Han. 2026b.

Grounding agent memory in contextual intent.

In Findings of the Association for Computational Linguistics: ACL 2026, pages 12008–12042, San Diego, California, United States. Association for Computational Linguistics.

Yao et al. (2023a)

Shunyu Yao, Howard Chen, John Yang, and Karthik Narasimhan. 2023a.

Webshop: Towards scalable real-world web interaction with grounded language agents.

Preprint, arXiv:2207.01206.

Yao et al. (2023b)

Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, and Yuan Cao. 2023b.

React: Synergizing reasoning and acting in language models.

Preprint, arXiv:2210.03629.

Yi et al. (2026)

Jung Yi, Minjae Kim, Paul Hyunbin Cho, Wooseok Jang, Sangdoo Yun, and Seungryong Kim. 2026.

Worldkv: Efficient world memory with world retrieval and compression.

arXiv preprint arXiv:2605.22718.

Yu et al. (2026a)

Hongli Yu, Tinghong Chen, Jiangtao Feng, Jiangjie Chen, Weinan Dai, Qiying Yu, Ya-Qin Zhang, Wei-Ying Ma, Jingjing Liu, Mingxuan Wang, and Hao Zhou. 2026a.

Memagent: Reshaping long-context llm with multi-conv rl-based memory agent.

Preprint, arXiv:2507.02259.

Yu et al. (2026b)

Jing Yu, Yibo Zhao, Jiaming Zhang, and Xiang Li. 2026b.

Lazymem: Retrieve broadly, construct selectively for efficient long-term agent memory.

Preprint, arXiv:2607.22690.

Yu et al. (2025)

Jiwen Yu, Jianhong Bai, Yiran Qin, Quande Liu, Xintao Wang, Pengfei Wan, Di Zhang, and Xihui Liu. 2025.

Context as memory: Scene-consistent interactive long video generation with memory retrieval.

In Proceedings of the SIGGRAPH Asia 2025 Conference Papers, pages 1–11.

Yue et al. (2026)

Yanwei Yue, Boci Peng, Xuanbo Fan, Jiaxin Guo, Qiankun Li, and Yan Zhang. 2026.

Mem-t: Densifying rewards for long-horizon memory agents.

arXiv preprint arXiv:2601.23014.

Zhang et al. (2025a)

Guibin Zhang, Muxin Fu, Guancheng Wan, Miao Yu, Kun Wang, and Shuicheng Yan. 2025a.

G-memory: Tracing hierarchical memory for multi-agent systems.

Preprint, arXiv:2506.07398.

Zhang et al. (2026a)

Haozhen Zhang, Quanyu Long, Jianzhu Bao, Tao Feng, Weizhi Zhang, Haodong Yue, and Wenya Wang. 2026a.

Memskill: Learning and evolving memory skills for self-evolving agents.

Preprint, arXiv:2602.02474.

Zhang et al. (2026b)

Haozhen Zhang, Haodong Yue, Tao Feng, Quanyu Long, Jianzhu Bao, Bowen Jin, Weizhi Zhang, Xiao Li, Jiaxuan You, Chengwei Qin, and Wenya Wang. 2026b.

Learning query-aware budget-tier routing for runtime agent memory.

Preprint, arXiv:2602.06025.

Zhang et al. (2026c)

Jenny Zhang, Shengran Hu, Cong Lu, Robert Lange, and Jeff Clune. 2026c.

Darwin gödel machine: Open-ended evolution of self-improving agents.

In International Conference on Learning Representations, volume 2026, pages 104223–104294.

Zhang et al. (2026d)

Jenny Zhang, Bingchen Zhao, Wannan Yang, Jakob Foerster, Jeff Clune, Minqi Jiang, Sam Devlin, and Tatiana Shavrina. 2026d.

Hyperagents.

Preprint, arXiv:2603.19461.

Zhang et al. (2026e)

Lvmin Zhang, Shengqu Cai, Muyang Li, Gordon Wetzstein, and Maneesh Agrawala. 2026e.

Frame context packing and drift prevention in next-frame-prediction video diffusion models.

Advances in Neural Information Processing Systems, 38:30546–30566.

Zhang et al. (2025b)

Yanzhao Zhang, Mingxin Li, Dingkun Long, Xin Zhang, Huan Lin, Baosong Yang, Pengjun Xie, An Yang, Dayiheng Liu, Junyang Lin, Fei Huang, and Jingren Zhou. 2025b.

Qwen3 embedding: Advancing text embedding and reranking through foundation models.

Preprint, arXiv:2506.05176.

Zhao et al. (2026)

Yujie Zhao, Boqin Yuan, Junbo Huang, Haocheng Yuan, Zhongming Yu, Haozhou Xu, Lanxiang Hu, Abhilash Shankarampeta, Zimeng Huang, Wentao Ni, Yuandong Tian, and Jishen Zhao. 2026.

Ama-bench: Evaluating long-horizon memory for agentic applications.

Preprint, arXiv:2602.22769.

Zhou et al. (2026a)

Wei Zhou, Xuanhe Zhou, Shaokun Han, Hongming Xu, Guoliang Li, Zhiyu Li, Feiyu Xiong, and Fan Wu. 2026a.

Are we ready for an agent-native memory system?

Preprint, arXiv:2606.24775.

Zhou et al. (2026b)

Yefan Zhou, Yang Li, Zeyu Leo Liu, Semih Yavuz, and Shafiq Joty. 2026b.

Just-in-time memory: Learning to curate task-adaptive memory for llm agents.

Preprint, arXiv:2609.27334.

Zhuo et al. (2025)

Terry Yue Zhuo, Minh Chien Vu, Jenny Chim, Han Hu, Wenhao Yu, Ratnadira Widyasari, Imam Nur Bani Yusuf, Haolan Zhan, Junda He, Indraneil Paul, Simon Brunner, Chen Gong, Thong Hoang, Armel Randy Zebaze, Xiaoheng Hong, Wen-Ding Li, Jean Kaddour, Ming Xu, Zhihan Zhang, and 14 others. 2025.

Bigcodebench: Benchmarking code generation with diverse function calls and complex instructions.

Preprint, arXiv:2406.15877.

### S20 · A.1 Benchmark Details

[原文定位](https://arxiv.org/html/2610.34073v1#A1.SS1)

Table 4 summarizes the evaluation data.

### S21 · LongMemEval-s ( Wu et al., 2025 ) .

[原文定位](https://arxiv.org/html/2610.34073v1#A1.SS1.SSS0.Px1)

Each question has its own chat history of about 50 sessions, with a few evidence sessions hidden among distractors. We use the full set, except a 100-corpus subset stratified by question type for GPT-5.6 Luna.

### S22 · PersonaMem-v2 ( Jiang et al., 2025b ) .

[原文定位](https://arxiv.org/html/2610.34073v1#A1.SS1.SSS0.Px2)

Each corpus is one simulated user’s chat history (128k-token variant), with four-way MCQs on the user’s implicit persona and preferences. We evaluate a 20% subset (40 of 200 corpora).

### S23 · MINT-Eval ( Lee et al., 2026 ) .

[原文定位](https://arxiv.org/html/2610.34073v1#A1.SS1.SSS0.Px3)

Each corpus is an ordered stream of steps from one of four sub-domains, testing memory under multi-target interference. We draw a 10% stratified sample (60 of 595 corpora).

### S24 · Vanilla.

[原文定位](https://arxiv.org/html/2610.34073v1#A1.SS2.SSS0.Px1)

These references use no retrieval or memory building. No Context answers from the question alone.

Full Context provides the entire raw corpus in chronological order, truncating the earliest units if it exceeds the model’s context window.

Gold Context provides only the gold evidence (raw turns supporting the answer) for each question, serving as an oracle reference. We omit this baseline on MINT-Eval, where author-annotated and verified gold evidence is available for only about half of the questions (Appendix C.2).

### S25 · Naive RAG.

[原文定位](https://arxiv.org/html/2610.34073v1#A1.SS2.SSS0.Px2)

The raw corpus is first chunked and indexed. Chunking follows conversation turns (or observation steps) and never crosses session boundaries. Short turns are greedily merged into chunks of about 1024 characters, with the last turn carried over as overlap. Longer turns remain separate, while turns exceeding 8192 characters are split into 8192-character windows with 1024-character overlap. Each chunk is prefixed with a session date-time header.

At question time, BM25 and dense retrieval (Qwen3-Embedding-0.6B) independently return their top- k chunks. Their deduplicated union is reranked by Qwen3-Reranker-0.6B, and the top k chunks, roughly half of the candidate pool, are passed to the backbone with the shared QA prompt.

For RAG (2-round), we add a second retrieval round. The backbone checks whether the first-round chunks suffice and, if not, issues a follow-up query against the remaining pool. Chunks from both rounds are used for answering.

### S26 · Memory systems.

[原文定位](https://arxiv.org/html/2610.34073v1#A1.SS2.SSS0.Px3)

We group the memory systems as follows:

Flat store keeps memory as a flat collection (extracted facts, notes, etc.), indexed for similarity search: A-Mem (Xu et al., 2026a), SimpleMem (Liu et al., 2026b), MemOS (Li et al., 2025b).

Hier/Lifecycle manages memory across tiers that differ in lifetime or abstraction, and moves, consolidates or updates units between them over time: MemoryOS (Kang et al., 2025), LightMem (Fang et al., 2026a), and OpenViking (Volcengine, 2026).

Graph-based links memory units through explicit relations (e.g., entities, events or causal edges), and retrieval can expand along them: HippoRAG2 (Gutiérrez et al., 2025), PlugMem (Yang et al., 2026a), MAGMA (Jiang et al., 2026a).

Trained Policy learns how memory is written, updated and used through reinforcement learning rather than a hand-designed pipeline, whatever the store layout (hierarchical for Mem-T, flat for Memory-R2): Mem-T (Yue et al., 2026), Memory-R2 (Yan et al., 2026b).

For these two systems, memory construction, update and retrieval are carried out by their own policy models (Qwen3-4B for Mem-T, Qwen2.5-7B-Instruct for Memory-R2), which we keep as released, replacing only the QA model with our backbones.

Table 4: Statistics of the evaluation data. Tokens and questions per corpus are medians. ∗Due to cost, we evaluate on a subset of the released benchmark (see text for the sampling procedure).

Benchmark

#Corpus

#Q

Q/corpus

Tokens/corpus

Answer format

LongMemEval-s

500

500

1

\sim 115k

short answer

PersonaMem-v2∗

40

934

25

\sim 123k

4-way MCQ

MINT-Eval∗

60

1,557

26

\sim 139k

short answer

Multi-turn dialogue

10

690

70

\sim 370k

State tracking

10

563

50

\sim 0.2k

GitHub commits

20

154

7.5

\sim 56k

Wiki revisions

20

150

7

\sim 129k

### S27 · Performance.

[原文定位](https://arxiv.org/html/2610.34073v1#A1.SS3.SSS0.Px1)

We score answers with an LLM-as-Judge backed by Qwen3.6-27B and deliberately avoid lexical-overlap metrics such as F1 or BLEU, which are sensitive to surface form and can penalize a correct but rephrased answer.

For general QA, the judge checks the generated answer against the gold answer. For MCQ, we match the parsed option exactly and send unparsable responses to the judge.

Judge prompts are in Appendix F.2, and Table 5 reports the judge reliability against human labels.

Table 5: Reliability of the LLM-as-Judge against human judgments, measured as the fraction of items on which the judge and human labels match.

LongMemEval-s

PersonaMem-v2

MINT-Eval

Agree. (%)

95.1%

100.0%†

97.3%

†PersonaMem-v2 is MCQ, so answers are scored by the option letter alone, matching the human labels on every item.

### S28 · Cost.

[原文定位](https://arxiv.org/html/2610.34073v1#A1.SS3.SSS0.Px2)

We report the following cost metrics for every system–benchmark–backbone triple.

Token cost. All input and output LLM tokens, summed over ingestion (memory construction, maintenance, etc.) and QA (retrieval, intermediate reasoning, answering, etc.).

End-to-end wall-clock time (Equivalent single-concurrency time). Systems run with different concurrency, so we normalize each runtime, covering construction, retrieval and answering, to its single-concurrency equivalent in hours. Times under the same backbone are broadly comparable, though endpoint throughput can still fluctuate.

LLM calls. The total number of LLM calls across ingestion and QA, which, unlike wall-clock time, does not depend on endpoint load.

Memory store size. The total tokens across all stored memory units after ingestion, averaged over corpora, reflecting how much a system expands or compresses the raw corpus.

### S29 · Retrieval scope.

[原文定位](https://arxiv.org/html/2610.34073v1#A1.SS4.SSS0.Px1)

In existing comparisons of memory systems, the retrieval top- k used at QA time is usually inherited from each repository’s default configuration or aligned with that of the proposed system.

Since memory units vary widely across systems, from a single turn to a merged chunk or session summary, the same top- k can span from a few hundred to tens of thousands of tokens.

So we measure Retrieval Scope (RS), defined as the fraction of tokens in memory units seen by the LLM from retrieval through QA over the total tokens in all memory units within the system’s retrieval range. We average this ratio over questions and report it as a percentage.

Tokens are counted with the Qwen3.6-27B tokenizer.

We adjust each system’s top- k so that its RS is no lower than that of “RAG (1-round)”, while keeping RS reasonably comparable across systems.

We further clarify what counts as “the docs LLM sees” in RS. This depends on the LLM’s involvement in retrieval, which falls into three levels: no involvement, where retrieval relies entirely on embeddings, indices, or other non-LLM components. pre-retrieval involvement, where LLM rewrites query or extracts keywords but reads no retrieved units. retrieval-time involvement, where the LLM reads retrieved units, e.g., to decide whether further retrieval is needed, reformulate the query, or assess whether a unit is useful.

Only level exposes the LLM to memory units beyond the final answer prompt. RS counts all such exposure, including every unit read from retrieval through QA regardless of whether it appears in the final answer context.

Both the numerator and denominator count only content that participates in retrieval. Metadata attached to memory units, such as topic, involved people, or date, is excluded when it is not searched over.

The RS requirement has some exceptions. Some memory systems produce only a few memory units, each covering a large part of the corpus. Forcing their RS to match would leave a very small top- k , as for OpenViking, so we fix a top- k for them.

### S30 · Inference settings.

[原文定位](https://arxiv.org/html/2610.34073v1#A1.SS4.SSS0.Px2)

We use NVIDIA H20 GPUs to locally served

Qwen3.6-27B and Qwen3.5-4B, and they are decoded with temperature 0.0 and top- p 1.0 for every ingestion and QA call, with reasoning disabled. GPT-5.6 Luna (low) is accessed through the OpenAI API with the default sampling config and reasoning effort set to low.

For a fair comparison, we unify the embedding model and, where a system uses one, the reranker model across all baselines.

Unless otherwise stated, all baselines use Qwen3-Embedding-0.6B (Zhang et al., 2025b) as the embedding model and Qwen3-Reranker-0.6B (Zhang et al., 2025b) as the reranker if used in certain memory system.

### S31 · A.5 More Explanations

[原文定位](https://arxiv.org/html/2610.34073v1#A1.SS5)

GPT-5.6 luna on PersonaMem-v2.

Interestingly, on PersonaMem-v2 5.6-luna usually scores lower than Q3.6-27B for most systems, while on LongMemEval-s and MINT-Eval, it’s usually better. Our inspection suggests this gap reflects answer preference of 5.6-luna, not the ability degradation. PersonaMem-v2 often contrasts a personalized answer with an almost identical generic distractor, and 5.6-luna tends to prefer the generic option. This preference appears to interact with 5.6-luna’s tendency to avoid relying on stereotypes, health-related, or privacy-sensitive information. This pattern is specific to PersonaMem-v2, whose multiple-choice questions often reward explicit use of user preferences, unlike the other two benchmarks.

Gold Context baseline on MINT-Eval.

MINT-Eval provides author-annotated gold context for only about half of its queris, so we skip it.

### S32 · Appendix B Configuration Validation

[原文定位](https://arxiv.org/html/2610.34073v1#A2)

The main results in Section 3 show that naive RAG performs surprisingly well, outperforming many memory systems across all our three benchmarks. To further examine and validate it, we provide three complementary analyses: component-wise ablations of our RAG baseline to show its stability (B.1); a review of RAG implementations in prior memory works (B.2); and a validation of memory baseline configurations, examining our deviations from the original repositories and their impact on performance (B.3).

### S33 · B.1 Ablations on RAG Baseline

[原文定位](https://arxiv.org/html/2610.34073v1#A2.SS1)

Since naive RAG serves as the reference point for our memory tax analysis throughout the paper, we examine how sensitive it is to its design choices. The default configuration is the single-round hybrid RAG (1rd), described in Section 3.1 (details in Appendix A.2), which uses buffer-merged chunks, BM25 and dense retrieval combined and then reranked, with Qwen3-Embedding-0.6B as the embedding model and Qwen3-Reranker-0.6B as the reranker.

Table 6: Ablations of the RAG baseline on chunking method, retrieval method, embedding model and reranker. Scores are judge accuracy (%).

Method

LongMemEval-s

PersonaMem-v2

MINT-Eval

Q4B

Q27B

Q4B

Q27B

Q4B

Q27B

Chunking Method

Original (Buffer-1024)

70.2

77.6

37.2

46.8

25.8

28.6

Buffer-512

71.2

76.8

35.8

46.5

25.6

25.7

Turn-level

70.8

76.6

35.2

47.2

25.8

26.1

Streaming-chunk

68.4

69.4

35.1

46.2

25.1

24.8

Retrieval Method

Original (Hybrid)

70.2

77.6

37.2

46.8

25.8

28.6

BM25

63.4

68.2

34.4

42.7

24.4

23.3

Emb-Only

67.2

72.6

35.4

47.3

26.5

24.7

Embedding Model

Qwen3-Embedding-0.6B

70.2

77.6

37.2

46.8

25.8

28.6

all-MiniLM-L6-v2 (0.02B)

68.0

74.6

35.7

45.7

25.3

25.3

BGE-Large-en-v1.5 (0.3B)

72.2

76.6

38.0

47.4

25.9

25.2

pplx-embed-v1 (4B)

68.4

75.8

37.6

47.5

26.3

25.6

NV-Embed-v2 (8B)

69.6

78.2

37.4

49.3

25.3

25.8

Reranker

Qwen3-Reranker-0.6B

70.2

77.6

37.2

46.8

25.8

28.6

BGE-Reranker-Large (0.6B)

69.8

76.4

34.5

45.6

25.7

25.1

Jina-Reranker-v3 (0.6B)

71.4

77.6

37.3

47.4

26.7

26.3

Qwen3-Reranker-4B

70.0

77.2

35.3

46.3

26.2

26.2

We vary one component at a time while keeping the rest at the default, along these dimensions:

Chunking method:

buffer-merged chunks with a 1024-chars buffer [default],

a smaller 512-chars buffer (with long turns split into 4096-chars windows);

turn-level chunks, where each conversation turn or observation step forms its own chunk;

streaming chunks, where the history is cut into fixed 1024-chars windows with a 256-chars overlap, regardless of turn boundaries.

Retrieval method:

hybrid retrieval [default];

BM25 only;

dense embedding retrieval only (Emb-Only), both without reranking.

Embedding model (ordered by model size):

Qwen3-Embedding-0.6B [default]

all-MiniLM-L6-v2 (0.02B) (Wang et al., 2020)

BGE-Large-en-v1.5 (0.3B) (Xiao et al., 2024)

pplx-embed-v1 (4B) (Eslami et al., 2026)

NV-Embed-v2 (8B) (Lee et al., 2025).

Reranker (ordered by model size):

Qwen3-Reranker-0.6B [default]

BGE-Reranker-Large (0.6B) (Liu et al., 2025)

Jina-Reranker-v3 (0.6B) (Wang et al., 2025)

Qwen3-Reranker-4B (Zhang et al., 2025b).

All other settings, including the retrieval top- k and the answer prompt, follow the default configuration.

The full results are shown in Table 6.

Across these ablations, naive RAG remains strong under a range of configurations, suggesting that its performance is not driven by any particular component, careful tuning, or a lucky configuration. Most variants stay within a few points of the default across settings. The largest drops occur when fixed-size windows split turns (streaming-chunk) or retrieval relies solely on lexical matching (BM25), yet even these variants remain competitive with several memory systems in Table 1.

### S34 · B.2 RAG Implementation in Prior Works

[原文定位](https://arxiv.org/html/2610.34073v1#A2.SS2)

All above results also raise a natural question: given its strong performance and simplicity, has the naive RAG been largely overlooked in prior memory methods and studies?

Revisiting the papers from all of our evaluated baselines along with several other influential memory papers (Chhikara et al. (2025b), Rasmussen et al. (2025), Packer et al. (2024),

Ma et al. (2026), Zhang et al. (2026a)), we find that only three of them (excluding originally RAG system like HippoRAG2) report RAG results (LightMem, PlugMem, and Mem-T), while the others primarily compare against other existing memory systems.

Specifically, LightMem segments corpus by turn and retrieves using all-MiniLM-L6-v2 embedding without specifying retrieval budget and other settings. PlugMem also uses turn-level chunks and retrieves using NV-Embed-v2 embedding (top-10). Mem-T adopts BGE-M3 with a top-5 retrieval, without specifying its chunking strategy.

These observations suggest that the potential of naive RAG may have been underestimated and not fully realized in prior memory studies. With a widely-used standard hybrid retrieval and reranking pipeline, RAG becomes a strong baseline, highlighting the importance of adequately evaluating retrieval controls when assessing the added value of constructed memory.

### S35 · B.3 Memory Baseline Config Offset Validation

[原文定位](https://arxiv.org/html/2610.34073v1#A2.SS3)

We largely follow the official configurations of each memory baseline as closely as possible. When modifications are necessary for controlled comparison, we further examine their impact to ensure that they DO NOT artificially disadvantage the corresponding baseline.

Table 7: The effect of retrieval top- k on LME-s.

A-Mem (luna)

SimpleMem (Q27B)

PlugMem (Q27B)

Ours

84.0 ( k =15)

73.6 ( k =25)

75.8 ( k =15)

Default

73.0 ( k =5)

= Ours

63.6 ( k =30)

HippoRAG2 (Q27B)

Mem-T (Q27B)

Memory-R2 (luna)

Ours

78.2 ( k =10)

75.0 ( k =15)

79.0 ( k =50)

Default

68.2 ( k =5)

67.2 ( k =5)

79.6 ( k =30)

Table 8: Retrieval top- k : ours vs. the default setting on PersonaMem-v2.

A-Mem (Q4B)

SimpleMem (Q4B)

PlugMem (Q27B)

Ours

33.7 ( k =20)

34.7 ( k =10)

45.2 ( k =15)

Default

33.1 ( k =5)

37.5 ( k =25)

43.5 ( k =30)

HippoRAG2 (Q27B)

Mem-T (Q4B)

Memory-R2 (Q4B)

Ours

46.5 ( k =10)

32.1 ( k =10)

38.2 ( k =50)

Default

47.3 ( k =5)

31.9 ( k =5)

35.8 ( k =30)

### S36 · Shared settings.

[原文定位](https://arxiv.org/html/2610.34073v1#A2.SS3.SSS0.Px1)

For fair comparison, we standardize several evaluation components across baselines, including the QA prompt, QA backbone, judge prompt, judge backbone, and embedding model. These settings are shared by design to reduce confounding factors unrelated to the memory mechanism itself, so we do not ablate them separately for individual baselines.

### S37 · Retrieval scope.

[原文定位](https://arxiv.org/html/2610.34073v1#A2.SS3.SSS0.Px2)

We additionally adjust the retrieval top- k to control the relative retrieval scope of each system.

RS is not intended to equalize exact inference token budgets across systems, but to avoid overly restrictive retrieval caused by heterogeneous memory-unit granularity and store sizes.

Using the same top- k across systems can be misleading because memory units differ substantially in granularity and store size. For example, one system may effectively access 10% of its store while another accesses only 1%. So we tune top- k based on Retrieval Scope (Appendix A.4), ensuring that each memory baseline has a scope no lower than RAG (1rd). In practice, this adjustment mostly increases the original top- k , giving memory baselines access to more of their stored information.

Table 8 shows the effect of adjusting retrieval top- k to align retrieval scope across systems. In most cases, we increase top- k beyond the repository defaults, which generally improves performance. In the few cases where top- k must be reduced to control its retrieval scope, the resulting performance degradation is minor.

### S38 · System-specific deviations.

[原文定位](https://arxiv.org/html/2610.34073v1#A2.SS3.SSS0.Px3)

Beyond the shared settings and the retrieval scope, a few systems need individual changes:

Table 9: MemOS: retrieval post-processing and reranking.

Backbone

Setting

LME-s

PM-v2

luna

Ours (no post-proc.)

78.0

41.7

+ official post-proc.

78.0

37.8

Q27B

Ours (reranking on)

76.6

50.2

default (reranking off)

45.6

42.7

Table 10: LightMem: extraction source on LongMemEval-s (Q27B).

Setting

LME-s

User + assistant (ours)

78.8

User only (default)

70.6

(1) MemOS: we disable the retrieval post-processing of its official evaluation (relativity threshold of 0.45 and MMR), whose threshold is calibrated for its original embedding model and overly strict with ours, and enable the cosine reranking that degenerates to constant scores by default. Both changes favor MemOS (Table 10).

(2) SimpleMem: its default ingestion window of 40 utterances is set for LoCoMo and packs unrelated sessions together elsewhere, so we use 10 on all three benchmarks.

(3) LightMem: its official LongMemEval-s script uses user turns only. We compare this setting with user+assistant turns on LongMemEval-s and find the latter performs better (Table 10), so we use it across all three benchmarks.

(4) Mem-T: we stop the policy model after retrieval, before it answers at finish, and let the shared QA backbone answer.

(5) Memory-R2: we raise the output limits of both construction stages (2048 and 1024 tokens) to 4096, its training length, since the defaults truncate about 12% of the calls on LongMemEval-s and drop whole blocks of memory operations.

### S39 · C.1 Overview

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS1)

Figures 12 to 12 show the Venn plot of per-query correctness overlap with RAG (1rd) for all memory systems on the three main benchmarks.

Figure 10: Per-query correctness overlap between each memory system and RAG (1rd) on LongMemEval-s, with Qwen3.5-4B (top) and Qwen3.6-27B (bottom).

Figure 11: Per-query correctness overlap between each memory system and RAG (1rd) on PersonaMem-v2, with Qwen3.5-4B (top) and Qwen3.6-27B (bottom).

Figure 12: Per-query correctness overlap between each memory system and RAG (1rd) on MINT-Eval, with Qwen3.5-4B (top) and Qwen3.6-27B (bottom).

### S40 · Source gold context

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS2.SSS0.Px1)

Table 11 summarizes the gold evidence of the three main benchmarks. Queries without gold are excluded from all gold-based analyses.

LongMemEval-s. 479 of the 500 queries have gold turns, and the other 21 are abstention questions with no supporting turn by design.

PersonaMem-v2. 836 of the 934 queries have gold turns. The other 98 are sensitive-information queries, whose relevant snippet is in the query itself and needs no memory.

MINT-Eval. 765 of the 1,557 queries have gold steps, covering all state-tracking queries, verified version-specific questions in wiki and github, and verifiable dialog queries.

Table 11: Gold evidence in the three main benchmarks. Gold items are summed over queries.

Benchmark

#Queries

#Queries w/ gold

#Gold items

LongMemEval-s

500

479

896

PersonaMem-v2

934

836

2618

MINT-Eval

1557

765

2153

Figure 13: QA accuracy with the oracle raw context vs. oracle memory units on LongMemEval-s and PersonaMem-v2 with Qwen3.5-4B and Qwen3.6-27B, with retrieval (hatched) as reference. Right of each panel: memory tax with normal retrieval vs. with oracle memory units.

Figure 14: Query similarity comparison of gold raw turns vs. gold memory units on LongMemEval-s (top) and PersonaMem-v2 (bottom) with Qwen3.6-27B. In each pair, point-wise similarity difference (top) and overall distributions (bottom).

### S41 · Mapping Gold Raw Turns to Gold Memory Units.

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS2.SSS0.Px2)

Given the benchmark-provided gold raw turns, we map them to the corresponding units in each memory store. The mapping falls into three cases. A raw turn may correspond to a single deterministic memory unit, multiple candidate units, or no unit when the relevant information is lost during memory processing. GPT-5.6 Terra and Claude Sonnet 5 independently select relevant memory units given the query, answer, and gold raw turn, with rare disagreements resolved by human adjudication.

A-Mem, MemoryOS, HippoRAG2, and MAGMA admit deterministic one-to-one mappings, while the remaining systems require this LLM-based filtering. Table 12 reports the resulting coverage and the average number of gold memory units per gold raw turn for some memory systems. To check the LLM-based selection, we manually inspect sampled cases for some systems and label each as correct, redundant, or missing (Table 13).

Table 12: Mapping from gold raw turns to gold memory units. Coverage is the share of gold raw turns mapped to at least one memory unit, and Avg. units is the average number of gold memory units per gold raw turn.

LongMemEval-s

MAGMA

A-Mem

MemoryOS

SimpleMem

Coverage

100.0%

100.0%

99.7%

98.7%

Avg. units

1.00

1.00

0.99

1.59

LightMem

OpenViking

PlugMem

Memory-R2

Coverage

96.8%

95.5%

95.5%

92.3%

Avg. units

2.78

1.99

2.07

1.28

PersonaMem-v2

MAGMA

A-Mem

MemoryOS

SimpleMem

Coverage

100.0%

100.0%

99.9%

90.9%

Avg. units

1.00

1.00

1.00

1.43

LightMem

OpenViking

PlugMem

Memory-R2

Coverage

99.0%

52.8%

75.9%

82.6%

Avg. units

5.78

0.88

1.99

1.41

Table 13: Human spot check of LLM-selected gold memory units (%), labeled as correct, extraneous (irrelevant units are selected), or missing (relevant units left out).

Method

LongMemEval-s

PersonaMem-v2

Correct

Extraneous

Missing

Correct

Extraneous

Missing

SimpleMem

92.2

5.8

2.0

91.7

5.0

3.3

LightMem

85.0

14.2

0.8

88.5

8.2

3.3

MemOS

88.7

8.2

3.2

87.3

12.7

0.0

Memory-R2

83.3

15.8

0.8

85.9

12.5

1.6

### S42 · Oracle raw context vs. oracle memory units

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS2.SSS0.Px3)

Figure 13 extends Figure 3 to both Qwen backbones on LongMemEval-s and PersonaMem-v2. Some systems show a clear gap between oracle raw context and oracle memory units, e.g., SimpleMem, OpenViking and Memory-R2 on LongMemEval-s with Qwen3.5-4B and PlugMem on PersonaMem-v2 with Qwen3.6-27B, indicating information loss during memory processing. For MAGMA and LightMem, oracle-memory performance is close to oracle-raw performance yet much higher than their retrieval performance, suggesting that the evidence is preserved but harder to recover, which motivates the accessibility analysis.

### S43 · Human Annotation of Information Preservation.

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS2.SSS0.Px4)

For the micro-level analysis, we sample 500 raw turns from the corpus of three benchmarks and trace each to its corresponding memory unit(s), without restricting the samples to gold evidence. For one-to-many mappings, we present annotators with all corresponding memory units without LLM filtering, avoiding any model-based preselection before human judgment. Annotators compare the raw turn with the full set of memory units and label its information as fully preserved, partially missing, largely missing, or having no corresponding memory unit (Table 2). Redundant memory units are allowed as long as the raw-turn information is fully preserved.

### S44 · Overview

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS3.SSS0.Px1)

We group the retrieval mechanisms of memory systems into four types in a representative but not exhaustive way: ranking scores memory units, e.g., by embedding similarity, lexical scores or a reranker; matching selects units by keywords or metadata filters; expansion grows the retrieved set along the memory structure, e.g., via graph neighbors or personalized PageRank; and persistence always places part of the memory, such as a user profile, preferences, knowledge entries, etc. into the context. Table 14 lists the types each system uses.

Table 14: Retrieval mechanisms used by each memory system at query time.

Type

Method

Ranking

Matching

Expansion

Persistence

Flat store

A-Mem

–

–

–

SimpleMem

–

–

MemOS

–

Hier/Lifecycle

MemoryOS

–

–

LightMem

–

–

–

OpenViking

–

–

Graph-based

HippoRAG2

–

–

MAGMA

–

PlugMem

–

–

Trained Policy

Mem-T

–

–

–

Memory-R2

–

–

–

### S45 · Iterative Retrieval Replay.

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS3.SSS0.Px2)

Following the definitions of gold raw turns and gold memory units in Appendix C.2, each query has one or more gold raw turns and their corresponding gold memory units. We repeatedly run retrieval to measure how many rounds are needed to recover all gold memory units. After each round, the retrieved units are excluded from the remaining memory store before the next round. The process continues until all gold units are recovered or the round limit is reached. For most baselines, this process can be reproduced offline from the stored memory and retrieval state. While for those systems involving graph expansion or LLM-based query refinement, we need to rerun the retrieval process.

Figure 5 shows that memory systems generally recover fewer gold units in the first round than RAG.

### S46 · Similarity Drift.

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS3.SSS0.Px3)

At the micro level, we compare \mathrm{sim}(q,g_{\mathrm{raw}}) with \mathrm{sim}(q,g_{\mathrm{mem}}) for each gold raw turn and its gold memory unit(s). This analysis is only indicative, since each system retrieves within its own memory store, so absolute similarity values are not directly comparable across systems. Some memory systems also do not always rank units by embedding similarity only, so we focus on the within-system shift from raw evidence to its memory representation.

We report both point-wise changes and overall similarity distributions. For point-wise analysis, when multiple units correspond to the same raw turn, we use their median similarity to reduce the influence of extreme values.

### S47 · C.4 Memory Tax - Robustness

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS4)

Figure 15: Cross-backbone robustness of memory systems (vertical version of Figure 7). Segments are red when the drop exceeds that of RAG (grey block) and green otherwise.

For each memory system, we construct memory with each of the three backbones and answer over each resulting memory with all three as the QA model, keeping the retrieved memory units fixed whenever retrieval does not call the LLM (otherwise it is replayed with the new QA model); naive RAG builds its index without any LLM, so it only varies with the QA model. Figure 15 shows representative systems with scores annotated. Each arrow goes from the score with the stronger QA model to that with the weaker one, the grey bar behind it has the length of RAG’s drop under the same downgrade, and the dashed lines connect the same QA model across construction models.

Table 15: Score and retrieval scope (RS) of the retrieval-only baselines on each benchmark. Backbone is Qwen3.6-27B. All scores use the judge of Appendix F.2. Benchmarks are ordered by the score of RAG-Hybrid.

EverMemBench-MCQ ( k =30)

HaluMem-Medium ( k =10)

LongMemEval-s ( k =10)

LoCoMo ( k =10)

Avg Corpus Len (549k tokens)

Avg Corpus Len (164k tokens)

Avg Corpus Len (106k tokens)

Avg Corpus Len (20.4k tokens)

Method

Score

RS

Score

RS

Score

RS

Score

RS

IDF-keyword

68.2

0.40%

52.5

0.52%

46.2

2.49%

58.8

2.85%

RAG-Emb

80.9

0.50%

69.7

0.60%

72.6

1.58%

69.6

3.38%

RAG-Hybrid

82.7

0.50%

79.9

0.61%

77.6

1.96%

75.3

3.43%

Mem-Gallery ( k =5)

PersonaMem-v1 ( k =5)

ES-MemEval ( k =3)

MemoryAgentBench ( k =10)

Avg Corpus Len (27.1k tokens)

Avg Corpus Len (65.0k tokens)

Avg Corpus Len (11.7k tokens)

Avg Corpus Len (193k tokens)

Method

Score

RS

Score

RS

Score

RS

Score

RS

IDF-keyword

48.5

3.06%

57.9

0.69%

55.6

3.74%

55.5

2.42%

RAG-Emb

72.4

3.56%

69.2

0.60%

58.7

4.02%

59.4

4.04%

RAG-Hybrid

74.5

3.64%

71.1

0.61%

69.2

4.01%

64.8

4.10%

LongMemEval-m ( k =10)

WorldMemArena ( k =5)

AMA-Bench ( k =10)

KnowMe-Bench ( k =20)

Avg Corpus Len (1044k tokens)

Avg Corpus Len (25.0k tokens)

Avg Corpus Len (32.4k tokens)

Avg Corpus Len (309k tokens)

Method

Score

RS

Score

RS

Score

RS

Score

RS

IDF-keyword

41.2

0.31%

38.0

15.71%

29.0

13.42%

17.6

0.43%

RAG-Emb

54.2

0.15%

52.5

23.14%

39.4

17.84%

40.9

0.95%

RAG-Hybrid

64.4

0.20%

55.6

26.14%

48.4

17.37%

47.0

0.94%

PersonaMem-v2 ( k =10)

RealMem ( k =10)

MINT-Eval ( k =35/5/3/5)

Avg Corpus Len (123k tokens)

Avg Corpus Len (210k tokens)

Avg Corpus Len (131k tokens)

Method

Score

RS

Score

RS

Score

RS

IDF-keyword

39.5

1.47%

25.2

1.40%

20.4

6.63%

RAG-Emb

47.3

1.36%

29.3

1.08%

24.7

6.58%

RAG-Hybrid

46.8

1.48%

32.9

1.22%

28.6

6.73%

### S48 · C.5 Benchmark Headroom Further Exposes the Memory Tax

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS5)

We probe the benchmark headroom with the retrieval-only controls on a broader set of long-term memory benchmarks, listed here in order of release date (including the three benchmarks used in our main experiments): LoCoMo (Maharana et al., 2024), LongMemEval-s and LongMemEval-m (Wu et al., 2025), PersonaMem-v1 (Jiang et al., 2025a), MemoryAgentBench (Hu et al., 2025b), HaluMem-Medium (Chen et al., 2026a), PersonaMem-v2 (Jiang et al., 2025b), MINT-Eval (Lee et al., 2026), KnowMe-Bench (Wu et al., 2026a), RealMem (Bian et al., 2026), EverMemBench-MCQ (Hu et al., 2026a), AMA-Bench (Zhao et al., 2026), ES-MemEval (Chen et al., 2026e), and the multimodal benchmarks Mem-Gallery (Bei et al., 2026) and WorldMemArena (Liu et al., 2026a).

### S49 · Simple baselines.

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS5.SSS0.Px1)

We run the four naive baselines of Section 4.5. For IDF-keyword, we select for each query the two terms with the highest inverse document frequency (IDF) in the corpus and prioritize chunks containing both terms, followed by those containing either one. Within each tier, chunks are sampled uniformly at random until the top- k budget is filled.

All retrieval baselines follow the default settings of Section 3.1. Their top- k and retrieval scope are listed in Table 15.

Figure 16: Simple retrieval baselines across benchmarks with Qwen3.6-27B.

marks multimodal benchmarks.

### S50 · Evaluation protocol.

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS5.SSS0.Px2)

All predictions are judged against the reference answers with the binary LLM judge of Appendix A.3. Deviations from the official evaluation setups are summarized below.

PersonaMem-v2, MINT-Eval, WorldMemArena: To reduce evaluation cost, we sample a subset of examples while approximately preserving the original distribution of question types.

LoCoMo: Following prior works, we exclude the adversarial category (category 5, abstention) and evaluate the remaining four categories.

ES-MemEval: We evaluate only the QA task, as the other two task types do not have deterministic reference answers.

Multimodal benchmarks (Mem-Gallery, WorldMemArena): We use a text-only retrieval setting for controlled comparison. Each image is first converted into a roughly 200-token caption by a VLM (Qwen3.6-27B), after which all retrieval baselines operate on the resulting captioned history.

Table 16: Full results of experiential memory with Qwen3.5-4B: task score, tokens per task (in thousands, with the cost of building the experience library amortised over the test tasks) and average steps (dialogue turns for \tau^{2} -Bench). Best score per benchmark in bold.

Method

ALFWorld (Embodied)

WebShop (Web)

Mind2Web (Web)

SR

Avg Tokens (K)

Avg Steps

Score

Avg Tokens (K)

Avg Steps

StepSR

Avg Tokens (K)

Avg Steps

No Memory

52.2

75.9

32.1

45.9

9.4

7.3

48.5

3.2

N/A‡

Naive RAG

73.1

234.8

22.7

38.4

36.8

8.8

45.3

9.6

N/A‡

ReasoningBank

62.7

254.0

29.7

34.3

40.1

9.7

49.9

11.4

N/A‡

Memp

76.1

237.7

23.4

44.5

37.6

7.8

47.9

6.4

N/A‡

G-Memory

73.9

259.6

24.4

39.5

65.1

8.4

47.0

14.4

N/A‡

SkillPro

47.0

1226.3

38.9

42.5

297.7

8.2

43.6

62.0

N/A‡

Method

BigCodeBench (Coding)

AppWorld (Tool Use)

\tau^{2} -Bench (Tool Use)

pass@1

Avg Tokens (K)

Avg Steps

TGC

Avg Tokens (K)

Avg Steps

passˆ1

Avg Tokens (K)

Avg Steps

No Memory

16.9

0.6

1†

12.5

278.3

22.4

61.0

154.2

16.7

Naive RAG

21.6

5.2

1†

22.6

339.6

20.0

69.0

394.5

14.3

ReasoningBank

14.9

13.7

1†

14.3

383.7

22.1

51.0

381.8

15.0

Memp

20.3

8.9

1†

14.3

317.1

20.9

62.0

396.2

14.6

G-Memory

20.3

62.9

1†

22.6

388.7

21.0

78.0

424.3

13.8

SkillPro

11.5

29.3

1†

10.7

661.9

22.7

55.0

1334.3

15.5

†BigCodeBench is single-shot generation, where each task takes one model call, with no interaction with an environment. ‡Mind2Web is evaluated offline step by step on the gold trajectories, so the number of steps is fixed by the dataset, not chosen by the agent.

Figure 17: Experiential memory on agentic tasks, task score (bars, left axis) and tokens per task (diamonds, right axis). Memory baselines are green when above Naive RAG and red otherwise, with darker shades for larger relative gaps. Dashed boxes below zero show the memory tax, the score that Naive RAG obtains where the memory fails.

### S51 · Benchmark Details.

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS6.SSS1.Px1)

Experience is accumulated on the training (or dev) split and evaluated on test split, with task counts provided (experience / test).

ALFWorld (Shridhar et al., 2021): text-based household tasks (300 / 134).

WebShop (Yao et al., 2023a): searching for and buying a product on a simulated e-commerce website (1,000 / 500).

Mind2Web (Deng et al., 2023): navigation on real-world websites, tested on the cross-task, cross-website and cross-domain splits (1,009 / 1,341).

BigCodeBench (Zhuo et al., 2025): Python programming with calls to diverse libraries, tested on the Hard subset (992 / 148).

AppWorld (Trivedi et al., 2024): everyday tasks solved by writing code that calls app APIs, tested on test-normal and test-challenge (147 / 585).

\tau^{2} -Bench (Barres et al., 2025): customer service with domain policies, tools and a simulated user in the airline, retail and telecom domains (178 / 100).

### S52 · Baseline Details.

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS6.SSS1.Px2)

No Memory: the agent interacts with the environment purely in the ReAct (Yao et al., 2023b), with no memory across tasks.

Naive RAG: At the start of each task, we retrieve the top-2 previously accumulated tasks based on their description similarity to the current task and include their raw trajectories in the prompt. We use the same embedding model as in Section 3.1, Qwen3-Embedding-0.6B.

Memp (Fang et al., 2026b): distills past trajectories into procedural memory, i.e., step-by-step workflows, and retrieves those of similar tasks as guidelines.

ReasoningBank (Ouyang et al., 2026): induces generalizable reasoning strategies from both successful and failed trajectories as structured memory items, retrieved by task similarity.

G-Memory (Zhang et al., 2025a): organizes experience in a three-tier graph hierarchy of insights, queries and interaction trajectories, and retrieves both high-level insights and condensed past trajectories from it.

SkillPro (Mi et al., 2026): maintains an evolving pool of skills, from which the agent selects one to follow at each step, and the skills are refined from the feedback of the tasks.

### S53 · Implementation Details.

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS6.SSS1.Px3)

We follow the default task protocols of each benchmark consistent with prior work, including a step limit of 50 for ALFWorld, 15 for Webshop, 50 for AppWorld and 50 for \tau^{2} -Bench, while Mind2Web imposes no explicit step limit. We follow each benchmark’s official metric: success rate for ALFWorld, task score for WebShop, step success rate for Mind2Web, pass@1 for BigCodeBench, passˆ1 for \tau^{2} -Bench, and Task Goal Completion (TGC) for AppWorld, where a task succeeds only if all associated unit tests pass. Although pass@ k and passˆk differ in definition, they are equivalent when k=1 .

### S54 · Benchmark Details.

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS6.SSS2.Px1)

2 benchmarks adopted:

Context-as-Memory Test set (Yu et al., 2025). We use 60 samples from it. Starting from the first-frame input image, each sample generates four video segments in sequence that complete a revisit, e.g., with instruction of turning right by 45∘, right by 45∘, left by 45∘ and left by 45∘, which return the camera to its original position. We then compare the final frame with the original view and report PSNR, SSIM and 1 - LPIPS, all higher is better.

MemoBench (Chen et al., 2026b). A target object undergoes a physical process (e.g., dissolution), leaves the view through camera motion, and must reappear in its updated state. We test 25% of it, i.e., 90 samples.

### S55 · Baseline Details.

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS6.SSS2.Px2)

6 baselines adopted:

I3DM (Li et al., 2026) retrieves the past frames most relevant to the current viewpoint with implicit 3D-aware matching and injects them as conditioning, so its memory is the naive past frames.

WorldKV (Yi et al., 2026) keeps the key-value cache of past frames as world memory, and retrieves and compresses the cached entries for the current generation step.

ReWorld (Chen et al., 2026f) an interactive world model that carries long-horizon memory in a learned, bounded key-value memory updated as the video is generated.

MagicWorld (Li et al., 2025a) stores the visual latents of past frames and reuses them as context to keep long-horizon exploration stable.

FramePack (Zhang et al., 2026e) packs the history into a fixed-length context of visual latents, compressing older frames more aggressively, with sampling that prevents drift.

HyDRA (Chen et al., 2026d) summarizes the history into a small set of memory tokens that the generator attends to.

Table 17: Full long-horizon consistency results of world models on C-as-M-eval and MemoBench.

Method

Mem

Carrier

PSNR \uparrow

SSIM \uparrow

1 - LPIPS \uparrow

C-as-M-eval

I3DM

naive frames

19.8

.560

.704

WorldKV

raw KV

13.5

.372

.459

ReWorld

learned KV

14.1

.378

.510

MagicWorld

visual latents

13.4

.388

.341

FramePack

visual latents

9.1

.217

.312

HyDRA

mem. tokens

11.7

.320

.319

MemoBench

I3DM

naive frames

14.4

.430

.476

WorldKV

raw KV

12.6

.379

.420

ReWorld

learned KV

12.9

.387

.422

MagicWorld

visual latents

13.9

.433

.412

FramePack

visual latents

9.7

.279

.303

HyDRA

mem. tokens

11.9

.355

.326

### S56 · Implementation Details.

[原文定位](https://arxiv.org/html/2610.34073v1#A3.SS6.SSS2.Px3)

All methods run on NVIDIA H100 GPUs with 50 inference steps.

### S57 · Appendix D Case Studies

[原文定位](https://arxiv.org/html/2610.34073v1#A4)

In this section, we show some representative case studies for both Memory Benefit (D.1) and Memory Tax (

D.2

, D.3

), and also some comparison examples of benefit and tax within the same memory mechanism to directly show the dual nature of memory (D.4).

### S58 · D.1 Memory Benefit

[原文定位](https://arxiv.org/html/2610.34073v1#A4.SS1)

Even the main results show memory underperform RAG in the overall performance in many cases, memory systems can still answer some questions correctly where naive RAG fails and we still need them in such scenarios. We inspect a sample of such questions and group the wins of memory into several representative types (Figures 18 and 19):

Focused atomic extraction: each fact becomes a short unit, so the gold facts fit into the retrieved context, while RAG’s top- k is filled by long chunks that other irrelevant information, making the evidence hard to recover.

Multi-hop linking: facts from different sessions are retrieved together and combined, while for naive RAG the evidences are scattered.

Implicit preference exposure: a trait mentioned only in passing becomes an explicit unit in the memory.

Temporal anchoring: relative time expressions are anchored to absolute dates during construction.

Explicit forgetting: a forget request updates the stored state by removing or deactivating the targeted content.

Processing for heterogeneous inputs: non-dialogue inputs such as code diffs are described in natural language, making it easier to be recalled with semantic retrieval.

Figure 18: Examples of memory benefit: (a) focused atomic extraction, (b) multi-hop linking, and (c) implicit preference exposure.

Figure 19: Examples of memory benefit-2: (d) temporal anchoring, (e) explicit forgetting, and (f) processing for heterogeneous inputs.

### S59 · D.2 Memory Tax - Faithfulness

[原文定位](https://arxiv.org/html/2610.34073v1#A4.SS2)

Figures 23 to 23 show examples from the annotation in Section 4.2, with varying degrees of information loss:

No Loss.

Partial Loss.

Major Loss.

No Corresponding Memory Unit.

Figure 20: Faithfulness case studies-1.

Figure 21: Faithfulness case studies-2.

Figure 22: Faithfulness case studies-3.

Figure 23: Faithfulness case studies-4.

### S60 · D.3 Memory Tax - Accessibility

[原文定位](https://arxiv.org/html/2610.34073v1#A4.SS3)

Figure 24 shows examples from the round replay in Section 4.3. In each case the evidence is still preserved in memory, but it is returned in a later round than the raw turns. The badges give the round in which a unit is first retrieved and the maximum number of rounds for that store. We observe three recurring patterns:

Fragmenting: one raw turn is split into several units, and a unit carrying a necessary part of the evidence ranks far behind the others.

Diluting: the evidence is wrapped in unrelated or additional content, such as a long profile or an elaborated note, which weakens its match with the query.

Rephrasing: the evidence is rewritten, sometimes with a slight shift in meaning, and no longer matches the query as well as the raw wording.

Figure 24: Examples of accessibility degradation: (a) fragmenting, (b) diluting, and (c) rephrasing.

### S61 · D.4 Direct Examples for the Double-edged Memory Mechanisms

[原文定位](https://arxiv.org/html/2610.34073v1#A4.SS4)

The same structure or mechanism of a memory system can help on one question and hurt on another. Figures 25 and 26 pair, for each mechanism, a question that the memory system answers correctly while RAG (1rd) fails (memory benefit) with a question where the same mechanism makes it fail while RAG (1rd) succeeds (memory tax).

Figure 25: Direct examples of the dual nature of memory-1: the same mechanism of a memory system brings memory benefit on one question (left) and memory tax on another (right).

Figure 26: Direct examples of the dual nature of memory-2: the same mechanism of a memory system brings memory benefit on one question (left) and memory tax on another (right).

### S62 · E.1 Full Results of LongMemEval-s

[原文定位](https://arxiv.org/html/2610.34073v1#A5.SS1)

Table 18: Full results on LongMemEval-s with GPT-5.6 Luna (low) including judge accuracy (%) followed by cost metrics. Token cost is split into memory construction (Build), maintenance (Mant) and inference (Infer), and end-to-end time into offline building and online QA. LongMemEval-s consists of 500 corpora (for GPT-5.6 Luna, we use a subset of 100 as mentioned in Appendix A.1), and we report the aggregate result over all corpora, i.e., the overall benchmark-level score.

Type

Method

Acc

Retrieval

Scope

Token Cost

E2E Time

LLM

Calls (K)

Memory

Storage (K)

Build (M)

Mant (M)

Infer (M)

Offline

Building

Online

QA

GPT-5.6 Luna (low)

Retrieval-only

RAG (1rd)

82.0

1.91%

–

–

0.27

0.11h

3.4min

0.10

122.5

RAG (2rd)

90.0

2.75%

–

–

0.65

0.11h

7.7min

0.20

122.5

Flat store

A-Mem

84.0

2.28%

29.3

145.0

0.44

117.0h

3.2min

98.4

188.5

MemOS

78.0

2.20%

58.8

–

0.12

63.8h

5.8min

25.2

44.7

SimpleMem

84.0

3.23%

38.5

–

1.42

13.9h

28.5min

6.98

90.9

Hier/Lifecycle

MemoryOS

80.0

3.18%

57.6

13.4

0.86

126.5h

135.6min

104.1

153.4

LightMem

77.0

3.48%

5.22

–

0.09

15.2h

3.0min

2.67

9.67

OpenViking

63.0

6.70%

71.7

–

0.18

24.9h

5.0min

10.9

27.2

Graph-based

HippoRAG2

81.0

1.28%

79.5

–

0.46

11.6h

4.4min

118.5

119.4

MAGMA

76.0

4.38%

79.9

–

0.68

103.2h

40.1min

98.5

144.5

PlugMem

70.0

3.77%

39.3

–

0.63

39.2h

30.3min

49.6

115.6

Trained Policy

Mem-T

78.0

2.69%

51.7

180.4

4.90

76.0h

22.7min

114.2

489.1

Memory-R2

79.0

2.51%

51.9

115.6

0.23

79.4h

2.7min

35.3

89.5

Figure 27: Pareto plots on LongMemEval-s with GPT-5.6 Luna (low), accuracy vs. token cost (left) and accuracy vs. the number of LLM calls (right). Bubble size is the memory store size in tokens. LongMemEval-s consists of 500 corpora (for GPT-5.6 Luna, we use a subset of 100 as in Appendix A.1), and report per-corpus averages.

### S63 · E.2 Full Results of PersonaMem-v2

[原文定位](https://arxiv.org/html/2610.34073v1#A5.SS2)

Table 19: Full results on PersonaMem-v2 with Qwen3.6-27B including judge accuracy (%) followed by cost metrics. Token cost is split into memory construction (Build), maintenance (Mant) and inference (Infer), and end-to-end time into offline building and online QA. PersonaMem-v2 consists of 200 corpora (we use a subset of 40 as mentioned in Appendix A.1), and we report the aggregate result over all corpora, i.e., the overall benchmark-level score.

Type

Method

Acc

Retrieval

Scope

Token Cost

E2E Time

LLM

Calls (K)

Memory

Storage (K)

Build (M)

Mant (M)

Infer (M)

Offline

Building

Online

QA

Qwen3.6-27B

Retrieval-only

RAG (1rd)

46.8

1.48%

–

–

2.77

0.07h

58.3min

0.93

166.2

RAG (2rd)

48.7

2.78%

–

–

7.68

0.07h

103.7min

1.87

166.2

Flat store

A-Mem

48.4

1.68%

19.6

94.4

4.18

227.4h

40.8min

79.0

251.7

MemOS

50.2

2.29%

44.8

–

1.31

35.3h

69.9min

20.7

43.9

SimpleMem

46.7

2.24%

19.8

–

10.6

94.1h

615.7min

12.5

77.8

Hier/Lifecycle

MemoryOS

48.2

1.36%

32.3

13.1

4.48

145.7h

36.2min

84.6

169.7

LightMem

47.0

1.57%

29.8

–

3.03

35.2h

20.2min

17.3

85.7

OpenViking

38.7

19.04%

40.2

–

2.29

14.2h

14.2min

7.11

15.7

Graph-based

HippoRAG2

46.5

1.68%

24.7

–

5.12

15.3h

410.1min

38.1

125.6

MAGMA

40.5

3.50%

49.2

–

6.72

62.6h

182.8min

79.1

182.6

PlugMem

45.2

2.12%

27.9

–

6.67

29.5h

295.8min

42.8

131.5

Trained Policy

Mem-T

42.1

1.46%

35.4

161.9

61.0

59.0h

6807.9min

106.1

707.3

Memory-R2

48.4

1.98%

29.0

64.4

2.61

85.6h

21.3min

20.4

114.5

Figure 28: Pareto plots on PersonaMem-v2 with Qwen3.6-27B, accuracy vs. token cost (left) and accuracy vs. the number of LLM calls (right). Bubble size is the memory store size in tokens. PersonaMem-v2 consists of 200 corpora (we use a subset of 40 as mentioned in Appendix A.1) and report per-corpus averages..

### S64 · E.3 Full Results of MINT-Eval

[原文定位](https://arxiv.org/html/2610.34073v1#A5.SS3)

Table 20: Full results on MINT-Eval with Qwen3.5-4B including judge accuracy (%) followed by cost metrics. Token cost is split into memory construction (Build), maintenance (Mant) and inference (Infer), and end-to-end time into offline building and online QA. MINT-Eval consists of 595 corpora (we use a subset of 60 as mentioned in Appendix A.1), and we report the aggregate result over all corpora, i.e., the overall benchmark-level score.

Type

Method

Acc

Retrieval

Scope

Token Cost

E2E Time

LLM

Calls (K)

Memory

Storage (K)

Build (M)

Mant (M)

Infer (M)

Offline

Building

Online

QA

Qwen3.5-4B

Retrieval-only

RAG (1rd)

25.8

6.73%

–

–

7.65

0.10h

68.9min

1.56

186.5

RAG (2rd)

26.1

11.93%

–

–

19.0

0.10h

158.2min

3.11

186.5

Flat store

A-Mem

24.4

6.68%

25.0

137.4

7.42

44.4h

50.9min

85.9

244.1

MemOS

18.0

13.93%

54.4

–

1.27

11.2h

42.3min

23.0

41.3

SimpleMem

18.6

4.96%

34.0

–

27.7

23.8h

191.6min

18.0

68.9

Hier/Lifecycle

MemoryOS

19.0

31.87%

45.7

27.2

7.65

18.3h

139.3min

82.3

296.4

LightMem

20.8

25.50%

93.0

–

2.03

53.5h

18.7min

67.8

82.8

OpenViking

10.2

24.95%

110.2

–

12.3

17.5h

23.6min

14.5

39.6

Graph-based

HippoRAG2

24.6

6.43%

52.0

–

7.62

11.8h

385.2min

62.5

150.6

MAGMA

23.7

23.31%

68.3

–

12.7

33.1h

206.1min

85.6

200.4

PlugMem

21.5

5.93%

38.5

–

9.17

11.7h

217.6min

46.6

204.8

Trained Policy

Mem-T

27.0

9.51%

54.0

199.2

86.6

87.0h

717.2min

118.2

1202.9

Memory-R2

21.3

30.01%

34.0

65.1

2.34

68.4h

17.8min

20.9

66.9

Figure 29: Pareto plots on MINT-Eval with Qwen3.5-4B, accuracy vs. token cost (left) and accuracy vs. the number of LLM calls (right). Bubble size is the memory store size in tokens. MINT-Eval consists of 595 corpora (we use a subset of 60 as mentioned in Appendix A.1), and report per-corpus averages.

### S65 · F.1 QA Prompts

[原文定位](https://arxiv.org/html/2610.34073v1#A6.SS1)

Table 21: QA prompt for general (open-ended) questions. The user-profile section

is omitted when no profile is available for this memory system.

Table 22: QA prompt for fully open-ended preference questions (e.g., the single-session-preference

questions of LongMemEval), which have no single reference answer. Compared with Table F.1,

the rule on unavailable information is dropped and the answer is asked to take the user’s preferences into account.

Table 23: QA prompt for multiple-choice questions. The user-profile section

is omitted when no profile is available.

### S66 · F.2 LLM-as-Judge Prompts

[原文定位](https://arxiv.org/html/2610.34073v1#A6.SS2)

Table 24: General LLM-as-Judge prompt for short-answer

questions.

Table 25: LLM-as-Judge prompt for LongMemEval

single-session-preference questions.

Table 26: LLM-as-Judge fallback prompt for PersonaMem-v2

multiple-choice responses that cannot be parsed into an option letter.
