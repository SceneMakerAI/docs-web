---
title: "The issue where `transcribe(chunk_length)` permanently changes the window size for subsequent calls"
sidebar_position: 23
slug: "23"
description: "faster-whisper: Reported a state leak where a call with a specified `chunk_length` changes the window size for subsequent calls to the same model"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-07
---

[https://github.com/SYSTRAN/faster-whisper/issues/1661](https://github.com/SYSTRAN/faster-whisper/issues/1661)

#### Problem

If `transcribe()` is called even once with the `chunk_length` argument, the window size for all subsequent calls using the same `WhisperModel` changes. Even calls that do not specify `chunk_length` are affected.

```python
print(seeks())                 # [0, 2200]
print(seeks(chunk_length=5))   # [0, 500, 1000, 1500, 2000, 2500]
print(seeks()) # [0, 500, 1000, 1500, 2000, 2500]  <- Should be [0, 2200]
```

The third call is decoded with a 5-second window, even though its arguments are the same as the first call’s.

For a server that runs a single model and processes multiple requests, once a request uses `chunk_length`, the results of all subsequent requests will quietly change until the process is restarted. SceneMaker’s `worker-prep_stt` also falls under the same conditions, as it uses a structure where the faster-whisper 1.2.1 model is kept running in the background for secondary transcription (the current code does not change `chunk_length` on a per-request basis, so there is no actual impact).

#### Cause

When `FeatureExtractor.__call__` receives `chunk_length`, it overwrites its own attributes (`n_samples`, `nb_max_frames`) and does not revert them (lines `faster_whisper/feature_extractor.py` 203–205). Since `self.chunk_length` remains at 30, their internal states become out of sync. Subsequently, `generate_segments` and `detect_language` read this value and split the window.

#### Reproduction

I reproduced the issue using `master` (f6ef59b), faster-whisper 1.2.1, ctranslate2 4.8.2, Python 3.12, CPU, and the `tiny` model. I’ve included the full script in the issue body.

#### Why an Issue Instead of a PR

A small fix (recalculating the value on every call) is ready along with tests. However, that alone does not isolate the state per call. Since `transcribe()` returns a lazy generator, the two transcriptions still interfere with each other when consumed alternately with different `chunk_length` values. To fix this completely, the function signature would need to be changed, so I first asked which approach you preferred.

#### Duplicate Check

I searched for open and closed issues and PRs involving combinations of `chunk_length` and `nb_max_frames` / `n_samples` / state / reuse, and found no duplicate reports. Issues #624 and #1204 concern different behaviors of `chunk_length`, and there are no open PRs that touch `feature_extractor.py`.

#### Result

Submitted on October 6, 2026. Awaiting a response from the maintainer.

Updated on October 7, 2026: The maintainer (Purfview) closed this issue on October 6, 2026, with the comment “AI bot problems.” There was no response regarding the content. I will not submit any further changes to this repository.

