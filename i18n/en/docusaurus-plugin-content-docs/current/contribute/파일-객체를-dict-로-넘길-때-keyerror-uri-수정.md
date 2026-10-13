---
title: "Fixing the \"KeyError 'uri'\" when passing a file object to a dict"
sidebar_position: 14
slug: "14"
description: "pyannote-audio: Fixed an issue where the pipeline failed with a KeyError because the default URI was missing from the input dict containing file objects"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

[https://github.com/pyannote/pyannote-audio/pull/2072](https://github.com/pyannote/pyannote-audio/pull/2072)

#### Purpose

The documentation states that `Audio.validate_file` accepts four types of input, one of which is a "Mapping with a file object stored in the `audio` key." You must use this format to pass `channel` along with it. However, the default `uri` was not filled in only in this case. This is because when the Mapping branch encounters a file object (`IOBase`), it returns immediately before reaching `setdefault("uri", ...)`.

The pipeline reads `file["uri"]` when generating the result (`speaker_diarization.py`, `voice_activity_detection.py`, `speech_separation.py`, `multilabel.py`). Therefore, `pipeline({"audio": f, "channel": 0})` fails with `KeyError: 'uri'` after the inference has completed.

SceneMaker’s `worker-prep_stt` uses pyannote 4.0.7 for speaker segmentation and follows an input path that bypasses file decoding. I discovered this while reading the code because it follows the same path through the input validation function.

#### Changes

- `src/pyannote/audio/core/io.py` — Fills the default `uri` with `"stream"` even for a Mapping containing a file object. When passing the file object as-is, it matches the value already in use, and the `uri` provided by the caller remains untouched (+2)
- `tests/io_test.py` — Added 2 tests to verify whether the default value is set or the `uri` provided by the caller is preserved (+15)
- `CHANGELOG.md` — Added one line to the `next` section (+1)

#### Reproduction

Reproduced on the `develop` branch without a pre-trained model.

```python
from pyannote.audio import Pipeline
from pyannote.core import Annotation

class Echo(Pipeline):
    def default_parameters(self):
        return {}

    def apply(self, file):
        return Annotation(uri=file["uri"])

pipeline = Echo()
pipeline.instantiate({})
with open("tests/data/dev00.wav", "rb") as f:
    pipeline(f) # OK, uri == "stream"
    pipeline({"audio": f, "channel": 0})    # KeyError: 'uri'
```

#### Tests

```text
$ pytest tests/io_test.py # Before modification: 1 new test failed (KeyError: 'uri')
$ pytest tests/io_test.py # After modification: 11 passed
```

My local environment is Python 3.12, torch 2.8.0 (CPU), and torchcodec 0.7.0. I did not run the remaining tests that require a model locally; I left those to CI.

#### Duplicate Check

Before submitting, I searched open and closed issues and PRs using the keywords `uri` + `IOBase` / file-like / `KeyError` and found no entries addressing the same issue. Among the open PRs, the only one touching `core/io.py` is an unrelated PR from 2023 (#1336).

#### Result

I submitted the pull request on 2026-10-06 targeting the `develop` branch. It is currently awaiting review. The scope of the changes is 3 files, with +18 lines of code.

