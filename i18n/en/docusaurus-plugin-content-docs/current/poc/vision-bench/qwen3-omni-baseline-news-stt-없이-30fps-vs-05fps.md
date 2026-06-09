---
title: "qwen3-omni-baseline-news-stt-off-30fps-vs-0.5fps"
sidebar_position: 2
slug: "2"
last_update:
  date: 2026-05-27
---

> Baseline analysis of **100 clips from the news category** using Qwen3-Omni without STT (Speech-to-Text) context.
Measured using two scenarios: **30 fps (original) vs. 0.5 fps (low-frame-rate converted version)** — comparing the impact of video frame rate on analysis performance.

---

####  1. Execution Environment

| Item | Value |
| --- | --- |
| Model | Qwen3-Omni-30B-A3B-Instruct |
| Serving | vLLM (OpenAI-compatible endpoint, single GPU) |
| Client | FastAPI server (`POST /analyze/by-clip-path` ) |
| Concurrency | 4 (server-side `asyncio.Semaphore` ) |
| STT Context | **None** — Dialogue sections from the prompt removed (for baseline measurement) |
| Measurement Date | 2026-05-22 |

#### 2. Data

- Category: `news` / Number of clips: **100** × 2 fps variants
- Each clip **6 seconds** → Total video duration 600 seconds (10 minutes)
- Clip naming: `0001_0600-0606` `0100_1194-1200` (absolute second encoding of the original video)

#### 2.1 Clip Specifications (by variant)

| Item | 30 fps (Original) | 0.5 fps (Low Frame Rate) |
| --- | --- | --- |
| Resolution | 1280×720 | 1280×720 |
| Frame rate | 30 fps | 0.5 fps (1 frame per 2 seconds) |
| Frames per clip | **180** | **3** |
| Codec | h264 | h264 |
| Duration | 6.037 seconds | 6.037 seconds |
| Size per clip | 1.2 MB | 492 KB |
| Bitrate | 1.6 Mbps | 0.67 Mbps |

#### 3. Processing Results

| variant | ok | fail | fail rate |
| --- | --- | --- | --- |
| 30fps | 97 | 3 | 3.0% |
| 0.5fps | **99** | **1** | 1.0% |

All failure cases resulted in an HTTP 500 Internal Server Error (temporary error on the vLLM side). This is usually resolved upon retry.

#### 4. Time Statistics

#### 4.1 30fps (Original)

| Measurement Item | n | Total (s) | Average (ms) | p50 (ms) | p95 (ms) | min / max (ms) |
| --- | --- | --- | --- | --- | --- | --- |
| Pipeline wall (entire batch) | 100 | 191.13 | 1,911.3 | — | — | — |
| **Qwen Inference** | 97 | 690.20 | **7,115.5** | 7,171.0 | 7,985.4 | 5,268 / 9,058 |
| Client elapsed (HTTPX) | 100 | 761.73 | 7,617.3 | 7,188.5 | 8,811.2 | 5,279 / 24,139 |
| Network + Server Overhead | 97 | 50.09 | 516.4 | 12.0 | 1,603.2 | -2,140 / 17,312 |

#### 4.2 0.5 fps (Low Frame Rate)

| Measurement Item | n | Total (s) | Average (ms) | p50 (ms) | p95 (ms) | min / max (ms) |
| --- | --- | --- | --- | --- | --- | --- |
| Pipeline wall (entire batch) | 100 | **78.10** | 781.0 | — | — | — |
| **Qwen Inference** | 99 | 294.01 | **2,969.8** | 2,910.0 | 3,470.1 | 2,429 / 3,767 |
| Client elapsed (HTTPX) | 100 | 309.57 | 3,095.7 | 2,917.0 | 3,551.1 | 2,431 / 15,023 |
| Network + Server Overhead | 99 | 12.86 | 129.8 | 2.0 | 451.9 | -693 / 12,142 |

#### 5. Token Usage

| variant | prompt total | prompt avg/clip | completion total | completion avg/clip |
| --- | --- | --- | --- | --- |
| 30fps | 1,143,727 | **11,791** | 14,843 | 153 |
| 0.5fps | 169,389 | **1,711** | 13,454 | 136 |

Most prompt tokens consist of MP4 Base64 encoding (video frames + audio). At 0.5fps, the video frame rate is reduced to 1/60, resulting in a **6.89× compression** of prompt tokens.

#### 6. Processing Speed Compared to Real-Time

| variant | Total video | wall-time | Real-time ratio |
| --- | --- | --- | --- |
| 30fps | 600 sec | 191 sec | **3.14×** |
| 0.5fps | 600 sec | 78 sec | **7.69×** |

#### 7. 30fps vs 0.5fps At-a-Glance Comparison

| Measurement | 30fps | 0.5fps | Difference |
| --- | --- | --- | --- |
| Pipeline wall | 191.13s | 78.10s | **2.45× faster** |
| Qwen inference avg | 7,115ms | 2,970ms | **2.40× faster** |
| Qwen p95 | 7,985ms | 3,470ms | 2.30× faster |
| Prompt tokens avg | 11,791 | 1,711 | **6.89× reduction** |
| Completion Tokens (avg) | 153 | 136 | -11% |
| Real-time Comparison | 3.14× | 7.69× | 2.45× improvement |
| ok/fail | 97/3 | 99/1 | Stability ↑ |

#### 8. Qualitative Comparison of Analysis Quality

Analysis results for the same clip (0050 — industrial statistics graphic scene) at two different frame rates:

**30fps** :

> This is a broadcast scene showing graphics displayed against an industrial site background, depicting raw materials such as steel and aluminum, as well as derivative products like automobile and aircraft parts. In the lower right corner, a sign language interpreter is performing sign language.

**0.5fps** :

> Graphics visualizing raw materials such as steel and aluminum, as well as derivative products like automobile and aircraft parts, are displayed against an industrial site background. A man waving his hand is visible in the lower right corner.

→ The key graphics and caption content are accurately depicted in both fps. **The difference lies in the dynamic element in the bottom right corner** — 30fps accurately depicts "a sign language interpreter performing sign language," while 0.5fps shows "a man waving his hand," **misinterpreting the meaning of the continuous motion**.

#### 8.1 Summary of Observations

| Category | 30fps | 0.5fps |
| --- | --- | --- |
| Graphics / Captions / Static Visual Elements | Accurate | Accurate (3 frames are sufficient) |
| Character clothing / background details | Accurate | Some details missing |
| Scene transition recognition | Accurate | Increased frequency of omissions |
| Continuous motion (sign language, etc.) | Accurate depiction | Simplified or misinterpreted (e.g., sign language → hand gesture) |
| Hallucinations (Generation of Non-Existent Elements) | Low | Slightly ↑ |
| `actions` Diversity | More Diverse on Average | Significantly Less |

#### 9. Conclusion

| Conclusion | Details |
| --- | --- |
| **Speed** | 0.5 fps is **2.40× faster and reduces prompt tokens by 6.89×** — Clear advantage in terms of cost and throughput |
| **Quality** | Equivalent for static elements such as subtitles, logos, and character positioning. However, **poor recognition of scene transitions and continuous motion**, with some hallucinations |
| **Recommended Use** | 0.5fps is sufficient for subtitles, OCR, and static scenes (e.g., subtitle recognition, static thumbnail generation). 30fps is recommended for motion, scene transitions, and detailed cut analysis |

#### 10. Next Steps

- Measure the remaining 6 categories under the same conditions (especially `baseball` and `lol`, which involve a lot of motion—the 0.5fps gap is expected to be even larger)
- Retest failed cases + analyze causes
- Re-measure the same 100 clips after adding STT context → Quantitatively compare quality improvements relative to the baseline
- Perform parallel measurements on Gemini with the same input → Compare models

#### 11. Reproduction Instructions

```bash
# FastAPI 서버 기동
./script/start.sh

# 30fps 측정 (baseline)
PYTHONPATH=src uv run script/run_batch.py news news --no-script --model qwen_no_script

# 0.5fps 측정
PYTHONPATH=src uv run script/run_batch.py news news_0.5fps --no-script --model qwen_no_script_0.5fps

# 사람 보기용 markdown
PYTHONPATH=src uv run script/render_summary.py qwen_no_script news news
PYTHONPATH=src uv run script/render_summary.py qwen_no_script_0.5fps news news_0.5fps
```

Deliverables:

- `predictions/{model}/news/{source}/{clip_id}.json` — Envelope per request
- `predictions/{model}/news/{source}/_meta.json` — Raw time and token statistics
- `predictions/{model}/news/{source}/summary.md` — Summary for human review

