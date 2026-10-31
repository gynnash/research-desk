---
schema_version: 1
kind: original_snapshot
title: 'MemCut: Every Secret Leaves a Trail in the Long-Term Memory of LLM Agents'
source_id: paper-e43add5a-50b1-432f-ae70-e351c43a7a8c
source: arXiv
authors:
- Zhang, Cheng
- Cao, Xuanning
- Zheng, Zhicheng
- Xiong, Hui
published_at: '2026-10-15'
source_version: v1
topics:
- agent-memory
source_url: https://arxiv.org/abs/2610.21405v1
captured_at: '2026-10-31T10:07:15.542927+00:00'
content_sha256: 4e0bb1183485f44331791fd4815beacddb516c99225bcd59198c4b2a794f3c95
coverage: full_text
research_coverage: full_text
---

# MemCut: Every Secret Leaves a Trail in the Long-Term Memory of LLM Agents

> TEST：原文抽取归档，用于阅读及重放，不代表正式研究结论。

- [打开来源原文](https://arxiv.org/abs/2610.21405v1)。
- 原文归档保存完整可用抽取文本；绑定的模型材料范围为 `full_text`，可小于本归档。
- 归档自身不表示已经执行研究或审阅；实际执行与审阅状态以对应研究回执为准。
- 不保存可执行网页、PDF 版式或图片，不保证公式和图表的抽取完整性，未复现实验。
- 抽取方式：`html`；抽取范围：`full_text`。
- 抽取限制：Text extraction does not verify figures, layout, or faithful mathematical rendering.
- 取材：html / success / extracted。

## 获取记录

- [text/html](https://arxiv.org/abs/2610.21405v1)；响应 SHA-256：`6db72f6e22790ac520d3815d2e5d8402d721bd8f2e040932a4412a7510954004`；抓取时间：2026-10-31T09:57:53.586291+00:00。
- [text/html](https://arxiv.org/html/2610.21405v1)；响应 SHA-256：`4cd8599795887b5e4e6bb57c79c53a73dc97745a674dd56751f19834e0786843`；抓取时间：2026-10-31T09:57:56.775460+00:00。

## 抽取正文

### S1 · MemCut : Every Secret Leaves a Trail in the Long-Term Memory of LLM Agents

[原文定位](https://arxiv.org/html/2610.21405v1)

Cheng Zhang

Affiliation: The Hong Kong University of Science and Technology (Guangzhou)

Email: chengzhang0525@gmail.com

Xuanning Cao

Affiliation: University of Science and Technology of China

Email: xionghui@ust.hk

Zhicheng Zheng

Affiliation: The Hong Kong University of Science and Technology (Guangzhou)

Hui Xiong

Affiliation: The Hong Kong University of Science and Technology (Guangzhou)

Affiliation: The Hong Kong University of Science and Technology

### S2 · Abstract

[原文定位](https://arxiv.org/html/2610.21405v1#abstract1)

Long-term memory has become a crucial component of large language model (LLM) agents, with most research focusing on retrieving relevant information accurately and efficiently. However, a dependable memory system must also forget sensitive user data upon request. To evaluate this capability, we introduce MemCut, a systematic benchmark for user-requested forgetting. Its 456 hand-designed secrets in long-horizon conversations have fully annotated evidence trails to test recovery after deletion, including from messages that never state the secrets directly. We propose two recovery metrics. Native recovery measures reader success through the system’s retrieval, whereas residual recovery measures the same reader’s success when directly given surviving objects traced to annotated disclosures or evidence. We establish three reference deletion baselines to test how far existing retrievers and write models support forgetting across five memory designs and four LLMs. Disclosure removal reduces native recovery far more than residual recovery. LLM-guided deletion of ten additional turns from twenty retrieval candidates leaves 39–76% residual recovery. Subset sweeps (144 facts, three systems, two models) show that widening the pool at a fixed budget reduces residual recovery more than deleting all original candidates. These sweeps identify candidate coverage as a bottleneck in the reference baselines.

### S3 · 1 Introduction

[原文定位](https://arxiv.org/html/2610.21405v1#S1)

Long-term memory is becoming an important part of LLM agents (Packer et al., 2023; Zhong et al., 2024; Chhikara et al., 2025), and most research has focused on retrieving the right memories quickly and accurately (Maharana et al., 2024; Wu et al., 2025). However, dependable memory should also forget sensitive information, such as a diagnosis or a confidential deal, when users ask. This ability has received much less attention than recall.

Figure 1: The message that directly discloses the secret is deleted, but the secret remains recoverable from the surviving trail. The assistant can no longer answer a colleague, while ordinary messages that never state the secret still reveal it when combined.

Benchmark

Probe

Human

design

LLM-

free

All

checked

LoCoMo

–

✗

✗

✓

LongMemEval-S

latest value

\LEFTcircle

✗

✓

MemoryAgentBench

latest value

✗

\LEFTcircle

✗

Memora

obsolete reuse

\LEFTcircle

✗

\LEFTcircle

ForgetEval

direct recall

\LEFTcircle

\LEFTcircle

\LEFTcircle

MemLeak

correlated cues

✗

✗

✗

TOFU

direct QA

✗

✗

✗

MemCut (ours)

derivability

✓

✓

✓

Table 1: Data construction in benchmarks for long-term memory, forgetting, and unlearning. Probe: test after forgetting. Human design: facts designed by people. LLM-free: no fact invented by an LLM, which may only phrase text. All checked: every item checked by people. \LEFTcircle partly.

To evaluate this capability, we introduce MemCut, a benchmark for user-requested forgetting in long-term agent memory. It tests whether a protected fact remains recoverable after deletion and helps diagnose why deletion succeeds or fails.

A user may ask an assistant to forget a secret they shared, and the GDPR recognizes a right to erasure (European Parliament and Council of the European

Union, 2016). Removing the disclosing record deletes the explicit statement, but ordinary records that never state the secret can still reveal it together. Figure 1 gives an example. A sufficient cut must break every supporting evidence combination without necessarily removing every related record.

An assistant’s failure to answer does not establish successful forgetting. Its retriever may miss surviving evidence that another query or retriever can expose. We therefore propose two recovery metrics. Native recovery measures reader success through the system’s own retrieval. Residual recovery measures the same reader’s success when directly given all surviving memory objects traced to annotated disclosures or evidence. Dividing their gap by residual recovery gives the hidden-risk share, a lower bound on the share of residual successes missed by native retrieval.

MemCut contains 456 hand-designed secrets in long-horizon conversations. For each secret, we annotate the deletion request, disclosure, evidence in other records, and look-alike records that do not support it. We also mark the minimal evidence combinations that imply the secret. These annotations support recovery measurement and analysis of surviving evidence.

We ask how far existing memory components support user-requested forgetting and what limits their effectiveness. We evaluate five memory designs and four LLMs using three reference deletion baselines that reuse native retrievers and write models. Subset sweeps separate candidate-coverage bottlenecks from selection failures.

Our contributions are as follows.

•

MemCut, a benchmark for user-requested forgetting in long-term agent memory, with 456 hand-designed secrets and fully annotated evidence trails.

•

Two recovery metrics and a hidden-risk share separating native retrieval from reader recovery given surviving evidence.

•

Experiments across five memory designs and four models evaluating forgetting, with subset sweeps identifying candidate coverage as a bottleneck in the reference deletion baselines.

### S4 · 2 Related Work

[原文定位](https://arxiv.org/html/2610.21405v1#S2)

Figure 2: One MemCut sample, abridged. Top: weeks of ordinary conversation hold one disclosure (D), evidence that never states the fact (E1–E3), and look-alike records (L1–L4). Bottom: deletion removes the disclosure and the look-alikes that resemble it. Retrieval misses an evidence turn, so the system cannot answer. However, the stored evidence (E1–E3) together still gives the answer.

### S5 · Long-term memory and recall.

[原文定位](https://arxiv.org/html/2610.21405v1#S2.SS0.SSS0.Px1)

Long-term memory helps LLM agents reuse information across interactions (Zhong et al., 2024; Chhikara et al., 2025; Zhang et al., 2024; Zhu et al., 2026). Most work focuses on accurate and efficient recall (Maharana et al., 2024; Wu et al., 2025). However, similarity-based retrieval may miss evidence linked through entities rather than similar wording, as in multi-hop QA (Yang et al., 2018; Trivedi et al., 2022). These omissions can also limit cleanup when retrieval supplies deletion candidates (§6.1).

### S6 · Forgetting and unlearning.

[原文定位](https://arxiv.org/html/2610.21405v1#S2.SS0.SSS0.Px2)

Memory must also forget sensitive information. Parametric unlearning and model editing target information in model weights, where an edited fact’s consequences can persist (Bourtoule et al., 2021; Cohen et al., 2024). In external memory, benchmarks test updated information, reuse of obsolete facts, or direct recall after deletion (Hu et al., 2026; Uddin et al., 2026; Yang, 2026). MemLeak also examines recovery through correlated cues (Wang and Zhang, 2026). MemCut tests whether surviving records jointly reveal a secret that none states directly. We annotate every minimal supporting combination. Table 1 compares these benchmarks.

### S7 · 3.1 Task definition

[原文定位](https://arxiv.org/html/2610.21405v1#S3.SS1)

We define a secret in MemCut as a protected fact, and we call its trail the fact’s evidence, which consists of the turns that support it without stating it.

Each sample pairs one protected fact with an episode, which is a long multi-session conversation stored as objects traceable to their source turns. Figure 2 shows one sample.

We also annotate its disclosure (turns stating it), its sufficient sets (minimal evidence combinations implying it, since the fact can be derived in many ways), and its distractors (look-alike turns that resemble the evidence).

Writing D for the disclosure, E for the evidence, and \mathcal{S} for the sufficient sets, a deletion X forgets the fact when

D\subseteq X\quad\text{and}\quad X\cap S\neq\emptyset\;\text{ for every }S\in\mathcal{S}.

A set of evidence turns that meets every sufficient set is a cut, and the minimal cut is the smallest one.

The task has two sides. A deleter receives a natural-language deletion request and removes objects from the store, and we then test whether the fact is still recoverable with a four-choice question that allows the model to decline.

### S8 · 3.2 Two recovery metrics

[原文定位](https://arxiv.org/html/2610.21405v1#S3.SS2)

We design two metrics to measure whether a deleted fact is still recoverable. Native recovery asks the fact’s question through the system’s own retrieval, so it measures what the assistant still brings up. Residual recovery skips retrieval and gives the model every surviving object derived from the fact’s evidence or disclosure, so it measures what the memory still supports. It estimates what the chosen reader can recover from these objects, providing a reference for native recovery.

The pair rests on three design choices. First, the same model answers both, holding the reader fixed. Second, cleanup and native recovery query the same retriever with the request and question, respectively. Third, deleting a turn removes every object derived from it (closure), so residual recovery sees only what the deleter kept. We call the gap between the two, as a share of residual recovery, the hidden-risk share,

\mathrm{Hid.}=\frac{\mathrm{Res}-\mathrm{Nat}}{\mathrm{Res}},

and Appendix B.1 shows that it is a conservative estimate of the share of residual successes that native recovery misses.

### S9 · 3.3 Construction and properties

[原文定位](https://arxiv.org/html/2610.21405v1#S3.SS3)

What each recovery metric needs

MemCut

Evidence is dispersed and redundant

sessions spanned by a fact’s evidence

8.0

evidence turns in the disclosure’s session

1.8%

minimal sufficient sets per fact

15.7

Evidence is harmless alone and complete

recovered from the best single evidence turn

0%

facts recoverable from combined evidence

96–99%

recovered with evidence and disclosure removed

0%

Recovery is not guessable

facts answered without memory

0%

targeted distractors per fact

26.6

Budget is sufficient

minimal cut size in turns (mean / max)

3.0 / 5

extra deletions allowed in cleanup

10

Built by hand, annotation is reliable

facts designed by the authors

456 / 456

author time per episode

\geq 12 h

two-annotator initial agreement

97.6%

minimal cuts verified by two algorithms

456 / 456

Table 2: Measurement guarantees of MemCut: conditions that make the recovery metrics interpretable, and the values that establish them (Qwen3.8-Flash as the reader).

MemCut uses author-specified evidence structures to measure post-deletion derivability. Each secret comes with annotated evidence and minimal sufficient sets, so deletion can be checked against every annotated derivation. The evidence trail is designed to support the secret independently of its disclosure. Table 2 summarizes the structural properties and validation results supporting these measurements. Appendix

efapp:data gives further statistics.

### S10 · Human design, model phrasing.

[原文定位](https://arxiv.org/html/2610.21405v1#S3.SS3.SSS0.Px1)

We design each episode’s disclosures, evidence, sufficient sets, and distractors. GPT-6 renders this specified content as dialogue. Authors check every turn against the design and revise deviations, spending at least twelve hours per episode.

### S11 · Long-horizon scenarios with something to lose.

[原文定位](https://arxiv.org/html/2610.21405v1#S3.SS3.SSS0.Px2)

Deletion gets harder as a fact is buried in more unrelated activity, and it matters more when a leak would hurt someone. So each of our fifteen episodes follows one scenario across work, family, and social threads for one to three months (2,893 turns on average) and protects about thirty facts with a reason to stay private, 456 in all.

### S12 · Four typical ways to derive a fact.

[原文定位](https://arxiv.org/html/2610.21405v1#S3.SS3.SSS0.Px3)

We cover the four most typical ways in which ordinary records yield an unstated fact, and each type challenges a deleter differently.

•

Fact assembly: records about one entity are joined, and they share the request’s entities and wording.

•

Relation chain: records about different entities are linked, and they share the request’s entities but not its wording, as when a contract names a firm, a filing names its owner, and dinner records name the owner’s spouse.

•

Aggregation: values are combined, and the derivation breaks when any value is deleted.

•

Temporal and state reasoning: records are ordered in time, and a question repeats their time cues.

The types have comparable fact, evidence, and distractor counts but differ in how evidence connects to the request (Table 5).

### S13 · Dispersed, redundant, and individually harmless evidence.

[原文定位](https://arxiv.org/html/2610.21405v1#S3.SS3.SSS0.Px4)

Evidence stored in the same object as its disclosure can be deleted with it, so we write evidence as the ordinary business around a fact, such as a booking, a filing, or a dinner. This evidence is spread over eight sessions on average and rarely appears in the disclosure’s session, and about two dozen distractors per fact keep a deleter from finding it by topic alone. Because a single derivation chain would make forgetting look easy, each fact’s eight evidence turns form sixteen minimal sufficient sets on average (7,148 in all), and a deleter has to break all of them.

### S14 · Questions that test memory, not guessing.

[原文定位](https://arxiv.org/html/2610.21405v1#S3.SS3.SSS0.Px5)

To ensure that a fact counts as recovered only when memory gives the answer, wrong options differ from the answer in one detail, the model may decline, and the model has to answer correctly under both option orders.

Overall

Fact assembly

Relation chain

Aggregation

Temporal state

Model

Nat.

Res.

Hid.

Nat.

Res.

Nat.

Res.

Nat.

Res.

Nat.

Res.

Turn RAG

DeepSeek

S0

59.9

98.2

39.1

68.7

100.0

18.4

99.1

75.4

94.7

77.0

99.1

S1

22.6

60.1

62.4

30.4

74.8

15.8

79.8

14.9

31.6

29.2

54.0

S2

10.3

44.3

76.7

20.0

55.7

11.4

72.8

2.6

16.7

7.1

31.9

Qwen

S0

56.6

97.8

42.2

60.9

100.0

24.6

100.0

45.6

91.2

95.6

100.0

S1

19.1

58.6

67.4

22.6

46.1

7.9

74.6

22.8

38.6

23.0

75.2

S2

7.5

41.4

82.0

12.2

28.7

4.4

71.9

0.9

0.9

12.4

64.6

GLM

S0

59.9

98.9

39.5

66.1

100.0

15.8

99.1

80.7

96.5

77.0

100.0

S1

21.1

61.2

65.6

29.6

68.7

12.3

77.2

14.0

38.6

28.3

60.2

S2

9.4

43.9

78.5

11.3

49.6

4.4

66.7

5.3

18.4

16.8

40.7

MiMo

S0

59.0

96.3

38.7

73.0

100.0

19.3

98.2

68.4

86.8

75.2

100.0

S1

22.6

62.3

63.7

34.8

73.9

11.4

79.8

10.5

33.3

33.6

61.9

S2

10.7

45.6

76.4

18.3

56.5

7.0

70.2

2.6

14.0

15.0

41.6

Session RAG

DeepSeek

S0

24.3

98.7

75.3

30.4

100.0

5.3

100.0

11.4

94.7

50.4

100.0

S1

16.0

71.5

77.6

16.5

64.3

6.1

88.6

2.6

50.0

38.9

83.2

S2

9.9

56.8

82.6

16.5

55.7

6.1

86.0

0.0

16.7

16.8

69.0

Qwen

S0

19.7

97.4

79.7

28.7

100.0

0.0

99.1

14.0

90.4

36.3

100.0

S1

16.0

73.2

78.1

28.7

64.3

7.0

86.0

7.0

64.0

21.2

78.8

S2

10.7

64.3

83.3

21.7

64.3

7.0

86.0

0.0

28.1

14.2

78.8

GLM

S0

17.3

98.7

82.4

16.5

100.0

2.6

100.0

16.7

94.7

33.6

100.0

S1

11.2

70.8

84.2

11.3

55.7

6.1

88.6

5.3

58.8

22.1

80.5

S2

4.2

54.2

92.3

0.0

50.4

5.3

78.1

0.0

24.6

11.5

63.7

MiMo

S0

28.5

98.2

71.0

40.0

100.0

3.5

100.0

14.0

93.0

56.6

100.0

S1

10.3

74.1

86.1

13.9

67.8

3.5

89.5

3.5

56.1

20.4

83.2

S2

8.6

58.6

85.4

20.9

53.0

0.0

81.6

3.5

29.8

9.7

69.9

Table 3: Recovery (%) after deletion in the two retrieval stores under their respective retrieval settings; all 456 facts. Nat.: through the system’s own retrieval. Res. (shaded by value): from the surviving evidence-derived memory. Hid.: hidden-risk share, (\mathrm{Res}-\mathrm{Nat})/\mathrm{Res} . S0 deletes the disclosure; S1 and S2 delete ten more turns.

Overall

Fact assembly

Relation chain

Aggregation

Temporal state

Model

Nat.

Res.

Hid.

Nat.

Res.

Nat.

Res.

Nat.

Res.

Nat.

Res.

MemoryBank

DeepSeek

S0

40.1

93.0

56.8

53.0

100.0

7.0

95.6

45.6

79.8

54.9

96.5

S1

23.0

80.9

71.5

32.2

92.2

5.3

88.6

20.2

58.8

34.5

84.1

S2

15.8

71.7

78.0

23.5

84.3

6.1

86.8

7.0

37.7

26.5

77.9

Qwen

S0

41.9

95.8

56.3

53.9

97.4

7.9

96.5

50.9

89.5

54.9

100.0

S1

21.7

80.5

73.0

28.7

88.7

5.3

92.1

17.5

57.9

35.4

83.2

S2

13.4

72.6

81.6

19.1

83.5

4.4

84.2

7.9

50.9

22.1

71.7

GLM

S0

44.1

99.3

55.6

53.0

100.0

7.9

98.2

58.8

99.1

56.6

100.0

S1

22.6

86.2

73.8

25.2

91.3

7.0

92.1

26.3

75.4

31.9

85.8

S2

13.8

76.3

81.9

20.0

82.6

6.1

85.1

7.9

57.0

21.2

80.5

MiMo

S0

42.3

93.6

54.8

56.5

100.0

5.3

97.4

47.4

78.9

60.2

98.2

S1

24.1

84.0

71.3

36.5

98.3

7.9

93.0

14.0

57.9

38.1

86.7

S2

16.7

76.1

78.1

26.1

89.6

6.1

88.6

6.1

47.4

28.3

78.8

Nemori

DeepSeek

S0

59.4

85.1

30.2

81.7

97.4

17.5

89.5

59.6

58.8

78.8

94.7

S1

41.7

67.1

37.9

65.2

84.3

18.4

73.7

21.1

32.5

61.9

77.9

S2

30.0

52.4

42.7

50.4

63.5

11.4

60.5

14.9

21.1

43.4

64.6

Qwen

S0

53.3

91.7

41.9

75.7

99.1

13.2

90.4

54.4

81.6

69.9

95.6

S1

32.7

68.6

52.4

54.8

83.5

8.8

78.1

21.9

38.6

45.1

74.3

S2

25.2

57.2

55.9

45.2

67.0

9.6

64.9

15.8

30.7

30.1

66.4

GLM

S0

64.9

93.9

30.8

79.1

94.8

17.5

88.6

84.2

92.1

78.8

100.0

S1

44.3

65.4

32.2

58.3

65.2

19.3

71.1

40.4

51.8

59.3

73.5

S2

33.1

55.7

40.6

38.3

50.4

21.1

61.4

28.9

42.1

44.2

69.0

MiMo

S0

62.1

93.4

33.6

84.3

100.0

17.5

100.0

58.8

73.7

87.6

100.0

S1

37.3

66.0

43.5

60.0

73.0

14.0

86.0

20.2

31.6

54.9

73.5

S2

28.9

55.5

47.8

50.4

60.0

7.0

75.4

9.6

19.3

48.7

67.3

LightMem

DeepSeek

S0

66.0

88.8

25.7

93.0

99.1

27.2

93.9

55.3

64.0

88.5

98.2

S1

34.6

55.0

37.1

53.9

62.6

22.8

77.2

12.3

20.2

49.6

60.2

S2

23.0

41.9

45.0

40.0

51.3

15.8

70.2

6.1

6.1

30.1

39.8

Qwen

S0

62.9

90.4

30.3

89.6

100.0

23.7

94.7

55.3

67.5

83.2

99.1

S1

26.1

47.6

45.2

48.7

58.3

11.4

67.5

5.3

12.3

38.9

52.2

S2

19.5

39.3

50.3

35.7

47.0

7.0

57.0

4.4

7.9

31.0

45.1

GLM

S0

77.2

93.9

17.8

93.0

97.4

38.6

97.4

81.6

80.7

95.6

100.0

S1

37.3

57.9

35.6

48.7

67.0

19.3

82.5

21.9

21.9

59.3

60.2

S2

23.2

42.1

44.8

33.0

42.6

14.0

68.4

11.4

14.9

34.5

42.5

MiMo

S0

68.2

92.3

26.1

100.0

100.0

29.8

95.6

51.8

78.1

91.2

95.6

S1

31.8

49.6

35.8

63.5

63.5

7.9

69.3

12.3

17.5

43.4

47.8

S2

21.9

43.0

49.0

45.2

50.4

12.3

64.9

0.0

4.4

30.1

52.2

Table 4: Recovery (%) after deletion in the three memory systems, as in Table 3; all 456 facts.

### S15 · Checking the design.

[原文定位](https://arxiv.org/html/2610.21405v1#S3.SS3.SSS0.Px6)

We check the dialogue with Qwen3.8-Flash as an independent reader. Recovery is 96–99% from combined evidence and 0% in three controls: the best single evidence turn, the episode after removing annotated evidence and disclosure, and the question and options alone. Two annotators audit 120 stratified facts. Two algorithms verify minimal cuts against the annotated sufficient sets for all 456 facts.

### S16 · 4.1 Reference deletion baselines

[原文定位](https://arxiv.org/html/2610.21405v1#S4.SS1)

We establish three reference deletion baselines to benchmark forgetting with existing recall components. They reuse native retrievers and write models with minimal adaptation.

S0 deletes the disclosure and all objects derived from it, providing a common baseline for disclosure removal.

S1 adds retrieval-ranked cleanup. For a request q , S1 constructs a twenty-turn candidate pool P_{q} from one query to the system’s retrieval and deletes its ten highest-ranked turns. No fact has more than ten evidence turns, and a minimal cut needs at most five. The budget therefore suffices if supporting evidence is reached and selected.

S2 reranks the same twenty candidates with the write model using their stored text and deletes the top ten (LLM-guided cleanup). The fixed pool isolates selection. Choice failures leave evidence unselected within the pool. Reach failures leave evidence outside it. Neither cleanup sees annotations. Section 6.1 varies pool and budget. At fixed cleanup budgets, the fraction of non-evidence selections provides a source-level reference measure of collateral damage (Appendix B.3).

### S17 · 4.2 One unit for every system

[原文定位](https://arxiv.org/html/2610.21405v1#S4.SS2)

Systems store different objects, so deleting one object removes a turn in one system but a whole session in another, and object counts are not comparable. However, every object derives from turns, so we anchor every operation to the turn. We record each object’s source turns at ingestion, delete by closure, and count pools and budgets in turns, so systems differ only in what they store and how they retrieve. Because the protocol needs only that a system can list, search, delete, and snapshot its objects, it extends to other designs, and we release its harness.

### S18 · 4.3 Memory systems and models

[原文定位](https://arxiv.org/html/2610.21405v1#S4.SS3)

We compare five memory designs along two properties, the unit retrieved and how much is derived (§6.2). Two retrieval stores keep every turn verbatim, retrieve by dense similarity (Karpukhin et al., 2020; Lewis et al., 2020), and derive nothing. They retrieve turns (Turn RAG) or sessions (Session RAG), letting us examine granularity under their respective retrieval settings. Three memory systems add derivation of increasing strength. MemoryBank keeps raw turns under daily summaries (Zhong et al., 2024), Nemori rewrites topical segments into narratives (Ma et al., 2025), and LightMem consolidates summaries offline without the raw text (Fang et al., 2025). Each system keeps its own retrieval. The verbatim stores test whether residual recovery can persist without summarization or rewriting.

In each configuration, one write model writes memory, scores deletion candidates, and answers questions, as in a deployed assistant. We use four write models from four developers, DeepSeek-V4.1-Flash, Qwen3.8-Flash, GLM-5.3-Flash, and MiMo-V2.5, which perform strongly and are efficient enough for thousands of deletion runs, and we run every system with each of them to separate the effects of the memory design from those of the model. Each fact is evaluated on a fresh copy of the store, so deleting one fact cannot affect another.

### S19 · 5 Results: Deleting Is Not Forgetting

[原文定位](https://arxiv.org/html/2610.21405v1#S5)

Tables 3 and 4 give the main results. Table 7 reports that residual recovery is 94–100% in every store before deletion, limiting the contribution of ingestion loss to post-deletion recovery. Within each system, residual recovery after S2 varies by at most about five points across the four write models, ten for Session RAG. We report ranges over the four and focus on patterns that recur across them.

### S20 · 5.1 Disclosure deletion mainly reduces visibility

[原文定位](https://arxiv.org/html/2610.21405v1#S5.SS1)

Figure 3: Why cleanup fails. (a, b) Residual recovery as the candidate pool widens (budget ten) and as the budget grows (pool twenty); dashed vertical lines mark the main setting. Solid lines: LLM-guided cleanup (S2); dashed: retrieval-ranked cleanup (S1); each line is the mean of DeepSeek and Qwen, with a band for their range, on the 144 facts of EP01–05 (Appendix B.3). (c) Native recovery after S0 against residual recovery after cleanup, per type and system; dark marks are means over the four write models, light marks are single models. (d) Hidden-risk share after cleanup by type, systems ordered by derivation strength.

Disclosure deletion (S0) initially appears effective. Native recovery drops by 12–50 points, in Turn RAG from 91–95% to 57–60%, so the assistant answers fewer questions correctly. Residual recovery nevertheless stays at 85–99%. Only 1.8% of the evidence shares a session with the disclosure, reflecting its wide dispersion. S0 also removes disclosure-derived objects by closure, but most indirect evidence remains.

### S21 · 5.2 Retrieval-based cleanup leaves substantial residual recovery

[原文定位](https://arxiv.org/html/2610.21405v1#S5.SS2)

After S1, residual recovery remains at 48–86%, although ten deletions could remove every annotated evidence turn of any fact. Turn RAG stores raw turns and derives nothing, ruling out survival through summaries, but its residual recovery remains at 59–62%. These outcomes motivate testing whether supporting evidence lies outside the candidate pool or remains unselected within it.

S2 asks an LLM to choose among the same twenty candidates, allowing it to select evidence ranked below the top ten. It lowers residual recovery by another 7–17 points, to 39–76%. This improvement shows that selection matters, but the remaining recovery may reflect incomplete coverage or imperfect selection. Section 6.1 tests these explanations by varying the pool and budget.

### S22 · 5.3 Deletion increases the hidden-risk share

[原文定位](https://arxiv.org/html/2610.21405v1#S5.SS3)

Deletion increases the reported share of residual recovery missed by native retrieval. In Turn RAG the hidden-risk share goes from 5–9% before deletion to 39–42% after S0 and 76–82% after S2, and across all 20 configurations it ends above where it started, above one half in 14 of them, as the Hid. columns of Tables 3 and 4 show.

Cleanup targets records retrieved by the deletion request, whereas question answering uses a different query. Evidence that is difficult to retrieve may survive cleanup and remain unseen during later questions. Native answers can therefore suggest successful forgetting even when the same reader still recovers the secret from surviving evidence.

### S23 · 6 Analysis: Why Forgetting Fails

[原文定位](https://arxiv.org/html/2610.21405v1#S6)

Figure 4: A relation-chain fact under LLM-guided cleanup (Turn RAG, S2). (a) Recovery needs one evidence turn per link, so emptying any link makes it underivable. (b) Similarity ranks of evidence and disclosure (#7, deleted by S0), and what S2 deletes (struck through) from pools of 20, 30, and 50; E2 enters at 30 but is kept (circled).

To identify bottlenecks in forgetting with existing components, we examine candidate coverage, memory design, and fact type.

### S24 · 6.1 Budget, choice, and reach

[原文定位](https://arxiv.org/html/2610.21405v1#S6.SS1)

Cleanup leaves a great deal behind, and there are three candidate explanations: the budget may be too small, the evidence may enter the candidate pool but not be chosen, or the evidence may never enter the pool at all. These are the budget, choice, and reach of §4.1. They respond differently when the pool and the budget change, so Figure 3a–b varies each with the other held at the main setting.

### S25 · Budget.

[原文定位](https://arxiv.org/html/2610.21405v1#S6.SS1.SSS0.Px1)

For S2, gains diminish beyond ten deletions, and deleting the entire pool of twenty still yields residual recovery of 43–51% in Turn RAG and LightMem and 66–72% in MemoryBank. Extra budget can remove only turns already in the pool. In the sweep subset, widening the pool from twenty to sixty at budget ten lowers reported S2 residual recovery by 12.5–23.9 points.

### S26 · Choice.

[原文定位](https://arxiv.org/html/2610.21405v1#S6.SS1.SSS0.Px2)

Choice can fail, as E2 in Figure 4 shows. Deleting the whole pool tests whether removing the unselected candidates would materially improve forgetting. Measured recovery need not be monotonic in deletion, since the reader can respond differently to the remaining context. In Table 9, whole-pool deletion lowers residual recovery by at most 6.5 points versus S2 at budget ten. These subset sweeps identify candidate coverage as the main bottleneck within the evaluated cleanup baselines.

### S27 · Reach.

[原文定位](https://arxiv.org/html/2610.21405v1#S6.SS1.SSS0.Px3)

Candidate reach limits these retrieval-based cleanup baselines. The pool holds only about half of a fact’s evidence, because other candidates resemble the request more than the evidence does. A minimal cut averages only three turns. A complete cut combines turns that jointly intersect every sufficient set. Across the 132 settings of the two sweeps, residual recovery tracks the number k of evidence turns removed almost exactly,

\mathrm{Res}\approx 13\,(8.2-k)\qquad(R^{2}=0.95),

while system, model, and strategy together shift it by at most four points. The fitted line extrapolates to zero near k=8.2 , nearly all the evidence of an average fact. For the evaluated deleters, removing more evidence strongly predicts lower residual recovery, linking their performance to the evidence their pools reach. Individual facts may need far fewer deletions when a complete cut is reached and selected.

Annotations were fixed before system evaluation and validated independently of retrieval and deletion results. The pool and budget sweeps then distinguish reach and selection limitations using these fixed annotations.

### S28 · 6.2 Retrieval unit and derivation

[原文定位](https://arxiv.org/html/2610.21405v1#S6.SS2)

The five memories of §4.3 retrieve different units and store different derived content, which may shape candidate coverage and both recovery metrics.

### S29 · Granularity.

[原文定位](https://arxiv.org/html/2610.21405v1#S6.SS2.SSS0.Px1)

Turn RAG and Session RAG hold the same text and derive nothing, allowing a comparison under their respective retrieval settings. Both yield 96–99% residual recovery after S0, but Session RAG hides far more, with a hidden-risk share of 71–82% against 39–42%. Its three retrieved sessions hold only 1.9 evidence turns, against 4.8 in Turn RAG’s sixteen turns. Session RAG’s cleanup also removes only 33–45 points of residual recovery against 51–56, because whole-session candidates are mostly not evidence. Under these settings, facts are harder both to see and to delete with session retrieval.

### S30 · Derivation.

[原文定位](https://arxiv.org/html/2610.21405v1#S6.SS2.SSS0.Px2)

Stronger derivation does not consistently correspond to higher residual recovery across the evaluated systems. Although LightMem has the strongest derivation, its residual recovery resembles Turn RAG’s (39–43% against 41–46%). MemoryBank has the lightest derivation and the highest residual recovery (72–76%), alongside lower candidate coverage (3.0 evidence turns against 4.5 in Turn RAG and LightMem). Derived objects may alter visibility by combining evidence and matching the question without the disclosure. After cleanup the hidden-risk share is 78–82% in MemoryBank against 41–56% in Nemori and LightMem. This pattern is consistent with derived objects changing which surviving evidence native retrieval exposes.

### S31 · 6.3 Derivation types

[原文定位](https://arxiv.org/html/2610.21405v1#S6.SS3)

To break every annotated derivation, a deleter must reach and select a complete cut. The four types have similar amounts of evidence but differ in how that evidence relates to the request. Relation chains have the smallest annotated cuts (2.7 turns); nevertheless, their evidence may be difficult to retrieve because it names the request’s people and firms without using its words. Small cuts therefore need not yield low residual recovery under these baselines.

Figure 3c shows that relation chains retain the most residual recovery after cleanup on average. Recovery drops 24 points from S0 to S2, and a Turn RAG pool of sixty holds 4.4 of their evidence turns against 6.9 for aggregation. Figure 3d shows hidden-risk shares of 81–94% across systems, plausibly because their links span topics while derived objects combine turns within topics. Aggregation loses 58 points to cleanup: more of its evidence enters the pool, allowing deletions to break its derivations. Under these baselines, evidence linked by entities rather than wording is associated with lower candidate coverage and higher residual recovery.

### S32 · 7 Case Study

[原文定位](https://arxiv.org/html/2610.21405v1#S7)

Figure 4 shows LLM-guided cleanup of a relation-chain fact in Turn RAG (Appendix D). The user asks the assistant to forget that their company hired a firm the company’s CFO’s wife owns. The fact rests on four links, (i) hiring, (ii) ownership, (iii) relationship, and (iv) identity, and it is forgotten once both evidence turns of any one link are deleted.

The evidence shares the request’s entities but little of its wording, ranking 3–141 by similarity. The pool of 20 holds only two evidence turns from different links. S2 deletes both with budget to spare, but neither link is cut, so the fact remains derivable (§6.1). With a pool of 30, E2 becomes available, but S2 leaves it unselected even though deleting it alongside E1 would cut the hiring link. At 50, S2 deletes E5 and E6, breaking the relationship link. A wider pool enables a complete cut, but S2 must still select all its turns. Every evidence turn is one hop from a request entity, so following entities could reach a complete cut.

### S33 · 8 Conclusion

[原文定位](https://arxiv.org/html/2610.21405v1#S8)

We introduce MemCut, a benchmark of 456 hand-designed secrets with annotated evidence trails, for evaluating forgetting in long-term agent memory. Its metrics distinguish native recovery from recovery by the same reader given surviving evidence. Across five memory designs, four models, and three reference baselines, disclosure deletion reduces native recovery far more than residual recovery. LLM-guided deletion of ten further turns from twenty retrieval candidates leaves 39–76% residual recovery, with higher reported hidden-risk shares than before deletion. Subset sweeps identify candidate coverage as the main bottleneck in the evaluated reference baselines.

### S34 · Limitations

[原文定位](https://arxiv.org/html/2610.21405v1#Sx1)

Controlled evaluation.

MemCut evaluates forgetting for secrets with specified evidence trails across four derivation types. Controlled construction supports comparisons of candidate coverage, deletion choices, and residual recovery under fixed annotations. The episodes model recurring work, family, and social activities. Deployment studies can establish how often these trails occur and how forgetting performance changes with naturally occurring evidence structures.

Reference baselines.

Our reference baselines reuse existing retrieval and write components through a common deletion procedure. The sweeps examine candidate coverage and selection within this setting. These results establish reference performance for this reuse strategy. MemCut also supports evaluating dedicated erasure methods that expand candidate coverage or change memory indexing.

Scope.

We study text memory. Multimodal and parametric memory remain outside our scope.

The source-level measure does not capture unrelated content removed through closure or downstream utility loss.

### S35 · Ethics Statement

[原文定位](https://arxiv.org/html/2610.21405v1#Sx2)

MemCut contains no real personal data; all people, organizations, and events are fictional. Describing how deleted secrets can be reconstructed could be misused. However, the reconstruction relies only on ordinary retrieval and reading of stored memory, and we believe that measuring this risk is a prerequisite for reducing it. The annotation audit was carried out by two graduate students in NLP who had no part in building the benchmark; each worked about 25 hours and was told in advance that all content is fictional. The benchmark will be released for research use.

### S36 · Use of AI Assistants

[原文定位](https://arxiv.org/html/2610.21405v1#Sx3)

We used generative models to phrase author-designed dialogue and polish the manuscript.

The research questions, the design of the benchmark and the experiments, the analyses, and every figure, table, and number were produced by the authors.

### S37 · References

[原文定位](https://arxiv.org/html/2610.21405v1#bib)

Bourtoule et al. (2021)

Lucas Bourtoule, Varun Chandrasekaran, Christopher A. Choquette-Choo, Hengrui

Jia, Adelin Travers, Baiwu Zhang, David Lie, and Nicolas Papernot. 2021.

Machine unlearning.

In 2021 IEEE Symposium on Security and Privacy (SP).

Chhikara et al. (2025)

Prateek Chhikara, Dev Khant, Saket Aryan, Taranjeet Singh, and Deshraj Yadav.

2025.

Mem0: Building production-ready AI agents with scalable long-term

memory.

arXiv preprint arXiv:2504.19413.

Cohen et al. (2024)

Roi Cohen, Eden Biran, Ori Yoran, Amir Globerson, and Mor Geva. 2024.

Evaluating the ripple effects of knowledge editing in language

models.

Transactions of the Association for Computational Linguistics,

12.

European Parliament and Council of the European

Union (2016)

European Parliament and Council of the European Union. 2016.

Regulation (EU) 2016/679 of the European Parliament and of the

Council (General Data Protection Regulation), article 17: Right to

erasure.

Fang et al. (2025)

Jizhan Fang, Xinle Deng, Haoming Xu, Ziyan Jiang, Yuqi Tang, Ziwen Xu, Shumin

Deng, Yunzhi Yao, Mengru Wang, Shuofei Qiao, Huajun Chen, and Ningyu Zhang.

2025.

LightMem: Lightweight and efficient memory-augmented generation.

arXiv preprint arXiv:2510.18866.

Gutiérrez et al. (2024)

Bernal Jiménez Gutiérrez, Yiheng Shu, Yu Gu, Michihiro Yasunaga, and

Yu Su. 2024.

HippoRAG: Neurobiologically inspired long-term memory for large

language models.

In Advances in Neural Information Processing Systems,

volume 37.

Hu et al. (2026)

Yuanzhe Hu, Yu Wang, and Julian McAuley. 2026.

Evaluating memory in LLM agents via incremental multi-turn

interactions.

In The Fourteenth International Conference on Learning

Representations.

Jang et al. (2023)

Joel Jang, Dongkeun Yoon, Sohee Yang, Sungmin Cha, Moontae Lee, Lajanugen

Logeswaran, and Minjoon Seo. 2023.

Knowledge unlearning for mitigating privacy risks in language models.

In Proceedings of the 61st Annual Meeting of the Association

for Computational Linguistics (Volume 1: Long Papers), pages 14389–14408,

Toronto, Canada. Association for Computational Linguistics.

Karpukhin et al. (2020)

Vladimir Karpukhin, Barlas Oguz, Sewon Min, Patrick Lewis, Ledell Wu, Sergey

Edunov, Danqi Chen, and Wen-tau Yih. 2020.

Dense passage retrieval for open-domain question answering.

In Proceedings of the 2020 Conference on Empirical Methods in

Natural Language Processing (EMNLP), pages 6769–6781. Association for

Computational Linguistics.

Lewis et al. (2020)

Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir

Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim

Rocktäschel, Sebastian Riedel, and Douwe Kiela. 2020.

Retrieval-augmented generation for knowledge-intensive NLP tasks.

In Advances in Neural Information Processing Systems,

volume 33.

Ma et al. (2025)

Wenquan Ma, Jiayan Nan, Wenlong Wu, and Yize Chen. 2025.

Nemori: Self-organizing agent memory inspired by cognitive science.

arXiv preprint arXiv:2508.03341.

Maharana et al. (2024)

Adyasha Maharana, Dong-Ho Lee, Sergey Tulyakov, Mohit Bansal, Francesco

Barbieri, and Yuwei Fang. 2024.

Evaluating very long-term conversational memory of LLM agents.

In Proceedings of the 62nd Annual Meeting of the Association

for Computational Linguistics (Volume 1: Long Papers).

Maini et al. (2024)

Pratyush Maini, Zhili Feng, Avi Schwarzschild, Zachary C. Lipton, and J. Zico

Kolter. 2024.

TOFU: A task of fictitious unlearning for LLMs.

In First Conference on Language Modeling.

Meng et al. (2022)

Kevin Meng, David Bau, Alex Andonian, and Yonatan Belinkov. 2022.

Locating and editing factual associations in GPT.

In Advances in Neural Information Processing Systems,

volume 35.

Mireshghallah et al. (2024)

Niloofar Mireshghallah, Hyunwoo Kim, Xuhui Zhou, Yulia Tsvetkov, Maarten Sap,

Reza Shokri, and Yejin Choi. 2024.

Can LLMs keep a secret? testing privacy implications of language

models via contextual integrity theory.

In The Twelfth International Conference on Learning

Representations.

Packer et al. (2023)

Charles Packer, Sarah Wooders, Kevin Lin, Vivian Fang, Shishir G. Patil, Ion

Stoica, and Joseph E. Gonzalez. 2023.

MemGPT: Towards LLMs as operating systems.

arXiv preprint arXiv:2310.08560.

Park et al. (2023)

Joon Sung Park, Joseph C. O’Brien, Carrie J. Cai, Meredith Ringel Morris, Percy

Liang, and Michael S. Bernstein. 2023.

Generative agents: Interactive simulacra of human behavior.

In Proceedings of the 36th Annual ACM Symposium on User

Interface Software and Technology.

Park (2026)

Young Bin Park. 2026.

Graph-native cognitive memory for AI agents: Formal belief revision

semantics for versioned memory architectures.

arXiv preprint arXiv:2603.17244.

Rasmussen et al. (2025)

Preston Rasmussen, Pavlo Paliychuk, Travis Beauvais, Jack Ryan, and Daniel

Chalef. 2025.

Zep: A temporal knowledge graph architecture for agent memory.

arXiv preprint arXiv:2501.13956.

Shao et al. (2024)

Yijia Shao, Tianshi Li, Weiyan Shi, Yanchen Liu, and Diyi Yang. 2024.

PrivacyLens: Evaluating privacy norm awareness of language models

in action.

In Advances in Neural Information Processing Systems (Datasets

and Benchmarks Track).

Shi et al. (2025)

Weijia Shi, Jaechan Lee, Yangsibo Huang, Sadhika Malladi, Jieyu Zhao, Ari

Holtzman, Daogao Liu, Luke Zettlemoyer, Noah A. Smith, and Chiyuan Zhang.

2025.

MUSE: Machine unlearning six-way evaluation for language models.

In The Thirteenth International Conference on Learning

Representations.

Tan et al. (2025)

Haoran Tan, Zeyu Zhang, Chen Ma, Xu Chen, Quanyu Dai, and Zhenhua Dong. 2025.

MemBench: Towards more comprehensive evaluation on the memory of

LLM-based agents.

In Findings of the Association for Computational Linguistics:

ACL 2025.

Trivedi et al. (2022)

Harsh Trivedi, Niranjan Balasubramanian, Tushar Khot, and Ashish Sabharwal.

2022.

MuSiQue: Multihop questions via single-hop question composition.

Transactions of the Association for Computational Linguistics,

10:539–554.

Uddin et al. (2026)

Md Nayem Uddin, Kumar Shubham, Eduardo Blanco, Chitta Baral, and Gengyu Wang.

2026.

From recall to forgetting: Benchmarking long-term memory for

personalized agents.

In Findings of the Association for Computational Linguistics:

ACL 2026, pages 26814–26841.

Wang and Zhang (2026)

Kuan Wang and Chao Zhang. 2026.

MemLeak: Diagnosing information leaks in multimodal agent memory.

arXiv preprint arXiv:2606.29788.

Wang et al. (2023)

Weizhi Wang, Li Dong, Hao Cheng, Xiaodong Liu, Xifeng Yan, Jianfeng Gao, and

Furu Wei. 2023.

Augmenting language models with long-term memory.

In Advances in Neural Information Processing Systems,

volume 36.

Wu et al. (2025)

Di Wu, Hongwei Wang, Wenhao Yu, Yuwei Zhang, Kai-Wei Chang, and Dong Yu. 2025.

LongMemEval: Benchmarking chat assistants on long-term interactive

memory.

In The Thirteenth International Conference on Learning

Representations.

Xu et al. (2022)

Jing Xu, Arthur Szlam, and Jason Weston. 2022.

Beyond goldfish memory: Long-term open-domain conversation.

In Proceedings of the 60th Annual Meeting of the Association

for Computational Linguistics (Volume 1: Long Papers), pages 5180–5197,

Dublin, Ireland. Association for Computational Linguistics.

Xu et al. (2025)

Wujiang Xu, Zujie Liang, Kai Mei, Hang Gao, Juntao Tan, and Yongfeng Zhang.

2025.

A-MEM: Agentic memory for LLM agents.

arXiv preprint arXiv:2502.12110.

Yang (2026)

Dongxu Yang. 2026.

Control-plane placement shapes forgetting: An architectural study of

agent memory across thirteen system configurations.

arXiv preprint arXiv:2606.15903.

Yang et al. (2018)

Zhilin Yang, Peng Qi, Saizheng Zhang, Yoshua Bengio, William Cohen, Ruslan

Salakhutdinov, and Christopher D. Manning. 2018.

HotpotQA: A dataset for diverse, explainable multi-hop question

answering.

In Proceedings of the 2018 Conference on Empirical Methods in

Natural Language Processing, pages 2369–2380, Brussels, Belgium.

Association for Computational Linguistics.

Zhang et al. (2024)

Zeyu Zhang, Xiaohe Bo, Chen Ma, Rui Li, Xu Chen, Quanyu Dai, Jieming Zhu,

Zhenhua Dong, and Ji-Rong Wen. 2024.

A survey on the memory mechanism of large language model based

agents.

arXiv preprint arXiv:2404.13501.

Zhong et al. (2024)

Wanjun Zhong, Lianghong Guo, Qiqi Gao, He Ye, and Yanlin Wang. 2024.

MemoryBank: Enhancing large language models with long-term memory.

In Proceedings of the AAAI Conference on Artificial

Intelligence, volume 38.

Zhong et al. (2023)

Zexuan Zhong, Zhengxuan Wu, Christopher Manning, Christopher Potts, and Danqi

Chen. 2023.

MQuAKE: Assessing knowledge editing in language models via

multi-hop questions.

In Proceedings of the 2023 Conference on Empirical Methods in

Natural Language Processing, pages 15686–15702, Singapore. Association for

Computational Linguistics.

Zhu et al. (2026)

Jinchang Zhu, Jindong Li, Cheng Zhang, Jiahong Liu, and Menglin Yang. 2026.

HeLa-Mem: Hebbian learning and associative memory for LLM agents.

In Proceedings of the 64th Annual Meeting of the Association

for Computational Linguistics (Volume 1: Long Papers), pages 13757–13769,

San Diego, California, United States. Association for Computational

Linguistics.

### S38 · Appendix A Dataset Details

[原文定位](https://arxiv.org/html/2610.21405v1#A1)

This appendix describes what MemCut contains. Table 5 gives per-fact statistics overall and by derivation type, and Table 6 gives per-episode statistics.

Derivation type

Per fact

Overall

Fact assembly

Relation chain

Aggregation

Temporal state

Protected facts

456

115

114

114

113

Evidence

Evidence turns per fact

8.1

7.9

8.3

8.1

8.2

Sessions they span

8.0

7.8

8.2

8.1

8.0

Span in days (median)

29

31

31

28

25

Turns from disclosure (median)

714

778

873

723

515

Share in disclosure’s session (% facts)

14.3

7.0

9.6

20.2

20.4

Recovery

Minimal sufficient sets

15.7

16.0

17.2

15.0

14.6

Turns per set (none of size 1)

2.7

2.4

3.0

3.0

2.6

Deletion

Minimal cut, mean

3.04

3.22

2.68

3.08

3.16

Minimal cut, max (budget: 10)

5

5

4

5

4

Cuttable with 2 deletions (%)

25.9

27.8

44.7

17.5

13.3

Distraction

High-confusion distractors per fact

26.6

27.3

26.4

27.3

25.5

Table 5: Per-fact statistics of MemCut, overall and by derivation type (means unless noted). Share in disclosure’s session: facts with at least one evidence turn in the disclosure’s session. Sufficient sets and minimal cuts are author-identified and cross-checked by two independent algorithms. Every fact can be cut with at most five deletions, half the ten-turn budget; relation chains (highlighted) need the fewest. No evidence turn is shared across facts, and 62.6% of turns carry no annotation.

EP

Turns

Tokens

Sess.

Tok./

turn

Turns/

sess.

Days

Facts

EP01

2,136

103,805

26

48.6

82.2

30

28

EP02

2,152

77,846

28

36.2

76.9

27

28

EP03

2,200

85,815

28

39.0

78.6

27

28

EP04

2,200

70,715

29

32.1

75.9

28

27

EP05

2,738

99,776

33

36.4

83.0

32

33

EP06

2,798

100,768

35

36.0

79.9

34

32

EP07

3,156

115,627

35

36.6

90.2

34

32

EP08

3,278

101,697

32

31.0

102.4

31

32

EP09

3,374

125,158

34

37.1

99.2

33

32

EP10

3,302

143,060

35

43.3

94.3

34

32

EP11

2,854

114,192

34

40.0

83.9

33

28

EP12

3,258

157,627

36

48.4

90.5

81

32

EP13

3,232

158,944

35

49.2

92.3

72

30

EP14

3,472

169,198

36

48.7

96.4

86

32

EP15

3,252

115,771

34

35.6

95.7

77

30

Mean

2,893

116,000

32.7

39.9

88.1

43.9

30.4

Table 6: Per-episode statistics: turns, tokens (o200k_base), sessions, tokens per turn, turns per session, days spanned, and protected facts.

### S39 · Derivation types.

[原文定位](https://arxiv.org/html/2610.21405v1#A1.SS0.SSS0.Px1)

The four types abstract the most typical ways separate records entail a proposition. Fact assembly joins attributes of one entity: a code name, a site visit, and an address make an acquisition target. Relation chains join entities: a contract names a firm, a filing names its owner, a dinner names the owner’s spouse, and a staff list names the spouse’s role. Aggregation combines values: several payments sum to a debt, several visits make a pattern. Temporal and state reasoning orders records in time: an offer, a revision, and a withdrawal fix what holds now. Longer derivations often compose them.

### S40 · Scale and balance.

[原文定位](https://arxiv.org/html/2610.21405v1#A1.SS0.SSS0.Px2)

The facts are balanced across types, and every episode is long. The 456 protected facts split evenly over the four derivation types, 113–115 each (Table 5), and every type appears in every episode six to nine times. The fifteen episodes that carry them hold 43,402 turns in 490 sessions (1.74M tokens); each averages 2,893 turns, 116k tokens, and 33 sessions over 27–86 days (Table 6).

### S41 · Derivation structure.

[原文定位](https://arxiv.org/html/2610.21405v1#A1.SS0.SSS0.Px3)

Every fact can be derived in many ways, but never from a single evidence turn. A fact has 8.1 evidence turns on average (6–10; 3,700 in all), which the authors grouped into 7,148 minimal sufficient sets, 15.7 per fact (4–38), each of two to five turns (mean 2.7). Breaking all of them takes two deletions for 25.9% of facts, three for 45.4%, four for 28.1%, and five for 0.7%; the minimal cuts were computed by enumeration and agree with an independent dynamic program on all 456 facts. Each fact also has 26.6 distractors (16–88; 12,092 distinct turns). No evidence turn serves two facts, five turns are evidence for one fact and a distractor for another, and 62.6% of turns carry no annotation.

### S42 · Dispersion.

[原文定位](https://arxiv.org/html/2610.21405v1#A1.SS0.SSS0.Px4)

Evidence is spread across the episode and mostly precedes the disclosure. A fact’s evidence spans 8.0 sessions (5–10), with a median first-to-last span of 2,259 turns and 29 days, and lies a median of 714 turns and eight sessions from the disclosure. Only 67 of the 3,700 evidence turns (1.8%) share the disclosure’s session, and 14.3% of facts have at least one such turn. Disclosures fall in the last third of the episode for 61% of facts. Time is annotated at the granularity of session dates.

### S43 · Appendix B Extended Results

[原文定位](https://arxiv.org/html/2610.21405v1#A2)

This appendix gives the complete results behind §5 and §6: recovery at every deletion level (§B.1), the retrieval unit and derivation (§B.2), and where cleanup loses the evidence (§B.3).

DeepSeek

Qwen

GLM

MiMo

System

Nat.

Res.

Nat.

Res.

Nat.

Res.

Nat.

Res.

Retrieval stores

Turn RAG

95.0

100.0

90.8

100.0

92.1

100.0

92.8

100.0

Session RAG

62.5

100.0

48.2

100.0

52.9

100.0

69.7

100.0

Memory systems

MemoryBank

89.9

99.8

89.0

99.8

90.6

99.8

89.5

99.3

Nemori

95.2

98.2

89.0

97.4

93.9

93.9

95.8

99.1

LightMem

86.2

98.0

82.7

96.1

89.0

97.6

82.5

94.5

Table 7: Recovery (%) before deletion. Every store supports nearly every fact (Res.), and retrieval reveals most of them (Nat.) in every system but Session RAG.

DeepSeek

Qwen

GLM

MiMo

System

Full

S0

S1

S2

Full

S0

S1

S2

Full

S0

S1

S2

Full

S0

S1

S2

Retrieval stores

Turn RAG

5.0

39.1

62.4

76.7

9.2

42.2

67.4

82.0

7.9

39.5

65.6

78.5

7.2

38.7

63.7

76.4

Session RAG

37.5

75.3

77.6

82.6

51.8

79.7

78.1

83.3

47.1

82.4

84.2

92.3

30.3

71.0

86.1

85.4

Memory systems

MemoryBank

9.9

56.8

71.5

78.0

10.8

56.3

73.0

81.6

9.2

55.6

73.8

81.9

9.9

54.8

71.3

78.1

Nemori

3.1

30.2

37.9

42.7

8.6

41.9

52.4

55.9

0.0

30.8

32.2

40.6

3.3

33.6

43.5

47.8

LightMem

12.1

25.7

37.1

45.0

13.9

30.3

45.2

50.3

8.8

17.8

35.6

44.8

12.8

26.1

35.8

49.0

Table 8: Hidden-risk share (%), computed as (\mathrm{Res}-\mathrm{Nat})/\mathrm{Res} at every deletion level. It is a lower bound on the share of residual successes that native recovery misses (Appendix B.1). Shading is proportional to the value. Full is the store before any deletion. The share rises from Full to S2 in all 20 configurations.

### S44 · Before deletion.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS1.SSS0.Px1)

Every system retains what recovery needs: residual recovery is 100% in both verbatim stores and 94–100% in the derived systems (Table 7), so later drops reflect deletion rather than encoding loss, apart from a small loss of aggregate values at write time in LightMem (Appendix C). Native recovery is 82–96% in every system except Session RAG, where it is 48–70% because three retrieved sessions hold only part of a fact’s evidence (§B.2).

### S45 · Write models.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS1.SSS0.Px2)

Within each system the four write models agree on residual recovery after S2 to within about five points, and to within ten for Session RAG. The main patterns of §5 are consistent across these four models within each system.

### S46 · Hidden-risk share.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS1.SSS0.Px3)

The hidden-risk share rises from Full to S2 in all 20 configurations, monotonically in the 16 outside Session RAG (Table 8). Session RAG hides the most at every level, from 30–52% before any deletion to 83–92% after S2.

The share is a conservative estimate.

Native and residual recovery are answered independently.

As a result, native recovery finds a few facts that residual recovery misses.

In the six configurations that we analyze per fact (MemoryBank, Nemori, and LightMem with DeepSeek and Qwen), these facts make up 4.8% of native successes.

Let R and N be the sets of facts that residual and native recovery find.

The share of facts in R that native recovery misses is |R\setminus N|/|R| .

The reported share also subtracts the facts in N that are not in R , so it is a lower bound on |R\setminus N|/|R| .

In the six configurations, |R\setminus N|/|R| is 0–12 points higher than the reported share, and the gap is largest after S2.

After S2 it is 80–85% in MemoryBank and 52–62% in Nemori and LightMem, while the reported share is 78–82% and 43–56%.

It also rises from Full to S2 in all six configurations.

The reported share is therefore conservative about the level of hidden risk in these configurations.

### S47 · Collateral deletion at S0.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS1.SSS0.Px4)

Most of the residual recovery that derived systems lose at S0 was carried away by closure deletion: a derived object that also contains the disclosure goes with it, together with any evidence it summarized. The largest overall loss, 13 points for Nemori with DeepSeek, is close to the share of facts with at least one evidence turn in the disclosure’s session (14.3%, Table 5). Four fifths of the loss falls on aggregation, for reasons given in Appendix C.

### S48 · Retrieval unit.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS2.SSS0.Px1)

Session retrieval reads more and finds less. At the evaluated retrieval depths, a Session RAG context averages 13.3k tokens and holds 1.9 evidence turns, a Turn RAG context 1.1k tokens and 4.8. After the disclosure is deleted, the two stores’ residual recovery agrees to within about two points in 15 of the 16 model–type cells of Table 3, while Session RAG’s native recovery is 31–43 points lower and its hidden-risk share is 71–82% against 39–42%. After cleanup Session RAG also leaves 10–23 points more recoverable, because its candidate pools are diluted by non-evidence turns from the same sessions.

### S49 · Derivation strength.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS2.SSS0.Px2)

Retrieval units help explain native recovery. In MemoryBank it is one turn, so once the disclosure is gone each evidence turn has to match the question on its own: deleting the disclosure costs 46–50 points of native recovery, and after cleanup four in five of the 72–76% of facts that remain recoverable are unseen by the system’s own retrieval. In Nemori it is a narrative or a distilled fact that fuses several turns, and in LightMem a consolidated entry that fuses more; such objects can still match the question without the disclosure, consistent with the smaller losses of 29–36 and 12–20 points. What a system retains follows instead how much evidence its deletion pool reaches (§B.3): MemoryBank’s pool of twenty holds 3.0 of a fact’s evidence turns against 4.5 in Turn RAG and LightMem, and cleanup lowers its residual recovery by only 18–23 points, against 33–38 in Nemori and 47–52 in LightMem. Closure deletion also removes a whole object when any of its source turns goes; what it costs in unrelated memory is a separate question, which we leave to future work.

### S50 · B.3 Where cleanup loses the evidence

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS3)

Turn RAG

MemoryBank

LightMem

DeepSeek

Qwen

DeepSeek

Qwen

DeepSeek

Qwen

S1

S2

S1

S2

S1

S2

S1

S2

S1

S2

S1

S2

Widening the candidate pool (budget =10 ; first column: pool size)

10

66.7

66.7

63.2

62.9

80.6

80.6

80.6

80.6

63.2

63.4

57.6

56.1

20⋆

66.7

52.1

63.2

47.9

80.6

72.2

80.6

72.2

62.5

49.3

52.1

47.2

30

66.7

47.2

63.2

44.1

80.6

68.1

80.6

58.7

62.5

44.9

52.1

39.3

40

66.7

43.8

63.2

39.2

80.6

61.5

80.6

60.0

62.5

37.9

52.1

37.0

50

66.7

40.3

63.2

35.5

80.6

62.5

80.6

51.9

62.5

39.4

52.1

33.8

60

66.7

39.6

63.2

30.8

80.6

58.0

80.6

48.3

62.5

34.3

52.1

31.6

Raising the deletion budget (pool =20 ; first column: budget)

2

95.1

93.1

93.1

90.9

91.0

91.0

86.4

90.7

88.9

86.1

85.4

81.9

4

84.0

66.0

81.8

68.1

91.0

89.6

87.3

88.2

81.9

63.2

78.5

69.9

6

76.4

54.9

72.9

52.1

86.1

80.6

80.9

76.6

72.7

52.8

68.5

54.9

10⋆

66.7

52.1

63.2

47.9

80.6

72.2

80.6

72.2

62.5

49.3

52.1

47.2

15

54.2

51.4

51.8

47.2

73.6

69.4

75.4

67.1

53.5

47.2

45.1

44.4

20

50.7

50.7

47.2

47.2

72.2

72.2

65.7

65.7

45.8

45.8

43.1

43.1

Table 9: Residual recovery (%) behind Figure 3a–b: retrieval-ranked (S1) and LLM-guided (S2) cleanup as the candidate pool widens with the budget fixed at ten turns (top), and as the budget grows with the pool fixed at twenty (bottom). The sweeps run on the 144 facts of EP01–05 (Appendix B.3), so values at the main-table setting (⋆) differ from Tables 3 and 4, which cover all 456. S2 is shaded in proportion to its value. Percentages are over completed runs: 98.9% of those planned, and at least 114 of the 144 facts in every cell.

Table 9 gives every point of Figure 3a–b. The sweeps cover the 144 facts of EP01–05, so values at the main setting differ from Tables 3 and 4, and the sweeps are read as changes from their own main setting.

### S51 · Candidate coverage.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS3.SSS0.Px1)

Candidate pools omit supporting evidence. At the main pool of 20, the candidates contain on average 4.5 of a fact’s evidence turns in Turn RAG and LightMem and 3.0 in MemoryBank, and S2 deletes 4.4, 4.3, and 2.7 of them (means over the two write models). Widening the pool to 60 raises the evidence it contains to 5.8, 5.9, and 4.5, still fewer than the six to ten evidence turns every fact has (Appendix A), and S2 deletes 5.5, 5.2, and 3.4. Raising the budget cannot go beyond the pool: at a budget of 20 the deleter removes the entire pool, S1 and S2 coincide, and 43–51% of facts remain recoverable in Turn RAG and LightMem and 66–72% in MemoryBank. In LightMem some pools of 20 hold fewer deletable turns than the budget, so a budget of 20 deletes 19.1 turns on average with DeepSeek and 16.6 with Qwen rather than 20.

### S52 · Evidence deleted on the full benchmark.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS3.SSS0.Px2)

The counts above come from the 144-fact sweep subset.

Table 10 repeats the count of deleted evidence on all 456 facts in the three memory systems with DeepSeek and Qwen: of the ten turns that cleanup deletes for a fact, it reports how many are annotated evidence.

With ten additional selected turns, k selected evidence turns imply an off-target fraction of 1-k/10 .

### S53 · Evidence removed by cleanup.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS3.SSS0.Px3)

Of the ten cleanup selections, 3.0 are evidence under S1 and 3.6 under S2, corresponding to approximately 70% and 64% off-target selections. An average fact has 8.1 evidence turns (Table 5).

This is consistent with the sweeps, where the pool of twenty holds only about half of a fact’s evidence (§6.1).

LLM judgment adds 0.7 evidence turns per fact over retrieval ranking; the sweeps show larger recovery reductions from widening the pool than from deleting its remaining candidates.

### S54 · Memory design changes reach.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS3.SSS0.Px4)

MemoryBank, whose pool holds the least evidence, deletes the least, 2.9 evidence turns per fact under S2, and keeps the most facts recoverable (72–73% residual recovery after S2; Table 4).

LightMem deletes the most, 4.7, and keeps the fewest (39–42%), and Nemori lies between them on both (3.4; 52–57%).

Across systems, residual recovery thus follows the evidence a system removes, as it does across the settings of the sweeps.

### S55 · Relation chains are the hardest to reach.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS3.SSS0.Px5)

In every system and under both strategies, relation chains lose the fewest evidence turns: 2.4 per fact under S2, against 3.8 for fact assembly, 3.9 for temporal state, and 4.6 for aggregation.

The gap holds within each system, at 1.7 against 3.0–3.7 in MemoryBank, 2.4 against 3.5–3.9 in Nemori, and 2.9 against 4.8–6.0 in LightMem.

Their evidence names the request’s people and firms but shares little of its wording, so similarity retrieval ranks it low (§6.3).

System

Assem.

Chain

Aggr.

Temp.

All

MemoryBank

S1

2.2

1.2

2.9

2.3

2.2

S2

3.0

1.7

3.7

3.2

2.9

Nemori

S1

2.9

1.8

3.5

2.9

2.8

S2

3.6

2.4

3.9

3.5

3.4

LightMem

S1

3.9

2.4

5.2

4.2

3.9

S2

4.8

2.9

6.0

5.1

4.7

All three

S1

3.0

1.8

3.9

3.2

3.0

S2

3.8

2.4

4.6

3.9

3.6

Table 10: Annotated evidence turns among the ten turns that cleanup deletes per fact, by system and derivation type (Assem.: fact assembly; Chain: relation chain; Aggr.: aggregation; Temp.: temporal state), over all 456 facts and the DeepSeek and Qwen write models.

### S56 · Judgment grows with reach.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS3.SSS0.Px6)

S1 deletes the ten top-ranked candidates, so its deletion set is unchanged across the pool sweep once the pool holds ten deletable turns. At a pool of ten both strategies delete the same turns. The gain of S2 over S1 is therefore what judgment adds from candidates beyond the top ten: 5–15 points at a pool of 20 and 20–32 at a pool of 60. Judgment is worth what reach gives it to choose from.

### S57 · Partial cuts leave derivations intact.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS3.SSS0.Px7)

A complete cut intersects every annotated sufficient set. At a pool of 60, S2 intersects 92–93% of a fact’s sufficient sets on average in Turn RAG and LightMem; residual recovery is still 31–40%.

### S58 · Types.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS3.SSS0.Px8)

Widening reaches more aggregation evidence than relation-chain evidence. At a pool of 60 the Turn RAG candidates contain 6.9 of an aggregate’s evidence turns but 4.4 of a relation chain’s, and after S2, 3–31% of aggregates and 49–78% of relation chains remain recoverable across the three systems and two write models. Relation chains have higher residual recovery than aggregation throughout both sweeps, the pattern of Appendix C.

### S59 · One quantity behind both sweeps.

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS3.SSS0.Px9)

Across the 132 distinct settings of the two sweeps (both strategies, three systems, two write models), residual recovery falls almost linearly with the mean number of annotated evidence turns a setting removes per fact, by about 13 points per turn ( R^{2}=0.95 ). Given that number, the system and the write model move residual recovery by at most about four points, and the strategy by less than one. The effects of pool width, budget, and judgment on residual recovery are closely associated with how much evidence they remove, consistent with MemoryBank retaining more because its pool holds less evidence. The fitted line reaches zero near 8.2 removed turns, close to the 8.1 evidence turns of an average fact (Table 5).

### S60 · B.4 Deletion cost and residual recovery

[原文定位](https://arxiv.org/html/2610.21405v1#A2.SS4)

We compare recovery at specified source-turn deletion budgets. Selecting the entire source history exceeds these budgets. The smallest annotated cut contains 3.04 evidence turns on average and at most five (Table 5). Forgetting therefore need not require deleting every evidence turn.

For the additional selected turns A and the target’s evidence E , the off-target fraction is |A\setminus E|/|A| . The denominator is the actual number selected, excluding the common disclosure removal. This is a source-level reference measure of collateral damage.

Pool

Selected

Off-target

Res. (%)

20

10

5.54

52.08

20

20

15.49

50.69

60

10

4.50

39.58

Table 11: Deletion cost and residual recovery for DeepSeek–Turn RAG, S2, on the same 144 facts, all completed. Pool, selected, and off-target counts are in source turns. Selected and off-target counts exclude disclosure removal and are means per fact.

Table 11 reuses three settings of the existing sweeps on the same 144 facts. Turn RAG stores one object per turn, so closure adds no other records. Doubling the budget from ten to twenty adds 9.95 non-evidence deletions per fact on average, while residual recovery falls by only 1.39 points. Widening the pool from twenty to sixty at budget ten instead lowers residual recovery by 12.50 points and removes 1.04 fewer non-evidence turns. Thus, broader coverage improves forgetting without selecting more turns and reduces off-target deletion in this comparison.

These results do not establish downstream utility preservation. Evidence turns can serve legitimate tasks, and deleting evidence beyond a complete cut can also be unnecessary. In derived stores, closure may remove unrelated content from shared objects, which the source-turn budget does not bound. Recovery and source-level deletion cost should therefore be read together, while retained task performance remains a separate evaluation dimension.

Derivation type

Fact

Rel.

Aggr.

Temp.

Recovery, mean %

Native before deletion

91.9

81.1

90.4

96.1

Native after S0 (visible)

73.8

18.2

60.9

76.6

Residual lost at S0

- 0.1

2.3

14.7

0.9

Residual recovery after S2

60.2

71.8

24.3

58.4

Removed by cleanup, S0 \to S2

38.9

24.1

57.7

40.1

Hidden-risk share after S2

49.2

87.1

66.3

52.8

Gain from LLM judgment

14.3

8.3

14.3

11.0

Annotated structure

Minimal cut (turns)

3.22

2.68

3.08

3.16

Cut by two deletions (%)

27.8

44.7

17.5

13.3

Table 12: Leakage by derivation type: means over the 16 configurations outside Session RAG (four write models, four systems), with the hidden-risk share computed from the mean recovery values. LLM judgment: residual recovery lowered by S2 relative to S1. Annotated structure from Table 5. Fact: fact assembly; Rel.: relation chain; Aggr.: aggregation; Temp.: temporal state. Bold marks the type that stands out in each row.

Full

S0

S1

S2

Type

System

Nat.

Res.

Nat.

Res.

Nat.

Res.

Nat.

Res.

DeepSeek

Fact assembly

MemoryBank

85.2

100.0

53.0

100.0

32.2

92.2

23.5

84.3

Nemori

94.8

98.3

81.7

97.4

65.2

84.3

50.4

63.5

LightMem

97.4

100.0

93.0

99.1

53.9

62.6

40.0

51.3

Relation chain

MemoryBank

84.2

100.0

7.0

95.6

5.3

88.6

6.1

86.8

Nemori

93.0

98.2

17.5

89.5

18.4

73.7

11.4

60.5

LightMem

74.6

96.5

27.2

93.9

22.8

77.2

15.8

70.2

Aggregation

MemoryBank

93.9

99.1

45.6

79.8

20.2

58.8

7.0

37.7

Nemori

93.0

98.2

59.6

58.8

21.1

32.5

14.9

21.1

LightMem

79.8

95.6

55.3

64.0

12.3

20.2

6.1

6.1

Temporal state

MemoryBank

96.5

100.0

54.9

96.5

34.5

84.1

26.5

77.9

Nemori

100.0

98.2

78.8

94.7

61.9

77.9

43.4

64.6

LightMem

92.9

100.0

88.5

98.2

49.6

60.2

30.1

39.8

Qwen

Fact assembly

MemoryBank

81.7

100.0

53.9

97.4

28.7

88.7

19.1

83.5

Nemori

86.1

96.5

75.7

99.1

54.8

83.5

45.2

67.0

LightMem

95.7

100.0

89.6

100.0

48.7

58.3

35.7

47.0

Relation chain

MemoryBank

84.2

100.0

7.9

96.5

5.3

92.1

4.4

84.2

Nemori

90.4

98.2

13.2

90.4

8.8

78.1

9.6

64.9

LightMem

66.7

97.4

23.7

94.7

11.4

67.5

7.0

57.0

Aggregation

MemoryBank

96.5

99.1

50.9

89.5

17.5

57.9

7.9

50.9

Nemori

87.7

96.5

54.4

81.6

21.9

38.6

15.8

30.7

LightMem

75.4

87.7

55.3

67.5

5.3

12.3

4.4

7.9

Temporal state

MemoryBank

93.8

100.0

54.9

100.0

35.4

83.2

22.1

71.7

Nemori

92.0

98.2

69.9

95.6

45.1

74.3

30.1

66.4

LightMem

92.9

99.1

83.2

99.1

38.9

52.2

31.0

45.1

Table 13: Recovery (%) by derivation type in the three memory systems with DeepSeek and Qwen, adding the pre-deletion baseline (Full) that Table 4 omits (113–115 facts per type). Res. is shaded in proportion to its value, as in Table 3.

### S61 · Appendix C Leakage by Derivation Type

[原文定位](https://arxiv.org/html/2610.21405v1#A3)

The four derivation types of §3.3 differ in how their evidence relates to a deletion request, not in how much evidence they have (Table 5). Section 6 reads them through derivation and reach (Figure 3c–d); Table 12 summarizes each type over the 16 configurations outside Session RAG and Table 13 gives the per-type results in full. After cleanup, relation chains have the highest residual recovery in 12 of these configurations and aggregation the lowest in all 16; temporal facts, whose time cues the question repeats, and fact assembly, whose evidence shares the request’s wording, stay the most visible after S0 (77% and 74%). Four further regularities follow from the same relation between a type’s evidence and the request.

### S62 · Relation chains are hard to recall and forget.

[原文定位](https://arxiv.org/html/2610.21405v1#A3.SS0.SSS0.Px1)

Relation chains are also the type retrieval answers least well before any deletion, 81% against 90–96% for the others and 68% in LightMem, and deleting the disclosure costs them 63 points of native recovery against 18–30. Their visibility rests almost entirely on the one turn that states them: at S0, LightMem still answers 94% of fact-assembly and 90% of temporal questions but only 30% of relation chains. Their evidence names the right people and firms but not in the words of the question or request, which may hinder similarity retrieval for both answering and deletion.

### S63 · Judgment helps least where reach fails most.

[原文定位](https://arxiv.org/html/2610.21405v1#A3.SS0.SSS0.Px2)

Replacing retrieval ranking with LLM judgment lowers residual recovery by 14 points for fact assembly and aggregation, 11 for temporal facts, and 8 for relation chains (Table 12). The smaller gain for relation chains is consistent with limited candidate coverage: judgment can select only turns already in the pool.

### S64 · Coarse retrieval costs aggregation most.

[原文定位](https://arxiv.org/html/2610.21405v1#A3.SS0.SSS0.Px3)

On the same text, Session RAG answers fewer questions than Turn RAG after S0 for every type, but by different margins: about 54 points for aggregation, 37 to 38 for fact assembly and temporal facts, and 17 for relation chains (Table 3). An aggregate needs several values at once, and three retrieved sessions rarely contain all of them; relation chains lose least because turn retrieval already fails to surface them.

### S65 · Derivation reveals every type but relation chains.

[原文定位](https://arxiv.org/html/2610.21405v1#A3.SS0.SSS0.Px4)

For fact assembly, aggregation, and temporal facts, the hidden-risk share after S2 falls from 68–85% in Turn RAG and MemoryBank to 20–39% in Nemori and LightMem (Figure 3d), consistent with derived objects combining evidence within topics. Relation chains stay 81–94% hidden in every system, likely because their links span topics (§6.2).

### S66 · Aggregation also loses what deletion did not target.

[原文定位](https://arxiv.org/html/2610.21405v1#A3.SS0.SSS0.Px5)

Aggregation is the only type whose residual recovery falls when only the disclosure is deleted: 15 points on average against at most 3 for the others, and 4 to 13 points even in Turn RAG, which derives nothing. Co-location does not explain it, since temporal facts share a session with their disclosure as often, in a fifth of facts (Table 5), and lose about one point. Two effects do. First, an aggregate has to be computed from several values, and the disclosure states the result, so once the disclosure is gone the reader has to carry out the computation itself, which it does less reliably than it reads a stated fact. The evidence still suffices by design. The reader recovers 96–99% of facts from evidence alone in the validation of §3.3, with misses concentrated in aggregation, consistent with arithmetic errors. Second, in derived systems a summary that folds the disclosure together with other values goes with it under closure. Part of aggregation’s small residue after cleanup is therefore collateral rather than evidence the deleter found, although cleanup also deletes more aggregation evidence than any other type (Table 10). LightMem also loses aggregate values at write time, with 92% residual recovery before deletion, the lowest of any type–system pair. In two cells native recovery of aggregation slightly exceeds residual recovery, which may miss aggregated values in objects without an annotated evidence source. The hidden-risk share remains a lower bound on the share of residual successes missed by native recovery.

### S67 · Appendix D Case Study Details

[原文定位](https://arxiv.org/html/2610.21405v1#A4)

This appendix gives the full record of the fact in Figure 4: its evidence and cuts, where similarity to the request ranks each evidence turn, what S2 deletes at each pool size, and how entity expansion could reach a complete cut.

### S68 · The fact and its cuts.

[原文定位](https://arxiv.org/html/2610.21405v1#A4.SS0.SSS0.Px1)

The fact is that Arden Advisory, the firm the user’s company hired, belongs to Nina Shah, the wife of its CFO, Ravi Shah. It rests on four links, each with two evidence turns: hiring, the Q3 contract with Arden (E1) and a note that Ravi, the CFO, hired Arden (E2); ownership, Arden’s filing listing Nina Shah as sole owner (E3) and Nina’s engagement letter as Arden’s owner (E4); relationship, the offsite dinner Ravi and his wife Nina host (E5) and a table booked for their wedding anniversary (E6); identity, the same note (E2) and a staff line naming Ravi Shah as CFO (E7). Recovery needs one evidence turn from every link, so the minimal cuts are \{ E1, E2 \} , \{ E3, E4 \} , \{ E5, E6 \} , and \{ E2, E7 \} , two turns each.

### S69 · Similarity scatters the evidence.

[原文定位](https://arxiv.org/html/2610.21405v1#A4.SS0.SSS0.Px2)

For the request “Forget that the firm we hired belongs to our CFO’s wife”, the evidence turns rank 3 (E1), 14 (E3), 22 (E2), 36 (E5), 45 (E6), 53 (E4), and 141 (E7), so the main-table pool of 20 holds only E1 and E3, one evidence turn from each of two links. They share entities with the request but almost no wording, while records above and between them share its words without supporting the fact: a booking at the Arden Hotel, an old vendor list, an advisory budget, an advisory call, a note about a Nina in HR, an address on Arden Street. The disclosure itself ranks seventh; S0 deletes it, and it is excluded from every pool.

### S70 · S2 completes a cut only at fifty.

[原文定位](https://arxiv.org/html/2610.21405v1#A4.SS0.SSS0.Px3)

With a budget of ten, S2 deletes E1 from a pool of 10 and E1 and E3 from a pool of 20; the pool holds at most one evidence turn per link, S2 deletes what it holds, the budget never binds, and the fact stays derivable. From a pool of 30, E2 is in the pool and never selected, although with E1 it would complete the hiring cut: it reads as a routine record of a hire and says nothing about ownership. At 40, E5 joins the deleted turns. At 50, E6 enters the pool and is deleted; the relationship link has lost both evidence turns, and the fact is no longer derivable. At 60, E4 is deleted as well, emptying the ownership link too. E7 enters no pool we ran. In miniature, this is why the budget curve of Figure 3b is flat while the pool curve of Figure 3a falls.

### S71 · Following entities could reach a complete cut.

[原文定位](https://arxiv.org/html/2610.21405v1#A4.SS0.SSS0.Px4)

Every evidence turn is one hop from an entity the request refers to: Ravi, the CFO, links to E2, E5, E6, and E7; Arden, the firm, to E1, E2, E3, and E4; Nina, the wife, to E3, E4, E5, and E6. In this example, entity expansion could place a complete cut within a ten-turn pool; its effectiveness as a deletion strategy remains untested.

### S72 · Appendix E Additional Related Work

[原文定位](https://arxiv.org/html/2610.21405v1#A5)

Beyond the five memories evaluated here, other agent memories (Park et al., 2023; Wang et al., 2023; Xu et al., 2025; Rasmussen et al., 2025; Gutiérrez et al., 2024; Zhu et al., 2026; Park, 2026) vary the same two properties (§6.2). Long-term memory is also evaluated for recall (Xu et al., 2022; Tan et al., 2025); forgetting in model parameters is studied through unlearning and knowledge editing (Jang et al., 2023; Maini et al., 2024; Shi et al., 2025; Meng et al., 2022; Zhong et al., 2023); and contextual-privacy benchmarks test whether models disclose information in the wrong context (Mireshghallah et al., 2024; Shao et al., 2024).
