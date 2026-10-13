---
title: "Fixed an issue where `get_all_files` excluded all files following those matched by `exclude_and`"
sidebar_position: 54
slug: "54"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-12
---

## speechbrain: Fixed an issue where `get_all_files` removed all files following those matched by `exclude_and`

Link: https://github.com/speechbrain/speechbrain/pull/3101

### Background

`speechbrain.utils.data_utils.get_all_files` is a function that recursively traverses folders to generate a list of files; it is used in data preparation scripts and testing tools. It filters the results using four pattern arguments: `match_and`, `match_or`, `exclude_and`, and `exclude_or`. `exclude_and` is an option that excludes only files whose names contain all the patterns in the list.

### Cause

Lines `speechbrain/utils/data_utils.py` 141–148. Four flags are recalculated for each file; `match_and_entry`, `match_or_entry`, and `exclude_or_entry` are reset to `False` for each file before evaluation, while only `exclude_and_entry` is not reset. Consequently, if one file triggers `exclude_and` and becomes `True`, all subsequent files in the same directory are excluded. There are no exceptions or warnings, and the number of files omitted depends on the order of `os.listdir`. This behavior has remained unchanged since the initial release in March 2020.

### Changes

- `speechbrain/utils/data_utils.py`: Added `exclude_and_entry = False` to the first line of the `exclude_and` evaluation block (line 1). It has the same format as the `exclude_or` block immediately below it.
- `tests/unittests/test_data_utils.py` New: Verify that when three files are created and excluded one by one using `exclude_and`, the remaining two are output as-is. Prior to this fix, this test would always fail regardless of the `os.listdir` order.

### Reproduction Steps

```python
import os, tempfile
from speechbrain.utils.data_utils import get_all_files

d = tempfile.mkdtemp()
for name in ["a.wav", "b.wav", "c.wav"]:
    open(os.path.join(d, name), "w").close()

print(sorted(os.path.basename(f) for f in get_all_files(d, exclude_and=["a.wav"])))
# develop: []  /  After modification: ['b.wav', 'c.wav']
```

### Verification

- The new test failed at `develop` (546bfc9f2) but passed after the fix.
- `pytest --doctest-modules speechbrain/utils/data_utils.py`: 6 passed, `pytest tests/consistency`: 6 passed.
- `pytest tests/unittests`: 756 passed, 5 skipped, 5 failed. The 5 failures (`test_filterbank`, 2 in `test_g2p`, and 2 in `test_rescorer`) still occur even after reverting the fix (in a torch 2.14.1 environment without `transformers` installed).
- `ruff check` and `ruff format --check` (0.12.4) passed. Codespell, Yamllint, integration tests, and the full doctest were not run.

### Note

- There are no calls within the repository that pass `exclude_and` (only `exclude_or` is used). The impact is limited to external user code.
- It appears that the docstring descriptions for `exclude_and` and `exclude_or` have been swapped, but this was not included in this change.

