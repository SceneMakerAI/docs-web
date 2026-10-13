---
title: "If I set UPLOAD_DIR to a string and enable UPLOAD_KEEP_FILENAME, I get a TypeError. Fix"
sidebar_position: 28
slug: "28"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## python-multipart: A TypeError occurs when UPLOAD_DIR is set to a string and UPLOAD_KEEP_FILENAME is enabled

Link: https://github.com/Kludex/python-multipart/pull/335

- Repository: Kludex/python-multipart (main, 212819d, version 0.0.32 and later)
- Type: PR (bug fix)
- Title: Accept a `str` `UPLOAD_DIR` when `UPLOAD_KEEP_FILENAME` is set

### Background

SceneMakerAI’s `poc-stt-bench` uses FastAPI to receive video and audio uploads, with `python-multipart` handling the multipart parsing. While reviewing the upload path, I examined the settings of this library’s `File` class. The configuration table in the `File` docstring specifies the `UPLOAD_DIR` type as `str`, and the `FileConfig` type hint is `str | bytes | None`. However, if a `str` path is provided along with `UPLOAD_KEEP_FILENAME=True`, an exception occurs during the first write that exceeds the memory limit (`MAX_MEMORY_FILE_SIZE`). Since the default FastAPI path does not use this setting, this issue only occurs in code that directly uses the `File` object.

| UPLOAD_DIR | UPLOAD_KEEP_FILENAME | Result |

|---|---|---|

| str | False | Normal |

| bytes | True | Normal |

| str | True | TypeError: Can't mix strings and bytes in path components |

### Cause

In `python_multipart/multipart.py`’s `File._get_disk_file()` (line 542), the branch for preserving the filename is as follows:

```python
path = os.path.join(file_dir, fname)  # type: ignore[arg-type]
```

Since `fname` is always bytes, if `file_dir` is str, `os.path.join` raises a TypeError. The temporary file branch immediately below handles both str and bytes, but this specific branch was missing, and `type: ignore` was masking the mypy warning. Since `TypeError` is not an `OSError`, it is not converted to ``FileError``. The existing tests did not catch this issue because they only used `bytes` paths in this combination.

### Changes

- Changed to `os.path.join(os.fsencode(file_dir), fname)` and removed `type: ignore` (1 line). The behavior of the `bytes` path remains unchanged.
- Added `test_str_upload_dir_with_keep_filename` to `tests/test_file.py`.

### Verification

- Before the fix: Verified that the new test failed due to the TypeError mentioned above.
- After the fix: `coverage run -m pytest` 163 passed, coverage 100% (based on the repository’s `fail_under=100`).
- `ruff format --check`, `ruff check`, `mypy --strict`, `check-sdist`, and `scripts/rename` (nox) all passed.
- Run only on Python 3.11. Do not run versions 3.12–3.15 from the CI matrix locally.

### Notes

- Duplicate check: Open PR #308, which addresses the same `_get_disk_file()`, deals with an AttributeError that occurs when `file_name=None` is used; the cause differs from this issue.
- Separately verified during investigation: In multipart, the base64/quoted-printable decoders are only finalized for the last part, so truncated base64 in non-final parts passes through without exceptions. This was not included in the scope of this PR.

