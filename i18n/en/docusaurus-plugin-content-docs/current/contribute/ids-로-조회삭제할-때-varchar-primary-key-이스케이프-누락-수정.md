---
title: "Fixed a missing escape character in the VARCHAR primary key when querying or deleting by ID"
sidebar_position: 22
slug: "22"
description: "pymilvus: Fixed an issue where MilvusClient's get/query/delete(ids=) method would cause errors or delete the wrong rows because it did not escape VARCHAR keys containing quotes or backslashes."
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## pymilvus: Fixed missing escape for VARCHAR primary key (MilvusClient get/query/delete by ids)

Link: https://github.com/milvus-io/pymilvus/pull/3823

### Background

SceneMakerAI handles collections of string primary keys using `MilvusClient` and `AsyncMilvusClient`. `get(ids=...)`, `query(ids=...)`, `delete(ids=...)` internally convert the list of IDs into a filter expression string and send it to the server; however, if the string PK contains single quotes, backslashes, or line breaks, the call fails or targets the wrong row.

### Cause

In `pymilvus/milvus_client/base.py`, `BaseMilvusClient._pack_pks_expr` simply wraps VARCHAR PK values in single quotes without escaping them (line 134 before the fix).

```python
ids = ["'" + str(entry) + "'" for entry in pks]
```

As a result, on master (9b1d5ad) + Milvus Lite 3.0, it behaves as follows:

- `O'Brien`: `unterminated string literal` error
- `back\slash`: `unknown escape sequence \s` error
- Key containing a line break: `unterminated string literal (newline)` error
- `a', 'plain`: The expression becomes `id in ['a', 'plain']`, so the line requested by `delete` is retained, while the unrelated `plain` line is deleted

### Changes

- Added the `_escape_str_pk` helper and used it in `_pack_pks_expr`. Only four characters are escaped: backslash, single quotes, `\n`, and `\r`. These are precisely the four characters prohibited within single-quoted strings in the Milvus expression syntax (`Plan.g4`’s `SingleSChar`).
- For keys that do not contain these characters, the expression is generated exactly as before.
- Since the helper is in a common base class, this applies to both sync and async clients.
- Added unit tests (validation of expressions passed to handlers) and Milvus Lite integration tests (get/query/delete round trips).

### Verification

- Wrote the failing tests first to confirm they failed before the fix (4 unit tests, 1 Lite test), then made the corrections.
- `pytest tests/unit`: 5261 passed, 3 skipped
- `pytest tests/integration/lite`: 5 passed
- `black --check` and `ruff check` passed
- Could not run on a standalone Milvus server. Substituted with Milvus Lite 3.0 execution results and verification of the Milvus core syntax file.

### Notes

- The PK expression on the iterator side (`pymilvus/client/iterator/`) was not addressed as it falls under a separate issue (#1960).
- This repository requires a DCO signature (`git commit -s`).

