---
schema_version: 1
kind: original_snapshot
title: Multimodal Filesystem Memory For Long-Horizon Embodied Agents
source_id: paper-9a0f0a87-ada0-4922-9f28-cd647e18d1f5
source: arXiv
authors:
- Su, Chloe
- Li, Jiahan
- Qi, Zhenting
- Cheng, Chaoran
- Chen, Haoyu
- Jun, Sejoon
- Ye, Weirui
- Du, Yilun
published_at: '2026-10-15'
source_version: v2
topics:
- agent_memory
source_url: https://arxiv.org/abs/2610.22686v2
captured_at: '2026-11-09T07:43:50.977418+00:00'
content_sha256: c59f55de5236fa281d0d281fd8d6f4f276140263ea222ca020b64c7bc64d490f
coverage: full_text
research_coverage: full_text
---

# Multimodal Filesystem Memory For Long-Horizon Embodied Agents

> 原文抽取归档，用于阅读及重放，内容不代表已核实的研究结论。

- [打开来源原文](https://arxiv.org/abs/2610.22686v2)。
- 原文归档保存完整可用抽取文本；绑定的模型材料范围为 `full_text`，可小于本归档。
- 归档自身不表示已经执行研究或审阅；实际执行与审阅状态以对应研究回执为准。
- 不保存可执行网页、PDF 版式或图片，不保证公式和图表的抽取完整性，未复现实验。
- 抽取方式：`html`；抽取范围：`full_text`。
- 抽取限制：Text extraction does not verify figures, layout, or faithful mathematical rendering.
- 取材：html / success / extracted。

## 获取记录

- [text/html](https://arxiv.org/abs/2610.22686v2)；响应 SHA-256：`03c49d76672c067a40bea984e9cfa1a039279a84d23698ad5471b70f6c5188ed`；抓取时间：2026-11-09T07:43:26.034113+00:00。
- [text/html](https://arxiv.org/html/2610.22686v2)；响应 SHA-256：`ae1966e66a74f28a8bf9fe59abfb872e13b9c4281f53db269abfc5473e227004`；抓取时间：2026-11-09T07:43:29.147477+00:00。

## 抽取正文

### S1 · Multimodal Filesystem Memory for Long-Horizon Embodied Agents

[原文定位](https://arxiv.org/html/2610.22686v2)

Chloe Su

Affiliation: Harvard

Affiliation: Kempner Institute

Jiahan Li

Affiliation: NYU

Zhenting Qi

Affiliation: Harvard

Chaoran Cheng

Affiliation: UIUC

Haoyu Chen

Affiliation: Harvard

Sejoon Jun

Affiliation: NEU

Weirui Ye

Affiliation: MIT

GitHub Project Page

Yilun Du

Affiliation: Harvard

Affiliation: Kempner Institute

### S2 · Abstract

[原文定位](https://arxiv.org/html/2610.22686v2#abstract1)

Agents operating over long horizons need an effective memory that allows them to reuse their experience throughout long interactions. If the entire history of an interaction is retained, it becomes difficult to find the relevant experience, while compressing it into summaries may result in the loss of visual and spatial details that are required later on. We present MFM, a multimodal filesystem memory architecture that keeps complementary types of agent memory. Episodic memory stores the observations, actions, and outcomes, and spatial memory associates experiences with locations. Semantic and procedural memory build up general knowledge and reusable methods of acting, and working memory holds the current plans. MFM makes use of searchable textual records to connect these different representations to the underlying multimodal episodes. The agents are able to find previous experiences by means of contextual cues and to examine the original observations in order to recover details that are missing from their textual descriptions. Through consolidation, the agents convert experience into higher-level knowledge and procedures while still keeping references to the original episodes. In the case of long-horizon Minecraft and computer-use tasks, MFM leads to improved performance with three base models. With GPT-6-Astra, MFM completes Mine Diamond from Scratch and reaches 16 out of 24 milestones on the Ender Dragon task, as against 12.7 for the best baseline. On CUABench-KiCad it attains a mean reward of 0.440, as compared to 0.400 for the best baseline and 0.267 in the case of no persistent memory.

$\star$$\star$footnotetext: Equal contribution.

### S3 · 1 Introduction

[原文定位](https://arxiv.org/html/2610.22686v2#S1)

Agents that are intelligent and capable of operating autonomously over long periods in complicated, open-ended environments need to remember what they have seen, discovered, and previously done (Park et al., 2025; Wang et al., 2026). A large part of this kind of memory will generally be visual or spatial in character, for instance the route by which one can get back to an object that it has seen before. It is not clear what the appropriate form of compact memory the agent should use to store such observations. If one stores everything directly then it becomes difficult to find relevant experiences as the amount of history increases. Conversely, summaries of the memory enable quicker retrieval, but may result in important details being discarded later (Lu et al., 2026; Zou et al., 2026).

We represent memory as a multimodal filesystem (MFM) which simultaneously holds different types of memory. We organize the memory based on the distinctions between various human memory systems (Tulving, 1972; Squire, 2004). In the MFM, episodic memory preserves past observations and interactions, spatial memory connects experiences to locations in the environment, semantic memory records facts and relationships, procedural memory contains reusable methods of acting, and working memory holds the current plan and the immediate subgoals. The five memory functions are realised using three common storage elements: episodic records, an associative index, and agent-written memory. These elements are arranged as folders and files in a shared filesystem, with references that link knowledge, procedures, and plans to their supporting episodes.

Previous work that has used a filesystem to store agent memory has shown the effectiveness of searchable textual records of interaction (Fox et al., 2026). With embodied agents, textual descriptions can fail to include important visual or spatial information. VISTA (Han et al., 2026) keeps visual observations and allows frames to be revisited using a turn or frame identifier, thus holding on to information that goes beyond its textual summaries. Yet it can be difficult to find the relevant experience, particularly as the memory increases. MFM offers an explicit structuring of the memory in the form of a filesystem, which enables quick retrieval of context and the aggregation of skills and knowledge.

Figure 1: MFM’s Memory Evolution in Minecraft. Over 36,000 steps, MFM continuously updates its memory and retrieves from it to support decision-making.

As shown in Fig. 2, associative indexing links these representations via searchable cues to the stored evidence. Text acts as an addressing layer for multimodal records: the agent begins by searching the descriptions of events, actions, and locations and then looks up the references in order to examine the corresponding observations. For instance, it can find a previous visit to a cave by means of its coordinates or by referring to an action that was attempted, check the recorded view, and then compare it with the current observation. The cues employed to locate an episode need not include a description of all the details of the episode. This enables us to navigate a long history of past episodes using compact records and at the same time retain detailed visual information which may only become relevant later.

With increasing experience, MFM employs self-evolving consolidation in order to update its knowledge, skills, and current working plans. Specific observations can lead to the establishment of new facts or relationships, useful action sequences can be turned into reusable procedures, and new information discovered can cause the agent to alter its present plan. These updates link episodic experience to semantic, procedural, and working memory. For instance, the agent might connect a resource with a cave that has just been explored, record a reliable procedure for getting to it, and change its route if a subsequent observation indicates that the entrance is blocked. Since the memories written by the agent include references to the episodes that support them, the agent can go back and look at the original evidence whenever its interpretation becomes uncertain or is contradicted. The evolution of the memory is illustrated in Fig. 1.

Our work consists of three parts. Firstly, we propose a method for organising a multimodal agent’s memory within a single filesystem, covering episodic, spatial, semantic, procedural, and working memory. Secondly, we implement this organisation in MFM, which combines cue-based retrieval and visual inspection with consolidation into revisable knowledge and reusable procedures. Thirdly, we demonstrate through long-horizon Minecraft and computer-use tasks that MFM surpasses both memory-free and memory-augmented baseline methods when using three base models, and that it is able to reuse its memory across different tasks. Using GPT-6-Astra, our system manages to complete the MCU Mine Diamond from Scratch task in all instances and achieves 16 out of 24 milestones on Ender Dragon, whereas the best baseline achieves an average of 12.7. On CUABench-KiCad, its mean reward is 0.440, compared to 0.400 for the best baseline and 0.267 for an agent lacking persistent memory.

### S4 · 2 Related Work

[原文定位](https://arxiv.org/html/2610.22686v2#S2)

Table 1: MFM versus prior agent memory systems across key memory properties.

Method

Raw multimodal

evidence

Index with

evidence pointers

Spatial

memory

Agent-writable

memory

Knowledge

linked to evidence

Retrieval

Voyager (Wang et al., 2024)

✗

✗

✗

✓a

✗

Embedding similarity

JARVIS-1 (Wang et al., 2025)

✓b

✗

✗

✓b

✗

Multimodal similarity

MrSteve (Park et al., 2025)

✓

✗

✓

✗

✗

Place/event lookup

PRO-LONG (Fox et al., 2026)

✗c

✗

✗

✓d

✗d

Regex / code over log

VISTA (Han et al., 2026)

✓

✗e

✗

✓e

✗

Inspect by frame ID

MFM (ours)

✓

✓

✓

✓

✓

Cue query + evidence inspection

aSkill library (code) only. bSuccessful trajectories only. cText log only. dOptional notes, not linked to log entries. eFrame IDs without a searchable index; free-form notes.

Filesystem and Multimodal Memory.

Approaches that use a filesystem allow agents to search through and modify persistent records. PRO-LONG has demonstrated that searchable textual interaction logs can support long-horizon reasoning (Fox et al., 2026), and in other cases filesystems are used as organizational structures for agent memory (Zhou et al., 2026a). Multimodal memory systems are designed to organize long sequences of visual data in order to enable question answering and reasoning (Fan et al., 2024; Liu et al., 2026a; Long et al., 2026). Other research looks into task-conditioned retention (Zou et al., 2026), retrieval reliability in the face of temporal decay and conflicting evidence (Lu et al., 2026), query-aware relational organization (Li et al., 2026), and analytic operations performed on accumulated observations (Tian et al., 2026). Table 1 summarizes the differences between MFM and related systems.

Memory for interactive agents with a long horizon.

The ability to carry out long-horizon interactions demands a type of memory that enables continuous perception, exploration, and planning. The latest ARC-AGI-3 systems integrate foundation models with interaction harnesses and external memory (ARC Prize Foundation, 2026; Fox et al., 2026; Zeng et al., 2026; Rodionov, 2026), and VISTA keeps records of visual information that agents can go back to and compare (Han et al., 2026). In the field of robotics, efforts are directed towards multi-scale memory, the learning of history compression, and the development of benchmarks for memory-dependent policies (Torne et al., 2026; Wang et al., 2026; Dai et al., 2026). Spatial memory also helps with navigation and reasoning (Ge et al., 2026; Zhang et al., 2026). In Minecraft, Voyager creates a collection of executable skills (Wang et al., 2024), JARVIS-1 retrieves successful plans from its multimodal memory (Wang et al., 2025), and later agents introduce hybrid multimodal memory (Li et al., 2024), what-where-when representations (Park et al., 2025), and accumulated knowledge as a means of self-improvement (Xie et al., 2026). New benchmarks have recently emphasised exploration and long-horizon competence (Zheng et al., 2025; Ju et al., 2026; Zhou et al., 2026b). Although PRO-LONG indexes only text and VISTA revisits frames without having a searchable index, MFM provides a general-purpose multimodal episodic filesystem.

### S5 · 3 Multimodal Filesystem Memory

[原文定位](https://arxiv.org/html/2610.22686v2#S3)

We present MFM, a multimodal filesystem memory architecture designed for long-horizon agents. This architecture incorporates three complementary elements: episodic records which store the multimodal experience, a searchable index that enables textual access to these records, and agent-written memory which structures plans, findings, environmental knowledge, and reusable procedures. Fig. 2 shows the structure of this approach, while Fig. 3 illustrates an example from Minecraft, covering the processes of episodic recording and indexing as well as retrieval and consolidation. Section 3.2 explains the various memory components and the way in which searchable records are linked to the multimodal evidence, Section 3.3 describes how the agent finds and examines relevant episodes, and Section 3.4 outlines how the accumulated experience is consolidated into reusable knowledge without losing the original evidence. Algorithm 1 gives a summary of the entire loop.

Figure 2: Overview of MFM. Five forms of memory in one filesystem. Harness-written episodic memory records observations, states, actions, and outcomes every step, with searchable cues for locating them; spatial

memory ties experiences to locations. Agent-written semantic, procedural, and working memory hold facts, reusable procedures, and the current plan, each citing its supporting episodes. The agent retrieves by

searching cues and inspecting original evidence (Sec. 3.3), and consolidates experience into knowledge, procedures, and plans without modifying episodic records (Sec. 3.4).

### S6 · 3.1 Problem Setup

[原文定位](https://arxiv.org/html/2610.22686v2#S3.SS1)

An agent interacts with an environment over a long horizon to achieve a task objective g . At step t , it receives an observation o_{t}=(v_{t},x_{t}) , where v_{t} is a visual observation and x_{t} contains textual or structured information, and selects an action a_{t} . Its interaction history is H_{t}=(o_{1},a_{1},\ldots,a_{t-1},o_{t}) . As this history grows beyond the model’s context budget, the agent must retain information outside its active context and retrieve it when needed. We represent this external memory as M_{t}=(E_{t},I_{t},C_{t}) , where E_{t}=(e_{1},\ldots,e_{N_{t}}) stores the N_{t} completed episodes retained at step t , I_{t} provides an index for locating these episodes, and C_{t} contains agent-written knowledge.

Below, we discuss how these components support complementary forms of memory.

### S7 · 3.2 Memory Representation

[原文定位](https://arxiv.org/html/2610.22686v2#S3.SS2)

As shown in Figure 2, MFM divides memory into three parts: episodic records of multimodal experience, a searchable index, and agent-written memory. This approach is based on the difference between episodic memory, which relates to specific experiences, and semantic and procedural memory, which concern knowledge and ways of acting (Tulving, 1972; Squire, 2004). The episodic store E_{t} holds the observations, states, and actions, while the index I_{t} gives cues for finding these records. The agent-written memory C_{t} links discoveries from different episodes and keeps environmental knowledge, reusable procedures, and working plans. The following section explains each of these in turn.

Episodic memory.

To revisit a past experience, the agent needs access to what it observed, what it attempted, and what happened. We retain episodes as multimodal records,

e_{i}=\bigl(\mathrm{id}_{i},\tau_{i},\mathcal{V}_{i},\mathcal{S}_{i},\mathcal{A}_{i},m_{i}\bigr),

where \mathrm{id}_{i} is the episode identifier, \tau_{i}=[b_{i},d_{i}] is the episode’s timestep interval, \mathcal{V}_{i} contains recorded visual observations, \mathcal{S}_{i} contains associated structured states, \mathcal{A}_{i} records actions, and m_{i} contains metadata such as plan progress and task milestones. Episode identifiers and timestep metadata link these records to the corresponding agent interactions. Images retain perceptual details that may be absent from a textual description, while states, actions, and outcomes allow the agent to reconstruct the circumstances of an event. Preserving these records allows the agent to inspect details whose relevance becomes apparent only later. Fig. 3(a) illustrates the contents of an episode.

Associative indexing.

Episodic memory is useful only if the agent can retrieve relevant experiences when needed. MFM associates each episode with cues describing what happened, where it occurred, and when it took place. This use of cues to access detailed records is motivated by indexing accounts of episodic memory (Teyler & Rudy, 2007). We represent the index as

I_{t}=(z_{1},\ldots,z_{N_{t}}),\qquad z_{i}=(\mathrm{id}_{i},k_{i},\rho_{i}),

where k_{i} contains searchable cues and \rho_{i} contains references to the stored evidence. The cues include temporal and available location metadata, action type, retrieval tags, and a short action–outcome description. The harness maintains one entry per completed episode in index.jsonl.

The index serves as an addressing layer: cues narrow the search to relevant episodes, while references provide access to their underlying observations. For example, the agent can locate an encounter near a cave through its recorded location, an object tag, or an attempted action, then inspect the corresponding image. This allows the agent to retrieve an experience through its context without first recalling its precise visual content. Details absent from the index remain available for inspection in the stored observations. Fig. 3(b) illustrates this separation between cues and evidence, and Algorithm 2 summarizes episode storage and indexing.

Spatial memory.

For embodied interaction, location provides a common frame for connecting experiences collected at different times. MFM supports this function through spatial information distributed across its episodic store, index, and agent-written memory. Our memory filesystem maintains an append-only grid of traversed cells in a world frame in grid.jsonl. Episode coordinates support retrieval by spatial proximity or vertical position, while stored egocentric views let the agent verify a retrieved location by its appearance (Fig. 1(a,d)). The agent further records landmark knowledge in notes.md, such as the entrance to a mine that has become blocked, together with coordinates and references to supporting episodes. These representations draw on complementary ideas from cognitive maps (Tolman, 1948), memory for events and their locations (Clayton & Dickinson, 1998), and visual place recognition (Cartwright & Collett, 1983).

Semantic and procedural memory. The agent must also accumulate knowledge that is still useful after a specific episode has ended. This knowledge is stored in the agent-created collection C_{t} , which provides support for both semantic and procedural memory as well as the working memory mentioned below. Semantic memory involves recording facts and the relationships between them across different experiences. For instance, a note can link a resource to a cave, connect the cave to its coordinates, or relate an attempted action to the result of that action. These associations are given in plain text and include episode identifiers or file paths, enabling the agent to refer back to the relevant evidence. Useful discoveries and local knowledge are stored in notes.md, while more general environmental patterns and operating instructions are kept in GUIDE.md.

Procedural memory consists of methods that can be reused. In the procedures/ directory there are textual or executable sequences of actions which the agent is able to reuse and modify during later interactions. Experience is converted into these kinds of knowledge and skill through periodic consolidation (Kumaran et al., 2016). The agent can add to, correct or reorganize these procedures as new evidence becomes available, the underlying episodic records staying unaltered.

Working memory.

To continue an ongoing task across context changes, MFM maintains the agent’s current plan and immediate subgoals in working.md (part of C_{t} ). This file records the current plan, unresolved questions, and information needed to resume after a context reset. It connects the agent’s accumulated experience and knowledge to the decisions required by its present objective.

Figure 3: Memory contents and operations in MFM. A Minecraft trajectory shows how each form of memory is populated and used. (a) An episode: observation, state, action, and outcome stored as persistent files. (b) Its index entry: searchable cues, including spatial coordinates, with references to the records. (c) Retrieval: the agent locates episodes by step and inspects the referenced frame. (d) Consolidation: the evidence updates semantic (GUIDE.md) and working memory while earlier entries and episode references are preserved. Bottom: where each form of memory lives at this step.

### S8 · 3.3 Memory Retrieval

[原文定位](https://arxiv.org/html/2610.22686v2#S3.SS3)

Retrieving an experience requires both locating a relevant episode and determining what its observations reveal about the current task. MFM separates this into two stages. The agent first searches for episodes through textual or structured cues, then inspects selected multimodal evidence. As the cues determine where to look without requiring the agent to describe every detail, the agent can ask new questions of past observations, including ones whose relevance was not apparent when the experience was recorded. Fig. 3(c) illustrates this process, and Algorithm 3 summarizes the retrieval procedure.

Agent-initiated search.

Given its current information need, the agent constructs a query q_{t} over the episode index I_{t} and receives matching entries R_{t} . A query specifies conditions on recorded context, such as a time interval or location. For example, an agent investigating a failed action can locate episodes around the time it occurred. Search then identifies episodes that match the requested context, while the agent judges which are useful for its current decision. Each result provides the episode identifier, contextual cues, an action–outcome summary, and references to the evidence. Matches are returned in chronological order, with an optional limit that retains only the most recent matches.

Visual inspection.

If you find a particular episode, you gain access to information that goes beyond the description in its index. The agent then chooses the references \mathcal{P}_{t}\subseteq\bigcup_{z_{i}\in R_{t}}\rho_{i} from the results and loads the relevant evidence into the context, D_{t}=\{\operatorname{Load}(p)\mid p\in\mathcal{P}_{t}\} , where \operatorname{Load} converts a reference into its stored frame, state, or other record. This approach of selectively loading evidence enables the agent to look at the evidence it needs without including the entire interaction history in the context. With respect to visual evidence, the agent may examine an original frame, compare a number of frames on a contact sheet, place a previous observation alongside the current view, or zoom in on a region of interest. These operations help answer different questions regarding the same experience, for example identifying an object, recognising a location, or understanding the outcome of an action. Since the observations are available independently of the textual clues, the agent is able to look at details that are missing from k_{i} and reconsider a previous interpretation. When an inspection involves a question, the agent keeps both the question and the result so that the reason for the lookup is not lost.

### S9 · 3.4 Self-Evolving Consolidation

[原文定位](https://arxiv.org/html/2610.22686v2#S3.SS4)

Episodic memory preserves past experiences, while semantic and procedural memory capture knowledge and skills for future scenarios. MFM connects these forms of memory through consolidation, drawing on how complementary memory systems support learning from experience (Kumaran et al., 2016). During consolidation, the agent examines accumulated evidence and updates its understanding of the environment, reusable procedures, and its current plan. These updates change the agent-written memory C_{t} while preserving the recorded history (E_{t},I_{t}) . Algorithm 4 summarizes this procedure.

From experience to knowledge and skills.

Consolidation allows findings from individual episodes to inform subsequent behavior. The agent can record a useful observation as local knowledge in notes.md, or update GUIDE.md when experience supports a broader regularity. For example, an encounter may establish where a resource was found, while repeated encounters may suggest conditions under which an action succeeds or fails. The agent can also qualify earlier guidance when new observations reveal limits to its applicability.

Procedural updates record effective methods of acting; the agent is able to convert a sequence of actions into a textual or executable procedure and then modify it as a result of the changes revealed by later attempts. Working-memory updates link the knowledge that has been accumulated to the current task by having the agent revise the file working.md to show the completed subgoals, any changes to the plan, and the questions that remain unanswered. The agent decides which of these updates to make on the basis of the evidence available and the role of each memory, and the resulting documents and procedures stay accessible during future interactions.

Revision with preserved episodic evidence. Knowledge gained from experience can become out of date or incorrect. By linking the knowledge that agents write to the episodic observations that support it, agents are able to go back and look at the basis of their earlier beliefs. For instance, after having noticed a sheep on a hillside the agent then decides to go back for food, enlarges the original frame, and discovers that the animal was in fact a wolf; it then corrects the note and alters its plan while still keeping the reference to the episode. If the agent had kept only the textual description it would have lost the visual details required to correct that interpretation. Therefore, by preserving the episodic evidence the agent can reevaluate its earlier conclusions as its understanding develops. Figure 3(d) shows that the agent updates its GUIDE to indicate that the death message names a Piglin and that the previous identification as a brute has not been confirmed.

### S10 · 4 Experiment Results

[原文定位](https://arxiv.org/html/2610.22686v2#S4)

We evaluate MFM to understand how persistent multimodal memory affects task performance, decision-making, and interaction efficiency. We compare MFM with baseline methods on long-horizon embodied and computer-use tasks (Section 4.2), examine the memory component contributions via ablation studies (Section 4.3), and illustrate qualitative retrieval behaviors (Section 4.4), with a portal-building case study examining task completion and interaction efficiency, and analyze how the

agent learns and reuses skills through memory (Section 5.1).

### S11 · 4.1 Experimental Setup

[原文定位](https://arxiv.org/html/2610.22686v2#S4.SS1)

We evaluate MFM across two diverse domains, averaging all main and ablation results over three random seeds (determining the Minecraft world or KiCad task order). We limit each configuration to three seeds because long-horizon runs with frontier models are expensive. All models are ran with high reasoning efforts.

•

Minecraft: MCU-AgentBeats (Zheng et al., 2025; Liu et al., 2026b): open-world exploration and interaction in Minecraft, scored via scene-specific milestones. The details of both tasks are included in E.1. For the Mine Diamond from Scratch task, we use 12,000 max steps; for the Ender Dragon task, we use 36,000 max steps. We use a “life” to denote an attempt from spawn until death; after death, the agent’s inventory and world modifications reset.

•

CUABench-KiCad. Built on the CUABench framework (Cua AI, Inc., 2025; Cua AI, 2026) via low-level action spaces, this environment evaluates visual GUI agents on realistic electronic design automation workflows in KiCad. It contains N=25 tasks. For MFM, VISTA, and PRO-LONG, memory can carry over across tasks. A task may receive a score in [0,1] when the solution satisfies only a subset of the required criteria.

Baselines and models. We compare MFM against direct evaluation (no persistent memory), PRO-LONG (Fox et al., 2026), and VISTA (Han et al., 2026) using frontier base models (GPT-5.6-Sol, Claude Opus 5, and GPT-6-Astra). For a fair comparison, all methods share identical base agent prompts, decoding settings, environments, harness, and context management.

Table 2: Finished milestones on long-horizon MCU tasks.

Number of milestones completed on Mine Diamond from Scratch and

Ender Dragon. Results are mean \pm std over

3 seeds; best in bold.

Method

Model

Diamond

Dragon

(Max: 10)

(Max: 24)

Direct

GPT-5.6-Sol

4.0 \pm 1.0

6.0 \pm 1.0

Evaluation

Claude Opus 5

6.0 \pm 1.0

6.0 \pm 1.0

GPT-6-Astra

6.3 \pm 0.6

6.3 \pm 0.6

PRO-LONG

GPT-5.6-Sol

8.0 \pm 1.0

8.3 \pm 0.6

(Fox et al., 2026)

Claude Opus 5

8.0 \pm 1.0

8.0 \pm 1.0

GPT-6-Astra

9.3 \pm 0.6

11.0 \pm 1.0

VISTA

GPT-5.6-Sol

9.3 \pm 0.6

9.0 \pm 1.0

(Han et al., 2026)

Claude Opus 5

8.7 \pm 0.6

8.7 \pm 0.6

GPT-6-Astra

9.7 \pm 0.6

12.7 \pm 0.6

MFM (ours)

GPT-5.6-Sol

9.7 \pm 0.6

10.7 \pm 0.6

Claude Opus 5

9.3 \pm 0.6

10.3 \pm 0.6

GPT-6-Astra

10.0 \pm 0.0

16.0 \pm 0.0

Table 3: Mean reward on CUABench-KiCad.

Results are mean \pm std over 3 seeds; best in bold.

Method

Model

Mean Reward

Direct

GPT-5.6-Sol

0.240 \pm 0.026

Evaluation

Claude Opus 5

0.240 \pm 0.023

GPT-6-Astra

0.267 \pm 0.021

PRO-LONG

GPT-5.6-Sol

0.306 \pm 0.014

(Fox et al., 2026)

Claude Opus 5

0.300 \pm 0.016

GPT-6-Astra

0.375 \pm 0.012

VISTA

GPT-5.6-Sol

0.400 \pm 0.011

(Han et al., 2026)

Claude Opus 5

0.373 \pm 0.013

GPT-6-Astra

0.400 \pm 0.010

MFM

GPT-5.6-Sol

0.400 \pm 0.009

(no cross-task

Claude Opus 5

0.375 \pm 0.010

memory)

GPT-6-Astra

0.413 \pm 0.009

MFM (ours)

GPT-5.6-Sol

0.413 \pm 0.009

Claude Opus 5

0.389 \pm 0.010

GPT-6-Astra

0.440 \pm 0.013

### S12 · 4.2 Performance on Long-Horizon Tasks

[原文定位](https://arxiv.org/html/2610.22686v2#S4.SS2)

MCU-AgentBeats. Table 3 shows completion counts. MFM + GPT-6-Astra finishes all 10 Diamond milestones (vs. 6.3 for direct evaluation, 9.3 for PRO-LONG, and 9.7 for VISTA). On the harder Dragon task, MFM achieves 16/24 milestones, outperforming direct evaluation (6.3), PRO-LONG (11.0), and VISTA (12.7). We observe that every baseline plateaus, making no further progress after at most 13 milestones. MFM consistently improves performance across all base models.

CUABench-KiCad. Table 3 indicates that MFM’s benefits extend to computer-use tasks, yielding mean rewards of 0.413 (GPT-5.6-Sol), 0.389 (Opus 5), and 0.440 (GPT-6): improving over direct evaluation baselines by 0.149–0.173 and outperforming memory baselines across models. Without cross-task memory, MFM’s reward drops by 0.013 – 0.027 across models.

Temporal reach and interaction efficiency. Fig. 6 reveals that MFM accesses much earlier history than VISTA (which favors recent experience) or PRO-LONG, demonstrating the effectiveness of MFM’s addressing layer. Furthermore, Fig. 9 shows that MFM and PRO-LONG execute more actions per turn than VISTA, with fewer total model queries and reducing execution overhead.

Table 4: Ablation of MFM’s memory components. Effects of removing stored frames, associative indexing, agent-written procedures or consolidation on the Diamond and Dragon tasks.

No visual obs.

Flat

No agent procedures

No consolidation

Model

Diamond

Dragon

Diamond

Dragon

Diamond

Dragon

Diamond

Dragon

GPT-5.6-Sol

8.0\pm 1.0

8.3\pm 0.6

8.7\pm 0.6

8.7\pm 0.6

8.7\pm 0.6

9.0\pm 1.0

8.3\pm 0.6

8.3\pm 0.6

GPT-6-Astra

8.7\pm 0.6

9.7\pm 0.6

9.3\pm 0.6

9.3\pm 0.6

8.7\pm 0.6

10.7\pm 1.2

8.7\pm 0.6

9.3\pm 0.6

### S13 · 4.3 Ablation Studies

[原文定位](https://arxiv.org/html/2610.22686v2#S4.SS3)

We evaluate the contributions of MFM’s memory components through four ablations that separately remove access to historical visual observations, associative indexing, agent-written procedures, and consolidation. Table 4 reports the ablation results. Historical visual observations appear essential for resolving perceptual ambiguities and spatial orientation (Section 4.4). Disabling stored frames drops completion significantly across models: for GPT-5.6-Sol, scores fall to 8.0\pm 1.0 (Diamond) and 8.3\pm 0.6 (Dragon), while GPT-6-Astra drops to 8.7\pm 0.6 (Diamond) and 9.7\pm 0.6 (Dragon). Associative indexing suggests that a dedicated addressing layer helps; Replacing it with chronological text matching over a flat log (Flat) reduces performance to 8.7\pm 0.6 on both tasks for GPT-5.6-Sol, and to 9.3\pm 0.6 on both tasks for GPT-6-Astra. Additionally, agent-written procedures seem to help compound past successes into reusable routines (Section 5.1), as disabling them decreases performance for GPT-5.6-Sol (Diamond: 8.7\pm 0.6 ; Dragon: 9.0\pm 1.0 ) and more sharply for GPT-6-Astra (Diamond: 8.7\pm 0.6 ; Dragon: 10.7\pm 1.2 ). Finally, the removal of consolidation lowers performance to 8.3\pm 0.6 on both tasks for GPT-5.6-Sol, and to 8.7\pm 0.6 (Diamond) and 9.3\pm 0.6 (Dragon) for GPT-6-Astra. The consistent drops across all four ablations is the main evidence that each component contributes.

### S14 · 4.4 How Memory Retrieval Helps in Long-Horizon Tasks

[原文定位](https://arxiv.org/html/2610.22686v2#S4.SS4)

We examine qualitative examples to understand how MFM supports decisions during long-horizon interaction. These examples illustrate how agents inspect visual evidence to revise earlier interpretations, recover spatial context from previous observations, and reuse evidence across tasks.

MCU-AgentBeats. Visual inspection enables agents to correct uncertain observations. In Fig. 10(a,b), magnifying ambiguous frames reveals a wolf instead of a sheep, preventing a costly attack; in (c,d), pink sheep observations guide resource gathering.

Retrieving earlier observations also helps the agent recover spatial context and connect past experience to the current environment. Agents utilize past frames to locate hole rims (Fig. 11), identify mine entrances (Fig. 12), and correct unfavorable viewing angles (Fig. 13).

We further examine a controlled construction task requiring the agent to align visual observations across multiple actions with a textual specification (full prompt in section E.3). Starting on a cleared stone platform with sufficient resources, the agent must build and activate a Nether portal. This probes multimodal capability: the agent must translate textual geometric constraints into a 3D structure, track construction progress from first-person views, and adjust accordingly. Only MFM successfully built the portal under a 6,000-step budget (Fig. 4), requiring lower overhead (Fig. 5): 30 model calls, 77 tool calls, and 77 environment actions (vs. 141/140/129 for VISTA and 43/131/151 for PRO-LONG).

(a) MFM completes the portal.

(b) VISTA

(c) PRO-LONG

Figure 4: Qualitative behavior on the Nether portal task. MFM successfully completes the Nether portal, whereas VISTA and PRO-LONG fail to finish the structure.

Figure 5: Interaction efficiency on the Nether portal task.

Comparison of model calls, tool calls, and executed environment actions.

Figure 6: Temporal reach of memory retrieval.

Retrieval-lag (environment steps between recording an experience and retrieving it) on Diamond and Dragon. VISTA favors recent experience; MFM reaches further back, especially on Dragon.

CUABench-KiCad. Fig. 14 shows 3 tasks where MFM outperforms VISTA (GPT-6-Astra). In Task 55f2eefb (switching an LED circuit’s supply from 9 V to 5 V), both methods log an “OK” from Change

Symbol, but only MFM verifies the resulting netlist: its final state reads +5V

while VISTA’s still reads +9V, underscoring the need to check task state through visual memory. On a buck-regulator task (c4baee36), both methods

produce identical components and wiring but different supply labels; on the

two-op-amp task (b7148878), MFM leaves 1 input pin unconnected versus 3 for

VISTA. Fig. 16 shows episodic retrieval across tasks: an

export sequence from one task is reused on another.

### S15 · 5.1 Skill Learning through Memory

[原文定位](https://arxiv.org/html/2610.22686v2#S5.SS1)

We look into whether long-term memory allows agents to enhance their future behaviour by turning experience from interactions into reusable procedures. In this context, self-improvement means adapting as a result of the memory accumulated in MFM. MFM includes the facilities needed to store, modify, and carry out procedures written by the agent, and it is the agent itself that decides which behaviours to keep and when to reuse them. We do not specify the resulting skill library and do not require a fixed number of skills for each run. The analysis presented in this section includes observations of skill creation and reuse over different trajectories, an ablation study of the agent-written procedures, and a controlled study of the number of steps required to solve new tasks with or without reusing the agent-written procedures.

Figure 7: More memory of the world makes new tasks faster. We take the memory of an earlier agent that explored the world and give fresh agents progressively larger portions of it: none, an early cut, a middle cut, or the full memory. Each agent is then asked to find and mine an ore (iron, diamond or gold). (a) As more memory is inherited, tasks take fewer steps and are solved more often. The gain comes from what the memory contains. Agents whose memory already records where the needed ore lies (blue) almost always succeed and finish well within budget. Agents whose memory predates that discovery (grey) do no better than agents with no memory. (b–d) The pattern holds for each task. Informed agents dig straight to the remembered location instead of searching blindly.

From experience to reusable behaviour. The trajectories show how agents convert their experience of interaction into permanent action routines. In a run of GPT-6-Astra Dragon, after manually cutting a descending staircase (steps 5,068 to 5,249), the agent created the procedure cut_step, which is parameterised by heading and cuts one step while advancing (); it then invoked this procedure 60 times, once for each of the four cardinal headings. A second procedure, quarry_north_pair, extracts the upper and lower block from the wall in front and gathers the dropped items (); the 27th time it was called, at step 17,462, it broke the first diamond ore block. Reuse also carries over from one life to another. The procedure bridge_north, which places one floor block while sneaking and takes the target cell as input (), was written in the previous life after the agent had manually placed two blocks over the lava and was then called three times in that same life. In this life the agent called it nine times between steps 19,261 and 20,103, using varying inputs. Each invocation placed one cobblestone block and left the agent’s health unchanged, and the bridge ended up reaching the lava pool where mining of obsidian took place at step 20,736. The agent also disabled one inherited procedure, level_step, having traced the previous death in the lava back to this procedure’s release of the sneak key.

Table 5: Skills learned from one task speed up new tasks. Mean environment

steps (over 5 seeds each) to solve three new tasks without (w.o.) and with (w.) the scripts an earlier life

wrote installed. Every life solved its task.

Iron shield

Climb out

Cook meat

w.o.

w.

\Delta

w.o.

w.

\Delta

w.o.

w.

\Delta

2422

1705

\downarrow 30\%

2010

1867

\downarrow 7\%

640

476

\downarrow 26\%

Contribution to task performance. The results from the procedure ablation show that the procedures written by the agent do in fact contribute to task performance in MFM. For instance, when these procedures are removed for GPT-5.6-Sol, the mean milestone completion drops from 9.7 to 8.7 on Diamond and from 10.7 to 9.0 on Dragon. Our analysis points to two mechanisms that account for these improvements. Firstly, the skills allow agents to carry out the tasks more quickly; as presented in Table 5, reusing skills acquired during an earlier task decreased the average number of environment steps required to complete three new tasks: Iron shield, Climb out, and Cook meat by 30%, 7%, and 26% respectively. Secondly, skills can enable agents to reach milestones that would otherwise be impossible for them to achieve, as shown in the case of the blaze-fighting skill. If there are no agent-written skills that take visual inputs (for example, ), then none of the methods or models evaluated is able to go beyond milestone 16 to accomplish milestones such as killing a blaze or an enderman. These findings indicate that procedures enhance both the efficiency of task completion and the variety of milestones that can be achieved, even though they do not mean that each stored procedure is beneficial or that having a larger library of skills will necessarily lead to better performance.

### S16 · 5.2 Transferring world knowledge to new tasks

[原文定位](https://arxiv.org/html/2610.22686v2#S5.SS2)

We next examine whether accumulated knowledge of an environment helps agents solve new objectives. We initialize fresh agents with memory from an earlier exploration trajectory, using four conditions: no inherited memory, memory collected through step 3,000, through step 6,000, or the full trajectory. Each agent is then tasked with finding and mining iron, diamond, or gold in the same world. Fig. 7 reports success and environment steps under each condition. Across the evaluated trials, success increases from 1/12 without inherited memory to 11/12 with full memory. The results suggest that the benefit depends on the information retained: agents whose inherited memory records the target ore’s location generally succeed within budget, whereas agents receiving memory from before its discovery often exhaust their budget.

### S17 · 6 Conclusion

[原文定位](https://arxiv.org/html/2610.22686v2#S6)

We introduced MFM, a multimodal filesystem memory that organizes episodic, spatial, semantic, procedural, and working memory as folders and files in one shared filesystem. Episodic records preserve raw observations, states, actions, and outcomes; a searchable index of contextual cues addresses them; and agent-written knowledge, procedures, and plans cite the episodes that support them. An agent can thus locate past experience by when, where, or what happened, inspect the original observation for details text omits, and revise what it has learned without discarding the evidence. Across Minecraft and KiCad with three base models, MFM outperforms memory-free and memory-augmented baselines, each component contributes, and memory transfers across tasks. We hope MFM can serve as a foundation for memory in long-horizon multimodal and embodied agents.

Limitations and Future Work. MFM improves long-horizon performance, but exploration remains hard: even GPT-6-Astra at maximum reasoning effort (from a concurrent experiment posted online) did not complete Ender Dragon. Finding better ways of coupling memory

to exploration and route planning could help agents find landmarks and avoid repeated traversal. Our evaluation is also limited to single agents in Minecraft and KiCad; shared memory across agents could combine experience from different regions or solution attempts, and broader environments would test how far the design transfers.

### S18 · References

[原文定位](https://arxiv.org/html/2610.22686v2#bib)

ARC Prize Foundation (2026)

ARC Prize Foundation.

Arc-agi-3.

https://arcprize.org/, 2026.

Accessed: 2026-08-15.

Cartwright & Collett (1983)

BA Cartwright and Thomas S Collett.

Landmark learning in bees: experiments and models.

Journal of comparative physiology, 151(4):521–543, 1983.

Clayton & Dickinson (1998)

Nicola S Clayton and Anthony Dickinson.

Episodic-like memory during cache recovery by scrub jays.

Nature, 395(6699):272–274, 1998.

Cua AI (2026)

Cua AI.

Cua-Bench Leaderboard.

https://cua.ai/cuabench, 2026.

Accessed: 2026-09-12.

Cua AI, Inc. (2025)

Cua AI, Inc.

Cua, 2025.

URL https://github.com/trycua/cua.

cua-bench KiCad EDA dataset (25 schematic-editing tasks, netlist-comparison scoring). MIT License. Accessed 2026-09-01.

Dai et al. (2026)

Yinpei Dai, Hongze Fu, Jayjun Lee, Yuejiang Liu, Haoran Zhang, Jianing Yang, Chelsea Finn, Nima Fazeli, and Joyce Chai.

Robomme: Benchmarking and understanding memory for robotic generalist policies.

arXiv preprint arXiv:2603.04639, 2026.

Fan et al. (2024)

Yue Fan, Xiaojian Ma, Rujie Wu, Yuntao Du, Jiaqi Li, Zhi Gao, and Qing Li.

Videoagent: A memory-augmented multimodal agent for video understanding.

In European Conference on Computer Vision, pp. 75–92, 2024.

Fox et al. (2026)

Alexis Fox, Junlin Wang, Paul Rosu, and Bhuwan Dhingra.

Pro-long: Programmatic memory enables long-horizon reasoning.

arXiv preprint arXiv:2607.20064, 2026.

Ge et al. (2026)

Zuhao Ge, Xiaosong Jia, Chao Wu, Yuchen Zhou, Zuxuan Wu, and Yu-Gang Jiang.

Evomemnav: Efficient self-evolving fine-grained memory for zero-shot embodied navigation.

arXiv preprint arXiv:2606.03509, 2026.

Han et al. (2026)

Qiushi Han, Keya Hu, Linlu Qiu, Cathy Wu, and Kaiming He.

VISTA: A visual harness for reasoning in an interactive world, aug 2026.

URL https://vista-research.github.io/.

Ju et al. (2026)

Tianjie Ju, Yueqing Sun, Zheng Wu, Wei Zhang, Yaqi Huo, Xi Su, Qi Gu, Xunliang Cai, Gongshen Liu, and Zhuosheng Zhang.

Mineexplorer: Evaluating open-world exploration of mllm agents in minecraft.

arXiv preprint arXiv:2605.30931, 2026.

Kumaran et al. (2016)

Dharshan Kumaran, Demis Hassabis, and James L McClelland.

What learning systems do intelligent agents need? complementary learning systems theory updated.

Trends in cognitive sciences, 20(7):512–534, 2016.

Li et al. (2026)

Geng Li, Yuhao Wang, Dong Li, Jianye Hao, and Yuxin Peng.

Graphmemix: Query-aware evidence forests for long-term multimodal agent memory.

arXiv preprint arXiv:2608.26983, 2026.

Li et al. (2024)

Zaijing Li, Yuquan Xie, Rui Shao, Gongwei Chen, Dongmei Jiang, and Liqiang Nie.

Optimus-1: Hybrid multimodal memory empowered agents excel in long-horizon tasks.

Advances in neural information processing systems, 37:49881–49913, 2024.

Liu et al. (2026a)

Runtao Liu, Ziyi Liu, Jiaqi Tang, Yue Ma, Renjie Pi, Jipeng Zhang, and Qifeng Chen.

Longvideoagent: Multi-agent reasoning with long videos.

In Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), pp. 40404–40416, 2026a.

Liu et al. (2026b)

Xiaoyuan Liu, Jianhong Tu, Yuqi Chen, Siyuan Xie, Sihan Ren, Tianneng Shi, Gal Gantar, Evan Sandoval, Donghyun Lee, Daniel Miao, et al.

Agentbeats: Agentifying agent assessment for openness, standardization, and reproducibility.

arXiv preprint arXiv:2606.13608, 2026b.

Long et al. (2026)

Lin Long, Yichen He, Wentao Ye, Yiyuan Pan, Yuan Lin, Hang Li, Junbo Zhao, and Wei Li.

Seeing, listening, remembering, and reasoning: A multimodal agent with long-term memory.

In International Conference on Learning Representations, volume 2026, pp. 146197–146246, 2026.

Lu et al. (2026)

Yihao Lu, Wanru Cheng, Zeyu Zhang, and Hao Tang.

Mma: Multimodal memory agent.

arXiv preprint arXiv:2602.16493, 2026.

Park et al. (2025)

Junyeong Park, Junmo Cho, and Sungjin Ahn.

Mrsteve: Instruction-following agents in minecraft with what-where-when memory.

In International Conference on Learning Representations, volume 2025, pp. 16922–16960, 2025.

Rodionov (2026)

Sergey Rodionov.

Executable world models for arc-agi-3 in the era of coding agents.

In International Conference on Artificial General Intelligence, pp. 198–210. Springer, 2026.

Squire (2004)

Larry R Squire.

Memory systems of the brain: A brief history and current perspective.

Neurobiology of learning and memory, 82(3):171–177, 2004.

Teyler & Rudy (2007)

Timothy J Teyler and Jerry W Rudy.

The hippocampal indexing theory and episodic memory: updating the index.

Hippocampus, 17(12):1158–1169, 2007.

Tian et al. (2026)

Zhoujin Tian, Yao Tian, Hao Zhang, Cheng Chen, Yakun Li, Lei Zhang, and Xiaofang Zhou.

Beyond retrieval: Analytic memory for multimodal agents.

arXiv preprint arXiv:2607.29440, 2026.

Tolman (1948)

Edward C Tolman.

Cognitive maps in rats and men.

Psychological review, 55(4):189, 1948.

Torne et al. (2026)

Marcel Torne, Karl Pertsch, Homer Walke, Kyle Vedder, Suraj Nair, Brian Ichter, Allen Z Ren, Haohuan Wang, Jiaming Tang, Kyle Stachowicz, et al.

Mem: Multi-scale embodied memory for vision language action models.

arXiv preprint arXiv:2603.03596, 2026.

Tulving (1972)

Endel Tulving.

Episodic and semantic memory.

Organization of memory, 1(381-403):1, 1972.

Wang et al. (2024)

Guanzhi Wang, Yuqi Xie, Yunfan Jiang, Ajay Mandlekar, Chaowei Xiao, Yuke Zhu, Linxi Fan, and Anima Anandkumar.

Voyager: An open-ended embodied agent with large language models.

Transactions on Machine Learning Research, 2024.

Wang et al. (2025)

Zihao Wang, Shaofei Cai, Anji Liu, Yonggang Jin, Jinbing Hou, Bowei Zhang, Haowei Lin, Zhaofeng He, Zilong Zheng, Yaodong Yang, et al.

Jarvis-1: Open-world multi-task agents with memory-augmented multimodal language models.

IEEE Transactions on Pattern Analysis and Machine Intelligence, 47(3):1894–1907, 2025.

Wang et al. (2026)

Ziye Wang, Modi Shi, Chaojun Ni, Jiazhi Yang, Mengdi Li, Zhizhong Su, Tianwei Lin, and Hongyang Li.

Nativemem: Native memory compression for long-horizon robotic manipulation.

arXiv preprint arXiv:2607.06678, 2026.

Xie et al. (2026)

Zhengwei Xie, Zhisheng Chen, Ziyan Weng, Jinhan Li, Chenglong Li, Zikai Xiao, Jingwei Song, Jinhao Jing, Vireo Zhang, and Kun Wang.

Mineevolve: Self-evolution with accumulated knowledge for long-horizon embodied minecraft agents.

arXiv preprint arXiv:2603.13131, 2026.

Zeng et al. (2026)

Guanning Zeng, Jiani Wang, Wenjie Ma, Shaofeng Yin, Chenyang Wang, Shichen Liu, Angjoo Kanazawa, Wode Ni, Xiuyu Li, Andrea Zanette, and Haiwen Feng.

[schema]: Frontier models with the right harness achieve \sim 99% on arc-agi-3 public.

Impossible Research. https://schema-harness.github.io/, 2026.

URL https://schema-harness.github.io/.

Zhang et al. (2026)

Haokai Zhang, Yuhang Ding, Yunshu Zhou, Xinze Du, Shengtao Zhang, Zhiyue Zhao, Yuling Xi, and Hao Chen.

Spatial memory agent: Experience-grounded procedure memory for spatial intelligence.

arXiv preprint arXiv:2608.12743, 2026.

Zheng et al. (2025)

Xinyue Zheng, Haowei Lin, Kaichen He, Zihao Wang, Qiang Fu, Haobo Fu, Zilong Zheng, and Yitao Liang.

Mcu: An evaluation framework for open-ended game agents.

In Proceedings of the 42nd International Conference on Machine Learning (ICML), 2025.

URL https://arxiv.org/abs/2310.08367.

Zhou et al. (2026a)

Sizhe Zhou, Sheldon Yu, Hui Wei, Junda Wu, Siru Ouyang, Yizhu Jiao, Shijia Pan, Julian McAuley, Yu Zhang, Tong Yu, et al.

Filesystem-based memory for llm agents: Organization, evolution, and sustainability.

arXiv preprint arXiv:2607.26637, 2026a.

Zhou et al. (2026b)

Ziheng Zhou, Huacong Tang, Jinyuan Zhang, Haowei Lin, Bangcheng Yang, Qian Long, Fang Sun, Yizhou Sun, Yitao Liang, Ying Nian Wu, et al.

Can current agents close the discovery-to-application gap? a case study in minecraft.

arXiv preprint arXiv:2604.24697, 2026b.

Zou et al. (2026)

Tao Zou, Yichen He, Tian Qiu, Yuan Lin, and Hang Li.

Task-focused memorization for multimodal agents.

arXiv preprint arXiv:2605.31075, 2026.

### S19 · Appendix A Additional Examples

[原文定位](https://arxiv.org/html/2610.22686v2#A1)

This appendix adds results and qualitative examples to Section 4.4.

Section A.1 covers milestone progression and interaction on Minecraft.

Section A.2 shows further cases of visual memory inspection.

Section A.3 gives qualitative examples on CUABench-KiCad.

### S20 · A.1 Milestone Progression and Interaction in Minecraft

[原文定位](https://arxiv.org/html/2610.22686v2#A1.SS1)

Fig. 8 tracks milestone progression on Kill the Ender Dragon with GPT-6-Astra, using one run per method.

VISTA gets diamond equipment earlier than MFM, but its progress then stalls.

MFM continues through obsidian and flint and steel and reaches netherrack within the same 36,000-step budget.

Table 3 reports seed-averaged results for all methods and base models.

Fig. 9 shows how many environment steps each method executes between successive model calls.

MFM and PRO-LONG generally execute more steps per turn than VISTA.

In other words, they issue longer action plans and call the model less often.

How MFM compares with PRO-LONG depends on the task.

On Ender Dragon, MFM executes more steps per turn than both baselines for 41–56% of each run.

On Mine Diamond, it does so for only 5–14% of each run, and PRO-LONG usually executes the most steps per turn.

Figure 8: Milestone progression on Kill the Ender Dragon with GPT-6-Astra.

Each curve shows one run’s progression through the Minecraft technology tree against environment steps (log scale).

Within the 36,000-step budget (dashed line), MFM reaches 16 of 24 milestones, compared with 13 for VISTA, 12 for PRO-LONG, and 6 for Direct Evaluation.

The shaded region marks milestones that no method reached.

One run is shown per method; Table 3 reports seed-averaged results.

Figure 9: Environment interaction per agent turn.

Rolling median of environment steps executed per agent turn over each run.

Columns are the three base models; rows are Mine Diamond from Scratch (top) and Kill the Ender Dragon (bottom).

Higher values mean more environment interaction between successive model calls; the vertical axis is logarithmic.

Shaded intervals mark where MFM exceeds both VISTA and PRO-LONG, and the annotation in each panel gives the shaded fraction.

### S21 · A.2 Visual Memory Inspection in Minecraft

[原文定位](https://arxiv.org/html/2610.22686v2#A1.SS2)

Figs. 10, 11, 12 and 13 expand on the Minecraft examples in Section 4.4.

In each case, the agent finds a stored frame through its index entry.

It then inspects the frame to answer a question that the textual record alone cannot:

what kind of animal it saw (Fig. 10),

where a hole it dug earlier is located (Fig. 11),

whether a place seen in an earlier life matches the current view (Fig. 12),

and why an earlier mining cut failed (Fig. 13).

(a) Stored frame: a pale animal on the hillside.

(b) Magnified crop: a wolf.

(c) Stored frame: a possible pink sheep.

(d) Magnified crop: a pink sheep.

Figure 10: Correcting and confirming perception with visual memory.

(a–b) At step 4,588, the agent records a pale animal on the hillside.

Magnifying the stored frame shows a wolf rather than a sheep, so the agent does not attack and looks for food elsewhere.

(c–d) At step 4,917, the agent is unsure whether an animal on the slope is a pink sheep.

Magnifying the stored frame confirms a sheep rather than a pig, and the agent hunts it for food.

(a) Stored frame of the hole the agent dug.

(b) Retrieved frame (left) beside the current view (right).

Figure 11: Memory-guided spatial relocation.

The retrieved and current views line up closely, which lets the agent identify the hole’s rim and recover its exact location.

(a) Life 1: stored frame of a shallow iron-mine entrance.

(b) Life 2: retrieved frame (left) beside the current view (right).

Figure 12: Cross-life visual memory retrieval.

After dying, the agent retrieves a frame recorded in an earlier life and compares it with its current view.

It recognizes the grass bank ahead as the entrance to that life’s iron mine, digs in, and mines iron ore at step 6,565.

(a) Retrieved frame: the earlier cut was pitched upward.

(b) Re-aimed view facing the mining face.

Figure 13: Using visual memory to recover mining orientation.

The agent inspects the frame of an earlier cut that failed to open a level passage.

It sees that the view was pitched upward rather than at the mining face.

It then re-aims with look_abs and resumes mining at the correct orientation.

### S22 · A.3 Qualitative Examples on CUABench-KiCad

[原文定位](https://arxiv.org/html/2610.22686v2#A1.SS3)

Fig. 14 shows the final schematics that MFM and VISTA produce on the three tasks discussed in Section 4.4.

On Task 55f2eefb, both agents get an “OK” from Change Symbol, but only MFM checks the resulting value; VISTA’s schematic still reads +9 V. Because MFM checks the resulting application state instead of trusting the “OK” returned by an edit operation, it catches incomplete edits that VISTA records as successful.

On Task c4baee36, both agents place the same components and wiring but use different supply labels.

On Task b7148878, MFM leaves one pin unconnected, compared with three for VISTA.

Fig. 15 shows how MFM verifies its own edits on three other tasks.

In each task, the agent follows the same three-step routine.

First, it inspects the schematic to confirm that component values and net labels match the specification.

Second, it runs the Electrical Rules Checker (ERC).

Third, it reads the ERC report to confirm that only the expected undriven-power errors remain and that no pins are left unconnected.

The agent first used this routine in an earlier task and later retrieved it from episodic memory, similar to the netlist-export reuse in Fig. 16.

Fig. 16 shows episode reuse across tasks.

While exporting a netlist in Task a6414tw4, the agent retrieves an episode from the earlier Task 4c913e30 whose action sequence is nearly identical, and follows it as a precedent.

(a) MFM, 55f2eefb: supply reads +5 V.

(b) MFM, c4baee36: +48 V and GND supply symbols.

(c) MFM, b7148878: one unconnected pin.

(d) VISTA, 55f2eefb: label still reads +9 V.

(e) VISTA, c4baee36: local label 3.3VDC on the output net.

(f) VISTA, b7148878: pins R1.1, U2.1, and U2.2 unconnected.

Figure 14: Qualitative comparison on CUABench-KiCad.

Final schematics produced by MFM (top) and VISTA (bottom); each column is one task.

(a, d) Task 55f2eefb, which switches an LED circuit’s supply from 9 V to 5 V: VISTA’s label still reads +9 V even though Change Symbol returned “OK”.

(b, e) Task c4baee36, a buck regulator: both agents place the same components and wiring but use different supply labels.

(c, f) Task b7148878, a two-op-amp circuit: MFM leaves one pin unconnected, compared with three for VISTA.

(a) ba34f1c3: the label and all five nets match the design; the title bar confirms the save.

(b) ERC dialog open; no error feedback from earlier actions.

(c) Only the two expected undriven-power errors; zero warnings.

(d) 4c913e30: wiring matches the committed design; the schematic is saved in the required directory.

(e) ERC dialog open; no error feedback from earlier actions.

(f) Only the three expected undriven-power errors (external supplies); zero warnings.

(g) 5dbc9e02: values, polarities, and all seven nets match the design.

(h) The title and status bar confirm the save location; ERC dialog open.

(i) Two expected undriven-power errors; zero warnings and no unconnected pins.

Figure 15: Self-verification of edits on CUABench-KiCad.

Each row shows one task.

MFM inspects the schematic against the specification (left), opens the Electrical Rules Checker (middle), and reads the report to confirm that only the expected errors remain (right).

(a) Current task a6414tw4, steps 6–10.

(b) Episode retrieved from the earlier task 4c913e30, steps 78–82.

Figure 16: Cross-task reuse of episodic memory in KiCad.

While working on the current task (top), the agent retrieves an episode from an earlier task (bottom) with a nearly identical action sequence.

The sequence is: save the blank schematic, open Export \rightarrow Netlist, select the native KiCad format, and set the output path.

The retrieved episode serves as a concrete precedent for the current task.

### S23 · A.4 Inspection Statistics

[原文定位](https://arxiv.org/html/2610.22686v2#A1.SS4)

We quantify a mechanism behind Sec. 4.4 over the main Minecraft runs (three models, two tasks, three seeds): how often inspecting a stored frame changed the agent’s next action (Fig. 17).

Does looking at a stored frame change the next action?

The agent looks before it commits, and the transcripts hold no counterfactual, so a

within-call before/after comparison is empty by construction. What can be measured is the

destination. A turn is a retarget if its plan names a

go_to/look_at coordinate the running plan did not contain, and a

recall target if that coordinate lies within 8 blocks of where the looked-at

episode was recorded; the null for recall is the fraction of all stored episodes that

would match the coordinate by position alone. On Mine Diamond

(Fig. 17), a turn that opened a stored frame retargets 2.5\times as often

as one that did not ( 17\% vs 7\% , p=5\times 10^{-6} , Fisher), and the new destination

is the retrieved episode’s location in 42 of 48 cases against a 37\% null

( p=6\times 10^{-13} , binomial). Ender Dragon shows the same pattern ( 33\% vs 14\% ;

15/17 against a 24\% null), as does the pool ( 19\% vs 11\% ; 57/65 against

33\% ). The

retrieval is therefore not merely correlated with replanning: it selects which

place the agent goes to next.

Figure 17: What follows a look at a stored frame. Left: the share of turns whose

plan names a destination the current plan did not have, after the agent opened a stored

episode frame (blue) against turns in which it opened no image at all (orange).

Right: of those new destinations, the share falling within 8 blocks of the

position at which the retrieved episode was recorded (blue), against the share of the

whole episode store that would match the same coordinate by position alone (orange).

### S24 · Appendix B Pseudocode

[原文定位](https://arxiv.org/html/2610.22686v2#A2)

Notation.

Let g denote the task objective, o_{t}=(v_{t},x_{t}) an observation,

and M_{t}=(E_{t},I_{t},C_{t}) the memory at step t .

Here E_{t} stores completed multimodal episodes, I_{t} provides searchable

cues and references to those episodes, and C_{t} contains revisable

agent-written knowledge. The algorithms use E , I , and C for their

current values. The initial memory may be empty or contain retained

experience. An episode groups a contiguous interaction interval;

B holds the interval currently being recorded, and \| denotes

sequence concatenation.

Algorithm 1 MFM: Multimodal Filesystem Memory

1:

Objective g ; environment \mathcal{E} ; initial memory M ; horizon T

2:

Updated memory M

3:

(E,I,C)\leftarrow M ; B\leftarrow\langle\rangle ; o_{1}\leftarrow\mathcal{E}.\textsc{Observe}()

4:

for t=1,\ldots,T do

5:

D_{t}\leftarrow\emptyset

6:

if past experience is needed then

7:

q_{t}\leftarrow\textsc{FormQuery}(g,C,\{o_{t}\})

8:

D_{t}\leftarrow\textsc{Retrieve}(q_{t},I)

9:

end if

10:

if consolidation is triggered then

11:

C\leftarrow\textsc{Consolidate}(g,C,E,I,\{o_{t}\}\cup D_{t})

12:

end if

13:

a_{t}\leftarrow\textsc{SelectAction}(g,o_{t},C,D_{t})

14:

(o_{t+1},f_{t})\leftarrow\mathcal{E}.\textsc{Step}(a_{t})

15:

Persist (o_{t},a_{t},o_{t+1},f_{t}) with their interaction identifiers

16:

Append references to these records to B

17:

if an episode boundary is reached then

18:

(E,I)\leftarrow\textsc{RecordEpisode}(B,E,I) ; B\leftarrow\langle\rangle

19:

end if

20:

if execution terminates then

21:

break

22:

end if

23:

end for

24:

if B\neq\langle\rangle then

25:

(E,I)\leftarrow\textsc{RecordEpisode}(B,E,I)

26:

end if

27:

return M=(E,I,C)

Here f_{t} denotes available interaction feedback. Episode boundaries and

consolidation triggers are supplied by the interaction protocol. Retrieval

may be repeated as needed, and action selection may reuse an existing plan

or procedure. Each resulting observation is recorded before its episode

is finalized, including at termination or the end of the horizon.

Algorithm 2 Episodic recording and indexing

1:

function RecordEpisode( B,E,I )

2:

\mathit{id}_{i}\leftarrow a unique episode identifier

3:

(\tau_{i},V_{i},S_{i},A_{i},m_{i})\leftarrow\textsc{OrganizeRecords}(B)

4:

e_{i}\leftarrow(\mathit{id}_{i},\tau_{i},V_{i},S_{i},A_{i},m_{i})

5:

\rho_{i}\leftarrow\textsc{StoreEpisode}(e_{i}) \triangleright Preserve the original evidence

6:

k_{i}\leftarrow\textsc{BuildCues}(e_{i})

7:

z_{i}\leftarrow(\mathit{id}_{i},k_{i},\rho_{i})

8:

return (E\|\langle e_{i}\rangle,\ I\|\langle z_{i}\rangle)

9:

end function

The episode contains its interval \tau_{i} , visual observations V_{i} ,

structured states S_{i} , attempted actions A_{i} , and metadata m_{i} .

The cues k_{i} include available temporal, spatial, action, and outcome

descriptions; \rho_{i} references the underlying stored evidence.

Organizing and indexing records does not replace or compress their

original multimodal content.

Algorithm 3 Retrieval through textual cues and evidence references

1:

function Retrieve( q,I )

2:

R\leftarrow\textsc{Filter}(I,q) \triangleright Retain entries satisfying all query predicates

3:

P\leftarrow\textsc{SelectReferences}(q,R)

4:

D\leftarrow\{\textsc{Load}(p):p\in P\}

5:

return D

6:

end function

Filtering preserves index order and may restrict results by recency when

requested. The agent selects P\subseteq\bigcup_{z_{i}\in R}\rho_{i} , specifying

which referenced observations or records to inspect. Textual cues locate

candidate episodes; the underlying evidence can contain details absent

from those cues.

Algorithm 4 Self-evolving consolidation

1:

function Consolidate( g,C,E,I,D )

2:

D^{\mathrm{cons}}\leftarrow D

3:

while additional evidence is needed do

4:

q\leftarrow\textsc{FormQuery}(g,C,D^{\mathrm{cons}})

5:

D^{\mathrm{cons}}\leftarrow D^{\mathrm{cons}}\cup\textsc{Retrieve}(q,I)

6:

end while

7:

C^{+}\leftarrow\mathcal{U}(C,D^{\mathrm{cons}},g)

8:

return C^{+} \triangleright E and I remain unchanged

9:

end function

The agent’s update \mathcal{U} revises plans, findings, relational memory,

general guidance, or reusable procedures as appropriate. Relations may be

expressed as \ell=(u,r,v;P_{\ell}) , where P_{\ell} references

supporting evidence. Consolidation changes interpretations while preserving

the episode archive and index; it does not execute environment actions.

### S25 · Appendix C Skills

[原文定位](https://arxiv.org/html/2610.22686v2#A3)

⬇

"""cut_step: cut one descending step and advance; requires a pick, close solid dirt/stone wall, centered cardinal alignment, safe footing and no opening or GUI. Proven at steps5068-5249."""

import argparse,json,sys

PARAMS={"yaw":"cardinal heading toward the inspected solid wall"}

p=argparse.ArgumentParser();p.add_argument(’–args’,default=’{}’)

a=json.loads(p.parse_args().args);s=json.load(sys.stdin);acts=[]

if not s.get(’gui_open’):

yaw=a.get(’yaw’,s[’pos’][’yaw’])

for pitch in (0,45,65):

acts += [{’procedure’:’look_abs’,’args’:{’pitch’:pitch,’yaw’:yaw,’ticks’:10}},{’action’:{’attack’:1},’repeat’:45}]

acts += [{’action’:{’forward’:1},’repeat’:8},{’action’:{},’repeat’:8},{’procedure’:’look_abs’,’args’:{’pitch’:60,’yaw’:yaw,’ticks’:10}}]

print(json.dumps({’actions’:acts}))

⬇

"""quarry_north_pair: mine one upper/lower north wall pair and collect; requires suitable pick held, solid close stone wall north, level solid floor, no GUI or opening; sweep advances about one block."""

import json,sys

s=json.load(sys.stdin)

a=[{’procedure’: ’look_abs’, ’args’: {’pitch’: 0, ’yaw’: 180, ’ticks’: 10}}, {’action’: {’attack’: 1}, ’repeat’: 30}, {’procedure’: ’look_abs’, ’args’: {’pitch’: 50, ’yaw’: 180, ’ticks’: 10}}, {’action’: {’attack’: 1}, ’repeat’: 30}, {’procedure’: ’collect_drops’, ’args’: {’ticks’: 24}}] if not s.get(’gui_open’) else []

print(json.dumps({’actions’:a}))

⬇

"""bridge_north: extend one northern floor block using continuous sneak; face within 90 degrees of north with cobblestone held, clear headroom, and verified floor ahead. Repaired after two raw successes."""

import argparse

import json

import math

import sys

PARAMS = {"x": "bridge floor x", "y": "bridge floor y", "z": "new northern floor cell z"}

p = argparse.ArgumentParser()

p.add_argument(’–args’, default=’{}’)

a = json.loads(p.parse_args().args)

s = json.load(sys.stdin)

pos = s[’pos’]

actions = []

north_error = abs((pos[’yaw’] - 180 + 180) % 360 - 180)

if (not s.get(’gui_open’) and s.get(’inventory’, {}).get(’cobblestone’, 0) > 0

and north_error <= 90 and -10 <= pos[’pitch’] <= 80

and math.floor(pos[’x’]) == a[’x’] and abs(pos[’y’] - a[’y’] - 1) < .05

and math.floor(pos[’z’]) - 1 == a[’z’]):

actions = [

{’action’: {’camera’: [80-pos[’pitch’], (180-pos[’yaw’]+180)\%360-180], ’sneak’: 1}, ’repeat’: 1},

{’action’: {’forward’: 1, ’sneak’: 1}, ’repeat’: 20},

{’action’: {’sneak’: 1}, ’repeat’: 8},

{’action’: {’camera’: [1, -90], ’sneak’: 1}, ’repeat’: 1},

{’action’: {’camera’: [0, -90], ’sneak’: 1}, ’repeat’: 1},

{’action’: {’use’: 1, ’sneak’: 1}, ’repeat’: 1},

{’action’: {’sneak’: 1}, ’repeat’: 8},

{’action’: {’camera’: [-16, 90], ’sneak’: 1}, ’repeat’: 1},

{’action’: {’camera’: [0, 90], ’sneak’: 1}, ’repeat’: 1},

{’action’: {’sneak’: 1}, ’repeat’: 8}

]

print(json.dumps({’actions’: actions}))

⬇

import json

import math

import sys

PARAMS = {"target_y": "target feet height, minimum 12", "pick": "pickaxe hotbar slot 1-9", "max_steps": "mining budget, maximum 370"}

arguments = json.loads(sys.argv[sys.argv.index("–args") + 1]) if "–args" in sys.argv else {}

state = json.load(sys.stdin)

position = state.get("pos")

if not position or state.get("gui_open"):

raise SystemExit("close the screen and stand on solid ground first")

if abs(position["y"] - round(position["y"])) > 0.05:

raise SystemExit("not standing at an integer block height")

for coordinate in ("x", "z"):

fraction = position[coordinate] - math.floor(position[coordinate])

if not 0.30 <= fraction <= 0.70:

raise SystemExit("center within the block before descending")

speeds = {"stone_pickaxe": (22, 19), "iron_pickaxe": (18, 15), "diamond_pickaxe": (15, 12)}

pickaxes = [entry for entry in state["hotbar"] if entry.get("item") in speeds]

if "pick" in arguments:

pickaxes = [entry for entry in pickaxes if int(entry["slot"]) + 1 == int(arguments["pick"])]

if not pickaxes:

raise SystemExit("requested pickaxe is not in the hotbar")

pickaxe = min(pickaxes, key=lambda entry: speeds[entry["item"]][0])

height = int(round(position["y"]))

target = max(12, int(arguments.get("target_y", 12)))

if height <= target:

raise SystemExit("target depth reached; mine horizontally")

normal_speed, minimum_speed = speeds[pickaxe["item"]]

steps = min(370, max(1, int(arguments.get("max_steps", 300))), (height - target) * normal_speed, (height - 11) * minimum_speed)

print(json.dumps({"actions": [

{"procedure": "equip_hotbar", "args": {"slot": int(pickaxe["slot"]) + 1}},

{"procedure": "look_abs", "args": {"pitch": 88, "steps": 8}},

{"procedure": "mine_ahead", "args": {"n": steps, "ore_watch": True}},

{"procedure": "look_abs", "args": {"pitch": 25, "steps": 8}}

]}))

⬇

"""tunnel: extend a level two-block-high tunnel by up to four cells, watching for ore and hazards."""

import json

import sys

PARAMS = {"cells": "one to four cells", "yaw": "cardinal tunnel heading", "pick": "pickaxe hotbar slot 1-9"}

arguments = json.loads(sys.argv[sys.argv.index("–args") + 1]) if "–args" in sys.argv else {}

state = json.load(sys.stdin)

position = state.get("pos")

if not position or state.get("gui_open"):

raise SystemExit("close the screen before tunneling")

if abs(position["y"] - round(position["y"])) > 0.05:

raise SystemExit("stand on solid ground before tunneling")

if position["y"] < 11:

raise SystemExit("restore feet to y11 or higher before tunneling")

heading = float(arguments.get("yaw", position["yaw"]))

if abs(heading / 90 - round(heading / 90)) > 0.01:

raise SystemExit("choose a cardinal heading")

slot = int(arguments.get("pick", 7))

pickaxes = [entry for entry in state["hotbar"] if int(entry["slot"]) + 1 == slot and entry.get("item") in ("iron_pickaxe", "stone_pickaxe", "diamond_pickaxe")]

if not pickaxes:

raise SystemExit("requested pickaxe is missing")

cells = min(4, max(1, int(arguments.get("cells", 4))))

actions = [{"procedure": "equip_hotbar", "args": {"slot": slot}}]

for cell in range(cells):

actions.extend([

{"procedure": "look_abs", "args": {"pitch": 0, "yaw": heading, "steps": 8}},

{"action": {"attack": 1}, "repeat": 30},

{"procedure": "look_abs", "args": {"pitch": 65, "yaw": heading, "steps": 8}},

{"action": {"attack": 1}, "repeat": 30},

{"action": {"forward": 1}, "repeat": 12}

])

actions.append({"procedure": "look_abs", "args": {"pitch": 0, "yaw": heading, "steps": 8}})

print(json.dumps({"actions": actions}))

⬇

"""probe: mine a stationary three-block side probe at a gentle downward angle, watching for ore."""

import json

import sys

PARAMS = {"yaw": "cardinal probe heading", "pick": "pickaxe hotbar slot 1-9"}

arguments = json.loads(sys.argv[sys.argv.index("–args") + 1]) if "–args" in sys.argv else {}

state = json.load(sys.stdin)

position = state.get("pos")

if not position or state.get("gui_open"):

raise SystemExit("close the screen before probing")

if position["y"] < 11 or abs(position["y"] - round(position["y"])) > 0.05:

raise SystemExit("stand on solid ground at y11 or higher before probing")

heading = float(arguments.get("yaw", position["yaw"]))

if abs(heading / 90 - round(heading / 90)) > 0.01:

raise SystemExit("choose a cardinal heading")

slot = int(arguments.get("pick", 8))

pickaxes = [entry for entry in state["hotbar"] if int(entry["slot"]) + 1 == slot and entry.get("item") in ("iron_pickaxe", "stone_pickaxe", "diamond_pickaxe")]

if not pickaxes:

raise SystemExit("requested pickaxe is missing")

actions = [

{"procedure": "equip_hotbar", "args": {"slot": slot}},

{"procedure": "look_abs", "args": {"pitch": 15, "yaw": heading, "steps": 8}}

]

for block in range(3):

actions.extend([

{"action": {"attack": 1}, "repeat": 30},

{"action": {}, "repeat": 1}

])

print(json.dumps({"actions": actions}))

⬇

First time:

“‘

Action 1 | Step 1 [ACTION] look(pitch=0,yaw=18) -> 1 ticks

Action 2 | Step 26 [ACTION] {"attack":1,"forward":1} x25

[STATE] pos=(-3010.70, 71.00, -5569.30) pitch=0 yaw=18 moved=3.42

[EVENT] mine_block spruce_leaves +1 (x2)

Action 3 | Step 226 [ACTION] mine_ahead(n=200) -> 200 ticks

[EVENT] mine_block spruce_leaves +1 (x4)

[NOTE] mine_ahead: finished 200 ticks, broke 4 blocks.

Action 4 | Step 227 [PLAN] OBSERVED vs EXPECTED: Leaves broke, but no wood; the exposed trunk is left of the crosshair.

[ACTION] look(yaw=-28,pitch=0) -> 1 ticks

Action 5 | Step 297 [ACTION] mine_ahead(n=100) -> 100 ticks

[EVENT] MILESTONE mine_log verified

[EVENT] mine_block spruce_log +1

“‘

Second time:

“‘json

{"actions":[{"procedure":"look_abs","args":{"pitch":0,"yaw":18,"steps":8}},

{"action":{"attack":1,"forward":1},"repeat":25},

{"procedure":"mine_ahead","args":{"n":70}},

{"procedure":"look_abs","args":{"pitch":0,"yaw":-10,"steps":8}},

{"procedure":"mine_ahead","args":{"n":150}}]

}

“‘

Third time:

> Spawn spruce approach verified two times: yaw18, attack+forward25, mine_ahead70, yaw-10, mine150.

⬇

The detector:

“‘

def find_blazes(path, ymax=150):

"""Return blobs [{’x’,’y’,’area’,’h’,’dist’}], nearest (biggest) first."""

from PIL import Image

im = Image.open(path).convert("RGB")

if im.size != (W, H):

im = im.resize((W, H))

px = im.load()

# A BLAZE IS YELLOW, FIRE IS ORANGE: the burning grass and the flames on the trees here

# measure (165, 66, 5) – green 66 – while a blaze’s rods are (167, 167, 79). The warm

# mask takes both (a blaze close up is wrapped in its own orange flames); ‘yellows‘ marks

# the rod-coloured ones, and a group must contain at least one to count as a mob.

warm = set()

yellows = set()

for y in range(0, ymax):

row_guard = y < 40

for x in range(0, W):

if row_guard and x >= 296:

continue

# my own arm holding the sword is screen-fixed at the bottom right and reads warm

if x >= 282 and y >= 42:

continue

r, g, b = px[x, y]

if r > 140 and g > 80 and b < 130 and r - b > 60 and g - b > 20:

warm.add((x, y))

if g > 110 and r - g < 70 and g - b > 40:

yellows.add((x, y))

… # erode on the 4-neighbour cross, then merge fragments on a 13-px grid (union-find)

for g, yel in merged.values():

if len(g) < MIN_AREA:

continue

# fire is orange THROUGHOUT; a blaze always shows its yellow rods … every real

# blaze frame measured here runs 33\% to 100\%. A 10\% line separates them.

if yel < YELLOW or yel < 0.10 * len(g):

continue

xs = [q[0] for q in g]

ys = [q[1] for q in g]

h = float(max(ys) - min(ys) + 1)

…

out.append({"x": sum(xs) / float(len(xs)), "y": sum(ys) / float(len(ys)),

"area": float(len(g)), "h": h, "yel": float(yel), "dtop": float(dtop),

"w": float(max(xs) - min(xs) + 1),

"dist": BLAZE_H * FOCAL / max(2.0, h)})

out.sort(key=lambda b: -b["area"])

return out

“‘

Aim and swing:

“‘

dyaw = _cap(_deg(tgt["x"] - CX))

tdown = MAXDOWN_Y if tgt["yel"] / max(tgt["area"], 1.0) >= YELSURE else MAXDOWN

dpitch = _cap(max(min(_deg(tgt["y"] - CY), tdown - pitch), MAXUP - pitch))

dist = tgt["dist"]

if dist <= reach + 0.5:

memo["inreach_t"] = ticks # the clock the vanish test above reads

aimed = abs(dyaw) < 10 and abs(dpitch) < 10

…

acts.append({"action": {"camera": [dpitch, dyaw]}, "repeat": 1})

if not aimed:

# SWING WHILE TURNING (step 510). 240 ticks bought 4 swings … The melee hitbox is

# wider than 10 deg and a swing at nothing costs nothing

if abs(dyaw) < 25 and abs(dpitch) < 25 and ticks - int(memo.get("last_swing", -99)) >= SWING - 1:

acts.append({"action": {"attack": 1}, "repeat": 1})

…

if ticks - int(memo.get("last_swing", -99)) >= SWING - 1:

acts.append({"action": {"attack": 1, "forward": 1 if (far and not under) else 0,

"sneak": 1 if edge else 0}, "repeat": 1})

“‘

### S26 · Appendix D Harness and Implementation Details

[原文定位](https://arxiv.org/html/2610.22686v2#A4)

This appendix covers five things:

the episode index (Section D.1),

the spatial grid (Section D.2),

the configuration of each method and the action interface shared by all methods (Section D.3),

and storage and cost statistics (Section D.4).

### S27 · D.1 Episode Index

[原文定位](https://arxiv.org/html/2610.22686v2#A4.SS1)

The harness appends one row to index.jsonl for each completed episode (Section D.1).

Each row contains:

•

the episode identifier and the path to the episode’s directory;

•

the first and last environment steps of the episode;

•

the kind of action executed;

•

a one-line summary;

•

a list of tags;

•

the agent’s position (x,y,z) .

The summary records the procedure call with its arguments, followed by its outcome: how long it ran, how far the agent moved, how the inventory changed, and any milestone reached.

Tags flag notable events such as a milestone, an inventory change, or a failure to move (stuck).

The harness computes all of these fields from the structured game state; the model does not write them.

### S28 · D.2 Spatial Grid

[原文定位](https://arxiv.org/html/2610.22686v2#A4.SS2)

The harness also maintains grid.jsonl, an append-only record of the world cells the agent has interacted with.

Each row gives a cell’s integer coordinates, the step at which it was recorded, and one of five kinds:

•

walked: the agent stood in the cell;

•

placed: the agent placed an item in the cell;

•

opened: the agent opened the screen of a block in the cell;

•

blocked: the agent could not move into the cell;

•

hazard: the agent took damage in the cell.

Rows of kind placed and opened also record the item and the agent’s pose at that moment.

Rows of kind hazard record the amount and type of damage.

Below we give one example of each kind.

### S29 · D.3 Method Configurations

[原文定位](https://arxiv.org/html/2610.22686v2#A4.SS3)

Table 6 lists the configuration of each method on Minecraft. All methods receive the same 12 KB standing brief in prompt.

The atoms are closed-loop: they read the structured game state at every step.

No method has access to task-specific macros such as tree harvesting, strip mining, or portal building.

We reimplemented PRO-LONG and VISTA in our harness without changing their core algorithms.

PRO-LONG keeps its programmatic text logs, and VISTA keeps its archive of visual observations and its inspect interface.

Matched inspection, different addressing. VISTA and MFM have equivalent visual inspection capabilities: both store every observation losslessly with its step identity, and both let the agent reopen earlier frames, crop and enlarge regions, and compare several past or current views in one context. The methods differ only in how the agent locates evidence and what it does with it. VISTA addresses frames by turn and frame identifier; MFM additionally provides a harness-written index of cues (time, position, action type, tags, outcome summary) that the agent can query, and agent-written memory that cites the supporting episodes. Our comparison with VISTA therefore isolates the contribution of the addressing layer and consolidation, not of the inspection tools.

Why only MFM writes executable procedures. Neither baseline provides a persistent place for agent-written procedures: PRO-LONG’s durable memory is a single harness-owned log, and VISTA’s writable memory is limited to two notes files. Turning an action sequence into a procedure also requires checking whether that sequence has succeeded before. MFM’s associative index makes this check direct: the agent can query past episodes by action type and outcome tags, then inspect the linked frames to confirm the result. VISTA addresses frames only by turn identifier, and PRO-LONG’s text log, while searchable, has no structured action or outcome fields and no links to visual evidence, so the same check requires scanning and reconstructing past attempts. Without these supports, the baselines kept their procedural knowledge as prose notes rather than callable procedures.

Table 6: Configuration of each method on Minecraft tasks.

All methods share the action and procedure reference, the knowledge sections, the ground-truth rules, and the per-turn state block; Direct Evaluation omits the block’s [RECENT] and [MAP] fields.

All methods with memory can write files and execute stored procedures through the same interface.

Capability

Direct

PRO-LONG

VISTA

MFM

Standing brief

12 KB

12 KB

12 KB

12 KB

Per-turn [RECENT] / [MAP]

no (as direct agent is not supposed to have any memory)

yes

yes

yes

Episode store and query tool

no

no

archived frames via inspect

yes

Write access to own files; procedure execution

yes

yes

yes

yes

Agent-written procedures (observed)

0

0

0

4 written / 14 calls

Plan cap

400 steps

400 steps

400 steps

400 steps

Images per call

current frame

current frame

current frame + inspected frames

current frame + inspected frames

### S30 · D.4 Storage and Cost

[原文定位](https://arxiv.org/html/2610.22686v2#A4.SS4)

All main and ablation results are averaged over 3 seeds; each seed fixes the Minecraft world or KiCad task order, with further variation from stochastic model sampling. In total we ran 96 Minecraft runs (72 main + 24 ablation, capped at 12k steps for Diamond and 36k for Dragon) and 1,125 KiCad episodes ( 25\text{ tasks}\times 15\text{ configurations}\times 3\text{ seeds} ). All 48 Dragon runs exhaust their budget

(Fig. 9), consuming \approx 1.7M steps and up to 14 hours each. In the Claude Opus 5 on Dragon configuration, a single run makes 0.9\text{--}3.9\text{k} model calls and costs \$108\text{--}\$969 (Table 8).

Table 7 reports storage, retrieval, and memory-use statistics for one MFM run.

Table 8 reports the cost of one Kill the Ender Dragon run per method with Claude Opus 5. Both tables come from single runs and are meant to show orders of magnitude.

Table 7: Storage, retrieval, and memory-use statistics for the GPT-6-Astra Mine Diamond run that reached all 10 milestones.

Quantity

Value

Environment steps

12,000

Model calls

130

Episodes stored

636

Episode directory on disk

46 MB

Index (index.jsonl) size

313 KB

Full-resolution frames on disk

720 MB

Query time over the full index

0.3–0.4 s

view_image calls

87

Agent-written procedures (written / calls)

4 / 14

Table 8: Costs of Ender Dragon runs with Claude Opus 5 (36,000 steps) using Claude Code.

Method

Milest. obs.

Calls

Tokens (M)

USD ($)

MFM

10

2,129

47

108

VISTA

9

2,177

69

172

PRO-LONG

8

895

57

168

Direct

6

3,934

155

969

### S31 · E.1 MCU Tasks Descriptions

[原文定位](https://arxiv.org/html/2610.22686v2#A5.SS1)

Mine Diamond from Scratch. The agent starts with no resources and must progress through the Minecraft technology tree: gathering wood, stone, and iron, crafting increasingly capable tools, and ultimately mining a diamond.

Kill Ender Dragon. The agent completes the same early-game progression, then prepares diamond equipment, enters the Nether to obtain blaze materials, crafts Eyes of Ender, reaches the End, and defeats the Ender Dragon.

Figure 18: Milestone progression for the Minecraft tasks. Mine Diamond from Scratch contains 10 milestones, while Kill Ender Dragon shares the same initial progression and adds 14 milestones required to reach and defeat the Ender Dragon. Numbers in the left column index the Mine Diamond list; inner and right-column numbers index the Ender Dragon list, in which Diamond ore is inserted as milestone 10, so Diamond becomes 11 and the added milestones continue from 12. Note that the milestones do not need to be finished strictly in this order.

### S32 · E.2 New Tasks for Evaluating Skill Reuse

[原文定位](https://arxiv.org/html/2610.22686v2#A5.SS2)

We design three additional Minecraft tasks to study whether reusing

agent-written skills reduces the steps required to solve new tasks.

These tasks introduce new objectives while providing opportunities

to apply procedures acquired during earlier interaction.

Iron Shield. The agent builds a furnace, mines iron ore,

smelts an iron ingot, and crafts a shield, combining intermediate

objectives familiar from Mine Diamond from Scratch with a new crafting

goal. A small vein of iron ore is placed underground, 13 blocks below

and 12 blocks south of the starting position, at coordinates given in

the task description.

Climb Out. The agent starts sealed in a two-block pocket deep

underground and must return to the surface, 40 blocks above, and mine a

block of bricks set in the ground there; the block’s coordinates are

given in the task description. Reaching it requires digging upward,

whereas the example procedures supplied to the agent only dig downward

or level.

Cook Meat. The agent builds a furnace, kills an animal, and

cooks its meat, introducing a hunting objective absent from Mine

Diamond from Scratch. Three cows are placed beside the starting

position.

In all three tasks, early-game resources are supplied (a stone pickaxe

and cobblestone, plus a crafting table and logs for Iron Shield and

Cook Meat, and a stone sword for Cook Meat) and the target is either

placed nearby or located in the task description, reducing the need to

repeat initial resource gathering and search.

We compare the steps required to complete each task with and without

access to previously written skills. This evaluation tests whether

procedures learned from earlier experience improve efficiency when

applied to new objectives.

Figure 19: Milestone structure of Diamond and three related tasks. Columns align the tasks by Diamond’s ten milestones. Blue indicates shared, scored milestones; orange indicates task-specific milestones; gray indicates milestones provided at initialization and excluded from scoring. Empty cells denote Diamond milestones not scored in the corresponding task.

### S33 · E.3 Prompts and Outputs Examples

[原文定位](https://arxiv.org/html/2610.22686v2#A5.SS3)

In this section, we provide examples of prompts used.
