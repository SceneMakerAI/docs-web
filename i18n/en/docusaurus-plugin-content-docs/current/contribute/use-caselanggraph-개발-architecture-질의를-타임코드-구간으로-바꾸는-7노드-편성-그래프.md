---
title: "[Use Case][LangGraph] Development Architecture — A 7-node graph that converts queries into timecode intervals"
sidebar_position: 9
slug: "9"
description: "A 7-node graph that converts queries into timecode intervals"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

GitHub Discussion: [https://github.com/SceneMakerAI/docs-web/discussions/33](https://github.com/SceneMakerAI/docs-web/discussions/33)

This post explains why the configuration graph in [`agent-compose`](https://github.com/SceneMakerAI/agent-compose) looks the way it does. Installation instructions are provided separately in [#32](https://github.com/SceneMakerAI/docs-web/discussions/32).

It takes queries such as live baseball broadcasts or “3 minutes of home runs only” and returns a list of clip segments (start and end seconds). The framework is similar to the RAG document, but the difference is that the answer consists of timecodes rather than paragraphs.

```text
load_inventory ─► parse_query ─► retrieve_evidence
  ─► select_clips ─► select_end_point ─► merge_overlap ─► trim_budget ─► END
```

| Node | LLM |  |
| --- | --- | --- |
| `load_inventory` |  | Reads the list of video segments from the database once. If none exist, proceeds directly to `END` |
| `parse_query` | O | Parses the query into filters (inning, team, label) and search terms |
| `retrieve_evidence` | Embedding | Searches for evidence in Milvus using the search terms |
| `select_clips` | O | Narrows down candidates using rules, and the LLM selects the final answer |
| `select_end_point` | O | Determine the start and end coordinates of the selected segment |
| `merge_overlap` |  | Merge overlapping clips when a single play is split into two |
| `trim_budget` |  | Trim the clip to fit the target length |

#### Tasks Not Entrusted to the LLM

The LLM only makes selections; the code performs the verification. In `parse_query`, the LLM selects filters only from the vocabulary actually present in that game, and the parser discards any values outside that vocabulary. In `select_clips`, only segment numbers that are actually present among the candidates are passed through.

Length calculation was completely removed from the LLM’s responsibilities. When I included rules like “Adjust to 3 minutes” in the prompt, the “thinking” phase became endlessly long. Now, the LLM only selects items in order of importance, and `trim_budget` trims the tail. It does not fill in gaps. If it starts pulling in segments not in the song selection to fill gaps, the query rules will override the selection.

The output format was also changed from JSON to the `키: 값` line format. In Qwen, this format resulted in fewer parsing errors.

#### Search

There are three types of evidence: commentary (stt), screen captions (shot), and bottom subtitles (etc.), and they are searched separately by type. If they are mixed together, the numerous “shot” and “etc.” entries dominate the top results, pushing the commentary down.

Queries without specific scene descriptions, such as “highlights,” bypass vector search. Searching with such terms results in chaotic matches. In these cases, the system does not search using the original query text instead; it organizes results using filters alone.

#### How far do we relax the conditions?

If there are 0 candidates, we only relax the content-related conditions (labels, scoreboard). Since inning and team are conditions specified directly by the user, we do not alter them. If there are still 0 results, we return an empty lineup. We determined this is better than filling in nonexistent information as if it existed.

#### State

The DB and LLM clients aren’t stored in state; instead, they’re passed as closures when constructing the graph. The interval list is a “frozen dataclass,” so nodes cannot modify it, and intermediate results are stored as new objects under different keys. We don’t use reducers—everything is handled via replacement.

The nodes are located under `src/domains/baseball/`, and `src/pipeline/dispatch.py` selects the domain based on video categories. Currently, only baseball is registered.

The code is in `src/domains/baseball/graph/`. The wiring is in `build.py`, and the state is in `state.py`.

