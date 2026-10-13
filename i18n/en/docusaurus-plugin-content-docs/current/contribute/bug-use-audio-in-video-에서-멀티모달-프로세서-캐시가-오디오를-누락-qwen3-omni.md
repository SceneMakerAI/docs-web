---
title: "[Bug] The multimodal processor cache omits audio in `use_audio_in_video` (Qwen3-Omni)"
sidebar_position: 12
slug: "12"
description: "Qwen3-Omni: \"StopIteration\" / HTTP 400 due to a processor cache conflict in the \"use_audio_in_video\" request"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-07
---

[https://github.com/vllm-project/vllm/issues/44538](https://github.com/vllm-project/vllm/issues/44538)

Written by MinsungIM · Posted on June 4, 2026

#### Environment

```text
vLLM 0.21.0 · transformers 5.8.1 · torch 2.11.0+cu130 (CUDA 13.0)
Python 3.12.13 · Amazon Linux 2023
GPU: NVIDIA RTX PRO 6000 Blackwell Server Edition (96 GB)
Model: Qwen/Qwen3-Omni-30B-A3B-Instruct
```

#### Symptoms

When serving Qwen3-Omni via an OpenAI-compatible API, requests that send only video via ``use_audio_in_video=True`` (audio is automatically extracted from the video) fail with an **HTTP 400** error. This occurs only when the server has already cached the same audio track from a **different video** in a previous request.

The actual exception in the server logs is ``StopIteration`` from transformers.

```text
transformers/models/qwen3_omni_moe/processing_qwen3_omni_moe.py
  replace_multimodal_special_tokens:
      audio_token_indices = np.arange(next(audio_lengths))   # StopIteration
```

The HF processor receives `audio=None`. Since the audio decoding itself is normal, the audio is being excluded from the **multimodal processor cache**.

#### Conditions for Occurrence

Two requests with the same resolution, frame rate, and duration, and **audio tracks that are identical byte-for-byte** (verified via MD5), but with different video frames. The first request caches the processed audio paired with the first video, and when the second request pairs that cache with a different video, the audio disappears.

#### Minimum Reproduction

```bash
ffmpeg -y -f lavfi -i color=c=black:s=1920x1080:r=30:d=6 \
  -f lavfi -i sine=frequency=440:duration=6 -c:v libx264 -c:a aac -shortest A.mp4
ffmpeg -y -f lavfi -i testsrc=s=1920x1080:r=30:d=6 \
  -f lavfi -i sine=frequency=440:duration=6 -c:v libx264 -c:a aac -shortest B.mp4
```

Based on a newly launched server (default `mm-processor-cache-gb=4`):

| Step | Request | Result |
| --- | --- | --- |
| 1 | `A.mp4`, `use_audio_in_video=True` | 200 OK |
| 2 | `B.mp4` (different video, same audio) | 400 (StopIteration) |
| Test | Different audio (880 Hz) on `B.mp4` | 200 OK |

If caching is disabled via `--mm-processor-cache-gb 0`, step 2 also passes.

#### Proposed Fix

1. Ensure that the `use_audio_in_video` audio cache key reflects the corresponding video (or do not share it between different videos).
2. When there is no audio, `replace_multimodal_special_tokens` should raise a clear error instead of `StopIteration`.

#### Progress

Registered on June 4, 2026. It was marked as “stale” after 90 days with no response from the maintainer and was automatically closed on October 6, 2026 (not planned). Related issues in the same cache series include #33865, #43941, #42995.

On the same day the issue was raised, external developer abinggo submitted a PR [#44543](https://github.com/vllm-project/vllm/pull/44543) (Couple audio+video in mm processor cache, "fixes #44538"), and vLLM maintainer Isotr0py reviewed it. As of October 7, 2026, this PR is still open and has not been merged.

