---
title: "Fixed an issue where `collect_env` would either read packages from a different environment or crash in a UV environment"
sidebar_position: 18
slug: "18"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

[https://github.com/vllm-project/vllm/pull/60191](https://github.com/vllm-project/vllm/pull/60191)

#### Purpose

Since virtual environments created with `uv` do not have ``pip``, ``collect_env`` reads the package list from ``uv pip list --format=freeze`` instead. However, since this call does not specify which environment to examine, `uv` selects the environment based on the working directory. As a result, two issues arise.

1. **Incorrect packages are reported.** If the script is run without activating the virtual environment (e.g., via `.venv/bin/python -m vllm.collect_env` or systemd), the list from a different environment is displayed. The actual virtual environment is `torch==2.14.1+cpu` / `numpy==2.5.3`, but the system environment’s `numpy==2.2.6` and `nvidia-*` were output instead. It fails silently without an error and is included as-is in the bug report.
2. **It crashes if the command fails.** If `uv` is not present in `PATH` or the environment cannot be found, it exits with `AttributeError: 'NoneType' object has no attribute 'splitlines'`. This was the reason why environment information had to be entered manually when filing vllm#44538.

This PR passes `--python sys.executable` to have the interpreter reading the package of the script currently running, and instead of terminating when a command fails, it outputs `[pip3] Could not collect` as per existing convention. This is a follow-up fix to #13888 and #15792, which added alternative paths for uv.

**This is not a duplicate.** I searched for open PRs using `collect_env` and `13888 in:body`. #48354 deals with `get_pkg_version` (non-Linux platforms), #39817 addresses ROCm labeling, and there is no PR to fix `get_pip_packages`.

#### Files Affected

- `vllm/collect_env.py`
- `tests/test_collect_env_pip.py` (new)

#### Test Plan

```bash
pytest tests/test_collect_env_pip.py -v
ruff check vllm/collect_env.py tests/test_collect_env_pip.py
ruff format --check vllm/collect_env.py tests/test_collect_env_pip.py
```

Manual verification in a UV virtual environment without pip:

```bash
# When "uv" is not in the PATH
env PATH=/usr/bin:/bin .venv/bin/python -m vllm.collect_env
# From a different directory without activating the virtual environment
cd /tmp && /path/to/.venv/bin/python -m vllm.collect_env
```

#### Test Results

```text
2 passed
ruff: All checks passed! / 2 files left unchanged
```

Both tests fail on `main` due to the issue described above regarding `AttributeError`.

| Situation | Before Fix | After Fix |

| --- | --- | --- |

| `uv` is missing in `PATH` | Exits with `AttributeError` | `[pip3] Could not collect` |

| Virtual environment not active | System packages (`numpy==2.2.6`, `nvidia-*`) | Virtual environment packages (`numpy==2.5.3`, `torch==2.14.1+cpu`) |

