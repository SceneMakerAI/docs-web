---
title: "Issue where sorting query/search results in place causes vectors and dynamic fields to end up in different rows"
sidebar_position: 31
slug: "31"
description: "pymilvus: Reported an issue where, when sorting, reversing, or removing elements from query/search results in place, delayed-decoding fields end up attached to different rows."
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-06
---

[https://github.com/milvus-io/pymilvus/issues/3824](https://github.com/milvus-io/pymilvus/issues/3824)

#### Issue

The lists returned by `MilvusClient.query()` and `MilvusClient.search()` are decoded when certain fields (vectors, JSON, dynamic fields) are read. This decoding is based on the "position within the list" and occurs only during index access and iteration. Therefore, if you sort, reverse, or extract results that haven’t been read yet in-place (`sort`, `reverse`, `reversed()`, `pop`), the fields may end up attached to different rows or remain as `None`. No exceptions are thrown.

```text
query, as-is: [(1, 'clip-1', [1.0, 1.0]), (2, 'clip-2', [2.0, 2.0]), (3, 'clip-3', [3.0, 3.0])]
query, .sort(id in reverse order): [(3, 'clip-1', [1.0, 1.0]), (2, 'clip-2', [2.0, 2.0]), (1, 'clip-3', [3.0, 3.0])]
query, reversed()     : [{'id': 3, 'vector': None}, {'id': 2, 'vector': None}, {'id': 1, 'vector': None}]
query, .pop()         : {'id': 3, 'vector': None}
```

After sorting, id 3 appears with the title and vector of id 1. `sorted(rows, ...)` is safe because it iterates first.

SceneMaker indexes range proofs in Milvus, and `agent-compose` handles search results in chronological order. I reported this as a type of issue where, if there is code that reads vectors or dynamic fields while setting the result to the time field via ``.sort()``, it silently writes incorrect values. I have not verified whether the current SceneMaker code actually follows this path.

#### Cause

- `HybridExtraList.__getitem__` / `__iter__` (`pymilvus/client/types.py` ) populate delayed fields using list indices.
- `HybridHits.materialize()` (`pymilvus/client/search_result.py` ) is also position-based.
- `sort`, `reverse`, `__reversed__`, `pop`, `insert`, `del`, and `copy` are the default implementations of `list` and therefore do not follow the path described above.

There is a history of similar bugs (#2986—last line, #3136—negative index, #2862/#2866—missing iterations) being fixed one by one for each access path.

#### Reproduction

I reproduced this issue using pymilvus `master` (9b1d5ad, 3.1.0rc90), Milvus Lite 3.2.1 (local file), and Python 3.12. I was unable to verify this on a standalone Milvus server, but all decoding occurs on the client side. I have included the full script in the issue body.

#### Why an Issue Instead of a PR

The fix (decoding the remaining rows before performing position-dependent list operations) and unit tests are ready. However, there is a performance cost to consider. Since `append` and `sort` decode an entire row at once, it is up to the maintainer to decide whether to block all operations or only those that reorder the rows. I asked for guidance on the approach first.

#### Duplicate Check

I searched for open and closed issues and PRs tagged with `HybridExtraList`, `sort query result`, `query result reversed`, `lazy sort vector wrong row`, and `in-place sort results`, and found no duplicate reports. Issue #3823 (VARCHAR primary key escape), posted in another session on the same day, concerns a different issue in a different function.

#### Result

I submitted the issue on October 6, 2026. I am awaiting a response from the maintainer.

