---
title: "Fixed an issue where `COPY_SKIP_CACHE` returned paths without `fetch()`"
sidebar_position: 34
slug: "34"
description: "speechbrain: Pull request to fix Issue #3091. Handles the name change that previously depended on `force_filename` in `COPY_SKIP_CACHE` directly, ensuring the label encoder loads correctly."
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## speechbrain: Fixed an issue where COPY_SKIP_CACHE returned paths without `fetch()`

Link: https://github.com/speechbrain/speechbrain/pull/3093

This is a pull request to fix the issue reported in https://github.com/speechbrain/speechbrain/issues/3091. Removed the `force_filename` pass and, when COPY_SKIP_CACHE is enabled, moves the file returned by `hf_hub_download` to the target path. Added regression test `test_fetch_hf_copy_skip_cache_save_filename`.

### Background

SceneMakerAI uses `EncoderClassifier.from_hparams("speechbrain/lang-id-voxlingua107-ecapa")` to identify the language of broadcast audio. If you use `local_strategy=LocalStrategy.COPY_SKIP_CACHE` to place the model file as an actual file in `savedir` instead of an HF cache symbolic link, model loading completes without errors, but an exception like `KeyError: 16` occurs on the first call to `classify_batch`. This is because the label encoder is empty.

- Repository: speechbrain/speechbrain, default branch `develop`, HEAD `89ead74d`
- Type: Issue (fix and unit tests are ready in a local branch `fix/fetch-copy-skip-cache-save-filename`, pending commit)

### Cause

In `speechbrain/utils/fetching.py`, lines `fetch()` (lines 417–424) passes `hf_hub_download`, `local_dir=savedir`, and `force_filename=save_filename` to `force_filename` when COPY_SKIP_CACHE is set, delegating the task of “saving to savedir with the name save_filename” to huggingface_hub. However, huggingface_hub does not behave this way.

- Latest version (verified in 0.33.4 and 2.1.1): It ignores `force_filename` with a warning and saves to `savedir/filename`.
- Older versions (verified in 0.19.4, 0.22.2, and 0.23.0): If `force_filename` is present, it falls back to the legacy cache path, ignores `local_dir`, and saves the file to the HF cache directory. `savedir` is empty.

When COPY_SKIP_CACHE is set, `download_file_hf` discards the return path of `hf_hub_download`, and `fetch()` returns `savedir/save_filename` without checking for its existence.

Since `Pretrainer.collect_files` always calls `save_filename = 로더블이름 + ".ckpt"`, entries with different filenames in `paths` (such as voxlingua107’s `label_encoder.txt`) are affected. The `.ckpt` weight is loaded normally because the names match, and since the label encoder returns only False for files lacking `CategoricalEncoder.load_if_possible`, it is silently skipped.

### Reproduction Steps

```python
import os, tempfile
from speechbrain.utils.fetching import fetch, LocalStrategy

with tempfile.TemporaryDirectory() as d:
    p = fetch("label_encoder.txt", source="speechbrain/lang-id-voxlingua107-ecapa",
              savedir=d, save_filename="label_encoder.ckpt",
              local_strategy=LocalStrategy.COPY_SKIP_CACHE)
    print(p, p.exists(), sorted(os.listdir(d)))
```

HEAD result: The return path is `label_encoder.ckpt`, but `exists` is False, and only `label_encoder.txt` exists in the directory.

End-to-end (`repro_e2e.py` ): The SYMLINK strategy returns 107 labels, and `text_lab` is normal. The COPY_SKIP_CACHE strategy returns 0 labels, and `classify_batch` to `KeyError: 16` .

### Changes (local patch, not submitted)

- `fetch()`: Removed the `force_filename` pass.
- `download_file_hf()`: If the path returned by `hf_hub_download` in COPY_SKIP_CACHE differs from `destination`, move it to `shutil.move`.
- `tests/unittests/test_fetch.py`: Added one regression test to replace `hf_hub_download`.

The removal of `local_dir_use_symlinks=False` (bundled with the huggingface_hub minimum version increase) and the silent skip in the label encoder itself are decisions to be made by the maintainer, so I noted them separately in the issue body.

### Verification

- Bug reproduced on HEAD: huggingface_hub 2.1.1, 0.33.4, 0.22.2 (original output is `repro.txt`).
- Regression test: Failed with a FileNotFoundError before the fix; passed after the fix.
- Reproduction script for `fetch()` after the fix: files exist in all versions of huggingface_hub (0.19.4, 0.22.2, 0.23.0, 0.33.4, 2.1.1).
- End-to-end after the fix: 107 labels, classification works normally.
- `pytest tests/unittests`: 750 passed, 7 failed. The 7 failures also occurred in the pre-fix HEAD version (due to Torch 2.14.1 compatibility issues and Transformers not being installed) and are unrelated to this change.
- `ruff check` and `ruff format --check` (0.12.4) passed.
- Not run: All of `pre-commit run -a`; same Torch 2.6.0 environment as integration tests and CI.

