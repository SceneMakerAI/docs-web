---
title: "Fixed an issue where speech was missing after a forced split when max_speech_duration_s was set"
sidebar_position: 33
slug: "33"
description: "silero-vad: Fixed an issue where speech retained by `neg_threshold` was discarded when forced to split at `max_speech_duration_s`."
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## silero-vad: Fixed an issue where speech was missing after forced segmentation using `max_speech_duration_s`

Link: https://github.com/snakers4/silero-vad/pull/813

### Background

SceneMakerAI trims 16 kHz mono broadcast audio (1–2 hours) using `get_speech_timestamps` at the front end of the STT process and uses `max_speech_duration_s` to adjust the STT input length. Although this option is documented as "splitting long segments," in practice, audio would sometimes disappear at the split points.

- With each forced split (when there is no silence to cut at, so the current window is split), one window (512 samples at 16 kHz, or 32 ms) does not fit into any segment. With the default value of `speech_pad_ms=30`, padding on both sides coincidentally fills the gap so it is not visible, but if `speech_pad_ms` is less than 16 ms, the gap remains visible.
- Intervals where the probability falls between `neg_threshold` (default 0.35) and `threshold` (0.5) are classified as “speech continuation” in the state machine; however, after a forced split, they are discarded entirely until a window with a probability exceeding `threshold` appears. This occurs even with the default parameters. Example: If a 9.6-second segment yields a value of `max_speech_duration_s=5`, only the first 4.96 seconds remain, and the last 4.6 seconds are lost.

### Cause

The fallback branch in `src/silero_vad/utils_vad.py`’s `get_speech_timestamps_from_probs` when the maximum length is reached (lines 527–534). After being cut at `current_speech['end'] = cur_sample`, it is replaced with `triggered = False` and then `continue` is executed. Consequently, the window at the cut-off point is not included in the new segment, and the new segment only begins when a window with a probability of `threshold` or higher appears afterward. This behavior has existed since `max_speech_duration_s` was first introduced in 2022 (PR 271).

### Changes

In the fallback branch, if the cut point is not within a silent interval (where `temp_end` is empty and the current probability is at least `neg_threshold`), `triggered` is retained, and the next interval begins immediately at `cur_sample`. If the cut occurs within a silent interval, a new interval begins when audio resumes, as before. The branches that cut at recorded silent points (`possible_ends`, `prev_end`) remain unchanged. Changes: 4 lines added, 1 line removed.

```python
if temp_end or speech_prob < neg_threshold:
    triggered = False  # cut inside a pause: wait for speech to return
else:
    current_speech['start'] = cur_sample  # speech goes on: keep it in the next chunk
```

Added test `tests/test_max_speech_split.py`. Verifies only the state machine by directly inputting a list of probabilities without a model (5 cases, 4 of which failed before the fix).

### Verification

- Reproduced in HEAD (1e261b0) before the fix: When a continuous utterance of 700 windows is truncated with a 2-second limit, 512 samples are missing at each of the 11 split points (352,768 / 358,400). The hysteresis interval example is missing the last 4.6 seconds.
- After the fix: 358,400 / 358,400; the hysteresis example is split correctly into two intervals. All intervals are still within the `max_speech_duration_s` limit.
- Actual speech `tests/data/test.wav` (60 seconds, JIT model, padding 0, 3-second limit): The number of missing windows—which were previously included in segments without restriction—decreased from 15 to 8. The remaining 8 are two silent sections (4 windows each) intentionally used as split points.
- `pytest tests`: 50 passed, 10 skipped (skipped due to tests run without torchcodec installed). torch 2.8.0 / torchaudio 2.8.0 / onnxruntime 1.30.0, Python 3.12.
- I verified the non-overlapping, range, and maximum length invariants using 40,000 random probability sequences, and no new violations were found following the fixes.

