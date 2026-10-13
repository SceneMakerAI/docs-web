---
title: "Fixed an issue where including \"16k\" in the path caused the default ONNX model to be mistakenly identified as 16 kHz-only"
sidebar_position: 35
slug: "35"
description: "silero-vad: Fixed an issue where OnnxWrapper would search the entire path for \"16k,\" and if the parent directory name contained \"16k,\" the default model would reject 8 kHz input."
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## silero-vad: Issue where a 16k in the path causes a standard ONNX model to be mistaken for a 16 kHz-specific model

Link: https://github.com/snakers4/silero-vad/pull/814

### Background

`OnnxWrapper` checks for `'16k' in path` to distinguish 16 kHz-specific models (`silero_vad_16k_op15.onnx`). However, `path` refers to the full path, not just the filename. Since `load_silero_vad(onnx=True)` passes the internal path of the installed package, if `16k` is included in the name of a virtual environment or project directory (e.g., `asr_16k_project/.venv/...`), even the default model `silero_vad.onnx`—which supports both 8 kHz and 16 kHz—is treated as 16 kHz-only.

### Cause

In `src/silero_vad/utils_vad.py`’s `OnnxWrapper.__init__` (line 79 in the master branch), a substring check is performed on the full path. If a match is found, `sample_rates` is set to `[16000]` and a warning is output; subsequently, 8 kHz input is rejected in `_validate_input` and set to `ValueError: Supported sampling rates: [16000] (or multiply of 16000)`.

### Steps to Reproduce

Copy the default model file to a directory named `asr_16k_project`, load it as `OnnxWrapper`, and then call `get_speech_timestamps` with 8 kHz audio.

```text
original location : [8000, 16000] []
asr_16k_project/  : [16000] ['This model support only 16000 sampling rate!']
ValueError: Supported sampling rates: [16000] (or multiply of 16000)
```

### Changes

- Limited the scope of the check to `os.path.basename(path)` (added 2 lines, including the addition of `import os`; deleted 1 line)
- New test: Verify that 8 kHz works even if `16k` exists in the parent directory, and that the op15 model is still recognized as 16 kHz-only

### Verification

- Before the fix: 1 new test failed (due to the warning above); after the fix: 2 tests passed
- `pytest tests` overall: 47 passed, 10 skipped (skipped due to torchcodec not being installed)
- Windows paths cannot be executed locally

