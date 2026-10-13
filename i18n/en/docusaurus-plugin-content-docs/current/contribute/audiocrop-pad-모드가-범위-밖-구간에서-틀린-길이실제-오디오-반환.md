---
title: "Audio.crop pad mode returns incorrect lengths and actual audio from sections outside the specified range"
sidebar_position: 20
slug: "20"
description: "pyannote-audio: Report of an issue where the \"pad\" mode in Audio.crop returns incorrect results for segments that fall completely outside the file range"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-06
---

[https://github.com/pyannote/pyannote-audio/issues/2073](https://github.com/pyannote/pyannote-audio/issues/2073)

#### Problem

The documentation states that `Audio.crop(..., mode="pad")` fills intervals that fall outside the file’s range with zeros. It works correctly when the interval partially overlaps with the file, but the result is incorrect when the interval **completely** falls outside the file’s range. The symptoms also differ between the waveform loaded into memory and the disk file.

If you cut a 1-second segment from a 10-second waveform (16 kHz, all values are 1), you should get 16,000 samples every time.

| Segment | Actual Result | Expected |

| --- | --- | --- |

| 9.5–10.5 seconds | 16,000 samples, 8,000 non-zero values | Normal |

| -0.5–0.5 seconds | 16,000 samples, 8,000 non-zero values | Normal |

| 12–13 seconds | 48,000 samples, all 0 | 16,000 samples of 0 |

| -3 to -2 seconds | 176,000 samples, 128,000 non-zero values | 16,000 samples of 0 |

In the disk file (30 seconds), intervals of this type fail at `ValueError: Invalid start seconds`. In particular, the -3 to -2 second interval is a nonexistent region, and the fact that it plays the actual audio quietly is the most dangerous aspect.

#### Cause

In both branches, only one end of the interval is pulled into the valid range (`src/pyannote/audio/core/io.py`).

- Memory branch: It aligns to 0 only when the start is negative, and to the last sample only when the end overflows. If the interval extends past the end, the fill length becomes the “distance from the end of the file” rather than the interval length; if the interval extends before the start, the negative end position is written directly as a negative index, causing the actual audio to be returned.
- File branch: After adjustment, the start becomes greater than the end, causing the decoder to reject it.

#### Reproduction

Reproduced on the `develop` branch (78a6e44b) without a pre-trained model.

```python
import torch
from pyannote.core import Segment
from pyannote.audio import Audio

audio = Audio()
file = {"waveform": torch.ones(1, 160000), "sample_rate": 16000}  # 10 seconds

for segment in [Segment(9.5, 10.5), Segment(12, 13), Segment(-0.5, 0.5), Segment(-3, -2)]:
    waveform, _ = audio.crop(file, segment, mode="pad")
    print(segment, waveform.shape[1], int((waveform != 0).sum()))
```

#### Why an Issue Instead of a PR

There are two possible expected behaviors: it could return zeros for the duration of the segment, or it could raise a clear error. Since it is up to the maintainer to decide which is correct, I first raised this as an Issue and noted that I would submit a PR once the direction is determined.

#### Checking for Duplicates

- #2068 (already merged): This involved a boundary issue where the interval exactly touched the end of the waveform, which is different from this issue.
- #1417 (Closed): This involved a case where the range in `mode="raise"` slightly exceeded the file boundaries, which is different from this issue.
- I searched for open and closed issues and PRs related to `crop pad negative segment`, `crop pad wrong number of samples`, `crop Invalid start seconds`, and `Audio.crop mode pad` and found no similar issues.

#### Result

Submitted on October 6, 2026. Awaiting a response from the maintainer.

