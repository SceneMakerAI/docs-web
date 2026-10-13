---
title: "Fixed an issue where the inference progress hook reported a higher number of completions than the total"
sidebar_position: 21
slug: "21"
description: "pyannote-audio: Fixed an issue where the number of completions passed to the progress hook was greater than the total when the last batch was small"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

[https://github.com/pyannote/pyannote-audio/pull/2074](https://github.com/pyannote/pyannote-audio/pull/2074)

#### Purpose

Sliding inference (`Inference`) calls the progress hook as `completed=c + self.batch_size` each time a batch is processed. Even if the last batch is smaller than `batch_size`, since `batch_size` is added as-is, the hook receives a value indicating that “more than the total has been completed” unless the number of chunks is a multiple of `batch_size`. Subsequently, if the last chunk reports the correct value, the progress may even reverse.

These are the `(completed, total)` values received by the hook in the `develop` branch (`duration=1.0`, `step=0.5`).

| Audio Length | `batch_size` | Call Value |

| --- | --- | --- |

| 3.0 seconds | 32 | `(0, 5), (32, 5)` |

| 3.05 seconds | 32 | `(0, 6), (32, 6), (6, 6)` |

| 3.05 seconds | 4 | `(0, 6), (4, 6), (8, 6), (6, 6)` |

| 10.0 seconds | 4 | `(0, 19), (4, 19), …, (16, 19), (20, 19)` |

With the default value of `batch_size=32`, files shorter than 32 chunks are processed starting from the first batch. Since the progress of the `segmentation` stage in the speaker segmentation pipeline is tracked by this hook, hooks that calculate ratios or determine completion using `completed >= total` will receive incorrect values.

#### Changes

- `src/pyannote/audio/core/inference.py` — Restricted `completed` to `min(c + self.batch_size, num_chunks)` (the actual number of chunks processed)
- `tests/test_inference_hook.py` — Added a new test using a small dummy model to verify four scenarios. Checks that the progress bar does not exceed 100%, does not move backward, and starts at 0 and ends at 100%.
- `CHANGELOG.md` — Added one line to the `next` entry

#### Tests

```text
$ pytest tests/test_inference_hook.py     # Before modification: 4 failed
$ pytest tests/test_inference_hook.py     # After modification: 4 passed
```

These are tests run without a pre-trained model. The local environment is Python 3.12, torch 2.8.0 (CPU). The remaining tests that require a model could not be run locally.

#### Duplicate Check

I searched for open and closed issues and PRs using the progress hook, `completed`, and `total`, and found no duplicate issues. Open PRs (#2048, #1992) that touch `inference.py` do not change this line.

#### Results

Submitted to the `develop` branch on October 6, 2026. Awaiting review.

