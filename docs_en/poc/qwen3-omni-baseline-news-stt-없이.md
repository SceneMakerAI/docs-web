---
title: "Qwen3-Omni baseline — news (without STT)"
sidebar_position: 5
slug: "5"
---

> Baseline results from analyzing **100 clips from the news category** using Qwen3-Omni without STT (Speech-to-Text) context.

> To be used as a control group when STT context is added in the future.

### 1. Execution Environment

| Item | Value |
| --- | --- |
| Model | Qwen3-Omni-30B-A3B-Instruct |
| Serving | vLLM (OpenAI-compatible endpoint, single GPU) |
| Client | FastAPI server (`POST /analyze/by-clip-path`) |
| Concurrency | 4 (server-side `asyncio.Semaphore`) |
| STT Context | **None** — Dialogue section of the prompt removed (for baseline measurement) |
| Measurement Date | 2026-05-22 |

### 2. Data

- Category: `news` / Number of clips: **100**

- Each clip **6 seconds** → Total video duration 600 seconds (10 minutes)

- Clip naming: `0001_0600-0606` ~ `0100_1194-1200` (absolute second encoding of the original video)

### 3. Processing Results

| Result | Count |
| --- | --- |
| ok (HTTP 200) | **97** |
| fail (HTTP 500 Internal Server Error) | **3** |
| Total | 100 |

Fail is presumed to be a temporary error on the vLLM side. Usually resolved upon retry.

### 4. Time Statistics

Measured separately: pipeline wall-time, Qwen inference time, and network overhead.

| Measurement Item | n | Total (s) | Average (ms) | p50 (ms) | p95 (ms) | min / max (ms) |
| --- | --- | --- | --- | --- | --- | --- |
| **Pipeline wall** (entire batch client) | 100 | **191.13** | 1,911.3 | — | — | — |
| **Qwen inference** (server-side `meta.elapsed_ms`) | 97 | 690.20 | **7,115.5** | 7,171.0 | 7,985.4 | 5,268 / 9,058 |
| Client elapsed (HTTPX) | 100 | 761.73 | 7,617.3 | 7,188.5 | 8,811.2 | 5,279 / 24,139 |
| Network + Server Overhead (Client − Qwen) | 97 | 50.09 | 516.4 | 12.0 | 1,603.2 | -2,140 / 17,312 |

Meaning of each metric:

- **Pipeline wall**: Wall clock time from batch client start to end — "Total processing time" from an operational perspective

- **Qwen inference**: Time measured by the server route for the vLLM `chat.completions.create()` call alone — processing cost of the model itself

- **Client elapsed**: Elapsed time of the client’s HTTPX call — includes Qwen inference + network round-trip + server serialization + Semaphore wait

- **Network + Server Overhead**: Client elapsed − Qwen inference — Incidental costs such as communication, serialization, file reads, and prompt building

### 5. Token Usage

| Type | Total | Average/Clip |
| --- | --- | --- |
| prompt | 1,143,727 | 11,791 |
| completion | 14,843 | 153 |

Almost all prompt tokens are filled with a 6-second MP4 base64 encoding (video frames + audio). The text prompt itself is approximately 200 tokens long.

### 6. Processing Speed Compared to Real-Time

| Item | Value |
| --- | --- |
| Total Video | 600 seconds (10 minutes) |
| Processing Wall-Time | 191 seconds (3 minutes 11 seconds) |
| **Speed Relative to Real-Time** | **3.14×** real-time |

In a 4-concurrent-call environment, the theoretical limit is Qwen inference total (690s) ÷ 4 ≈ 172s. The measured result of 191s represents **approximately 91% efficiency** (queuing wait + network loss approx. 9%).

### 7. Analysis Quality (Qualitative Observation)

Even without STT context, Qwen3-Omni:

- Accurately reads OCR (Optical Character Recognition) text from on-screen subtitles and incorporates it into the description

- Consistently describes visual elements such as characters’ clothing, backgrounds, and scene transitions

- Extracts noun and verb keywords for `objects` and `actions` in a well-organized format without duplication

Even at the baseline level, its ability to recognize subtitles and logos is significantly higher. The key point to watch in the next measurement is where additional improvements appear when STT context is added.

### 8. Next Steps

- [ ] Measure the remaining 6 categories (`docu`, `baseball`, `entertain`, `drama`, `hist_drama`, `lol`) under the same conditions

- [ ] Retry failed cases + analyze causes (check vLLM logs)

- [ ] Re-measure the same 100 clips after adding STT context → Quantitatively compare quality improvements relative to the baseline

- [ ] Conduct parallel measurements with Gemini using the same input → Qualitatively and quantitatively compare models

### 9. Reproduction Instructions (Summary)

```bash
# FastAPI 서버 기동
./script/start.sh

# 배치 실행 (STT 컨텍스트 없음)
PYTHONPATH=src uv run script/run_batch.py news news --no-script --model qwen_no_script

# 사람 보기용 markdown 생성
PYTHONPATH=src uv run script/render_summary.py qwen_no_script news news
```

Outputs:

- `predictions/qwen_no_script/news/news/{clip_id}.json` — Envelope per request

- `predictions/qwen_no_script/news/news/_meta.json` — Raw time and token statistics

- `predictions/qwen_no_script/news/news/summary.md` — Summary for human review

