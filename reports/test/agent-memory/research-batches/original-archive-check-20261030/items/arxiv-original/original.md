---
schema_version: 1
kind: original_snapshot
title: Multimodal Filesystem Memory For Long-Horizon Embodied Agents
source_id: paper-1337d0ee-7403-4fe2-8802-f1771af20c20
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
source_version: v1
topics:
- agent-memory
source_url: https://arxiv.org/abs/2610.22686v1
captured_at: '2026-10-30T09:49:48.381885+00:00'
content_sha256: e4a87f0e5968e2f3401058bb0fd33b6678e64ccbce092702cb0e2fe55a108786
coverage: full_text
research_coverage: full_text
---

# Multimodal Filesystem Memory For Long-Horizon Embodied Agents

> TEST：原文抽取归档，用于阅读及重放，不代表正式研究结论。

- [打开来源原文](https://arxiv.org/abs/2610.22686v1)。
- 原文归档保存完整可用抽取文本；研究与审阅实际范围为 `full_text`，可小于本归档。
- 不保存可执行网页、PDF 版式或图片，不保证公式和图表的抽取完整性，未复现实验。
- 抽取方式：`html`；抽取范围：`full_text`。
- 抽取限制：Text extraction does not verify figures, layout, or faithful mathematical rendering.
- 取材：html / success / extracted。

## 获取记录

- [text/html](https://arxiv.org/abs/2610.22686v1)；响应 SHA-256：`e6294b365069f75ad55c48e84826a3cb0ff90028eb8e607d25304429e93a6846`；抓取时间：2026-10-30T09:49:44.991289+00:00。
- [text/html](https://arxiv.org/html/2610.22686v1)；响应 SHA-256：`f4630633078fae50299f76cd548118f70f9941672cce132d2a2af45effc5a5cc`；抓取时间：2026-10-30T09:49:48.208954+00:00。

## 抽取正文

### S1 · Multimodal Filesystem Memory for Long-Horizon Embodied Agents

[原文定位](https://arxiv.org/html/2610.22686v1)

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

GitHub Project Page

Weirui Ye

Affiliation: MIT

Yilun Du

Affiliation: Harvard

Affiliation: Kempner Institute

### S2 · Abstract

[原文定位](https://arxiv.org/html/2610.22686v1#abstract1)

Agents operating over long horizons need an effective memory that allows them to reuse their experience throughout long interactions. If the entire history of an interaction is retained, it becomes difficult to find the relevant experience, while compressing it into summaries may result in the loss of visual and spatial details that are required later on. We present MFM, a multimodal filesystem memory architecture that keeps complementary types of agent memory. Episodic memory stores the observations, actions, and outcomes, and spatial memory associates experiences with locations. Semantic and procedural memory build up general knowledge and reusable methods of acting, and working memory holds the current plans. MFM makes use of searchable textual records to connect these different representations to the underlying multimodal episodes. The agents are able to find previous experiences by means of contextual cues and to examine the original observations in order to recover details that are missing from their textual descriptions. Through consolidation, the agents convert experience into higher-level knowledge and procedures while still keeping references to the original episodes. In the case of long-horizon Minecraft and computer-use tasks, MFM leads to improved performance with three base models. With GPT-6-Astra, MFM completes Mine Diamond from Scratch and reaches 16 out of 24 milestones on the Ender Dragon task, as against 12.7 for the best baseline. On CUABench-KiCad it attains a mean reward of 0.440, as compared to 0.400 for the best baseline and 0.267 in the case of no persistent memory.

$\star$$\star$footnotetext: Equal contribution.

### S3 · 1 Introduction

[原文定位](https://arxiv.org/html/2610.22686v1#S1)

Agents that are intelligent and capable of operating autonomously over long periods in complicated, open-ended environments need to remember what they have seen, discovered, and previously done (Park et al., 2025; Wang et al., 2026). A large part of this kind of memory will generally be visual or spatial in character, for instance the route by which one can get back to an object that it has seen before. It is not clear what the appropriate form of compact memory the agent should use to store such observations. If one stores everything directly then it becomes difficult to find relevant experiences as the amount of history increases. Conversely, summaries of the memory enable quicker retrieval, but may result in important details being discarded later (Lu et al., 2026; Zou et al., 2026).

We represent memory as a multimodal filesystem (MFM) which simultaneously holds different types of memory. We organize the memory based on the distinctions between various human memory systems (Tulving, 1972; Squire, 2004). In the MFM, episodic memory preserves past observations and interactions, spatial memory connects experiences to locations in the environment, semantic memory records facts and relationships, procedural memory contains reusable methods of acting, and working memory holds the current plan and the immediate subgoals. The five memory functions are realised using three common storage elements: episodic records, an associative index, and agent-written memory. These elements are arranged as folders and files in a shared filesystem, with references that link knowledge, procedures, and plans to their supporting episodes.

Previous work that has used a filesystem to store agent memory has shown the effectiveness of searchable textual records of interaction (Fox et al., 2026). With embodied agents, textual descriptions can fail to include important visual or spatial information. VISTA (Han et al., 2026) keeps visual observations and allows frames to be revisited using a turn or frame identifier, thus holding on to information that goes beyond its textual summaries. Yet it can be difficult to find the relevant experience, particularly as the memory increases. MFM offers an explicit structuring of the memory in the form of a filesystem, which enables quick retrieval of context and the aggregation of skills and knowledge.

Figure 1: MFM’s Memory Evolution in Minecraft. Over 36,000 steps, MFM continuously updates its memory and retrieves from it to support decision-making.

As shown in Fig. 2, associative indexing links these representations via searchable cues to the stored evidence. Text acts as an addressing layer for multimodal records: the agent begins by searching the descriptions of events, actions, and locations and then looks up the references in order to examine the corresponding observations. For instance, it can find a previous visit to a cave by means of its coordinates or by referring to an action that was attempted, check the recorded view, and then compare it with the current observation. The cues employed to locate an episode need not include a description of all the details of the episode. This enables us to navigate a long history of past episodes using compact records and at the same time retain detailed visual information which may only become relevant later.

With increasing experience, MFM employs self-evolving consolidation in order to update its knowledge, skills, and current working plans. Specific observations can lead to the establishment of new facts or relationships, useful action sequences can be turned into reusable procedures, and new information discovered can cause the agent to alter its present plan. These updates link episodic experience to semantic, procedural, and working memory. For instance, the agent might connect a resource with a cave that has just been explored, record a reliable procedure for getting to it, and change its route if a subsequent observation indicates that the entrance is blocked. Since the memories written by the agent include references to the episodes that support them, the agent can go back and look at the original evidence whenever its interpretation becomes uncertain or is contradicted. The evolution of the memory is illustrated in Fig. 1.

Our work consists of three parts. Firstly, we propose a method for organising a multimodal agent’s memory within a single filesystem, covering episodic, spatial, semantic, procedural, and working memory. Secondly, we implement this organisation in MFM, which combines cue-based retrieval and visual inspection with consolidation into revisable knowledge and reusable procedures. Thirdly, we demonstrate through long-horizon Minecraft and computer-use tasks that MFM surpasses both memory-free and memory-augmented baseline methods when using three base models, and that it is able to reuse its memory across different tasks. Using GPT-6-Astra, our system manages to complete the MCU Mine Diamond from Scratch task in all instances and achieves 16 out of 24 milestones on Ender Dragon, whereas the best baseline achieves an average of 12.7. On CUABench-KiCad, its mean reward is 0.440, compared to 0.400 for the best baseline and 0.267 for an agent lacking persistent memory.

### S4 · 2 Related Work

[原文定位](https://arxiv.org/html/2610.22686v1#S2)

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

[原文定位](https://arxiv.org/html/2610.22686v1#S3)

We present MFM, a multimodal filesystem memory architecture designed for long-horizon agents. This architecture incorporates three complementary elements: episodic records which store the multimodal experience, a searchable index that enables textual access to these records, and agent-written memory which structures plans, findings, environmental knowledge, and reusable procedures. Fig. 2 shows the structure of this approach, while Fig. 3 illustrates an example from Minecraft, covering the processes of episodic recording and indexing as well as retrieval and consolidation. Section 3.2 explains the various memory components and the way in which searchable records are linked to the multimodal evidence, Section 3.3 describes how the agent finds and examines relevant episodes, and Section 3.4 outlines how the accumulated experience is consolidated into reusable knowledge without losing the original evidence. Algorithm 1 gives a summary of the entire loop.

Figure 2: Overview of MFM. Five forms of memory in one filesystem. Harness-written episodic memory records observations, states, actions, and outcomes every step, with searchable cues for locating them; spatial

memory ties experiences to locations. Agent-written semantic, procedural, and working memory hold facts, reusable procedures, and the current plan, each citing its supporting episodes. The agent retrieves by

searching cues and inspecting original evidence (Sec. 3.3), and consolidates experience into knowledge, procedures, and plans without modifying episodic records (Sec. 3.4).

### S6 · 3.1 Problem Setup

[原文定位](https://arxiv.org/html/2610.22686v1#S3.SS1)

An agent interacts with an environment over a long horizon to achieve a task objective g . At step t , it receives an observation o_{t}=(v_{t},x_{t}) , where v_{t} is a visual observation and x_{t} contains textual or structured information, and selects an action a_{t} . Its interaction history is H_{t}=(o_{1},a_{1},\ldots,a_{t-1},o_{t}) . As this history grows beyond the model’s context budget, the agent must retain information outside its active context and retrieve it when needed. We represent this external memory as M_{t}=(E_{t},I_{t},C_{t}) , where E_{t}=(e_{1},\ldots,e_{N_{t}}) stores the N_{t} completed episodes retained at step t , I_{t} provides an index for locating these episodes, and C_{t} contains agent-written knowledge.

Below, we discuss how these components support complementary forms of memory.

### S7 · 3.2 Memory Representation

[原文定位](https://arxiv.org/html/2610.22686v1#S3.SS2)

As shown in Figure 2, MFM divides memory into three parts: episodic records of multimodal experience, a searchable index, and agent-written memory. This approach is based on the difference between episodic memory, which relates to specific experiences, and semantic and procedural memory, which concern knowledge and ways of acting (Tulving, 1972; Squire, 2004). The episodic store E_{t} holds the observations, states, and actions, while the index I_{t} gives cues for finding these records. The agent-written memory C_{t} links discoveries from different episodes and keeps environmental knowledge, reusable procedures, and working plans. The following section explains each of these in turn.

Episodic memory.

To revisit a past experience, the agent needs access to what it observed, what it attempted, and what happened. We retain episodes as multimodal records,

e_{i}=\bigl(\mathrm{id}_{i},\tau_{i},\mathcal{V}_{i},\mathcal{S}_{i},\mathcal{A}_{i},m_{i}\bigr),

where \mathrm{id}_{i} is the episode identifier, \tau_{i}=[b_{i},d_{i}] is the episode’s timestep interval, \mathcal{V}_{i} contains recorded visual observations, \mathcal{S}_{i} contains associated structured states, \mathcal{A}_{i} records actions, and m_{i} contains metadata such as plan progress and task milestones. Episode identifiers and timestep metadata link these records to the corresponding agent interactions. Images retain perceptual details that may be absent from a textual description, while states, actions, and outcomes allow the agent to reconstruct the circumstances of an event. Preserving these records allows the agent to inspect details whose relevance becomes apparent only later. Fig. 3(a) illustrates the contents of an episode.

Associative indexing.

Episodic memory is useful only if the agent can retrieve relevant experiences when needed. MFM associates each episode with cues describing what happened, where it occurred, and when it took place. This use of cues to access detailed records is motivated by indexing accounts of episodic memory (Teyler and Rudy, 2007). We represent the index as

I_{t}=(z_{1},\ldots,z_{N_{t}}),\qquad z_{i}=(\mathrm{id}_{i},k_{i},\rho_{i}),

where k_{i} contains searchable cues and \rho_{i} contains references to the stored evidence. The cues include temporal and available location metadata, action type, retrieval tags, and a short action–outcome description. The harness maintains one entry per completed episode in index.jsonl.

The index serves as an addressing layer: cues narrow the search to relevant episodes, while references provide access to their underlying observations. For example, the agent can locate an encounter near a cave through its recorded location, an object tag, or an attempted action, then inspect the corresponding image. This allows the agent to retrieve an experience through its context without first recalling its precise visual content. Details absent from the index remain available for inspection in the stored observations. Fig. 3(b) illustrates this separation between cues and evidence, and Algorithm 2 summarizes episode storage and indexing.

Spatial memory.

For embodied interaction, location provides a common frame for connecting experiences collected at different times. MFM supports this function through spatial information distributed across its episodic store, index, and agent-written memory. Our memory filesystem maintains an append-only grid of traversed cells in a world frame in grid.jsonl. Episode coordinates support retrieval by spatial proximity or vertical position, while stored egocentric views let the agent verify a retrieved location by its appearance (Fig. 1(a,d)). The agent further records landmark knowledge in notes.md, such as the entrance to a mine that has become blocked, together with coordinates and references to supporting episodes. These representations draw on complementary ideas from cognitive maps (Tolman, 1948), memory for events and their locations (Clayton and Dickinson, 1998), and visual place recognition (Cartwright and Collett, 1983).

Semantic and procedural memory. The agent must also accumulate knowledge that is still useful after a specific episode has ended. This knowledge is stored in the agent-created collection C_{t} , which provides support for both semantic and procedural memory as well as the working memory mentioned below. Semantic memory involves recording facts and the relationships between them across different experiences. For instance, a note can link a resource to a cave, connect the cave to its coordinates, or relate an attempted action to the result of that action. These associations are given in plain text and include episode identifiers or file paths, enabling the agent to refer back to the relevant evidence. Useful discoveries and local knowledge are stored in notes.md, while more general environmental patterns and operating instructions are kept in GUIDE.md.

Procedural memory consists of methods that can be reused. In the procedures/ directory there are textual or executable sequences of actions which the agent is able to reuse and modify during later interactions. Experience is converted into these kinds of knowledge and skill through periodic consolidation (Kumaran et al., 2016). The agent can add to, correct or reorganize these procedures as new evidence becomes available, the underlying episodic records staying unaltered.

Working memory.

To continue an ongoing task across context changes, MFM maintains the agent’s current plan and immediate subgoals in working.md (part of C_{t} ). This file records the current plan, unresolved questions, and information needed to resume after a context reset. It connects the agent’s accumulated experience and knowledge to the decisions required by its present objective.

Figure 3: Memory contents and operations in MFM. A Minecraft trajectory shows how each form of memory is populated and used. (a) An episode: observation, state, action, and outcome stored as persistent files. (b) Its index entry: searchable cues, including spatial coordinates, with references to the records. (c) Retrieval: the agent locates episodes by step and inspects the referenced frame. (d) Consolidation: the evidence updates semantic (GUIDE.md) and working memory while earlier entries and episode references are preserved. Bottom: where each form of memory lives at this step.

### S8 · 3.3 Memory Retrieval

[原文定位](https://arxiv.org/html/2610.22686v1#S3.SS3)

Retrieving an experience requires both locating a relevant episode and determining what its observations reveal about the current task. MFM separates this into two stages. The agent first searches for episodes through textual or structured cues, then inspects selected multimodal evidence. As the cues determine where to look without requiring the agent to describe every detail, the agent can ask new questions of past observations, including ones whose relevance was not apparent when the experience was recorded. Fig. 3(c) illustrates this process, and Algorithm 3 summarizes the retrieval procedure.

Agent-initiated search.

Given its current information need, the agent constructs a query q_{t} over the episode index I_{t} and receives matching entries R_{t} . A query specifies conditions on recorded context, such as a time interval or location. For example, an agent investigating a failed action can locate episodes around the time it occurred. Search then identifies episodes that match the requested context, while the agent judges which are useful for its current decision. Each result provides the episode identifier, contextual cues, an action–outcome summary, and references to the evidence. Matches are returned in chronological order, with an optional limit that retains only the most recent matches.

Visual inspection.

If you find a particular episode, you gain access to information that goes beyond the description in its index. The agent then chooses the references \mathcal{P}_{t}\subseteq\bigcup_{z_{i}\in R_{t}}\rho_{i} from the results and loads the relevant evidence into the context, D_{t}=\{\operatorname{Load}(p)\mid p\in\mathcal{P}_{t}\} , where \operatorname{Load} converts a reference into its stored frame, state, or other record. This approach of selectively loading evidence enables the agent to look at the evidence it needs without including the entire interaction history in the context. With respect to visual evidence, the agent may examine an original frame, compare a number of frames on a contact sheet, place a previous observation alongside the current view, or zoom in on a region of interest. These operations help answer different questions regarding the same experience, for example identifying an object, recognising a location, or understanding the outcome of an action. Since the observations are available independently of the textual clues, the agent is able to look at details that are missing from k_{i} and reconsider a previous interpretation. When an inspection involves a question, the agent keeps both the question and the result so that the reason for the lookup is not lost.

### S9 · 3.4 Self-Evolving Consolidation

[原文定位](https://arxiv.org/html/2610.22686v1#S3.SS4)

Episodic memory preserves past experiences, while semantic and procedural memory capture knowledge and skills for future scenarios. MFM connects these forms of memory through consolidation, drawing on how complementary memory systems support learning from experience (Kumaran et al., 2016). During consolidation, the agent examines accumulated evidence and updates its understanding of the environment, reusable procedures, and its current plan. These updates change the agent-written memory C_{t} while preserving the recorded history (E_{t},I_{t}) . Algorithm 4 summarizes this procedure.

From experience to knowledge and skills.

Consolidation allows findings from individual episodes to inform subsequent behavior. The agent can record a useful observation as local knowledge in notes.md, or update GUIDE.md when experience supports a broader regularity. For example, an encounter may establish where a resource was found, while repeated encounters may suggest conditions under which an action succeeds or fails. The agent can also qualify earlier guidance when new observations reveal limits to its applicability.

Procedural updates record effective methods of acting; the agent is able to convert a sequence of actions into a textual or executable procedure and then modify it as a result of the changes revealed by later attempts. Working-memory updates link the knowledge that has been accumulated to the current task by having the agent revise the file working.md to show the completed subgoals, any changes to the plan, and the questions that remain unanswered. The agent decides which of these updates to make on the basis of the evidence available and the role of each memory, and the resulting documents and procedures stay accessible during future interactions.

Revision with preserved episodic evidence. Knowledge gained from experience can become out of date or incorrect. By linking the knowledge that agents write to the episodic observations that support it, agents are able to go back and look at the basis of their earlier beliefs. For instance, after having noticed a sheep on a hillside the agent then decides to go back for food, enlarges the original frame, and discovers that the animal was in fact a wolf; it then corrects the note and alters its plan while still keeping the reference to the episode. If the agent had kept only the textual description it would have lost the visual details required to correct that interpretation. Therefore, by preserving the episodic evidence the agent can reevaluate its earlier conclusions as its understanding develops. Figure 3(d) shows that the agent updates its GUIDE to indicate that the death message names a Piglin and that the previous identification as a brute has not been confirmed.

### S10 · 4 Experiment Results

[原文定位](https://arxiv.org/html/2610.22686v1#S4)

We evaluate MFM to understand how persistent multimodal memory affects task performance, decision-making, and interaction efficiency. We compare MFM with baseline methods on long-horizon embodied and computer-use tasks (Section 4.2), examine the memory component contributions via ablation studies (Section 4.3), and illustrate qualitative retrieval behaviors (Section 4.4), with a portal-building case study examining task completion and interaction efficiency, and analyze how the

agent learns and reuses skills through memory (Section 5.1).

### S11 · 4.1 Experimental Setup

[原文定位](https://arxiv.org/html/2610.22686v1#S4.SS1)

We evaluate MFM across two diverse domains, averaging all main and ablation results over three random seeds (determining the Minecraft world or KiCad task order). We limit each configuration to three seeds because long-horizon runs with frontier models are expensive. All models are ran with high reasoning efforts.

•

Minecraft: MCU-AgentBeats (Zheng et al., 2025; Liu et al., 2026b): open-world exploration and interaction in Minecraft, scored via scene-specific milestones. The details of both tasks are included in E.1. For the Mine Diamond from Scratch task, we use 12,000 max steps; for the Ender Dragon task, we use 36,000 max steps.

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

[原文定位](https://arxiv.org/html/2610.22686v1#S4.SS2)

MCU-AgentBeats. Table 3 shows completion counts. MFM + GPT-6-Astra finishes all 10 Diamond milestones (vs. 6.3 for direct evaluation, 9.3 for PRO-LONG, and 9.7 for VISTA). On the harder Dragon task, MFM achieves 16/24 milestones, outperforming direct evaluation (6.3), PRO-LONG (11.0), and VISTA (12.7). We observe that every baseline plateaus, making no further progress after at most 13 milestones. MFM consistently improves performance across all base models.

CUABench-KiCad. Table 3 indicates that MFM’s benefits extend to computer-use tasks, yielding mean rewards of 0.413 (GPT-5.6-Sol), 0.389 (Opus 5), and 0.440 (GPT-6): improving over direct evaluation baselines by 0.149–0.173 and outperforming memory baselines across models. Without cross-task memory, MFM’s reward drops by 0.013 – 0.027 across models.

Temporal reach and interaction efficiency. Fig. 6 reveals that MFM accesses much earlier history than VISTA (which favors recent experience) or PRO-LONG, demonstrating the effectiveness of MFM’s addressing layer. Furthermore, Fig. 8 shows that MFM and PRO-LONG execute more actions per turn than VISTA, with fewer total model queries and reducing execution overhead.

Table 4: Ablation of MFM’s memory components. Effects of removing stored frames, associative indexing, agent-written procedures or consolidation on the Diamond and Dragon tasks with GPT-5.6-Sol.

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

### S13 · 4.3 Ablation Studies

[原文定位](https://arxiv.org/html/2610.22686v1#S4.SS3)

We evaluate the contributions of MFM’s memory components through four ablations that separately remove access to historical visual observations, associative indexing, agent-written procedures, and consolidation. Table 4 reports the ablation results. Historical visual observations appear essential for resolving perceptual ambiguities and spatial orientation (Section 4.4), since disabling stored frames drops completion to 8.0\pm 1.0 (Diamond) and 8.3\pm 0.6 (Dragon). Associative indexing suggests that a dedicated addressing layer helps; replacing it with chronological text matching over a flat log (Flat) reduces scores to 8.7\pm 0.6 on both tasks. Additionally, agent-written procedures seem to help compound past successes into reusable routines (Section 5.1), as disabling it tends to decrease performance (Diamond: 8.7; Dragon: 9.0). Finally, the removal of consolidation lowers performance to 8.3\pm 0.6 on both tasks. The consistent drops across all four ablations is the main evidence that each component contributes.

### S14 · 4.4 How Memory Retrieval Helps in Long-Horizon Tasks

[原文定位](https://arxiv.org/html/2610.22686v1#S4.SS4)

We examine qualitative examples to understand how MFM supports decisions during long-horizon interaction. These examples illustrate how agents inspect visual evidence to revise earlier interpretations, recover spatial context from previous observations, and reuse evidence across tasks.

MCU-AgentBeats. Visual inspection enables agents to correct uncertain observations. In Fig. 9(a,b), magnifying ambiguous frames reveals a wolf instead of a sheep, preventing a costly attack; in (c,d), pink sheep observations guide resource gathering.

Retrieving earlier observations also helps the agent recover spatial context and connect past experience to the current environment. Agents utilize past frames to locate hole rims (Fig. 10), identify mine entrances (Fig. 11), and correct unfavorable viewing angles (Fig. 12).

We further examine a controlled construction task requiring the agent to align visual observations across multiple actions with a textual specification (full prompt in section E.3). Starting on a cleared stone platform with sufficient resources, the agent must build and activate a Nether portal. This probes multimodal capability: the agent must translate textual geometric constraints into a 3D structure, track construction progress from first-person views, and adjust accordingly. Only MFM successfully built the portal under a 6,000-step budget (Fig. 4), requiring lower overhead (Fig. 5): 30 model calls, 77 tool calls, and 77 environment actions (vs. 141/140/129 for VISTA and 43/131/151 for PRO-LONG).

(a) MFM completes the portal.

(b) VISTA

(c) PRO-LONG

Figure 4: Qualitative behavior on the Nether portal task. MFM successfully completes the Nether portal, whereas VISTA and PRO-LONG fail to finish the structure.

Figure 5: Interaction efficiency on the Nether portal task.

Comparison of model calls, tool calls, and executed environment actions.

Figure 6: Temporal reach of memory retrieval.

Retrieval-lag distributions on Diamond and Dragon. VISTA favors recent experience; MFM reaches further back, especially on Dragon.

CUABench-KiCad. Fig. 13 shows 3 tasks where MFM outperforms VISTA (GPT-6-Astra). In Task 55f2eefb (switching an LED circuit’s supply from 9 V to 5 V), both methods log an “OK” from Change

Symbol, but only MFM verifies the resulting netlist: its final state reads +5V

while VISTA’s still reads +9V, underscoring the need to check task state through visual memory. On a buck-regulator task (c4baee36), both methods

produce identical components and wiring but different supply labels; on the

two-op-amp task (b7148878), MFM leaves 1 input pin unconnected versus 3 for

VISTA. Fig. 15 shows episodic retrieval across tasks: an

export sequence from one task is reused on another.

### S15 · 5.1 Skill Learning through Memory

[原文定位](https://arxiv.org/html/2610.22686v1#S5.SS1)

We look into whether long-term memory allows agents to enhance their future behaviour by turning experience from interactions into reusable procedures. In this context, self-improvement means adapting as a result of the memory accumulated in MFM. MFM includes the facilities needed to store, modify, and carry out procedures written by the agent, and it is the agent itself that decides which behaviours to keep and when to reuse them. We do not specify the resulting skill library and do not require a fixed number of skills for each run. The analysis presented in this section includes observations of skill creation and reuse over different trajectories, an ablation study of the agent-written procedures, and a controlled study of the number of steps required to solve new tasks with or without reusing the agent-written procedures.

From experience to reusable behaviour. The trajectories show how agents convert their experience of interaction into permanent action routines. In a run of GPT-6-Astra Dragon, after manually cutting a descending staircase (steps 5,068 to 5,249), the agent created the procedure cut_step, which is parameterised by heading and cuts one step while advancing (); it then invoked this procedure 60 times, once for each of the four cardinal headings. A second procedure, quarry_north_pair, extracts the upper and lower block from the wall in front and gathers the dropped items (); the 27th time it was called, at step 17,462, it broke the first diamond ore block. Reuse also carries over from one life to another. The procedure bridge_north, which places one floor block while sneaking and takes the target cell as input (), was written in the previous life after the agent had manually placed two blocks over the lava and was then called three times in that same life. In this life the agent called it nine times between steps 19,261 and 20,103, using inputs ranging from (x=-3037, y=29, z=-5657) to (x=-3037, y=33, z=-5665). Each invocation placed one cobblestone block and left the agent’s health unchanged, and the bridge ended up reaching the lava pool where mining of obsidian took place at step 20,736. The agent also disabled one inherited procedure, level_step, having traced the previous death in the lava back to this procedure’s release of the sneak key.

Contribution to task performance. The results from the procedure ablation show that the procedures written by the agent do in fact contribute to task performance in MFM. For instance, when these procedures are removed for GPT-5.6-Sol, the mean milestone completion drops from 9.7 to 8.7 on Diamond and from 10.7 to 9.0 on Dragon. Our analysis points to two mechanisms that account for these improvements. Firstly, the skills allow agents to carry out the tasks more quickly; as presented in Table 5, reusing skills acquired during an earlier task decreased the average number of environment steps required to complete three new tasks: Iron shield, Climb out, and Cook meat by 30%, 7%, and 26% respectively. Secondly, skills can enable agents to reach milestones that would otherwise be impossible for them to achieve, as shown in the case of the blaze-fighting skill. If there are no agent-written skills that take visual inputs (for example, ), then none of the methods or models evaluated is able to go beyond milestone 16 to accomplish milestones such as killing a blaze or an enderman. These findings indicate that procedures enhance both the efficiency of task completion and the variety of milestones that can be achieved, even though they do not mean that each stored procedure is beneficial or that having a larger library of skills will necessarily lead to better performance.

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

### S16 · 6 Conclusion

[原文定位](https://arxiv.org/html/2610.22686v1#S6)

We introduced MFM, a multimodal filesystem memory that organizes episodic, spatial, semantic, procedural, and working memory as folders and files in one shared filesystem. Episodic records preserve raw observations, states, actions, and outcomes; a searchable index of contextual cues addresses them; and agent-written knowledge, procedures, and plans cite the episodes that support them. An agent can thus locate past experience by when, where, or what happened, inspect the original observation for details text omits, and revise what it has learned without discarding the evidence. Across Minecraft and KiCad with three base models, MFM outperforms memory-free and memory-augmented baselines, each component contributes, and memory transfers across tasks. We hope MFM can serve as a foundation for memory in long-horizon multimodal and embodied agents.

Limitations and Future Work. MFM improves long-horizon performance, but exploration remains hard: even GPT-6-Astra at maximum reasoning effort (from a concurrent experiment posted online) did not complete Ender Dragon. Finding better ways of coupling memory

to exploration and route planning could help agents find landmarks and avoid repeated traversal. Our evaluation is also limited to single agents in Minecraft and KiCad; shared memory across agents could combine experience from different regions or solution attempts, and broader environments would test how far the design transfers.

### S17 · References

[原文定位](https://arxiv.org/html/2610.22686v1#bib)

ARC Prize Foundation (2026)

ARC Prize Foundation

ARC-agi-3.

Note: https://arcprize.org/Accessed: 2026-08-15

Cited by: §2.

Cartwright and Collett (1983)

B. Cartwright and T. S. Collett

Landmark learning in bees: experiments and models.

Journal of comparative physiology 151 (4), pp. 521–543.

Cited by: §3.2.

Clayton and Dickinson (1998)

N. S. Clayton and A. Dickinson

Episodic-like memory during cache recovery by scrub jays.

Nature 395 (6699), pp. 272–274.

Cited by: §3.2.

Cua AI, Inc. (2025)

Cua AI, Inc.

Cua.

Note: cua-bench KiCad EDA dataset (25 schematic-editing tasks,

netlist-comparison scoring). MIT License. Accessed 2026-09-01

External Links: Link

Cited by: 2nd item.

Cua AI (2026)

Cua AI

Cua-Bench Leaderboard.

Note: https://cua.ai/cuabenchAccessed: 2026-09-12

Cited by: 2nd item.

Dai et al. (2026)

Y. Dai, H. Fu, J. Lee, Y. Liu, H. Zhang, J. Yang, C. Finn, N. Fazeli, and J. Chai

Robomme: benchmarking and understanding memory for robotic generalist policies.

arXiv preprint arXiv:2603.04639.

Cited by: §2.

Fan et al. (2024)

Y. Fan, X. Ma, R. Wu, Y. Du, J. Li, Z. Gao, and Q. Li

VideoAgent: a memory-augmented multimodal agent for video understanding.

In European Conference on Computer Vision,

pp. 75–92.

Cited by: §2.

Fox et al. (2026)

A. Fox, J. Wang, P. Rosu, and B. Dhingra

PRO-long: programmatic memory enables long-horizon reasoning.

arXiv preprint arXiv:2607.20064.

Cited by: §1,

Table 1,

§2,

§2,

§4.1,

Table 3,

Table 3.

Ge et al. (2026)

Z. Ge, X. Jia, C. Wu, Y. Zhou, Z. Wu, and Y. Jiang

EvoMemNav: efficient self-evolving fine-grained memory for zero-shot embodied navigation.

arXiv preprint arXiv:2606.03509.

Cited by: §2.

Han et al. (2026)

Q. Han, K. Hu, L. Qiu, C. Wu, and K. He

VISTA: a visual harness for reasoning in an interactive world.

External Links: Link

Cited by: §1,

Table 1,

§2,

§4.1,

Table 3,

Table 3.

Ju et al. (2026)

T. Ju, Y. Sun, Z. Wu, W. Zhang, Y. Huo, X. Su, Q. Gu, X. Cai, G. Liu, and Z. Zhang

MineExplorer: evaluating open-world exploration of mllm agents in minecraft.

arXiv preprint arXiv:2605.30931.

Cited by: §2.

Kumaran et al. (2016)

D. Kumaran, D. Hassabis, and J. L. McClelland

What learning systems do intelligent agents need? complementary learning systems theory updated.

Trends in cognitive sciences 20 (7), pp. 512–534.

Cited by: §3.2,

§3.4.

Li et al. (2026)

G. Li, Y. Wang, D. Li, J. Hao, and Y. Peng

GraphMemix: query-aware evidence forests for long-term multimodal agent memory.

arXiv preprint arXiv:2608.26983.

Cited by: §2.

Li et al. (2024)

Z. Li, Y. Xie, R. Shao, G. Chen, D. Jiang, and L. Nie

Optimus-1: hybrid multimodal memory empowered agents excel in long-horizon tasks.

Advances in neural information processing systems 37, pp. 49881–49913.

Cited by: §2.

Liu et al. (2026a)

R. Liu, Z. Liu, J. Tang, Y. Ma, R. Pi, J. Zhang, and Q. Chen

Longvideoagent: multi-agent reasoning with long videos.

In Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers),

pp. 40404–40416.

Cited by: §2.

Liu et al. (2026b)

X. Liu, J. Tu, Y. Chen, S. Xie, S. Ren, T. Shi, G. Gantar, E. Sandoval, D. Lee, D. Miao, et al.

AgentBeats: agentifying agent assessment for openness, standardization, and reproducibility.

arXiv preprint arXiv:2606.13608.

Cited by: 1st item.

Long et al. (2026)

L. Long, Y. He, W. Ye, Y. Pan, Y. Lin, H. Li, J. Zhao, and W. Li

Seeing, listening, remembering, and reasoning: a multimodal agent with long-term memory.

In International Conference on Learning Representations,

Vol. 2026, pp. 146197–146246.

Cited by: §2.

Lu et al. (2026)

Y. Lu, W. Cheng, Z. Zhang, and H. Tang

Mma: multimodal memory agent.

arXiv preprint arXiv:2602.16493.

Cited by: §1,

§2.

Park et al. (2025)

J. Park, J. Cho, and S. Ahn

MrSteve: instruction-following agents in minecraft with what-where-when memory.

In International Conference on Learning Representations,

Vol. 2025, pp. 16922–16960.

Cited by: §1,

Table 1,

§2.

Rodionov (2026)

S. Rodionov

Executable world models for arc-agi-3 in the era of coding agents.

In International Conference on Artificial General Intelligence,

pp. 198–210.

Cited by: §2.

Squire (2004)

L. R. Squire

Memory systems of the brain: a brief history and current perspective.

Neurobiology of learning and memory 82 (3), pp. 171–177.

Cited by: §1,

§3.2.

Teyler and Rudy (2007)

T. J. Teyler and J. W. Rudy

The hippocampal indexing theory and episodic memory: updating the index.

Hippocampus 17 (12), pp. 1158–1169.

Cited by: §3.2.

Tian et al. (2026)

Z. Tian, Y. Tian, H. Zhang, C. Chen, Y. Li, L. Zhang, and X. Zhou

Beyond retrieval: analytic memory for multimodal agents.

arXiv preprint arXiv:2607.29440.

Cited by: §2.

Tolman (1948)

E. C. Tolman

Cognitive maps in rats and men..

Psychological review 55 (4), pp. 189.

Cited by: §3.2.

Torne et al. (2026)

M. Torne, K. Pertsch, H. Walke, K. Vedder, S. Nair, B. Ichter, A. Z. Ren, H. Wang, J. Tang, K. Stachowicz, et al.

Mem: multi-scale embodied memory for vision language action models.

arXiv preprint arXiv:2603.03596.

Cited by: §2.

Tulving (1972)

E. Tulving

Episodic and semantic memory.

Organization of memory 1 (381-403), pp. 1.

Cited by: §1,

§3.2.

Wang et al. (2024)

G. Wang, Y. Xie, Y. Jiang, A. Mandlekar, C. Xiao, Y. Zhu, L. Fan, and A. Anandkumar

Voyager: an open-ended embodied agent with large language models.

Transactions on Machine Learning Research.

Cited by: Table 1,

§2.

Wang et al. (2025)

Z. Wang, S. Cai, A. Liu, Y. Jin, J. Hou, B. Zhang, H. Lin, Z. He, Z. Zheng, Y. Yang, et al.

Jarvis-1: open-world multi-task agents with memory-augmented multimodal language models.

IEEE Transactions on Pattern Analysis and Machine Intelligence 47 (3), pp. 1894–1907.

Cited by: Table 1,

§2.

Wang et al. (2026)

Z. Wang, M. Shi, C. Ni, J. Yang, M. Li, Z. Su, T. Lin, and H. Li

NativeMEM: native memory compression for long-horizon robotic manipulation.

arXiv preprint arXiv:2607.06678.

Cited by: §1,

§2.

Xie et al. (2026)

Z. Xie, Z. Chen, Z. Weng, J. Li, C. Li, Z. Xiao, J. Song, J. Jing, V. Zhang, and K. Wang

MineEvolve: self-evolution with accumulated knowledge for long-horizon embodied minecraft agents.

arXiv preprint arXiv:2603.13131.

Cited by: §2.

Zeng et al. (2026)

G. Zeng, J. Wang, W. Ma, S. Yin, C. Wang, S. Liu, A. Kanazawa, W. Ni, X. Li, A. Zanette, and H. Feng

[Schema]: frontier models with the right harness achieve \sim 99% on arc-agi-3 public.

Note: Impossible Research. https://schema-harness.github.io/

External Links: Link

Cited by: §2.

Zhang et al. (2026)

H. Zhang, Y. Ding, Y. Zhou, X. Du, S. Zhang, Z. Zhao, Y. Xi, and H. Chen

Spatial memory agent: experience-grounded procedure memory for spatial intelligence.

arXiv preprint arXiv:2608.12743.

Cited by: §2.

Zheng et al. (2025)

X. Zheng, H. Lin, K. He, Z. Wang, Q. Fu, H. Fu, Z. Zheng, and Y. Liang

MCU: an evaluation framework for open-ended game agents.

In Proceedings of the 42nd International Conference on Machine Learning (ICML),

External Links: Link

Cited by: §2,

1st item.

Zhou et al. (2026a)

S. Zhou, S. Yu, H. Wei, J. Wu, S. Ouyang, Y. Jiao, S. Pan, J. McAuley, Y. Zhang, T. Yu, et al.

Filesystem-based memory for llm agents: organization, evolution, and sustainability.

arXiv preprint arXiv:2607.26637.

Cited by: §2.

Zhou et al. (2026b)

Z. Zhou, H. Tang, J. Zhang, H. Lin, B. Yang, Q. Long, F. Sun, Y. Sun, Y. Liang, Y. N. Wu, et al.

Can current agents close the discovery-to-application gap? a case study in minecraft.

arXiv preprint arXiv:2604.24697.

Cited by: §2.

Zou et al. (2026)

T. Zou, Y. He, T. Qiu, Y. Lin, and H. Li

Task-focused memorization for multimodal agents.

arXiv preprint arXiv:2605.31075.

Cited by: §1,

§2.

### S18 · Appendix A Additional Examples

[原文定位](https://arxiv.org/html/2610.22686v1#A1)

This appendix adds results and qualitative examples to Section 4.4.

Section A.1 covers milestone progression and interaction on Minecraft.

Section A.2 shows further cases of visual memory inspection.

Section A.3 gives qualitative examples on CUABench-KiCad.

### S19 · A.1 Milestone Progression and Interaction in Minecraft

[原文定位](https://arxiv.org/html/2610.22686v1#A1.SS1)

Fig. 7 tracks milestone progression on Kill the Ender Dragon with GPT-6-Astra, using one run per method.

VISTA gets diamond equipment earlier than MFM, but its progress then stalls.

MFM continues through obsidian and flint and steel and reaches netherrack within the same 36,000-step budget.

Table 3 reports seed-averaged results for all methods and base models.

Fig. 8 shows how many environment steps each method executes between successive model calls.

MFM and PRO-LONG generally execute more steps per turn than VISTA.

In other words, they issue longer action plans and call the model less often.

How MFM compares with PRO-LONG depends on the task.

On Ender Dragon, MFM executes more steps per turn than both baselines for 41–56% of each run.

On Mine Diamond, it does so for only 5–14% of each run, and PRO-LONG usually executes the most steps per turn.

Figure 7: Milestone progression on Kill the Ender Dragon with GPT-6-Astra.

Each curve shows one run’s progression through the Minecraft technology tree against environment steps (log scale).

Within the 36,000-step budget (dashed line), MFM reaches 16 of 24 milestones, compared with 13 for VISTA, 12 for PRO-LONG, and 6 for Direct Evaluation.

The shaded region marks milestones that no method reached.

One run is shown per method; Table 3 reports seed-averaged results.

Figure 8: Environment interaction per agent turn.

Rolling median of environment steps executed per agent turn over each run.

Columns are the three base models; rows are Mine Diamond from Scratch (top) and Kill the Ender Dragon (bottom).

Higher values mean more environment interaction between successive model calls; the vertical axis is logarithmic.

Shaded intervals mark where MFM exceeds both VISTA and PRO-LONG, and the annotation in each panel gives the shaded fraction.

### S20 · A.2 Visual Memory Inspection in Minecraft

[原文定位](https://arxiv.org/html/2610.22686v1#A1.SS2)

Figs. 9, 10, 11 and 12 expand on the Minecraft examples in Section 4.4.

In each case, the agent finds a stored frame through its index entry.

It then inspects the frame to answer a question that the textual record alone cannot:

what kind of animal it saw (Fig. 9),

where a hole it dug earlier is located (Fig. 10),

whether a place seen in an earlier life matches the current view (Fig. 11),

and why an earlier mining cut failed (Fig. 12).

(a) Stored frame: a pale animal on the hillside.

(b) Magnified crop: a wolf.

(c) Stored frame: a possible pink sheep.

(d) Magnified crop: a pink sheep.

Figure 9: Correcting and confirming perception with visual memory.

(a–b) At step 4,588, the agent records a pale animal on the hillside.

Magnifying the stored frame shows a wolf rather than a sheep, so the agent does not attack and looks for food elsewhere.

(c–d) At step 4,917, the agent is unsure whether an animal on the slope is a pink sheep.

Magnifying the stored frame confirms a sheep rather than a pig, and the agent hunts it for food.

(a) Stored frame of the hole the agent dug.

(b) Retrieved frame (left) beside the current view (right).

Figure 10: Memory-guided spatial relocation.

The retrieved and current views line up closely, which lets the agent identify the hole’s rim and recover its exact location.

(a) Life 1: stored frame of a shallow iron-mine entrance.

(b) Life 2: retrieved frame (left) beside the current view (right).

Figure 11: Cross-life visual memory retrieval.

After dying, the agent retrieves a frame recorded in an earlier life and compares it with its current view.

It recognizes the grass bank ahead as the entrance to that life’s iron mine, digs in, and mines iron ore at step 6,565.

(a) Retrieved frame: the earlier cut was pitched upward.

(b) Re-aimed view facing the mining face.

Figure 12: Using visual memory to recover mining orientation.

The agent inspects the frame of an earlier cut that failed to open a level passage.

It sees that the view was pitched upward rather than at the mining face.

It then re-aims with look_abs and resumes mining at the correct orientation.

### S21 · A.3 Qualitative Examples on CUABench-KiCad

[原文定位](https://arxiv.org/html/2610.22686v1#A1.SS3)

Fig. 13 shows the final schematics that MFM and VISTA produce on the three tasks discussed in Section 4.4.

On Task 55f2eefb, both agents get an “OK” from Change Symbol, but only MFM checks the resulting value; VISTA’s schematic still reads +9 V. Because MFM checks the resulting application state instead of trusting the “OK” returned by an edit operation, it catches incomplete edits that VISTA records as successful.

On Task c4baee36, both agents place the same components and wiring but use different supply labels.

On Task b7148878, MFM leaves one pin unconnected, compared with three for VISTA.

Fig. 14 shows how MFM verifies its own edits on three other tasks.

In each task, the agent follows the same three-step routine.

First, it inspects the schematic to confirm that component values and net labels match the specification.

Second, it runs the Electrical Rules Checker (ERC).

Third, it reads the ERC report to confirm that only the expected undriven-power errors remain and that no pins are left unconnected.

The agent first used this routine in an earlier task and later retrieved it from episodic memory, similar to the netlist-export reuse in Fig. 15.

Fig. 15 shows episode reuse across tasks.

While exporting a netlist in Task a6414tw4, the agent retrieves an episode from the earlier Task 4c913e30 whose action sequence is nearly identical, and follows it as a precedent.

(a) MFM, 55f2eefb: supply reads +5 V.

(b) MFM, c4baee36: +48 V and GND supply symbols.

(c) MFM, b7148878: one unconnected pin.

(d) VISTA, 55f2eefb: label still reads +9 V.

(e) VISTA, c4baee36: local label 3.3VDC on the output net.

(f) VISTA, b7148878: pins R1.1, U2.1, and U2.2 unconnected.

Figure 13: Qualitative comparison on CUABench-KiCad.

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

Figure 14: Self-verification of edits on CUABench-KiCad.

Each row shows one task.

MFM inspects the schematic against the specification (left), opens the Electrical Rules Checker (middle), and reads the report to confirm that only the expected errors remain (right).

(a) Current task a6414tw4, steps 6–10.

(b) Episode retrieved from the earlier task 4c913e30, steps 78–82.

Figure 15: Cross-task reuse of episodic memory in KiCad.

While working on the current task (top), the agent retrieves an episode from an earlier task (bottom) with a nearly identical action sequence.

The sequence is: save the blank schematic, open Export \rightarrow Netlist, select the native KiCad format, and set the output path.

The retrieved episode serves as a concrete precedent for the current task.

### S22 · A.4 Inspection Statistics

[原文定位](https://arxiv.org/html/2610.22686v1#A1.SS4)

We quantify a mechanism behind Sec. 4.4 over the main Minecraft runs (three models, two tasks, three seeds): how often inspecting a stored frame changed the agent’s next action (Fig. 16).

Does looking at a stored frame change the next action?

The agent looks before it commits, and the transcripts hold no counterfactual, so a

within-call before/after comparison is empty by construction. What can be measured is the

destination. A turn is a retarget if its plan names a

go_to/look_at coordinate the running plan did not contain, and a

recall target if that coordinate lies within 8 blocks of where the looked-at

episode was recorded; the null for recall is the fraction of all stored episodes that

would match the coordinate by position alone. On Mine Diamond

(Fig. 16), a turn that opened a stored frame retargets 2.5\times as often

as one that did not ( 17\% vs 7\% , p=5\times 10^{-6} , Fisher), and the new destination

is the retrieved episode’s location in 42 of 48 cases against a 37\% null

( p=6\times 10^{-13} , binomial). Ender Dragon shows the same pattern ( 33\% vs 14\% ;

15/17 against a 24\% null), as does the pool ( 19\% vs 11\% ; 57/65 against

33\% ). The

retrieval is therefore not merely correlated with replanning: it selects which

place the agent goes to next.

Figure 16: What follows a look at a stored frame. Left: the share of turns whose

plan names a destination the current plan did not have, after the agent opened a stored

episode frame (blue) against turns in which it opened no image at all (orange).

Right: of those new destinations, the share falling within 8 blocks of the

position at which the retrieved episode was recorded (blue), against the share of the

whole episode store that would match the same coordinate by position alone (orange).

### S23 · Appendix B Pseudocode

[原文定位](https://arxiv.org/html/2610.22686v1#A2)

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

### S24 · Appendix C Skills

[原文定位](https://arxiv.org/html/2610.22686v1#A3)

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

{’action’: {’camera’: [80-pos[’pitch’], (180-pos[’yaw’]+180)%360-180], ’sneak’: 1}, ’repeat’: 1},

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

"""aim_speckles: turn the crosshair onto the (x, y) pixel a ’mining stopped: …-ore-like speckles’ [NOTE] names, then mine that block and sweep its drop."""

# Why it exists: the life that found the diamond did exactly this within 20 steps of the

# watcher’s [NOTE] – aim at the speckles, mine the block under the crosshair, walk to the

# drop. Lives that answered a sighting with "finish the column first" or "craft a sword

# first" never mined the ore at all: by the next turn the view had moved and the speckles

# were gone. So: a sighting [NOTE] outranks everything; call this from its (x, y) BEFORE any

# other look or step, while the view is still the flag-time view (the runner dropped the

# rest of the plan for exactly that).

# The frame the watcher reads is 640x360 with a 70-degree vertical field of view: the focal

# length is 180 / tan(35 deg) = 257 px, so an offset of d pixels from the centre (320, 180) is

# atan(d / 257) degrees – 104 px right is 22 degrees of yaw, not the 17 a linear scale gives.

# Two 30-step holds: ore takes longer than stone, and the hold is cut the moment the block

# breaks anyway. collect_drops then sweeps the drop; the milestone is the PICKUP, not the break.

import json, math, sys

PARAMS = {"x": "screen x from the [NOTE] (0-640)", "y": "screen y from the [NOTE] (0-360)",

"pick": "hotbar slot 1-9 with the pickaxe (default: the best in the hotbar)"}

args = json.loads(sys.argv[sys.argv.index("–args") + 1]) if "–args" in sys.argv else {}

s = json.load(sys.stdin)

if s.get("gui_open"):

raise SystemExit("a screen is open: close_inventory first")

if "x" not in args or "y" not in args:

raise SystemExit("pass x and y: the pixel the sighting [NOTE] names, e.g. (424, 145)")

x, y = float(args["x"]), float(args["y"])

if not (0 <= x <= 640 and 0 <= y <= 360):

raise SystemExit("x must be 0-640 and y 0-360 (the [NOTE]’s frame)")

rank = {"diamond_pickaxe": 0, "iron_pickaxe": 1, "stone_pickaxe": 2, "wooden_pickaxe": 3}

picks = [h for h in s["hotbar"] if h.get("item") in rank]

if args.get("pick") is not None:

picks = [h for h in picks if int(h["slot"]) + 1 == int(args["pick"])]

if not picks:

raise SystemExit("no pickaxe in the hotbar (diamond ore needs IRON or better to drop a diamond)")

pick = min(picks, key=lambda h: rank[h["item"]])

F = 180.0 / math.tan(math.radians(35.0)) # 257 px

dpitch = round(math.degrees(math.atan((y - 180.0) / F)), 1) # + is down, like the screen

dyaw = round(math.degrees(math.atan((x - 320.0) / F)), 1) # + is right, like the screen

plan = [{"procedure": "equip_hotbar", "args": {"slot": int(pick["slot"]) + 1}},

{"action": {"camera": [dpitch, dyaw]}, "repeat": 1},

{"action": {"attack": 1}, "repeat": 30},

{"action": {"attack": 1}, "repeat": 30},

{"procedure": "collect_drops", "args": {"steps": 48}}]

print(json.dumps({"actions": plan}))

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

### S25 · Appendix D Harness and Implementation Details

[原文定位](https://arxiv.org/html/2610.22686v1#A4)

This appendix covers five things:

the episode index (Section D.1),

the spatial grid (Section D.2),

the configuration of each method and the action interface shared by all methods (Section D.3),

and storage and cost statistics (Section D.4).

### S26 · D.1 Episode Index

[原文定位](https://arxiv.org/html/2610.22686v1#A4.SS1)

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

### S27 · D.2 Spatial Grid

[原文定位](https://arxiv.org/html/2610.22686v1#A4.SS2)

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

### S28 · D.3 Method Configurations

[原文定位](https://arxiv.org/html/2610.22686v1#A4.SS3)

Table 6 lists the configuration of each method on Minecraft. All methods receive the same 12 KB standing brief in prompt. All methods act through the same 28 atomic procedures (Table 7).

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

Procedure set

28 atoms

28 atoms

28 atoms

28 atoms

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

Table 7: The 28 atomic procedures shared by all methods (procedures.ATOMS).

They include closed-loop movement and aiming primitives, GUI cursor control, one-call crafting, and placement.

Atom

Description

Aiming and walking

look

Turn the camera by a relative (pitch, yaw) in degrees, in safe increments.

look_at

Aim the crosshair at a world coordinate, using the exact position from [STATE].

look_abs

Steer the camera to an absolute pitch and yaw, closed-loop against [STATE] at every step; works from any starting pose.

go_to

Walk to a world coordinate (x,z) , re-aiming against [STATE] at every step until within reach.

watch

Wait up to n steps, stopping as soon as a condition read from the game state holds: none (plain wait), inventory (any count changes), gui (a screen opens), health, damage, y_below:<v>, y_above:<v>, or moved:<blocks>.

Mining and pickup

mine_ahead

Hold attack on the block under the crosshair, without re-aiming or walking.

collect_drops

Walk a short out-and-back sweep to pick up item drops; stop as soon as the inventory count rises, and report whether it did.

Inventory and GUI cursor

equip_hotbar

Select hotbar slot 1–9.

open_inventory

Press E to open the inventory screen.

close_inventory

Press E to close the current screen.

cursor_to_slot

Move the cursor onto a player inventory slot, given its [INV] slot ID.

cursor_to_cell

Move the cursor onto a crafting or furnace cell, or onto the output cell.

gui_click

Left-click at the cursor (pick up or place a stack).

gui_right_click

Right-click at the cursor (place one item).

stow_items

Move the cursor stack and the named crafting cells into empty inventory slots, so the screen can close without dropping anything.

discard_stack

Throw away the stack in slot (there is no drop key): open the inventory, lift the stack, force-close the screen so it lands on the ground, and step back to avoid picking it up again.

drop_and_pickup

Drop the stack in slot and walk over it, so the game registers a pickup.

Crafting and smelting

craft

Craft a recipe from the current inventory in one call: place each ingredient, take the output count times, return leftovers, move tools to the hotbar, and verify the result.

place_and_open

Place a crafting table or furnace on the ground one block ahead and open its screen, moving it to the hotbar first if needed; verify the placement and the screen type.

furnace_load

Load n of an item into the open furnace (0 = the whole stack) along with enough fuel, chosen in the order coal, charcoal, planks, logs, sticks.

furnace_take

Take the finished output from the open furnace into the inventory, after checking that the output cell is not empty; report what was taken.

Placing and using items

place_at

Place item into the cell (x,y,z) by clicking a face of an adjacent block (by default, the block below the cell).

use_at

Right-click a face of the block at (x,y,z) with item selected, e.g., to pour water, light with flint and steel, till soil, plant seeds, or open a door or chest; with no item, use the block with whatever is held.

use_held

Hold use with the selected item, e.g., to draw a bow (release after \geq 25 steps), drink a potion, look through a spyglass, or raise a shield.

fill_bucket

Fill an empty bucket from visible water: sweep the crosshair over the ground ahead (pitch 18–60∘, yaw \pm 40∘), pressing use at each aim until a filled bucket appears; report which liquid was collected.

throw

Throw a snowball, egg, ender pearl, or eye of ender n times; verify that the item count decreases.

eat

Eat the named food, or the best food carried; holds use for about 40 steps.

pillar_up

Jump and place n blocks underfoot, verifying each by the measured height; used to build a lookout or escape a mob.

### S29 · D.4 Storage and Cost

[原文定位](https://arxiv.org/html/2610.22686v1#A4.SS4)

All main and ablation results are averaged over 3 seeds; each seed fixes the Minecraft world or KiCad task order, with further variation from stochastic model sampling. In total we ran 96 Minecraft runs (72 main + 24 ablation, capped at 12k steps for Diamond and 36k for Dragon) and 1,125 KiCad episodes ( 25\text{ tasks}\times 15\text{ configurations}\times 3\text{ seeds} ). All 48 Dragon runs exhaust their budget

(Fig. 8), consuming \approx 1.7M steps and up to 14 hours each. In the Claude Opus 5 on Dragon configuration, a single run makes 0.9\text{--}3.9\text{k} model calls and costs \$108\text{--}\$969 (Table 9).

Table 8 reports storage, retrieval, and memory-use statistics for one MFM run.

Table 9 reports the cost of one Kill the Ender Dragon run per method with Claude Opus 5. Both tables come from single runs and are meant to show orders of magnitude.

Table 8: Storage, retrieval, and memory-use statistics for the GPT-6-Astra Mine Diamond run that reached all 10 milestones.

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

Table 9: Costs of Ender Dragon runs with Claude Opus 5 (36,000 steps) using Claude Code.

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

### S30 · E.1 MCU Tasks Descriptions

[原文定位](https://arxiv.org/html/2610.22686v1#A5.SS1)

Mine Diamond from Scratch. The agent starts with no resources and must progress through the Minecraft technology tree: gathering wood, stone, and iron, crafting increasingly capable tools, and ultimately mining a diamond.

Kill Ender Dragon. The agent completes the same early-game progression, then prepares diamond equipment, enters the Nether to obtain blaze materials, crafts Eyes of Ender, reaches the End, and defeats the Ender Dragon.

Figure 17: Milestone progression for the Minecraft tasks. Mine Diamond from Scratch contains 10 milestones, while Kill Ender Dragon shares the same initial progression and adds 14 milestones required to reach and defeat the Ender Dragon. Numbers in the left column index the Mine Diamond list; inner and right-column numbers index the Ender Dragon list, in which Diamond ore is inserted as milestone 10, so Diamond becomes 11 and the added milestones continue from 12. Note that the milestones do not need to be finished strictly in this order.

### S31 · E.2 New Tasks for Evaluating Skill Reuse

[原文定位](https://arxiv.org/html/2610.22686v1#A5.SS2)

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

Figure 18: Milestone structure of Diamond and three related tasks. Columns align the tasks by Diamond’s ten milestones. Blue indicates shared, scored milestones; orange indicates task-specific milestones; gray indicates milestones provided at initialization and excluded from scoring. Empty cells denote Diamond milestones not scored in the corresponding task.

### S32 · E.3 Prompts and Outputs Examples

[原文定位](https://arxiv.org/html/2610.22686v1#A5.SS3)

In this section, we provide examples of prompts used.
