---
title: "0.7 regression where ContentDetector discards cuts that fall short of `min_scene_len` at 29.97/59.94 fps"
sidebar_position: 45
slug: "45"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-07
---

## PySceneDetect: In a 29.97/59.94 fps video, ContentDetector discards cuts that are separated by a number of frames equal to `min_scene_len`.

Link: https://github.com/Breakthrough/PySceneDetect/issues/577

- Repo: Breakthrough/PySceneDetect (approx. 5.2k stars, default branch `main`, HEAD `81c414c`, version 0.7.1)
- Type: Issue (bug report, "Python API" template). Since it has fewer than 10,000 stars, I did not prepare a pull request, and there are no code changes in the clone.

### Background

`worker-prep-vision` splits broadcast video (29.97/59.94 fps) into shots using `ContentDetector(threshold, min_scene_len=round(min_sec * fps))`. If `prep_min_sec=1.0`, then `min_scene_len` is 30 (29.97 fps) or 60 (59.94 fps) frames.

Starting with version 0.7, cuts that fall “exactly `min_scene_len` frames after the previous cut” based on these values are discarded. The API default of 15 also falls under this category. This behavior was normal in version 0.6.7.

### Cause

`scenedetect/detector.py`’s `FlashFilter` (lines 179–181, 194–196).

- During the VFR support work in version 0.7 (#540), `FlashFilter` was changed to compare time (in seconds) instead of the number of frames.
- The integer frame duration is converted to seconds using `self._filter_length / float(frame_rate)`, then compared to the elapsed time `(timecode - self._last_above)` as a float.
- For NTSC-based systems, `float(frame_rate)` is not precise, so the quotient may be 1 ulp larger than the true value. At 30,000/1,001 fps, 15 frames have an elapsed time of `0.5005` and a reference value of `0.5005000000000001`, so `>=` evaluates to False.
- Based on the exact PTS (PyAV) standard, N = 3, 6, 12, 15, 24, 25, 30, 39, 48, 50, 59, and 60 always apply (Verified for N ≤ 60; 29.97 and 59.94 are identical).
- Since the OpenCV backend rounds positions to the nearest microsecond, if the frame duration is not an integer multiple of the frame rate (30, 23.976, 29.97, 59.94) where the frame rate is not an integer multiple of 3, the same issue occurs because the frame is 1 µs short depending on the starting position. Example: At 29.97 fps, OpenCV discards the clip 17 frames after `min_scene_len=17`, while PyAV retains it.
- `HistogramDetector`, `HashDetector`, `AdaptiveDetector`, and `ThresholdDetector` have no impact when comparing frame numbers with `FrameTimecode >= int`.

### Reproduction Method

This can be reproduced without video (`repro_min.py`). Create a stream at 30000/1001 fps that exactly matches the position returned by the PyAV backend, and insert a cut signal every 15 frames at `FlashFilter(length=15)`.

```text
gap.frame_num          : 15
gap.seconds            : 0.5005
15 / float(fps)        : 0.5005000000000001
gap >= 15 / float(fps) : False  <- what FlashFilter evaluates
gap >= 15              : True  <- what the other detectors evaluate
> MERGE    cuts every 15 frames - []
> SUPPRESS cuts every 15 frames - [30, 60, 90, 120, 150, 180, 210, 240, 270]
```

The expected values for both modes are 15, 30, 45, ..., 285, and version 0.6.7 of `FlashFilter` returns these values correctly.

I also verified this using actual files (`repro.py`). I used ffmpeg to create 150-frame clips with shot lengths of exactly 15 frames at five different frame rates and detected them using `min_scene_len=15`.

| Frame Rate | ContentDetector (HEAD) | HistogramDetector / AdaptiveDetector (HEAD) | ContentDetector (0.6.7) |

|---|---|---|---|

| 25, 30, 24000/1001 | 9 cuts | 9 cuts | 9 cuts |

| 30000/1001 | 0 cuts | 9 cuts | 9 cuts |

| 60,000/1001 | 0 frames | 9 frames | 9 frames |

The HEAD version yields the same results for both the OpenCV and PyAV backends. The 0.7 and 0.6.7 versions on PyPI were run only with the OpenCV backend, and version 0.7 produces the same results as the HEAD version. The HistogramDetector in version 0.6.7 does not output the first frame (15), resulting in 8 frames, but this is unrelated to the current issue.

### Verification

- The same script was run in three environments: HEAD `81c414c` (editable installation), PyPI `scenedetect==0.7`, and `scenedetect==0.6.7`. The original output is `repro.txt`.
- I generated a list of N values affected by frame rate and backend using `repro_timing.py`.
- Items not tested: the entire pytest suite in the repo (requires test video resources), `TransNetV2Detector` (though it likely behaves the same as `FlashFilter`, it was not executed).
- The proposed fix was summarized in a single paragraph in the main text (calculate integer length precisely using `Fraction` or compare by frame count; allow for sub-frame tolerance in OpenCV’s microsecond rounding). Since #540 intentionally changed the unit to time, the maintainer’s judgment is required.

### Duplicate Check

- #540 (merged): A PR that changed `FlashFilter` to a time unit. This issue concerns the float conversion problem introduced at that time.
- #408, #571 (merged), #557 (closed): An issue where `AdaptiveDetector` was checking `min_scene_len` based on the current frame. Different detector, different cause.
- #569 (Open): Issue where `frame_num` is an approximate value in VFR. This case involves CFR.
- #477 (Open): Question regarding the difference between the CLI default of 0.6s and the API default of 15 frames.
- #539 (Open): Issue in 0.6.7 where the last scene is 1 frame long.
- Search terms: min_scene_len, min-scene-len, FlashFilter, filter_secs, floating point, off-by-one, 29.97, NTSC, 30000/1001, time-based units, ContentDetector regression, missing cuts, fewer scenes 0.7

