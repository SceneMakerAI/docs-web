---
title: "Fixed an issue where `dotenv run` rejected .env files in FIFO format"
sidebar_position: 27
slug: "27"
description: "python-dotenv: Fixed an issue where `dotenv run` would reject a .env file in named-pipe format with a \"does not exist\" error; now handles it the same way as the library's `list/get` methods."
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## python-dotenv: Fixed an issue where `dotenv run` rejected FIFO-formatted .env files

Link: https://github.com/theskumar/python-dotenv/pull/723

### Background

Starting with version 1.2.2, python-dotenv officially supports reading from a FIFO (named pipe) via `.env` (PR #586; also specified in the “File format” section of the README). This is intended to prevent plaintext secrets from being left on disk, similar to 1Password’s local `.env` mount or process substitutions like `dotenv -f <(sops -d secrets.env) ...`.

However, only the CLI’s `dotenv run` does not accept this path. The libraries (`load_dotenv`, `dotenv_values`) and `dotenv list`, `dotenv get` all function normally with the same path.

### Cause

The `src/dotenv/cli.py` command (line 196) checks the path using `run` before passing it to `DotEnv`. Since a FIFO is not a regular file, it exits with a “does not exist” error (exit 2). In the library, `DotEnv._get_stream` and `find_dotenv` were changed from #586 to `_is_file_or_fifo`, but this guard was omitted in the CLI.

### How to Reproduce

```shell
$ dotenv -f <(echo A=1) list
A=1
$ dotenv -f <(echo A=1) run printenv A
Error: Invalid value: Invalid value for '-f' "/dev/fd/63" does not exist.
```

The same issue occurs when using a named pipe created with `mkfifo .env` as the default path.

### Changes

- `src/dotenv/cli.py`: Replaced the guard for `run` from `os.path.isfile` to `_is_file_or_fifo` (1 import line, 1 conditional line).
- `tests/test_fifo_dotenv.py`: Added `test_cli_run_from_fifo`. Verified that `dotenv run printenv MY_PASSWORD` outputs a value for the FIFO `.env`.
- `CHANGELOG.md`: Added an entry to “Unreleased / Fixed.” The PR number is a placeholder for `#NNN`, so it must be replaced with the actual number after the PR is created.

Non-existent paths and directories continue to be rejected with the same message as before.

### Verification

- Before the fix: New test failed (exit 2, "does not exist").
- After the fix: `pytest` 285 passed, 4 skipped. `ruff check src tests`, `ruff format --check src tests`, and `mypy --python-version=3.10~3.14 src tests` all passed.
- Run only on Python 3.11 / Linux. The full tox matrix (3.10–3.14, 3.14t, PyPy, Windows) and `check-manifest` were not tested.

