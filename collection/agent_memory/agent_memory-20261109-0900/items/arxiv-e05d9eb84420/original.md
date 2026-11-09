---
schema_version: 1
kind: original_snapshot
title: 'From Memory Hits to Answerable Evidence: Query-Conditioned Memory Compilation
  for Long-Term Agent Memory'
source_id: paper-0038cf95-bc43-4519-979f-d764269fb589
source: arXiv
authors:
- Li, Shangze
- Yao, Yanyu
- Xu, Derong
- Zheng, Zhi
- Xu, Tong
published_at: '2026-10-16'
source_version: v1
topics:
- agent_memory
source_url: https://arxiv.org/abs/2610.23313v1
captured_at: '2026-11-09T07:43:51.753356+00:00'
content_sha256: 798769fd9d2f4502650c40d7692ffe29fe1c1bcdb13e8f28d2d1fbe34e738cc2
coverage: full_text
research_coverage: full_text
---

# From Memory Hits to Answerable Evidence: Query-Conditioned Memory Compilation for Long-Term Agent Memory

> 原文抽取归档，用于阅读及重放，内容不代表已核实的研究结论。

- [打开来源原文](https://arxiv.org/abs/2610.23313v1)。
- 原文归档保存完整可用抽取文本；绑定的模型材料范围为 `full_text`，可小于本归档。
- 归档自身不表示已经执行研究或审阅；实际执行与审阅状态以对应研究回执为准。
- 不保存可执行网页、PDF 版式或图片，不保证公式和图表的抽取完整性，未复现实验。
- 抽取方式：`html`；抽取范围：`full_text`。
- 抽取限制：Text extraction does not verify figures, layout, or faithful mathematical rendering.
- 取材：html / success / extracted。

## 获取记录

- [text/html](https://arxiv.org/abs/2610.23313v1)；响应 SHA-256：`e088cb52eb626d56f33248ac80f1a1337f4bf281335879e2029da4c55ab43390`；抓取时间：2026-11-09T07:43:31.909267+00:00。
- [text/html](https://arxiv.org/html/2610.23313v1)；响应 SHA-256：`9e66d483f9c271a37ddfc8fe39fe9d7b8b3073e94544a16793923f081cd8856d`；抓取时间：2026-11-09T07:43:35.093521+00:00。

## 抽取正文

### S1 · From Memory Hits to Answerable Evidence: Query-Conditioned Memory Compilation for Long-Term Agent Memory

[原文定位](https://arxiv.org/html/2610.23313v1)

Shangze Li

Affiliation: State Key Laboratory of Cognitive IntelligenceUniversity of Science and Technology of China, Hefei, China

{lishangze ,yyyao, derongxu}@mail.ustc.edu.cn, {zhengzhi97, tongxu}@ustc.edu.cn

Yanyu Yao

Affiliation: State Key Laboratory of Cognitive IntelligenceUniversity of Science and Technology of China, Hefei, China

{lishangze ,yyyao, derongxu}@mail.ustc.edu.cn, {zhengzhi97, tongxu}@ustc.edu.cn

Derong Xu

Affiliation: State Key Laboratory of Cognitive IntelligenceUniversity of Science and Technology of China, Hefei, China

{lishangze ,yyyao, derongxu}@mail.ustc.edu.cn, {zhengzhi97, tongxu}@ustc.edu.cn

Zhi Zheng

Affiliation: State Key Laboratory of Cognitive IntelligenceUniversity of Science and Technology of China, Hefei, China

{lishangze ,yyyao, derongxu}@mail.ustc.edu.cn, {zhengzhi97, tongxu}@ustc.edu.cn

Tong Xu

Affiliation: State Key Laboratory of Cognitive IntelligenceUniversity of Science and Technology of China, Hefei, China

{lishangze ,yyyao, derongxu}@mail.ustc.edu.cn, {zhengzhi97, tongxu}@ustc.edu.cn

### S2 · Abstract

[原文定位](https://arxiv.org/html/2610.23313v1#abstract1)

Long-term agent memory requires recovering answer-relevant evidence dispersed across turns and sessions. Existing systems increasingly use structured memories and adaptive retrieval, yet often pass retrieved or expanded units directly to the reader, coupling memory addressing with evidence presentation and leaving the final context redundant or incomplete. To address this gap, we propose MemCompile, a query-conditioned evidence compilation framework for long-term conversational memory. Given a query, the Address Plane locates relevant support through compact source-linked descriptors and capacity-aware Cells, while a normalization boundary resolves heterogeneous retrieval hits to stable SourcePacket identities. Its Evidence Plane then allocates a bounded evidence budget across complementary packets, admits limited additional support, and renders the retained claims associated with each selected packet into an answer-ready context. MemCompile achieves 80.52% Judge Accuracy on LoCoMo and extends the empirical quality–cost Pareto frontier to a higher-quality regime. Its strong performance on LongMemEval-S further suggests that the benefits of query-conditioned compilation generalize across long-term conversational-memory benchmarks.

The implementation code is publicly available at https://github.com/MINE-USTC/MemCompile

Figure 1: Motivation and overview of MemCompile.

Existing memory systems face different trade-offs in retrieval units

and evidence representation. MemCompile addresses these challenges

through source-normalized retrieval, complementary evidence selection,

and packet-scoped reader-view compilation.

### S3 · 1 Introduction

[原文定位](https://arxiv.org/html/2610.23313v1#S1)

Long-term memory is essential for interactive agents to sustain coherent, personalized, and reliable behavior across sessions. By carrying forward user preferences, past events, commitments, and evolving states, it allows an agent to respond in light of what has happened before Maharana et al. (2024); Wu et al. (2025). However, the information needed for a new query may be distributed across distant turns and sessions or revised by later interactions. Persistent interaction therefore depends not only on retaining past information, but also on making the relevant parts of an accumulated history accessible when needed.

Foundational long-term memory systems addressed this need by extracting and retrieving salient records, including persistent memories and atomic conversational facts Zhong et al. (2023); Chhikara et al. (2025). Subsequent work improved access by compressing dialogue into facts, notes, summaries, profiles, and events, and by organizing these representations in graphs or hierarchies Xu et al. (2025); Rasmussen et al. (2025); Liu et al. (2026); Yao et al. (2026). As retrieval representations became increasingly compact and structured, recent work began to distinguish the units used to locate memory from the evidence exposed to the reader. AnchorMem reconstructs immutable contexts from retrieved fact anchors, xMemory adaptively discloses segments or raw messages from a hierarchy, and MemIR projects heterogeneous retrieval cues into provenance-scoped claim bundles Shen et al. (2026); Hu et al. (2026); Jin et al. (2026). Together, these developments move long-term memory systems from improving addressability toward separating memory location from evidence presentation.

However, this separation remains incomplete: the retrieved representation, or the expansion attached to it, still largely determines the context presented to the reader. Existing systems therefore do not fully separate two decisions: which underlying conversation sources should receive the limited evidence budget, and how evidence from those sources should be represented for answer generation. This coupling is problematic because the two decisions favor different properties. Address representations should be compact, discriminative, and broad enough to support reliable recall, whereas reader evidence should preserve relevant qualifications, connect complementary facts, and avoid unnecessary context. When a single unit serves both purposes, the system must accept a fixed trade-off. As illustrated in Figure 1, an atomic claim may be easy to retrieve but may omit causal relationships or sibling facts from the same source. A raw turn preserves such details but may reintroduce noise, such as greetings and irrelevant dialogue, whereas a hierarchy node can provide an effective navigation unit without matching the granularity required for answer generation. Moreover, without an explicit source-level boundary, multiple claims or retrieval channels may allocate context budget repeatedly to the same underlying source. This coupling not only creates avoidable quality loss after successful retrieval, but also makes it difficult to distinguish failures of source recovery from failures of evidence presentation.

In this paper, we propose MemCompile, a source-normalized evidence compiler for long-term conversational memory. Its central principle is to locate relevant information through compact representations and allocate the evidence budget at the level of original dialogue turns while generating from a separately compiled reader view. MemCompile realizes this principle through an Address–Evidence two-plane architecture. The Address Plane organizes source-linked atomic descriptors into capacity-bounded Cells and combines diminishing-benefit Cell routing with lexical retrieval to construct primary source candidates while a broader dense packet pool supplies proposals for bounded semantic refinement. An explicit normalization boundary resolves these heterogeneous results to stable SourcePacket identities, ensuring that one underlying source occupies one evidence unit regardless of how many descriptors or channels locate it. The Evidence Plane then selects complementary packet identities, preserves the initial anchors while admitting bounded additional support, completes evidence within each selected packet, and compiles the result into a reader-facing view. By separating packet selection from textual rendering, MemCompile can optimize and evaluate source recovery and evidence presentation as distinct decisions.

Our main contributions are summarized as follows:

•

We formulate long-term memory serving as query-conditioned evidence compilation, distinguishing two decisions that are commonly coupled: which underlying sources receive the evidence budget and how evidence from those sources is represented to the reader.

•

We introduce MemCompile, an Address–Evidence two-plane architecture that addresses memory through compact derived views, allocates evidence budget at the level of immutable SourcePackets, and generates from a separately compiled reader view.

•

Comprehensive evaluations on long-term memory

benchmarks demonstrate that MemCompile consistently outperforms state-of-the-art baselines while extending the empirical quality–cost Pareto frontier. On the LoCoMo benchmark, packet-scoped compilation improves F1 by 15.26 points and Judge Accuracy by 23.51 points over representative-claim rendering.

### S4 · Structured long-term memory for LLM agents

[原文定位](https://arxiv.org/html/2610.23313v1#S2.SS0.SSS0.Px1)

Early long-term memory systems store and retrieve salient interaction records to support persistent personalization and multi-session reasoning. MemoryBank combines retrieval with time-dependent forgetting and memory reinforcement, while Mem0 extracts and consolidates conversational facts into vector- and graph-based stores Zhong et al. (2023); Chhikara et al. (2025). Subsequent systems construct richer memory organizations. A-MEM creates dynamically linked notes whose attributes and relations evolve as new experiences arrive while Zep represents evolving conversational knowledge in a temporal graph Xu et al. (2025); Rasmussen et al. (2025). Other approaches improve information density or associative access through

semantic compression, atomic facts, profiles, events, and higher-level memory scenes Liu et al. (2026); Yao et al. (2026).

### S5 · Reconstructive and adaptive memory access

[原文定位](https://arxiv.org/html/2610.23313v1#S2.SS0.SSS0.Px2)

Recent systems recognize that a representation useful for locating memory need not be self-contained answer evidence. AnchorMem retrieves atomic facts as anchors and reconstructs their associated raw contexts and events Shen et al. (2026). xMemory organizes intact memory units into a revisable hierarchy and adaptively discloses episodes or raw messages when additional

detail reduces reader uncertainty Hu et al. (2026). MemIR takes a typed approach, separating raw evidence, retrieval cues, and truth-bearing claims, and projecting heterogeneous hits into provenance-scoped claim bundles exposed through a normalized fact

interface Jin et al. (2026). MemCompile builds on the shared insight that retrieval representations and answer evidence serve different purposes, but places its architectural boundary at a different level. MemCompile instead resolves derived

address results to immutable SourcePacket identities before evidence selection. This source-normalized boundary makes it possible to vary and evaluate reader representation while holding the selected source set fixed.

### S6 · 3.1 Problem Formulation

[原文定位](https://arxiv.org/html/2610.23313v1#S3.SS1)

Let a conversational history be

\mathcal{H}=(\mathcal{P},\prec) , where

\mathcal{P}=\{p_{1},\ldots,p_{N}\} contains the original dialogue turns

and \prec denotes their temporal order. Each turn p_{i} includes its

speaker, session, interaction time, and content. Given a query q , the

task is to construct an ordered and bounded reader context X_{q} grounded

in \mathcal{H} . The context should contain sufficient and complementary

support for answering q , preserve traceability to the original dialogue

turns, and limit irrelevant or redundant content.

### S7 · 3.2 Address Plane

[原文定位](https://arxiv.org/html/2610.23313v1#S3.SS2)

MemCompile instantiates each original turn p_{i}\in\mathcal{P} as an

immutable SourcePacket that stores its speaker, session, interaction

time, raw content, and stable identifier. The Address Plane builds compact source-linked descriptors and organizes them for complementary retrieval. Its objective is to preserve source coverage under fixed limits on opened Cells and sparse and dense candidate pools.

Figure 2: The overall architecture of MemCompile

### S8 · 3.2.1 Source-Linked Atomic Descriptors

[原文定位](https://arxiv.org/html/2610.23313v1#S3.SS2.SSS1)

From immutable SourcePackets, MemCompile constructs the descriptor

set \mathcal{X}=\{x_{1},\ldots,x_{M}\} . Each descriptor retains a foreign key to its owning SourcePacket,

\pi:\mathcal{X}\rightarrow\mathcal{P}.

(1)

For each SourcePacket, a large language model extracts standalone factual claims while

using the immediately preceding turn to resolve local references. A retained

descriptor is

\displaystyle x_{i}=\bigl(f_{i},d_{i},s_{i},j_{i},t_{i},\mathsf{Per}_{i},\mathsf{Key}_{i},\tau_{i},\bar{\tau}_{i},n_{i},\pi_{i}\bigr),

(2)

where f_{i} is the claim text, d_{i} is the dialogue-turn identifier, s_{i}

is the speaker, j_{i} is the session index, and t_{i} is the recorded session

time. \mathsf{Per}_{i} and \mathsf{Key}_{i} are the extracted people and

keyword sets; \tau_{i} and \bar{\tau}_{i} are the described-event time and

interaction time; n_{i} is the claim token count; and

\pi_{i}\in\mathcal{P} is its SourcePacket foreign key. Claims provide sparse

and semantic retrieval keys while preserving a path to their originating

dialogue evidence.

### S9 · 3.2.2 Bounded Cell Placement

[原文定位](https://arxiv.org/html/2610.23313v1#S3.SS2.SSS2)

Cells are capacity-constrained routing structures over atomic descriptors.

Let \mathcal{C} be the set of Cells. Descriptor x_{i} is feasible for cell c only if

\operatorname{Token}(c)+n_{i}\leq B_{C},\qquad|c|<M_{C},

(3)

where B_{C} is the token capacity and M_{C} is the item capacity. A feasible

Cell is scored by

\displaystyle S_{\mathrm{place}}(i,c)={}

\displaystyle L(i,c)+\beta C(i,c)

(4)

\displaystyle}{\displaystyle-\gamma X(i,c)-\eta E(i,c),

where L , C , X , and E respectively measure metadata locality, weighted

keyword–person–time coherence, polarity inconsistency, and capacity/entropy

pressure. Creating a new Cell is an additional candidate with expansion

pressure 0.65+n_{i}/B_{C} . The highest-scoring candidate receives x_{i} .

Placement is serialized in dialogue and claim order, producing a fixed Cell

layout before query serving. Appendix B

specifies every score component, hyperparameter, and stopping condition.

### S10 · 3.2.3 Diminishing-Benefit Cell Routing

[原文定位](https://arxiv.org/html/2610.23313v1#S3.SS2.SSS3)

For a query q , we calculate the query relevance u(c,q) for each cell based on the normalized query term set of q and the person set.

Given the set of memory units \mathcal{O}_{t} opened before round t , the marginal benefit of candidate memory cell c is denoted as g(c\mid\mathcal{O}_{t},q) :

g(c\mid\mathcal{O}_{t},q)=u(c,q)\left[1-\lambda_{R}J\!\left(M_{c},M_{\mathcal{O}_{t}}\right)\right]-\kappa_{\mathrm{open}}

(5)

Here, u(c,q) combines keyword, person, time, and density signals and J(A,B) denotes Jaccard similarity between two sets.

M_{c} contains the Cell’s people and keywords, and M_{\mathcal{O}_{t}} is their

cumulative set over opened Cells. The implementation sets \lambda_{R}=0.45

and defines \kappa_{\mathrm{open}} as an opening cost that increases with the number of

opened Cells plus a token-proportional reading cost. Cells are opened greedily

until the marginal gain or relative-utility criterion fails, the cumulative

utility reaches its threshold, or the six-Cell cap is reached. Exact

weights and stopping conditions appear in Appendix B.3.

### S11 · 3.2.4 Multi-Channel Candidate Union

[原文定位](https://arxiv.org/html/2610.23313v1#S3.SS2.SSS4)

BM25 ranks all atomic descriptors and supplies a lexical channel alongside

Cell routing; its top eight descriptors also act as Cell-routing seeds. Let

\mathcal{C}_{q} denote the opened Cell set, the complete address candidate pool is

\displaystyle\mathcal{K}_{q}={}

\displaystyle\bigcup_{c\in\mathcal{C}_{q}}\operatorname{claims}(c){}\cup\operatorname{BM25}(q),

(6)

where \operatorname{BM25}(q) denotes the top 96 lexical candidates.

For x_{i}\in\mathcal{K}_{q} , let \mathsf{Term}_{i} be the normalized claim

terms and let b_{i} be its normalized BM25 score, or zero when it is not

returned by the lexical channel. Its candidate score is

\displaystyle r_{i}={}

\displaystyle\alpha_{f}J(\mathsf{Term}_{q},\mathsf{Term}_{i})+\alpha_{k}J(\mathsf{Term}_{q},\mathsf{Key}_{i})

(7)

\displaystyle+\alpha_{p}J(\mathsf{Per}_{q},\mathsf{Per}_{i})+\alpha_{t}\mathbf{1}_{t}(i,q)+\alpha_{b}b_{i},

where \mathbf{1}_{t}(i,q) indicates that a temporal query matches a descriptor

with normalized time. The coefficients are specified in

Appendix B.3. The descriptors in the union are then

reordered according to the candidate score.

In parallel with structured Cell routing, the supplemental channel performs global semantic retrieval over the complete packet collection. Let K_{D} denote the semantic proposal depth. It encodes the enriched query q^{+} and each packet document z(p) , and selects the K_{D} packets with the highest

cosine similarity; we use K_{D}=40 in the reported configuration:

\mathcal{D}_{q}=\operatorname{TopK}^{K_{D}}_{p\in\mathcal{P}}\operatorname{cos}\!\left(e(q^{+}),e(z(p))\right).

### S12 · 3.3 Plane Transition via Source-Normalization Boundary

[原文定位](https://arxiv.org/html/2610.23313v1#S3.SS3)

The candidate pool \mathcal{K}_{q} contains address hits rather than distinct

pieces of evidence. Several claims can paraphrase the same dialogue turn,

and the same claim can be reached through both BM25 and one or more Cells. We

therefore resolve every claim through

\rho(x_{i})=\pi_{i}\in\mathcal{P}

(8)

and collapse all candidates with the same resolved packet. The normalized

packet pool is

\displaystyle\mathcal{U}_{q}=\bigl\{p\in\mathcal{P}:{}

\displaystyle\exists x_{i}\in\mathcal{K}_{q},\rho(x_{i})=p\bigr\},

(9)

with packet score

s(p,q)=\max_{\begin{subarray}{c}x_{i}\in\mathcal{K}_{q}\\

\rho(x_{i})=p\end{subarray}}r_{i}.

(10)

This many-to-one transition

separates the multiplicity of retrieval keys from the amount of evidence:

multiple successful addresses to one turn create one evidence candidate, not

multiple budget items.

### S13 · 3.4 Evidence Plane

[原文定位](https://arxiv.org/html/2610.23313v1#S3.SS4)

The Evidence Plane converts the normalized packet candidates into a bounded

and coherent context. We organize it around the two decisions: how to compile a selected packet,

and when to supplement the selected packet set.

### S14 · 3.4.1 Complementary Packet Scheduling

[原文定位](https://arxiv.org/html/2610.23313v1#S3.SS4.SSS1)

A closed-pool listwise scheduler receives q and \mathcal{U}_{q} and selects

K_{0}=10 complementary SourcePackets,

\mathcal{A}_{0}(q)=\operatorname{Schedule}_{K_{0}}(q,\mathcal{U}_{q}),

(11)

where \mathcal{A}_{0}(q) is the baseline evidence anchor set. Each candidate is

rendered with an opaque label, dialogue identifier, speaker, recorded date,

and source content. The scheduler is instructed to rank direct answer-bearing

packets first while retaining complementary packets for relational, temporal,

comparative, and list questions. It returns exactly K_{0} distinct labels in

descending usefulness; labels are validated against the closed pool and

resolved back to SourcePacket identities. The scheduler can therefore reorder

and select only packets in \mathcal{U}_{q} . Appendix A.2

provides the complete request construction, output validation, and prompt.

After this transition,

Cells, claim multiplicity, and retrieval-channel identity no longer define the

evidence state; the Evidence Plane operates over SourcePackets and their

reader projections.

### S15 · 3.4.2 Anchor-Preserving Bounded Frontier

[原文定位](https://arxiv.org/html/2610.23313v1#S3.SS4.SSS2)

Source-scoped claim-bundle rendering improves the usability of selected evidence, while

the frontier addresses support that is absent from the baseline anchor set. The closed frontier pool is

\mathcal{W}_{q}=\mathcal{A}_{0}(q)\cup\mathcal{D}_{q}.

(12)

A listwise reranker returns an ordering \sigma_{q} over \mathcal{W}_{q} . The

system examines its first K_{R}=5 positions and admits at most K_{\Delta}=2

previously unselected packets:

\displaystyle\Delta(q)

\displaystyle=\operatorname{First}_{K_{\Delta}=2}\left(\sigma_{q}[1{:}K_{R}]\setminus\mathcal{A}_{0}(q)\right),

(13)

\displaystyle\mathcal{E}_{q}

\displaystyle=\mathcal{A}_{0}(q)\cup\Delta(q).

(14)

Here \operatorname{First}_{m}(S) returns the first at most m elements of an

ordered sequence S while preserving their order. The construction preserves the baseline anchors and bounds the evidence change.

In Appendix C.2.1 we report the sensitivity of reranking cutoff and append cap.

### S16 · 3.4.3 Reader-View Compilation

[原文定位](https://arxiv.org/html/2610.23313v1#S3.SS4.SSS3)

After obtaining the final ordered SourcePacket sequence \mathcal{E}_{q} , we

construct a source-scoped claim-bundle view for each packet p :

B_{p}=\left\langle x\in\mathcal{X}\mid\pi(x)=p\right\rangle_{\prec_{\mathcal{X}}}.

(15)

The system retrieves every retained atomic claim originating from p , formats

the bundle with the packet timestamp, and concatenates the evidence blocks in

packet scheduling order. This compilation is complete with respect to the

retained descriptor set, rather than a reconstruction of the packet’s raw text. Let \mathcal{E}_{q}=\langle p_{1},\ldots,p_{L}\rangle be the final scheduled

packet sequence. The final reader context is

X_{q}=\operatorname{Render}(p_{1},B_{p_{1}})\mathbin{\|}\cdots\mathbin{\|}\operatorname{Render}(p_{L},B_{p_{L}}),

(16)

where \| denotes order-preserving concatenation of the rendered evidence blocks.

### S17 · 4 Experiments

[原文定位](https://arxiv.org/html/2610.23313v1#S4)

Our experiments are designed to answer four central research questions:

RQ1 Does MemCompile deliver meaningful performance improvements over long-term-memory baselines under the same evaluation protocol?

RQ2 Does bounded Cell placement improve fixed-budget source recovery, and how does it complement the Evidence Plane? RQ3 Does budgeting by SourcePacket reduce source aliasing and distinguish source-recovery failures from evidence-presentation failures?

RQ4 Given the same recovered SourcePackets, how does reader-view granularity affect answer quality?

### S18 · Datasets

[原文定位](https://arxiv.org/html/2610.23313v1#S4.SS1.SSS0.Px1)

We evaluate MemCompile on LoCoMo Maharana et al. (2024) and LongMemEval Wu et al. (2025) benchmarks. LoCoMo evaluates long-term conversational memory over extended, multi-session dialogues which contains ten conversations, each comprising roughly 600 dialogue turns and 16K tokens on average. LongMemEval-s evaluates the ability of chat assistants to retain and use information across sustained user-assistant interactions, which contains 500 questions, each embedded in a history of approximately 115K tokens.

### S19 · Baselines and Metrics

[原文定位](https://arxiv.org/html/2610.23313v1#S4.SS1.SSS0.Px2)

We compare against representative long-term memory systems spanning flat, atomic, graph, and hierarchical designs including MemoryBank Zhong et al. (2023), A-Mem Xu et al. (2025), Mem0 Chhikara et al. (2025), MemoryOS Kang et al. (2025), LightMem Fang et al. (2026)

, AnchorMem Shen et al. (2026), xMemory Hu et al. (2026)

, SimpleMem Liu et al. (2026), AtomMem Yao et al. (2026).

We report token-level F1, BLEU-1 Papineni et al. (2002) and Judge accuracy Zheng et al. (2023). We report token cost through memory construction and query-time retrieval/generation. For Open-Domain questions, we do not

use F1 or BLEU-1 for cross-method comparisons due to this category require combining conversational evidence

with commonsense or world knowledge and may admit multiple

lexically divergent yet semantically valid answers.

### S20 · Experimental Details

[原文定位](https://arxiv.org/html/2610.23313v1#S4.SS1.SSS0.Px3)

Unless otherwise specified, all generative components of MemCompile use gpt-4o-mini with temperature 0 and default top- p , and set the maximum output length to 2,048 tokens. Dense retrieval uses text-embedding-3-small without task-specific fine-tuning or dimensionality reduction.

The LLM-as-a-Judge metric employs gpt-5-nano with a rigorous evaluation prompt to assess semantic correctness.

To ensure a controlled comparison, we rerun all baselines under the same evaluation protocol while preserving their method-specific memory construction and retrieval mechanisms. All methods are evaluated on the same dataset release and use the same model configuration including the same backbone model and the same answer/judge prompt.

Single-Hop

Multi-Hop

Temporal

Open-Domain

Overall

Method

F1 \uparrow

BLEU-1 \uparrow

J \uparrow

F1 \uparrow

BLEU-1 \uparrow

J \uparrow

F1 \uparrow

BLEU-1 \uparrow

J \uparrow

J \uparrow

F1 \uparrow

BLEU-1 \uparrow

J \uparrow

Tokens (K)

LoCoMo

37.81

26.23

57.07

20.97

11.09

48.58

34.79

15.46

38.01

41.67

33.85

20.88

50.58

827.20

MemoryBank

17.85

12.13

46.61

11.25

8.20

28.01

14.26

9.60

34.27

23.96

15.76

10.80

39.22

926.98

A-Mem

33.87

27.64

54.10

21.17

15.40

43.26

34.13

29.98

34.89

32.29

31.45

25.77

46.75

11,687.58

Mem0

54.95

44.71

82.40

36.02

25.25

60.99

30.36

29.69

33.02

50.00

45.79

37.57

66.17

55,300.30

MemoryOS

49.72

43.58

66.47

37.15

26.87

60.99

41.99

36.32

34.58

51.04

45.55

38.70

57.86

19,207.67

LightMem

49.30

42.45

71.58

36.59

27.27

62.41

47.41

41.29

57.63

44.79

46.40

39.23

65.32

5,021.56

AnchorMem

57.73

50.91

81.09

34.82

25.97

57.45

23.47

18.40

42.37

36.46

45.64

38.81

65.91

5,840.46

xMemory

50.26

43.81

81.81

40.13

31.77

64.89

53.36

47.33

60.44

44.79

48.97

42.24

71.95

17,573.40

SimpleMem

51.18

44.75

75.98

38.50

30.82

64.18

31.66

26.48

38.94

42.71

44.36

37.97

64.03

18,077.08

AtomMem

54.43

47.56

76.20

39.76

31.43

66.31

57.73

52.46

65.73

48.95

52.30

45.50

70.51

24,553.27

MemCompile

59.41

51.98

88.59

41.20

32.59

75.00

59.82

54.03

73.52

49.48

55.94

48.65

80.52

26,720.82

Table 1: LoCoMo category and overall results. Best results are bold and second-best results are underlined. Tokens exclude judging and embedding.

Overall

Setting

F1 \uparrow

BLEU-1 \uparrow

Recall \uparrow

Judge \uparrow

A0 Full system

55.94

48.65

85.50

80.52

A1 w/o frontier

51.78

44.87

80.84

74.94

A2 w/o scheduler and frontier

42.00

36.01

51.99

60.91

A3 w/o scheduler, with frontier

51.91

44.75

76.55

75.26

A4 Cell-only route

50.64

43.85

69.85

71.88

A5 BM25-only route

52.31

45.14

81.54

77.53

A6 w/o query intent

53.61

46.47

84.84

77.34

A7 Dense SourcePacket Top-10

48.80

42.23

65.69

70.91

Table 2: Controlled pipeline-path ablations on LoCoMo. A1 retains the packet anchors returned by Complementary Packet Scheduling but disables subsequent semantic-frontier

expansion. A2 and A3 replace the scheduled anchors with deterministic dialogue-level MMR Top-10 anchors, the scoring function and weights are detailed in Appendix B.3. A7 directly selects the dense cosine Top-10

SourcePackets and presents their claim bundles to the Reader.

Figure 3: RQ1 quality-cost comparison, blue squares form the empirical Pareto frontier.

### S21 · 4.2 RQ1: Analysis of End-to-End Quality and Cost

[原文定位](https://arxiv.org/html/2610.23313v1#S4.SS2)

On LoCoMo, Table 1 shows that MemCompile ranks first on all reported single-hop, multi-hop, and temporal metrics and obtains the best overall F1/BLEU/Judge scores of 55.94/48.65/80.52. Besides the dominant performance on Single-Hop, MemCompile achieves substantial improvements over the strongest baseline on Multi-Hop and Temporal, increasing the J score by 8.69 and 7.79 percentage points. This consistent enhancement across direct, compositional, and time-sensitive queries confirms the effectiveness of separating multi-view addressing from source-budgeted evidence compilation: source normalization preserves precise direct recall, while complementary scheduling and packet-scoped rendering remain effective when evidence is distributed across sources or time.

Figure 3 illustrates the corresponding quality-cost trade-off. Compared with Mem0, MemCompile improves Judge by 14.35 points while using 51.7% fewer tokens (26.72M vs. 55.30M). AtomMem provides the closest cost comparison: MemCompile uses only 8.8% more tokens (26.72M vs. 24.55M), yet improves overall Judge by 10.01 points. Thus, although MemCompile does not minimize absolute token usage, it converts a moderate computational budget into substantially higher answer quality and extends the empirical frontier to 80.52% Judge. The detailed per phase cost accounting is in Appendix E.

On LongMemEval-S, MemCompile shows strong cross-benchmark performance. On temporal reasoning and single-session assistant, MemCompile increases the J score by 24.1 and 50 percentage points comparing with Mem0. Table 7 in Appendix D reports the full results.

### S22 · 4.3 RQ2: Analysis of Cell Placement

[原文定位](https://arxiv.org/html/2610.23313v1#S4.SS3)

We first compare five placement layouts that organize the same memory items under a fixed candidate budget. Detailed

layouts definitions are provided in

Appendix B.4. Figure 5 shows that structured placement improves candidate recovery across complementary query types. Bounded Cell produces the largest gains on single-hop and multi-hop questions, increasing recall by 5.13 percentage points (pp) and 3.42 pp, respectively. It also improves temporal recall by 1.71 pp and open-domain recall by 2.78 pp.

The upstream coverage improvement carries into the Evidence Plane. Removing Cell-routed candidates while keeping the downstream scheduler and evidence compilation pipeline fixed reduces final recall to 81.54%, a decrease of 3.96 percentage points, F1 to 52.31, BLEU-1 to 45.14, and Judge to 77.53%. Cell placement expands the set of answer-relevant addresses available to the Evidence Plane, and the downstream pipeline converts this additional source coverage into measurable answer-quality gains.

Controlled stage ( K=10 )

Unique \uparrow

DBR \downarrow

Gold \uparrow

\Delta Gold vs. previous (95% CI)

Robust

Unnormalized claim top- K

7.690

23.08

48.89

—

—

Exact-text deduplication

7.742

22.56

48.56

-0.33 [ -0.87 , 0.21]

—

Source-normalized top- K

9.988

0.00

51.91

+3.35 [2.45, 4.26]

\dagger

+ Complementary source scheduler

9.988

0.00

80.84

+28.93 [26.81, 31.14]

\dagger

Table 3: Controlled source selection at K=10 . Gold Recall and DBR are percentages. Gold differences are percentage points with paired question-bootstrap 95% CIs; \dagger means that both question-level and conversation-cluster CIs exclude zero.The source-normalized Top- K ranks packets directly by the maximum claim score.

### S23 · Multiple hits repeatedly occupy the same source slots

[原文定位](https://arxiv.org/html/2610.23313v1#S4.SS4.SSS0.Px1)

Table 5 exposes the mismatch between hit count and source coverage. A Top-20 ranking contains 20 hits but only 14.60 distinct sources on average while same-source hits consume 27.02% of the nominal budget and affect 97.27% of questions. Thus adding hits or channels does not translate directly into broader evidence coverage.

### S24 · source normalization releases duplicate address slot

[原文定位](https://arxiv.org/html/2610.23313v1#S4.SS4.SSS0.Px2)

Table 3 indicates that standard text deduplication provides almost no improvement against directly sending top-10 claims into the reader. While Source normalization instead resolves every hit to its SourcePacket key before applying the budget, yielding a significant but moderate Gold Recall gain of 3.35 pp.

### S25 · Complementary scheduling converts released capacity into coverage

[原文定位](https://arxiv.org/html/2610.23313v1#S4.SS4.SSS0.Px3)

Complementary scheduling reallocates the normalized slots toward sources that add missing support. Crucially, the number of distinct sources remains 9.988 and DBR remains zero, while Gold Recall rises from 51.91% to 80.84%—a +28.93 pp gain [26.81, 31.14]. Figure 4 also shows the same large scheduling gain in every category. The contrast separates the two mechanisms: normalization prevents redundant sources from consuming the budget; scheduling determines which complementary sources fill that budget.

### S26 · 4.5 RQ4: Analysis of Reader Evidence Granularity

[原文定位](https://arxiv.org/html/2610.23313v1#S4.SS5)

Table 4 isolates evidence presentation by holding the final SourcePacket exactly constant. Compressing each selected packet to a single representative claim reduces Judge from 80.52% to 57.01% indicating that aggressive compression can discard answer-bearing relations, temporal qualifiers, and other context needed to interpret an otherwise correct source.

Presenting the raw SourcePacket recovers much of this loss, reaching 75.32% Judge, but remains significantly below the complete claim bundle. The compiled bundle preserves the relations and qualifications lost by single-claim compression while filtering the conversational noise retained by raw dialogue. This fixed-source comparison isolates evidence presentation as a separate design problem from source recovery.

### S27 · 4.6 Ablation Study

[原文定位](https://arxiv.org/html/2610.23313v1#S4.SS6)

Table 2 compares controlled pipeline paths while

holding the frozen memory and claim-bundle Reader fixed. The full system

achieves the strongest performance across all reported metrics.

A0-A3 separate the effects of anchor construction and subsequent

frontier expansion. These comparisons reveal that frontier expansion compensates most strongly for weaker deterministic anchors, while complementary packet scheduling produces a stronger initial evidence set and reduces reliance on later expansion.

The A4 and A5 variants show an asymmetric complementarity between

BM25 and Cell routing. BM25 provides the stronger standalone route,

whereas adding Cell-derived candidates to BM25 supplies non-redundant

evidence that improves the full pipeline. A6 further suggests that

structured query intent primarily improves evidence prioritization rather

than source coverage while A7 shows that directly retrieving the dense

cosine Top-10 SourcePackets and presenting their claim bundles to the

Reader does not match the compiled pipeline.

Fixed-packet view

F1 \uparrow

BLEU-1 \uparrow

Judge \uparrow

Representative claim

40.68

35.13

57.01

Raw SourcePacket

53.00

46.01

75.32

Full claim bundle

55.94

48.65

80.52

Table 4: Reader-view ablation at identical packet Recall (85.50%).

### S28 · 5 Conclusion

[原文定位](https://arxiv.org/html/2610.23313v1#S5)

We introduced MemCompile, an Address-Evidence dual-plane architecture that separates memory location from reader-facing compilation. The Address Plane improves addressing and memory placement through organizing source-linked atomic descriptors in bounded Cells. Source normalization then releases duplicate address slot by resolving cross-channel hits to its SourcePacket key; the Evidence Plane schedules complementary sources, preserves initial anchors during bounded expansion, and compiles packet-scoped claims. Experiments on the LoCoMo benchmark confirm that MemCompile achieves state-of-the-art performance while the result on LongMemEval-S demonstrates strong cross-benchmark performance. Ultimately, MemCompile offers a source-normalized and cost-effective evidence-compilation framework for deploying intelligent agents capable of sustaining reliable,

evidence-grounded long-term interactions.

### S29 · Limitations

[原文定位](https://arxiv.org/html/2610.23313v1#Sx1)

Evaluation is limited to two conversational-memory benchmarks and proprietary LLMs; broader domains and open-model replications remain future work. Although MemCompile achieves a favorable quality-cost trade-off, its overall token consumption could be further optimized.

### S30 · References

[原文定位](https://arxiv.org/html/2610.23313v1#bib)

Chhikara et al. (2025)

P. Chhikara, D. Khant, S. Aryan, T. Singh, and D. Yadav

Mem0: building production-ready AI agents with scalable long-term memory.

External Links: 2504.19413,

Document

Cited by: Table 7,

§1,

§2,

§4.1.

Fang et al. (2026)

J. Fang, X. Deng, H. Xu, Z. Jiang, Y. Tang, Z. Xu, S. Deng, Y. Yao, M. Wang, S. Qiao, H. Chen, and N. Zhang

LightMem: lightweight and efficient memory-augmented generation.

In The Fourteenth International Conference on Learning Representations,

External Links: Link

Cited by: Table 7,

§4.1.

Hu et al. (2026)

Z. Hu, Q. Zhu, R. Zhao, D. Liang, H. Yan, Y. He, and L. Gui

Beyond rag for agent memory: retrieval by decoupling and aggregation.

External Links: 2602.02007,

Link

Cited by: §1,

§2,

§4.1.

Jin et al. (2026)

Z. Jin, B. Wang, J. Li, R. Xu, and M. Zhang

Mitigating provenance-role collapse in long-term agents via typed memory representation.

External Links: 2605.25869,

Link

Cited by: §1,

§2.

Kang et al. (2025)

J. Kang, M. Ji, Z. Zhao, and T. Bai

Memory OS of AI agent.

In Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing, C. Christodoulopoulos, T. Chakraborty, C. Rose, and V. Peng (Eds.),

Suzhou, China, pp. 25961–25970.

External Links: Link,

Document,

ISBN 979-8-89176-332-6

Cited by: §4.1.

Liu et al. (2026)

J. Liu, Y. Su, P. Xia, S. Han, Z. Zheng, C. Xie, M. Ding, and H. Yao

SimpleMem: efficient lifelong memory for LLM agents.

In Proceedings of the 43rd International Conference on Machine Learning, T. Zhang, M. Dudik, M. Jaggi, A. Agarwal, S. Li, D. Schuurmans, J. Zhu, F. Berkenkamp, H. Dong, and A. Bietti (Eds.),

Proceedings of Machine Learning Research, Vol. 306, pp. 78500–78513.

External Links: Link

Cited by: §1,

§2,

§4.1.

Maharana et al. (2024)

A. Maharana, D. Lee, S. Tulyakov, M. Bansal, F. Barbieri, and Y. Fang

Evaluating very long-term conversational memory of LLM agents.

In Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), L. Ku, A. Martins, and V. Srikumar (Eds.),

Bangkok, Thailand, pp. 13851–13870.

External Links: Link,

Document

Cited by: §1,

§4.1.

Papineni et al. (2002)

K. Papineni, S. Roukos, T. Ward, and W. Zhu

Bleu: a method for automatic evaluation of machine translation.

In Proceedings of the 40th Annual Meeting of the Association for Computational Linguistics, P. Isabelle, E. Charniak, and D. Lin (Eds.),

Philadelphia, Pennsylvania, USA, pp. 311–318.

External Links: Link,

Document

Cited by: §4.1.

Rasmussen et al. (2025)

P. Rasmussen, P. Paliychuk, T. Beauvais, J. Ryan, and D. Chalef

Zep: a temporal knowledge graph architecture for agent memory.

External Links: 2501.13956,

Link

Cited by: §1,

§2.

Shen et al. (2026)

Z. Shen, S. Cheng, Z. Guo, W. Wang, Y. Wang, and H. Huang

AnchorMem: anchored facts with associative contexts for building memory in large language models.

In Findings of the Association for Computational Linguistics: ACL 2026, M. Liakata, V. P. Moreira, J. Zhang, and D. Jurgens (Eds.),

San Diego, California, United States, pp. 34784–34798.

External Links: Link,

Document,

ISBN 979-8-89176-395-1

Cited by: §1,

§2,

§4.1.

Wu et al. (2025)

D. Wu, H. Wang, W. Yu, Y. Zhang, K. Chang, and D. Yu

LongMemEval: benchmarking chat assistants on long-term interactive memory.

In The Thirteenth International Conference on Learning Representations,

External Links: Link,

2410.10813,

Document

Cited by: §1,

§4.1.

Xu et al. (2025)

W. Xu, Z. Liang, K. Mei, H. Gao, J. Tan, and Y. Zhang

A-mem: agentic memory for llm agents.

In Advances in Neural Information Processing Systems, D. Belgrave, C. Zhang, H. Lin, R. Pascanu, P. Koniusz, M. Ghassemi, and N. Chen (Eds.),

Vol. 38, Main Conference, pp. 17577–17604.

External Links: Document,

Link

Cited by: §1,

§2,

§4.1.

Yao et al. (2026)

Y. Yao, S. Li, Z. Zheng, H. Zheng, Q. Liu, T. Xu, and E. Chen

AtomMem: building simple and effective memory system for llm agents via atomic facts.

External Links: 2606.19847,

Link

Cited by: §1,

§2,

§4.1.

Zheng et al. (2023)

L. Zheng, W. Chiang, Y. Sheng, S. Zhuang, Z. Wu, Y. Zhuang, Z. Lin, Z. Li, D. Li, E. Xing, H. Zhang, J. Gonzalez, and I. Stoica

Judging llm-as-a-judge with mt-bench and chatbot arena.

In Advances in Neural Information Processing Systems, A. Oh, T. Naumann, A. Globerson, K. Saenko, M. Hardt, and S. Levine (Eds.),

Vol. 36, pp. 46595–46623.

External Links: Document,

Link

Cited by: §4.1.

Zhong et al. (2023)

W. Zhong, L. Guo, Q. Gao, H. Ye, and Y. Wang

MemoryBank: enhancing large language models with long-term memory.

External Links: 2305.10250,

Document

Cited by: §1,

§2,

§4.1.

### S31 · A.1 Serving Pipeline

[原文定位](https://arxiv.org/html/2610.23313v1#A1.SS1)

Algorithm 1 specifies the complete serving path. The

construction stage creates one immutable SourcePacket per dialogue turn,

extracts an ordered set of atomic descriptors, records a foreign key from each

descriptor to its packet, and places the descriptors into bounded Cells. At

query time, query-only intent fields augment the lexical query. Cell routing

and BM25 produce atomic candidates, which are collapsed by SourcePacket

identity before listwise scheduling. The semantic frontier operates over a

separate packet index and can only append packets to the scheduled anchors.

Finally, the reader view is materialized without changing the selected packet

sequence.

Algorithm 1 End-to-end query-conditioned memory compilation

0:

Ordered dialogue turns \mathcal{H} , query q

0:

Reader context X_{q}

1:

\mathcal{P}\leftarrow\emptyset , \mathcal{X}\leftarrow\emptyset ,

\mathcal{C}\leftarrow\emptyset

2:

for each turn d in dialogue order do

3:

register immutable packet p_{d} with content hash

4:

extract standalone facts F_{d} using d and its preceding turn

5:

for each retained fact f\in F_{d} in extraction order do

6:

extract people, keywords, event time, and interaction time

7:

construct descriptor x and set \pi(x)\leftarrow p_{d}

8:

place x by Algorithm 2

9:

end for

10:

end for

11:

extract query-only intent I_{q} and form normalized query terms

12:

\mathcal{K}_{q}\leftarrow Cell/BM25 candidates from

Algorithm 3

13:

\mathcal{U}_{q}\leftarrow\operatorname{CollapseBySource}(\mathcal{K}_{q})

14:

\mathcal{A}_{0}\leftarrow\operatorname{ListwiseSchedule}_{10}(q,\mathcal{U}_{q})

15:

\mathcal{D}_{q}\leftarrow\operatorname{SemanticTop}_{40}(q^{+},\mathcal{P})

16:

\sigma_{q}\leftarrow\operatorname{ListwiseSchedule}(q,\mathcal{A}_{0}\cup\mathcal{D}_{q})

17:

\Delta_{q}\leftarrow first two packets in

\sigma_{q}[1{:}5]\setminus\mathcal{A}_{0}

18:

\mathcal{E}_{q}\leftarrow\mathcal{A}_{0}\mathbin{\|}\Delta_{q}

19:

for each p\in\mathcal{E}_{q} in scheduled order do

20:

B_{p}\leftarrow\langle x\in\mathcal{X}:\pi(x)=p\rangle

21:

append packet timestamp and ordered claim bundle B_{p} to X_{q}

22:

end for

23:

return X_{q}

### S32 · A.2 Source Normalization and Scheduler Validation

[原文定位](https://arxiv.org/html/2610.23313v1#A1.SS2)

Atomic candidates are grouped by their stored source_packet_id.

Within each group, the descriptor with the largest retrieval score becomes the

representative address; ties retain the earliest candidate. Packet ordering is

then descending by the representative score, followed by first candidate

position and packet identifier. This operation changes the selection state

from claims to sources without adding any source absent from the closed

candidate pool.

For listwise scheduling, candidate packets are assigned opaque labels

C001, C002, and so forth. The request displays each label

with the packet’s dialogue identifier, speaker, recorded date, and content.

The requested cardinality is \min(K,|\mathcal{U}_{q}|) . A valid response must

contain exactly that many distinct labels, all drawn from the request. Invalid

responses are retried up to three times with a schema correction; after the

final attempt, the parser retains only valid, unique labels in response order.

If fewer than K labels survive, the remaining closed candidate pool is

submitted in a subsequent round until the target cardinality is reached. Cache

identity binds the query, ordered candidate tensor, rendered packet contents,

prompt, model, protocol version, and K .

### S33 · A.3 Complexity

[原文定位](https://arxiv.org/html/2610.23313v1#A1.SS3)

Let N=|\mathcal{P}| be the number of source packets, M=|\mathcal{X}| the

number of atomic descriptors, C=|\mathcal{C}| the number of Cells, M_{C} the

item capacity per Cell, and d the embedding dimension. With bounded M_{C} ,

online Cell placement costs O(MCM_{C}) in the direct implementation. The

lexical query pass scores M descriptor documents,

while Cell routing scores C Cells and examines at most six opened Cells plus

the bounded BM25 pool. Dense packet retrieval costs O(Nd) for a matrix–vector

product and O(N\log 40) for a comparison-based Top-40 implementation. Source

normalization is linear in the atomic candidate count. Reader compilation is

linear in the number of claims attached to the selected packets. LLM calls for

fact extraction, metadata extraction, the two listwise schedules, and answer

generation dominate wall-clock cost and are accounted for separately in

Appendix E.

### S34 · A.4 Source-Aliasing Audit

[原文定位](https://arxiv.org/html/2610.23313v1#A1.SS4)

Eligible N is the number of questions for which the retrieval stage returned at least the requested depth. DBR is the fraction of retrieved slots beyond the first occurrence of each distinct SourcePacket. A question is Affected if at least one retrieved slot duplicates a SourcePacket already present at that depth.

Depth

Eligible N

Unique

DBR \downarrow

Affected

Max-source \mu /P95/max

Top-10

1,539

7.69

23.08%

84.21%

2.42/4/6

Top-20

1,537

14.60

27.02%

97.27%

3.18/5/7

Top-40

1,533

26.94

32.66%

100.00%

4.12/6/8

Table 5: Pre-normalization aliasing at three retrieval depths. DBR and

Affected are percentages. Max-source reports the mean, 95th percentile, and

global maximum number of slots occupied by one source.

Figure 4: Category-level effects of source normalization, complementary

scheduling, and source-scoped claim-bundle compilation. (a) Gold Source Recall

after exact-text deduplication, source-ID normalization, and complementary

source scheduling. (b) Judge Accuracy across the controlled stages and the

fixed-source claim-bundle reader view.

### S35 · B.1 Source-Linked Descriptor Construction

[原文定位](https://arxiv.org/html/2610.23313v1#A2.SS1)

For a turn d_{i} , fact extraction observes the current turn, its immediately

preceding turn, and the recorded session time. Greetings, acknowledgements,

system-context statements, and configured low-value prefixes are removed.

Each retained fact receives an identifier composed of the conversation,

dialogue-turn, and within-turn fact indices. Metadata extraction supplies up

to five keyword phrases, involved people, an event time when supported, the

interaction time, and event-role fields. The main experimental layout is the

bounded lexical Cell layout: its Cell topology uses descriptor text, people,

keywords, session index, and token count. Each descriptor is linked to exactly

one immutable packet, and packet claim identifiers retain construction order.

### S36 · B.2 Bounded Cell Placement

[原文定位](https://arxiv.org/html/2610.23313v1#A2.SS2)

For descriptor x_{i} and Cell c , define keyword and person Jaccard

similarities J_{K} and J_{P} . The temporal term is

T(i,c)=\begin{cases}1,&j_{i}\in[j_{c}^{\min},j_{c}^{\max}+1],\\

0.25,&\text{otherwise}.\end{cases}

(17)

The implemented coherence is

\displaystyle C(i,c)={}

\displaystyle 0.45J_{K}(i,c)+0.35J_{P}(i,c)

(18)

\displaystyle+0.20T(i,c).

The locality gain is

\displaystyle L(i,c)=\log\!\bigl(1

\displaystyle+|\mathsf{Key}_{i}\cap\mathsf{Key}_{c}|

(19)

\displaystyle+|\mathsf{Per}_{i}\cap\mathsf{Per}_{c}|\bigr).

The inconsistency penalty X(i,c) is 0.45 when an existing descriptor in

c shares a person and at least one keyword with x_{i} but only one of the two

contains a negation marker; otherwise it is zero. Let H(c) be the sum of

keyword entropy, person entropy, a log-scaled session-span penalty, and the

fraction of repeated dialogue identifiers:

\displaystyle H(c)={}

\displaystyle H_{K}(c)+H_{P}(c)

\displaystyle+0.2\log(1+j_{c}^{\max}-j_{c}^{\min})

\displaystyle+\frac{\sum_{d}\max(0,n_{d}-1)}{|c|}.

(20)

Writing r_{c}=\max(1,B_{C}-\operatorname{Tok}(c)) and

\Delta_{H}=\max(0,H(c\cup\{x_{i}\})-H(c)) , expansion pressure is

\displaystyle E(i,c)={}

\displaystyle\frac{n_{i}}{r_{c}}+0.4\Delta_{H}

\displaystyle+0.25\max\!\left(0,\frac{|c|+1}{M_{C}}-C(i,c)\right)

\displaystyle+0.25\max(0,H(c)-1.8).

(21)

The final placement score is

L(i,c)+1.4C(i,c)-X(i,c)-0.45E(i,c) . A new Cell is scored with

L=0 , C=0.55 , X=0 , and E=0.65+n_{i}/B_{C} . The experiment uses

B_{C}=360 and M_{C}=12 .

Algorithm 2 Online bounded Cell placement

0:

Descriptor x_{i} , current Cells \mathcal{C}

1:

Q\leftarrow\emptyset

2:

for each c\in\mathcal{C} do

3:

if \operatorname{Tok}(c)+n_{i}\leq 360 and |c|<12 then

4:

compute L(i,c),C(i,c),X(i,c),E(i,c)

5:

append (L+1.4C-X-0.45E,c) to Q

6:

end if

7:

end for

8:

create candidate c_{\mathrm{new}} with score

1.4(0.55)-0.45(0.65+n_{i}/360)

9:

append (S_{\mathrm{new}},c_{\mathrm{new}}) to Q

10:

c^{*}\leftarrow\arg\max_{(S,c)\in Q}S

11:

append x_{i} to c^{*} and recompute token, people, keyword, session,

title, and entropy summaries

### S37 · B.3 Cell Routing and Candidate Union

[原文定位](https://arxiv.org/html/2610.23313v1#A2.SS3)

BM25 scores all descriptors and retains

the top 96; its first eight descriptors seed Cell scoring. For query term set

Q , person set P , and Cell c , the base relevance is

\displaystyle u(c,q)={}

\displaystyle 2J(Q,K_{c})+2.2J(P,P_{c})

\displaystyle+0.7J(Q,\operatorname{Tok}(t_{c}))+T_{q}(c)

\displaystyle+0.03\frac{\log(1+|c|)}{\log(1+M_{C})},

(22)

where T_{q}(c)=0.25 for a temporal query when c contains temporal metadata

and is zero otherwise. Cells with base relevance below 0.08 are excluded.

The route pool contains the first

\max(12,6B_{\mathrm{cell}})=36 Cells, with B_{\mathrm{cell}}=6 .

At step t , redundancy is the Jaccard overlap between the candidate Cell’s

people/keywords and their union over already opened Cells. The implemented

marginal gain is

\displaystyle g(c\mid\mathcal{O}_{t},q)={}

\displaystyle u(c,q)(1-0.45R(c,\mathcal{O}_{t}))

\displaystyle-0.02(1+|\mathcal{O}_{t}|)

\displaystyle-0.0005\operatorname{Tok}(c).

(23)

After at least one Cell is opened, routing stops when g<0 or the

redundancy-adjusted utility falls below 0.68 of the best Cell utility. It

also stops once cumulative adjusted utility reaches 90\% of positive route

pool utility, or after six Cells. Descriptors from opened Cells are united with

the BM25 Top-96. Descriptors reached by both channels receive the configured

BM25 contribution, and the complete candidate tensor records both channel

identities before source normalization.

Descriptor relevance combines text, keyword, person, and temporal matches as

specified in Eq. 7, with

(\alpha_{f},\alpha_{k},\alpha_{p},\alpha_{t},\alpha_{b})=(2.0,1.6,2.4,0.3,0.45) . BM25 uses k_{1}=1.5 and b=0.75 over

documents formed by descriptor text, keywords, and people. Raw BM25 values are

mapped to 2\log(1+s_{i})/\log(1+s_{\max}) before applying the weight 0.45 .

For the diagnostic pre-scheduler Top-10, descriptors are first consolidated by

dialogue identifier. The representative relevance is augmented by

0.10\log(1+\sum_{i}\max(0,r_{i})) over same-source support. Greedy MMR then

subtracts 0.58 times maximum token-set overlap with an already selected

representative and 0.08 for each already selected representative from the

same Cell. The query-conditioned packet scheduler instead receives the complete

source-normalized candidate tensor, so this diagnostic Top-10 does not restrict

its closed candidate pool.

Algorithm 3 Diminishing-benefit Cell routing

0:

Query q , Cells \mathcal{C} , descriptors \mathcal{X}

1:

extract query-only people, keywords, and time; normalize Q,P

2:

S\leftarrow\operatorname{BM25Top}_{96}(Q,\mathcal{X}) ; seed with S[1{:}8]

3:

score Cells by u(c,q) and discard base score below 0.08

4:

V\leftarrow first 36 scored Cells; \mathcal{O}\leftarrow\emptyset

5:

for each c\in V in descending u(c,q) do

6:

compute redundancy-adjusted utility and marginal gain g

7:

if at least one Cell is open and g<0 or relative utility <0.68 then

8:

break

9:

end if

10:

append c to \mathcal{O}

11:

if |\mathcal{O}|=6 or cumulative adjusted utility reaches 90\% then

12:

break

13:

end if

14:

end for

15:

return descriptors in \mathcal{O} united with S

### S38 · Controlled intervention

[原文定位](https://arxiv.org/html/2610.23313v1#A2.SS4.SSS0.Px1)

All layouts use the same atomic memory items, BM25 baseline ranking, total candidate budget, question set, source packet scheduler, semantic frontier, Reader, and Judge. Evaluation is read-only with respect to persistent memory.

### S39 · Flat

[原文定位](https://arxiv.org/html/2610.23313v1#A2.SS4.SSS0.Px2)

Flat disables Cell-derived candidates rather than placing all items in one container. Its candidate sequence is the BM25-only sequence used by the no-Cell endpoint. Flat establishes the candidate recall of 0.8154 against which every structured layout is measured.

### S40 · Bounded Cells

[原文定位](https://arxiv.org/html/2610.23313v1#A2.SS4.SSS0.Px3)

For every new item, all capacity-feasible existing Cells compete with a new Cell under the placement objective in Eq. 4. The resulting organization jointly reflects person and keyword locality, session proximity, coherence, conflict avoidance, capacity, and entropy pressure. The policy is deterministic and accumulative, not a gradient-trained clustering model. The bouned cell layout improves recall by 3.959 points.

### S41 · Sequential

[原文定位](https://arxiv.org/html/2610.23313v1#A2.SS4.SSS0.Px4)

Sequential orders items by session index and then by dialogue identifier within each session order, and partitions the resulting sequence into fixed-length contiguous blocks. It discards people, keywords, coherence, and conflict signals, retaining only dialogue adjacency. This layout tests whether simple sequential locality accounts for the Cell benefit.

### S42 · Session

[原文定位](https://arxiv.org/html/2610.23313v1#A2.SS4.SSS0.Px5)

Session first groups items by session index, preserves their within-session order, and partitions each session independently into fixed-length blocks. Comparing Session with Sequential therefore isolates the value of the dataset’s session boundaries.

### S43 · Entity

[原文定位](https://arxiv.org/html/2610.23313v1#A2.SS4.SSS0.Px6)

Entity assigns each item to a bucket keyed by its primary person entity, orders each bucket by dialogue order, and partitions it into fixed-length blocks. It tests person identity as a cross-turn and cross-session address without using the complete placement objective. Entity layout improves the recall by 2.910 points. The result identifies person locality as a useful but incomplete component of the persistent organization.

Figure 5: Cell-placement contribution to recall. Bars are

gains over Flat construction; translucent bands and dashed endpoints show

conversation-bootstrap 95% intervals.

### S44 · C.1 LoCoMo Protocol

[原文定位](https://arxiv.org/html/2610.23313v1#A3.SS1)

The LoCoMo evaluation contains 1,540 questions from ten conversations and retains the benchmark’s single-hop, multi-hop, temporal, and open-domain categories. Memory construction receives conversation sessions only. Query text is exposed to query-intent extraction and retrieval at evaluation time; answers, question categories, gold evidence, and judge labels are not inputs to construction, addressing, scheduling, frontier selection and answer generation. Evaluation is read-only with respect to persistent memory state.

Component

Setting

Value

Models

construction, intent, scheduling, answer

gpt-4o-mini

dense retrieval

text-embedding-3-small

temperature / maximum completion

0 / 2,048 tokens

Cell construction

layout / token cap / item cap

bounded lexical Cell / 360 / 12

\beta,\gamma,\eta / new-Cell penalty

1.4, 1.0, 0.45 / 0.65

entropy weight / entropy threshold

0.4 / 1.8

Addressing

maximum/minimum opened Cells

6 / 1

admission / open / token costs

0.08 / 0.02 / 0.0005

relative floor / cumulative top- p

0.68 / 0.90

BM25 seeds / BM25 candidates

8 / 96

BM25 weight / descriptor support weight

0.45 / 0.10

descriptor MMR duplicate / same-Cell weights

0.58 / 0.08

Evidence Plane

initial SourcePackets K_{0}

10

semantic packet proposals

40

frontier rank cutoff / append cap

5 / 2

reader view

source-scoped atomic-claim bundle

Evaluation

answer metrics

token F1, BLEU-1, Judge Accuracy

judge model

gpt-5-nano

source metric

Gold Source Recall

generation cost metric

construction + query-time LLM tokens

Table 6: Configuration of the reported MemCompile experiment.

### S45 · C.2 Dense Frontier

[原文定位](https://arxiv.org/html/2610.23313v1#A3.SS2)

Each packet document concatenates raw turn text, image caption and query fields

when present, all retained packet claims, packet-level people and keywords, and

the recorded session time. Documents and the enriched query are embedded and

\ell_{2} -normalized; cosine similarity is therefore a matrix–vector dot

product. The enriched query concatenates the question with query-only people,

keywords, and time. The semantic Top-40 is united with the ten scheduled

anchors by dialogue identifier. A second closed-pool listwise schedule orders

this union. All ten anchors are preserved, and at most two previously

unselected packets among the first five scheduled positions are appended.

### S46 · C.2.1 Frontier Hyperparameter Sensitivity

[原文定位](https://arxiv.org/html/2610.23313v1#A3.SS2.SSS1)

Figure 6: Post-hoc frontier sensitivity around the fixed reported configuration.

We analyze how the frontier budgets affect evidence coverage on the

full LoCoMo benchmark, with K_{D}=40 fixed. This diagnostic sweep

characterizes the behavior of the bounded frontier around the reported

configuration.

Figure 6 shows the interaction between the

rank cutoff K_{R} and append cap K_{\Delta} . When K_{\Delta}=0 , all

curves coincide because no frontier proposal can enter the final evidence

set. For K_{R}=1 , increasing the cap beyond one has no effect by

construction. Larger rank windows make more frontier proposals eligible,

but for K_{R}\in\{3,5\} most of the observed coverage gain is obtained

by K_{\Delta}=2 . In contrast, K_{R}=10 continues to benefit from larger

append caps, indicating that a wider rank window is useful mainly when

more context growth is permitted.

At the fixed setting (K_{R},K_{\Delta})=(5,2) , mean Gold Source Recall

reaches 85.50%, with 1,217 questions achieving complete gold-source

coverage. Increasing the append cap from two to four adds only 0.28

recall points and four fully covered questions. Because K_{\Delta}=2

limits expansion to at most two packets beyond the ten scheduled anchors,

this setting represents a bounded coverage–context operating point capturing most of the observed gain for K_{R}\leq 5 while limiting

additional reader context.

### S47 · C.3 Reader Views

[原文定位](https://arxiv.org/html/2610.23313v1#A3.SS3)

The representative-claim view renders the highest-scoring address claim for

each selected source. The raw-source view renders the packet’s text and, when

present, its image caption and query fields. The claim-bundle view renders all

retained claims linked to the selected packet in construction order. Packet

selection and ordering are held fixed across the three views.

### S48 · Appendix D LongMemEval Results

[原文定位](https://arxiv.org/html/2610.23313v1#A4)

LongMemEval examples are converted into the same neutral session/turn schema used by LoCoMo. Each official haystack session retains its identifier and date; each turn receives a stable identifier formed from the session ID and turn position. The system constructs a separate memory for each evaluation instance and applies the same source-linked descriptor, Cell routing, SourcePacket scheduling, semantic frontier, and reader compilation pipeline. The official question types comprise single-session user, single-session

assistant, single-session preference, temporal reasoning, knowledge update, and multi-session questions. Answer-session and turn-level evidence labels are used only for offline evidence evaluation. On LongMemEval-S, MemCompile achieves the best Judge Accuracy among

the evaluated methods in five of the six reported categories: single-session user (91.43%), temporal reasoning (72.18%), knowledge update (78.21%), single-session assistant (94.64%), and single-session preference (70.00%). Table 7 reports the full category-level results.

Category

MemCompile

LightMem Fang et al. (2026)

Mem0 Chhikara et al. (2025)

J \uparrow

J \uparrow

J \uparrow

SSU

91.43

84.29

90.00

MS

54.14

57.14

65.41

TR

72.18

51.88

48.12

KU

78.21

76.92

74.36

SSA

94.64

33.93

44.64

SSP

70.00

60.00

63.33

Table 7: Judge accuracy (%) on LongMemEval-S. Best category-level results are bold. SSU, MS, TR, KU, SSA, and SSP denote single-session user, multi-session, temporal reasoning, knowledge update, single-session assistant, and single-session preference, respectively.

Stage

Total tokens

Tokens/question

Share of non-Judge total

Fact extraction

1,578,484

1,025

5.9%

Metadata extraction

12,492,607

8,112

46.8%

Cold-build subtotal

14,071,091

9,137

52.7%

Query intent

313,178

203

1.2%

packet scheduler

6,170,000

4,006

23.1%

frontier reranker

4,380,000

2,844

16.4%

Answer generation

1,786,551

1,160

6.7%

Online subtotal

12,649,729

8,214

47.3%

Non-Judge end-to-end

26,720,820

17,351

100.0%

Table 8: Generation-token accounting for MemCompile on the 1,540 LoCoMo

questions. Totals include prompt and completion tokens from unique successful

LLM calls; Judge and embedding usage are excluded. Per-question costs amortize

each total over all 1,540 questions, and shares are rounded independently.

### S49 · Appendix E Cost Accounting

[原文定位](https://arxiv.org/html/2610.23313v1#A5)

The reported generation-token cost is the sum of prompt and completion tokens

for unique successful LLM requests used in memory construction and query-time

serving:

\displaystyle T_{\mathrm{reported}}={}

\displaystyle T_{\mathrm{fact}}+T_{\mathrm{metadata}}+T_{\mathrm{intent}}

\displaystyle+T_{\mathrm{schedule}}+T_{\mathrm{frontier}}+T_{\mathrm{answer}}.

(24)

Judge calls and embedding tokens are recorded separately and are excluded from

the Tokens column in Table 1. Construction cost is incurred once

per conversation. Query-time cost includes query-intent extraction, packet

scheduling, frontier scheduling, and answer generation. Reader evidence length

is recorded separately from API-reported LLM usage.

Successful LLM responses are stored under an identity containing the system

prompt, user request, response format, model, temperature, maximum completion

length, and call type. A cache hit contributes zero incremental tokens to the

current invocation. Durable usage is reconstructed from unique successful

cache entries, preventing both double counting after replay and omission when

an API response is committed before the coordinating checkpoint. Embedding

requests use a separate identity-addressed cache and an idempotent usage

ledger. Packet scheduler caches additionally bind the ordered candidate tensor

and rendered packet content hashes.

Cold construction accounts for 14.07M tokens, or 52.7% of non-Judge usage,

and is amortized across subsequent questions over the same conversation.

Online serving accounts for the remaining 12.65M tokens. Within serving, the

R2 packet scheduler and E0.7 frontier reranker consume 10.55M tokens in total,

equivalent to 39.5% of the end-to-end total (and 83.4% of online usage).

These two stages are therefore the principal online cost paid for packet-level

selection and progressive evidence compilation; query-intent extraction and

answer generation together account for the remaining 7.9% of the total.

### S50 · Appendix F Prompts and Output Parsing

[原文定位](https://arxiv.org/html/2610.23313v1#A6)

The following boxes reproduce the stored prompt artifacts verbatim. All baselines use the same prompt settings as MemCompile to ensure a fair comparison.

⬇

Extract factual metadata as one JSON object. Use only information supported by the standalone Fact and supplied dialogue context.

Return:

- ‘people‘: complete person names explicitly involved.

- ‘keywords‘: at most five concise noun phrases useful for lexical retrieval; exclude people and time.

- ‘time‘: ‘[event_time, interaction_time]‘; normalize an explicit/inferable event date, otherwise use ‘""‘; interaction time is the supplied session time.

- ‘needs_profile_extraction‘: true only for a stable personal attribute.

- ‘event‘: one event/state represented by:

- ‘subject_people‘: subjects of the action/state, not all mentioned participants.

- ‘predicate‘: one lowercase English base-form verb lemma; never include auxiliaries or arguments.

- ‘focus_terms‘: one or more short noun/state phrases directly changed, chosen, evaluated, owned, experienced, or described by this Fact. Prefer wording grounded in the Fact.

- ‘goal_context_terms‘: optional wider named endeavor, purpose, task, or background explicitly supported by the Fact and potentially shared with distinct events. It is not the predicate/action, an emotion or quality, a time expression, or a generic category. Leave it empty unless the Fact states a genuinely wider context.

- ‘event_type‘: ‘occurrence‘, ‘plan‘, ‘state‘, ‘preference‘, or ‘relationship‘.

- ‘event_time‘: same normalized event time.

- ‘polarity‘: ‘positive‘, ‘negative‘, ‘neutral‘, or ‘unknown‘.

- ‘confidence‘: 0.0 to 1.0.

Distinct direct focuses remain distinct events even when they share a person, predicate, or goal. A repeated or elaborating statement about the same direct focus may represent the same event. Use empty arrays rather than invented content.

JSON shape:

{"people":[],"keywords":[],"time":["", ""],"needs_profile_extraction":false,"event":{"subject_people":[],"predicate":"","focus_terms":[],"goal_context_terms":[],"event_type":"occurrence","event_time":"","polarity":"unknown","confidence":0.0}}

⬇

Extract query-only retrieval intent as one JSON object. Do not answer the

query, use conversation memory, or infer facts not stated or implied by the

query.

Return:

- ‘need_attribute‘: whether answering requires a stable personal attribute,

preference, relationship, occupation, health fact, or long-term goal;

- ‘people‘: complete person names explicitly mentioned in the query;

- ‘keywords‘: at most five concise topics, concepts, or named entities useful

for retrieval, preferably normalized noun phrases;

- ‘time‘: explicit absolute or relative time constraints from the query, or

null when the query supplies none.

JSON shape:

{"need_attribute":false,"people":[],"keywords":[],"time":null}

⬇

You rank conversation source packets for evidence retrieval.

Given a query and a closed candidate list, return exactly the requested number

of distinct candidate labels in descending usefulness for answering the query.

Rank packets that directly contain answer-bearing evidence first. When the

answer requires multiple facts, include complementary packets that jointly

support it. Do not answer the query and do not invent labels.

Return one JSON object with this schema:

{"ranked_candidate_ids": ["C001", "C002"]}

Every returned string must be one of the bracketed ‘C###‘ labels in the

candidate list. Never return a ‘dia_id‘, packet ID, explanation, duplicate,

or label that is absent from the candidate list. Count the distinct labels

before returning the object.

⬇

You are a query-conditioned evidence selector.

Given a question and a closed list of source packets, return exactly the

requested number of distinct candidate labels, ordered from most to least

useful for answering the question.

Select packets that directly support the requested answer slot. Preserve

complementary packets when the answer needs a relation, a temporal anchor and

event, a comparison, or multiple list members. Prefer explicit evidence over

mere topical or name overlap. Avoid redundant packets when a different packet

adds necessary answer-bearing information. Do not answer the question and do

not infer facts that are absent from the candidates.

Return one JSON object with this schema:

{"ranked_candidate_ids": ["C001", "C002"]}

Every string must be one of the bracketed C### labels in the candidate list.

Never return a dia_id, packet ID, explanation, duplicate, or absent label.

Count the distinct labels before returning the object.

⬇

Answer from the selected evidence only.

First identify the answer slot requested by the question: person, place,

object, number, date, duration, reason, feeling, yes/no judgment, or list. Then

output only the minimum text that fully answers that slot.

Rules:

- Reuse the most direct and specific wording from the evidence whenever possible.

- For one value, give one short phrase rather than a sentence.

- For a list, merge all and only the explicitly supported requested items into

a concise comma-separated list. Do not drop supported items merely to shorten it.

- For yes/no or likelihood questions, begin with Yes or No and add only a

necessary short qualifier supported by the evidence.

- Directly perform evidence-supported merging, counting, comparison, and simple

time conversion. These operations are not reasons to abstain.

- Match the question’s date or duration granularity. Resolve relative time only

from a reliable date anchor in the evidence; otherwise retain the supported

expression.

- Preserve negation, subject, and time qualifiers needed for correctness.

Do not repeat the question, explain, cite sources, add politeness, use outside

knowledge, or infer unsupported personal facts. Output "Unknown" only if all

selected evidence is insufficient.

⬇

You are answering a question that requires temporal reasoning over selected

conversation evidence.

First identify the final answer slot. A date in the question may only constrain

which event is relevant. If the question asks for a person, place, object,

activity, or other non-time value, use the timeline to select the event and

output only that value. Apply temporal output formatting only when the final

requested slot is a time or duration.

Temporal expression rules:

1. Use only the selected evidence.

2. If a clear absolute event date is directly supported and there is no

conflicting anchored relative expression, use the absolute date.

3. Resolve simple offsets such as last year or last month from a reliable

event-linked anchor.

4. For week- or weekday-based expressions such as last week, next Saturday, or

last Sunday, do not calculate an exact date. Preserve the relative expression

or combine it with its reliable anchor, such as "the week before 9 July 2023"

or "the Sunday before 22 May 2023".

5. If only a month is supported, return the month and year. If only a year is

supported, return the year.

6. For duration, return only the shortest duration value without a "Duration:"

label. Perform evidence-supported counting and comparison.

7. Do not treat a record date by itself as an event date. Preserve event,

subject, negation, and ownership.

Output only the shortest final value for the requested slot. Do not include

reasoning, explanation, citation, or sentence framing. Output Unknown only if

all selected evidence is insufficient.

⬇

Your task is to label an answer to a question as "CORRECT" or "WRONG".

You will be given:

1. a question,

2. the gold answer,

3. a generated answer.

The question asks about something one user should know about another user based

on prior conversations. Be generous: if the generated answer refers to the same

topic or same fact as the gold answer, mark it CORRECT even if the wording is

longer, shorter, or formatted differently.

For time-related questions, the gold answer may be a date, month, year, or

relative time expression. Mark the generated answer CORRECT if it refers to the

same time period, even if the format differs.

Question: {question}

Gold answer: {gold_answer}

Generated answer: {generated_answer}

Return only JSON with this schema:

{{"label": "CORRECT"}}

The label must be exactly "CORRECT" or "WRONG".

### S51 · F.1 Dynamically Constructed Requests

[原文定位](https://arxiv.org/html/2610.23313v1#A6.SS1)

Fact extraction uses the following system message exactly:

Its user request supplies the preceding turn when present, followed by the

current dialogue identifier, speaker, session time, text, and available image

caption or image keywords. Metadata extraction supplies the standalone fact,

preceding turn, current turn, and session time. Query-intent extraction supplies

only the query. For both packet schedulers, the dynamic request uses the

candidate format

[C###] dia_id=... speaker=... recorded_date=...

content="..." and explicitly requests the exact output cardinality. Answer

generation supplies the query and the materialized evidence blocks.

JSON responses are parsed directly and, when a provider wraps a requested list

in a generic object, the parser accepts the corresponding schema alias. Packet

scheduler outputs additionally undergo exact cardinality, uniqueness, and

closed-label validation. Judge responses are parsed into the two permitted

labels after substituting the question, gold answer, and generated answer into

Prompt .

⬇

You extract high-value factual information from conversation turns. Return only a JSON array of complete standalone factual statements.
