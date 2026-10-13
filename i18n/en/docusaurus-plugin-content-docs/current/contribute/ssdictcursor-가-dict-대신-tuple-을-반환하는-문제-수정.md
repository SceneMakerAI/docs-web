---
title: "Fixed an issue where `SSDictCursor` returned a tuple instead of a dict"
sidebar_position: 17
slug: "17"
description: "asyncmy: Since it's a Cython `cdef` method, overrides don't work. Fixed the issue where `SSDictCursor` was returning a tuple by changing it to `cpdef`."
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## asyncmy: Fixed a bug where SSDictCursor returned a tuple instead of a dict

Link: https://github.com/long2ice/asyncmy/pull/164

- Target: long2ice/asyncmy (default branch `dev`, HEAD `0000bd0`)
- Type: PR (bug fix + regression testing)
- Title: `fix: return dicts from SSDictCursor instead of tuples`

### Background

SceneMakerAI uses asyncmy as the MySQL/MariaDB driver in its FastAPI service and primarily receives results as `DictCursor`. `SSDictCursor`, the dictionary version of the unbuffered cursor for bulk queries, is described in the class docstring as “An unbuffered cursor, which returns results as a dictionary,” but in reality, both `fetchone` and `fetchmany` / `fetchall` / `async for` all return tuples. Since there were no cases in the repository tests using `SSCursor` / `SSDictCursor`, this issue went unnoticed.

### Cause

`asyncmy/cursors.pyx`’s `SSCursor.read_next()` converts rows to `self._conv_row(...)`. However, `_conv_row` is declared as the `cdef` method in both `Cursor` and `SSCursor` (both of which are `cdef class`). Cython dispatches method calls within `cdef class` directly to the C vtable, and pure Python subclasses cannot override vtable slots. Therefore, in `class SSDictCursor(DictCursorMixin, SSCursor)`, the `DictCursorMixin._conv_row` method—which comes first in the MRO—is not called; only `SSCursor._conv_row`, which returns the input as-is, is executed.

The reason `DictCursor` behaves correctly is that, in the buffered path, the conversion is completed within the Python method `DictCursorMixin._do_get_result`. For unbuffered cursors, since `_rows` is `None` at that point, `read_next()` is the only conversion point.

This is a regression introduced in the April 2022 commit `8836fc5`, where `def` was changed to `cdef` relative to `git log -S"cdef _conv_row"`.

### Changes

- `asyncmy/cursors.pyx`: Changed `Cursor._conv_row` and `SSCursor._conv_row` from `cdef` to `cpdef` (2 lines). Since `cpdef` searches for and calls the Python override when it is a subclass instance, `DictCursorMixin._conv_row` and the user-defined `dict_type` are reapplied.
- `tests/test_cursor.py`: Added `test_ss_dict_cursor` (`fetchone` / `fetchmany` / `fetchall` / `async for`).
- `CHANGELOG.md`: Added one line to the 0.2.16 section.

### Reproduction Steps

```python
async with conn.cursor(cursor=SSDictCursor) as cur:
    await cur.execute("SELECT 1 AS a, 'x' AS b UNION ALL SELECT 2, 'y'")
    print(await cur.fetchone())   # Before modification: (1, 'x')   After modification: {'a': 1, 'b': 'x'}
```

### Verification

- Ran on a temporary `mariadbd` instance on 10/11/15 (dedicated datadir, port 33917). Existing containers and volumes were left untouched and cleaned up after the task.
- Before the fix: New test failed with an AssertionError (a tuple was returned, which did not match the dict).
- After the fix: All `pytest` 87 tests passed, 4 skipped. `ruff format --check`, `ruff check`, and `mypy` passed.
- For `stubtest`, the 9 existing errors related to `contexts.TypeVar` in the Python 3.11 environment remained unchanged before and after the fix (CI uses 3.14). No new errors were introduced by this change.
- I was unable to run tests on a local machine with a MySQL server and a different Python version.

