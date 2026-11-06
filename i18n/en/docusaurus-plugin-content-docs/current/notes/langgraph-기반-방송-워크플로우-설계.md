---
title: "Designing a Langgraph-Based Broadcast Workflow"
sidebar_position: 6
slug: "6"
last_update:
  date: 2026-11-06
---

### Introduction

---

In the previous article (“Building the RAG Pipeline”), I introduced the steps involved in the scheduling process. The sequence is as follows: parse the query, gather candidate scenes, select the appropriate scene, cut the clip, and adjust the ranking and duration. This article discusses the design—specifically, how those steps were divided and integrated using LangGraph.

A scheduling request consists of the target episode, a single query line, and the desired duration. The system responds immediately upon receiving the request and notifies the client of a list of clip segments once the graph processing is complete. The scheduling graph handles the processing in between.

The reason for using LangGraph is simple. Scheduling involves model calls at each stage; some stages must process multiple requests simultaneously; and if a result is missing during the process, the process must halt at that point. If this workflow were woven together using function calls, branching and parallelism would be scattered throughout the code. By representing it as a graph, each step (node) handles only its own task, while the paths (edges) connecting them are centralized in one place. Adding a single node simply requires one additional edge.

---

### 1. Two Layers of Graphs

The scheduling graph consists of two layers: the **iteration graph**, which handles a single iteration, and the **overall graph**, which handles the entire request.

![image](/img/notes/langgraph-기반-방송-워크플로우-설계/img-00.jpg)

- **Iteration Graph:** Read materials → Interpret query → Gather candidates → Select scenes → Split into segments → Rank. It only performs tasks that are completed within a single iteration.
- **Overall Graph:** For each run contained in a request, a separate run graph is launched and runs simultaneously. Once all runs are complete, the results are consolidated into a single list, and cross-run operations—such as finalization, volume adjustment, and volume execution—are performed.

The reason for this division is that the scope of decision-making differs. Questions such as “Does this scene match the query?” and “Where should I cut from and to?” can be decided within a single round. On the other hand, conditions such as “only 3 out of the total” or “1 per episode,” as well as the total volume, can only be determined after all episodes have been gathered. Tasks specific to individual episodes are run simultaneously for each episode, while tasks requiring an overview of the entire set are performed only once at the end.

The episode graphs running in parallel each record their results below their respective episode numbers. The overall graph is configured to merge these results without overwriting them, ensuring that results do not get mixed up or lost, regardless of which episode finishes first.

---

### 2. State: Read once at the beginning; each step reads only its own portion

The nodes in the graph pass work through a shared **state**. Each node reads what it needs from the state and adds only what it has produced to the state.

![image](/img/notes/langgraph-기반-방송-워크플로우-설계/img-01.jpg)

- **Materials are read only once at the beginning.** The first node in an iteration graph reads the outline, sequence, scene, cut, and dialogue for that iteration—starting from the highest-level units—all at once and adds them to the state. Subsequent nodes refer only to this snapshot without consulting the database again. Since the source material does not change while the graph is running, identical requests are treated as using the same source material.
- **The plan is parsed once and used throughout the process.** The query parsing node breaks down the query into conditions such as style, characters, location, keywords, length, and quantity to create a plan. Subsequent nodes read this plan along with the original query text. Conditions such as quantity are not re-parsed at each stage.
- **Each node fills only its own slot.** The candidate gathering node fills the candidate scenes slot, the scene selection node fills the selected scenes slot, and the segment cutting node fills the clip slot. The ranking node is the only exception; it filters the clip list, assigns rankings, and rewrites the list.

---

### 3. When Empty or Failed

In scheduling, “found but none available” is a common outcome. There may be no scenes matching the query in that episode. Therefore, we distinguish between **Empty** and **Failed**.

- **“Empty” is a normal termination.** Candidate collection, scene selection, and segment cutting leave an “End” marker in the status if there are no results. The graph checks each node for this marker; if present, it skips subsequent nodes and terminates immediately. That episode ends without clips, and other episodes are not affected.
- **If there is no source material, it is a failure.**If even one of the sequence, scene, cut, or line of dialogue is missing in an episode, it is considered an incompletely analyzed episode. In this case, it does not proceed with an empty lineup but ends in failure. This is to ensure that “no matching scene” and “no content to view” are not treated as the same result.
- **A single failure stops at that point.** Scene selection calls the model simultaneously for each sequence, and segment cutting calls it for each scene group. Even if one of them fails, the rest proceed as usual. The failed item is handled according to the method defined for each step.
  - If query interpretation fails, the process proceeds by using the query itself as the basis, without any filtering conditions.

  - If a scene selection call fails, only that sequence is skipped, and the failure count is recorded.

  - If the interval-cutting response cannot be interpreted, the entire scene in the bundle is used as a clip.

  - If duration adjustment fails or the result is longer than the original, the original clip is left as is.

---

### 4. Tasks for the Model vs. Tasks for the Code

We determined whether to call the model or handle each node solely through code. The criteria are “Does it require judgment?” and “Does the model frequently make mistakes?”

Tasks handled by the model include interpreting queries, selecting scenes, selecting segments, ranking, determining the order across episodes, and reselecting key segments to meet the runtime requirement. Tasks handled by the code include gathering candidates, converting line numbers to seconds, enforcing quantity conditions, merging overlapping clips, enforcing runtime limits, and sorting the playback order.

We divided the three borderline tasks as follows:

**Segments: The model only selects line numbers.** The interval-splitting node mixes the scene descriptions and dialogue of the selected scene onto a single timeline and displays each line with its number and corresponding time stamp. The model only provides the numbers of the start and end lines. The code converts the line numbers to seconds and discards any intervals with numbers not in the list or with reversed order.

![image](/img/notes/langgraph-기반-방송-워크플로우-설계/img-02.jpg)

**Count: The code counts them.** Conditions such as “3 in total” or “1 per episode” are parsed into numbers during the query interpretation phase and executed by the code during the finalization phase. For the N clips per round, they are sorted by rank within that round before calling the model; for the total N clips, they are sorted after the model has determined the overall rankings. This is because, when the model was tasked with counting, it sometimes omitted rounds or counted two clips from a single round.

**Duration: Only clips are removed; none are added.** If the total duration exceeds the limit, the model first reselects key segments from the highest-ranked clips within the target time allocated proportionally to their original lengths. If it still exceeds the limit, the code removes clips starting with the lowest-ranked ones (leaving at least one clip). Even if the duration falls short, it does not pull in unselected segments to fill the gap.

We also adjusted the amount of input provided to the model. During the finalization phase, which determines the order across episodes, only scene summaries and characters are provided for each clip; cuts and dialogue are omitted. When the input was too long, the model tended to follow instructions less strictly. The process of filtering based on cuts and dialogue had already been completed during the ranking phase within each episode.

---

### 5. Query styles are categorized by instructions, not by graphs

Queries are divided into three styles.

- **Summary:** For when you want a brief overview of an episode’s plot. All scenes from the main episode are candidates.
- **Search:** For finding specific actions or scenes. Scenes matching the characters or locations, as well as those identified by vector search, are candidates.
- **Other:** Requests that do not fall under the above two categories. The query itself serves as the criterion.

We did not create separate graphs for each style. The workflow is the same for all three; only the instructions given to the model by nodes—such as “select a scene” or “cut a segment”—vary depending on the style. The “Summary” style instructs the model to select scenes necessary for the plot, while the “Search” style instructs it to select scenes where the queried action actually takes place. Even within “Summary,” the instructions are divided into two methods: one that cuts a long, continuous segment from cause to effect, and another that cuts to the minimum length containing the decisive moment. When adjusting the length, “Summary” includes more content and shortens it significantly, while “Search” includes less content and shortens it minimally, using different scaling ratios.

Even if a new style is added, the nodes and wiring remain the same; only one instruction is added.

---

### 6. Execution Log

The graph receives the updated status after each node completes and records which node took how many seconds and what changes were made. Once all tasks for a given round are complete and the process moves to the consolidation phase, the status is changed to “Under Review” so that the progress can be viewed from the outside.

Model calls log the full input and response text separately for each compilation. To trace back later and understand “Why was this clip selected?” or “Why was this scene omitted?”, it is necessary to know what the model observed and how it responded at each stage. These logs are also consulted when revising the instructions.

---

### Conclusion

---

The editing graph is structured to separate decisions made within a single episode from those requiring an overview of the entire project, to pass tasks between states, to distinguish between empty slots and failures, and to automate tasks where the model is prone to errors via code. The resulting list of clip segments is verified on screen before proceeding to video compositing to produce an MP4 file.

Reference Links)

- [https://github.com/langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)

*This article presents research results conducted with support from the Ministry of Science and ICT and the National IT Industry Promotion Agency’s “2026 Open-Source AI and Software Development and Utilization Support Project.”*

