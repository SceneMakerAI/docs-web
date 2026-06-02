---
title: "[Part 1] Benchmarking Multimodal LLMs&#x27; Understanding of 6-Second Clips from Korean Broadcasts — Building the Pipeline"
sidebar_position: 1
slug: "1"
---

<br />

<br />

**Project Overview:**

PoC for a multimodal LLM video understanding quality benchmark covering 7 Korean broadcast genres (news, documentaries, baseball, variety shows, dramas, historical dramas, and esports) × 100 clips × 6-second clips (700 clips total)

**Evaluation Environment:**

AWS g7e.4xlarge (96 GB VRAM) vLLM serving / Qwen3-Omni-30B-A3B-Instruct (OpenAI-compatible endpoint)

<br />

## 1. Project Overview

- **Objective:** To demonstrate, via a single multimodal LLM call, whether it is possible to consistently generate a structured JSON with four fields—`{summary, objects, actions, audio}`—that integrates visual and auditory information without hallucinations, using Korean broadcast clips (video + audio + dialogue script) segmented into 6-second intervals.

- **PoC Scope:** Limited to multimodal LLM invocation, enforced structured responses, and result evaluation. **Video segmentation (ffmpeg) is performed separately as a pre-processing step** (segmentation is pre-generated using an in-house ffmpeg script; the script was written manually).

- **Key Objectives:**
  1. Eliminate post-processing and refinement steps by enforcing JSON Schema (vLLM guided decoding + pydantic `extra="forbid"`)

  1. Quantitatively evaluate the strengths and weaknesses of SceneMaker by genre using a benchmark of 7 genres (News, Documentary, Variety, Drama, Historical Drama, Baseball, Esports) × 100 clips

- Expected Processing Workflow

```smalltalk
[Input of original broadcast video (10-minute window)]

───── Preliminary Preparation (Outside the scope of this PoC · Performed separately · Planned for future automation) ─────

(A) Video Segmentation  — In-house FFmpeg script (separate)
  Split the 00:10:00 to 00:20:00 segment of the original video into 100 clips, each 6 seconds long.
  File names encode the original absolute timestamp (e.g., 0001_0600-0606.mp4) to prevent conflicts even if the time window changes.
  ※ Planned for future integration into the main SceneMaker pipeline.

(B) Dialogue Scripts  — scripts.json, manually written
  Groups dialogue from the previous 6 seconds, current 6 seconds, and next 6 seconds into three segments to provide context to the model.
  Specifies in the prompt that the analysis is limited to the 'current' 6 seconds, while the preceding and following segments are for context.
  ※ Planned for automatic retrieval via integration with external subtitle and STT systems in the future.

───── Scope of This PoC Validation ─────

[6-second MP4 clip + dialogue scripts for before, during, and after]
⬇️
Step 1. Single-call multimodal analysis (Qwen3-Omni via vLLM)
Send the MP4 base64 data URI (video_url) and text prompt as an OpenAI-compatible `chat.completions`
in a single request. Audio is embedded within the MP4 and decoded simultaneously via the vLLM video pipeline.
⬇️
Step 2. Enforce JSON Schema Response (Guided Decoding)
Enforce the 4 fields {summary, objects, actions, audio} using vLLM response_format=json_schema(strict).
Block any additional fields with a pydantic ValidationError.
⬇️
Step 3. Save Results / Comparative Evaluation
Save to `predictions/{category}/{original_name}/{clip_id}.json`. Perform qualitative comparison by sampling by category.
```

<br />

## 2. Preliminary Research

#### **2.1. Analysis Model: Qwen3-Omni-30B-A3B-Instruct**

- **Conclusion:** Adopted `Qwen3-Omni-30B-A3B-Instruct` for integrated analysis of 6-second multimodal clips via a single API call.

- **Reason:** It is nearly the only open-source option capable of processing all four modalities (Image / Video / Audio / Text) with a single model and supporting OpenAI-compatible vLLM serving. **Thinker–Talker MoE** architecture. The inference core (Thinker) has a total of 30B parameters (3B active); the full checkpoint, including the Talker (speech), audio, and vision encoders, is approximately **35B** (this PoC uses only text output → Talker not used).

**Model Specifications**

| Item | Value |
| --- | --- |
| Architecture | Thinker–Talker MoE (native omnimodal end-to-end) |
| Parameters | Inference core (Thinker): 30B total / 3B active; total including Talker and encoders ≈ 35B |
| Input | Text · Image · Audio · Video |
| Output | Text (+speech) — This PoC uses text only (Talker not used) |
| Context | Native 32,768 tokens (16,384 used in production → see table below) |
| Multilingual Support | 119 languages for text / 19 for audio input / 10 for audio output → All supported in Korean |
| License | Apache 2.0 (Commercial use permitted) |

**VRAM / Production Settings (g7e.4xlarge · 1 GPU)**

| **Item** | **Value** | **Notes** |
| --- | --- | --- |
| GPU | NVIDIA RTX PRO 6000 Blackwell × 1 (96 GB) | Oregon us-west-2 |
| BF16 Memory (Official Card) | 15 sec 78.85 GB / 30 sec 88.52 / 60 sec 107.74 | 96 GB is sufficient for a 6-second clip |
| `--dtype` | bfloat16 | Original precision (not quantized, 66 GiB full checkpoint) |
| `--gpu-memory-utilization` | 0.85 (≈ 81.6 GB allocated) |  |
| `--tensor-parallel-size` | 1 | Single GPU |
| `--max-num-seqs` | 8 | Larger than app concurrency (4), so plenty of headroom |

**Serving Context Limits**

| **Item** | **Value** | **Impact** |
| --- | --- | --- |
| Production `--max-model-len` | **16,384** (half of native 32,768) | Context budget constraint |
| Observed `prompt_tokens` | ≈ 11,887 (approx. 73% used) | Already using a significant portion |
| Risk | Video tokens surge at high fps → Exceeds 16k limit | Caution required during 30fps experiments |
| Response | Increase `--max-model-len`(KV cache vs. VRAM trade-off) or impose fps constraints | — |

#### **2.2. Input Method:** `from_video` **(single MP4 input) vs** `from_frames_audio` **(separate inputs)**

- **Conclusion:** Adopt the `from_video` method, which passes a single 6-second MP4 file as a single `video_url` (base64 data URI) component. Separate input (`from_frames_audio`) is **on hold**.

- **Reason:** Since Qwen3-Omni natively supports the integrated understanding of video and audio via `use_audio_in_video`, the `from_video` method—which passes a single MP4 file as-is—is the model’s recommended input method and results in the simplest pipeline. Separate input was put on hold because it increases the number of components to four and introduces the risk of motion loss between keyframes and alignment issues.

| **Comparison** | `from_video` **(Adopted)** | `from_frames_audio` **(On hold)** |
| --- | --- | --- |
| **Input Configuration** | 1 MP4 file → 1 component (`video_url`, data URI) | 3 keyframe JPGs + 1 WAV file → 4 components |
| **Timing Alignment** | Video and audio automatically synchronized within the container | Requires separate client-side alignment |
| **Server-side dependencies** | Uses only the vLLM default video pipeline | Requires separate installation of `vllm[audio]` (`av` / `soundfile` / `librosa`) |
| **Preprocessing Output Size** | 6-second MP4 (~1–3 MB per clip) | 3 JPG frames + WAV (~hundreds of KB per clip) |
| **Hallucination Impact** | Natural preservation of video/audio alignment and context | Potential for missing motion between keyframes |
| **PoC Final Status** | **Main Pipeline Finalized** | Resuming after strengthening server dependencies (preserving `data/derived/`) |####

<br />

**2.3. Output Schema / Hallucination Guard**

- **Conclusion:** Responses are **strictly** fixed to the **4 fields**: `{summary, objects, actions, audio}`. Double enforcement via vLLM `response_format=json_schema(strict=True)` + pydantic `extra="forbid"`.

- **Reason:** Can be stored and consumed as-is without post-processing (parsing, cleaning, adding/removing fields) code. The analysis is limited to a 6-second 'current' clip, and while the preceding, current, and following dialogue are attached, the prompt explicitly states, "The preceding and following dialogue are for context only; do not incorporate them into the description." The two issues discovered during the `from_video` validation phase (summary copying vision text verbatim / prompt rule text mixed into the audio field) have been addressed in the field-specific guidelines.

| **Field** | **Definition and Guidelines** |
| --- | --- |
| `summary` (string) | Summarize visual and audio information into a single Korean sentence. Do not copy text from the `vision` or `audio` fields verbatim. |
| `objects` (array of string) | Noun keywords for objects, people, subtitles, logos, etc., appearing in the video (no duplicates; each entry must be within 3 words). |
| `actions` (array of string) | Verb phrases describing actions, movements, and scene transitions occurring in the video (no duplicates). |
| `audio` (array of strings) | Only clearly audible dialogue, sound effects, and background noise, independent of the visuals (each as a separate string element). Format: `(Dialogue)~` / `(Sound Effect)~` / `(Background Noise)~`. |

#### **2.4. Result Verification / Evaluation Criteria**

- **Conclusion:** The output is **verified in two stages**
  1. **Format Verification**: Mechanically enforce the 4-field structure using schema and PyDantic (→ 2.3, 100% automated)

  1. **Quality Evaluation**: Create a ground truth using a baseline model (Gemini), measure **alignment** using automated metrics per field, and have humans perform qualitative checks on a sample.

- **Reason:** Automatic scoring for absolute accuracy is impossible due to the lack of ground truth labels → We use the currently best **Gemini output as a reference** to quantify the alignment of Qwen’s output. We use **semantic-based matching** (embedding similarity) instead of exact string matching to treat synonyms (e.g., "anchor" ≈ "news anchor") as the same. However, the score is not an absolute correct answer but rather a **"match rate against Gemini"**, and **10–20 sample clips are manually reviewed** to calibrate the reliability of the Gemini labels.

**Quality Evaluation Metrics (Compared to Gemini Answer Key)**

| **Field** | **Metric** | **Measurement Method** | **What It Captures** |
| --- | --- | --- | --- |
| `objects` | Precision / Recall / **F1** | Set comparison after cosine matching of item embeddings ≥ threshold | Precision = Hallucinations/False positives, Recall = Omissions |
| `actions` | Precision / Recall / **F1** | Same as above | Ability to capture actions and scene transitions |
| `audio` | Precision / Recall / **F1** | Item embedding cosine matching (same as objects·actions) | Dialogue·sound effects·background noise detection·hallucinations |
| `summary` | **BERTScore** (P/R/F1) | Semantic similarity with Gemini summary | Content match·distortion·hallucinations |
| All Fields | Cosine Similarity (0–1) | Sentence Embedding Cosine | Overall Semantic Matching Score |

**Quantitative Metrics (Operational, Automatically Aggregated → Actual Values in Chapter 3)**

| **Metric** | **Description** |
| --- | --- |
| Success Rate | ok / fail (HTTP error rate) |
| Average Inference Time | Average Qwen Inference Time (ms) |
| Average Token Usage | Average prompts / completions per clip |

**⚠️ Note:** Scores represent **alignment with the baseline model (Gemini)**, not "correct answers." The possibility of errors in Gemini itself is corrected through human review of samples.

---

<br />

## 3. Testing

### 3.0. Testing Method

1. **Generate 6-second clips** (source data prepared in advance) — Cut a 10-minute segment of the original broadcast into 100 6-second clips.

1. **Run the analysis server** — Start the API server that receives the clips and handles analysis for the model.

1. **Batch request clips** — Send the prepared clips one by one to the server to request analysis. At this time, include the dialogue from the clip as well as the preceding, current, and following context.

1. **Model Analysis** — The model (Qwen3-Omni) processes the 6-second video, audio, and dialogue all at once and generates a JSON object with four fields: `{summary, objects, actions, audio}`.

1. **Save Results** — Save the analysis results for each clip and processing statistics (elapsed time, number of tokens) to a file.

1. **Summary and Evaluation** — Organize the saved results into a human-readable table and evaluate quality based on the 2.4 standard.

<br />

### 3.1. Test Data

The original data used for testing is as follows. Videos ranging from 50 minutes to 2 hours that closely resemble actual broadcast footage.

| **Broadcast** | **Duration** | **URL** |
| --- | --- | --- |
| KBS 9 News | 48:30 | [https://www.youtube.com/watch?v=rX1P-jOoNmM](https://www.youtube.com/watch?v=rX1P-jOoNmM) |
| Superfish Part 1 | 58:40 | [https://www.youtube.com/watch?v=iNbWqC1iqKw](https://www.youtube.com/watch?v=iNbWqC1iqKw) |
| KBS Winter Sonata | 1:04:52 | [https://www.youtube.com/watch?v=irVKEhb9g8M](https://www.youtube.com/watch?v=irVKEhb9g8M) |
| Taejo Wang Geon | 54:10 | [https://www.youtube.com/watch?v=nmlE2iPWLGM](https://www.youtube.com/watch?v=nmlE2iPWLGM) |
| Chuljang Sipo-ya X Starship National Sports Festival Full Version | 1:00:06 | [https://www.youtube.com/watch?v=6wJGpi1nkCg](https://www.youtube.com/watch?v=6wJGpi1nkCg) |
| 2009 KBO League Korean Series Game 7 | 1:55:22 | [https://www.youtube.com/watch?v=fP1QEs1Uj5U](https://www.youtube.com/watch?v=fP1QEs1Uj5U) |
| **2024 LCK Summer Finals: GEN vs HLE** | 2:11:23 | [https://www.youtube.com/watch?v=_A_I75nJMF8](https://www.youtube.com/watch?v=_A_I75nJMF8) |

**Download Original (Reproduction Procedure)**

Download the original files from the table above using the procedure below and store them in `data/raw/{category}/` (for internal reproduction).

- **Prerequisites**: `uv` (→ `uvx`) and `ffmpeg` installed (ffmpeg is required for merging video and audio streams)

- **① Download Original** — Download each URL from the table into the corresponding category folder

```bash
uvx yt-dlp -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b" \
--merge-output-format mp4 \
-o "data/raw/&lt;영상 카테고리&gt;/%(title)s.%(ext)s" "&lt;테스트 대상 URL&gt;"
```

- `-f "bv*[ext=mp4]+ba[ext=m4a]/…"` : **Prioritize H.264+AAC MP4** (compatible with vLLM/FFmpeg decoding). If this format is not available, fallback to highest quality (`/b`)

- `--merge-output-format mp4` : Merge into an MP4 container

- **② Split into 6-second clips** (Preparation) — Split the `00:10:00~00:20:00` (original absolute time 600–1200s) range into 100 clips of 6 seconds each. File names include the original absolute time → `data/clips/{category}/{original_name}/{seq}_{start}-{end}.mp4`

```bash
CAT=&lt;카테고리&gt;; NAME=&lt;원본명&gt;
SRC="data/raw/$CAT/$NAME.mp4"
OUT="data/clips/$CAT/$NAME"; mkdir -p "$OUT"
for i in $(seq 0 99); do
  start=$((600 + i*6)); end=$((start + 6))  # 절대초 600,606,…,1194
  name=$(printf "%04d_%04d-%04d" $((i+1)) "$start" "$end")  # 0001_0600-0606
  ffmpeg -nostdin -ss "$start" -i "$SRC" -t 6 -c:v libopenh264 -b:v 1500k -c:a aac -movflags +faststart "$OUT/$name.mp4"
done
```

- **Encoder**: `libopenh264`. If using `libx264`, use `-c:v libx264 -crf 20` for identical results

- **Split for Re-encoding** — Independent keyframes for each clip → Accurate boundaries and standalone decoding possible (original remains unchanged; only clips are generated)

- **Include audio** (`-c:a aac`) — Required

<br />

because vLLM must decode the audio within the MP4 file**Final Test Clip Data**

| **Category Key** | **Genre** | **Number of Clips** | **Resolution** | **fps** | **Average Size** | **Remarks** |
| --- | --- | --- | --- | --- | --- | --- |
| `news` | News | 100 | 1280×720 | 30 | 1.12 MB | High proportion of subtitles and anchor commentary |
| `docu` | Documentary | 100 | 1280×720 | 30 | 1.18 MB | Narration + mix of nature and ambient sounds |
| `baseball` | Baseball Broadcast | 100 | 640×360 | 29.97 | 1.13 MB | Commentator + crowd cheers + scoreboard UI |
| `entertain` | Variety | 100 | 1280×720 | 29.97 | 1.14 MB | Group conversation + subtitle effects |
| `drama` | Modern Drama | 100 | 720×480 | 29.97 | 1.08 MB | Character Dialogue + BGM |
| `hist_drama` | Historical Drama | 100 | 1280×720 | 29.97 | 1.16 MB | Period Costumes & Props + Formal Dialogue |
| `esports` | Esports | 100 | 1280×720 | **60** | 1.16 MB | Game UI overlay + Caster + Game audio |
| **Total** | — | **700** | — | — | ≈ 1.14 MB | 7 original videos (1 per genre, 10-minute window divided into 100 segments) |

> 🔒 **Data Handling Policy**
>
> - Videos are used **solely for internal quality assessment (PoC) purposes** and will not be distributed or republished externally.
>
> - Videos (data/) and analysis results (predictions/) **must not be included in the code repository (gitignore, no public commits)**.
>
> - Inference inputs are **encoded in memory using base64 and transmitted once**; no processed copies are stored separately.
>
> - After evaluation concludes, local videos and outputs are **disposed of** in accordance with retention policies.

<br />

### 3.2. Analysis Server (vLLM Frontend API Gateway)

A lightweight server that receives analysis requests and relays them to vLLM. The entry point is `src/app.py` (`PYTHONPATH=src uv run uvicorn app:app --port 8001`). Interactive API documentation is provided via `/docs` (Swagger), `/redoc`, and `/openapi.json`.

#### 3.2.1. Design

- **Conclusion:** The `vision-bench` server is a **thin gateway** (FastAPI) sitting in front of the vLLM’s `/v1/chat/completions` endpoint. The vLLM handles all inference, while the server passes the request body through without modification, adding **only three things**.
  1. Semaphore concurrency gate, 

  1. Batch NDJSON streaming, 

  1. request_id logging (`X-Request-Id` header). Prompt assembly, base64 encoding, `response_format` schema enforcement, and response validation are **all the client’s responsibility**.

- **Reason:** By configuring the gateway as a pass-through, experimental variations (prompt, schema, fps, sampling) can be swapped out and A/B tested **only on the client**, while the server remains untouched once deployed. The server is responsible only for vLLM protection (concurrency cap) and multi-request efficiency(fan-out streaming). Upstream calls use raw `httpx` instead of the OpenAI SDK — this prevents the SDK from subtly modifying the payload and breaking the "pass-through" mechanism.

| **Method** | **Path** | **Role** | **Notes** |
| --- | --- | --- | --- |
| GET | `/healthz` | Health check | Always returns 200 after the lifespan expires. **Does not check if the upstream vLLM was reached** |
| POST | `/chat` | Single-item pass-through | vLLM body as-is → vLLM response as-is (no envelope). Returns **502** if the upstream cannot be reached |
| POST | `/chat/batch` | Multi-item NDJSON streaming | `{items:[{id, body}]}` → Streamed line by line in **completion order** |

#### 3.2.2. Concurrency · Backpressure

- vLLM upstream calls are gated by `asyncio.Semaphore(VLLM_CONCURRENCY)` (default 4). Excess requests are **not rejected but queued**. `/chat` and `/chat/batch` **share the same Semaphore** → The total number of active tasks across both routes is maintained below the limit.

- The semaphore is created once during the FastAPI lifecycle and injected into `app.state` (no runtime changes).

- `VLLMClient.chat()` acquires the semaphore **first**, then measures the time using `time.monotonic()` → The returned `elapsed_ms` represents **the round-trip time of the vLLM call (network + inference) excluding queue wait time** (not just GPU inference). The denominator of the throughput metric is not contaminated by queue wait time.

**Server Configuration (** `.env` **→** `Settings` **)**

| **Key** | **Default** | **Role** |
| --- | --- | --- |
| `VLLM_BASE_URL` | — | vLLM `/v1` endpoint |
| `VLLM_CONCURRENCY` | 4 | Maximum concurrent calls (Semaphore). Recommended 1–8 |
| `MAX_BATCH_ITEMS` | 128 | Maximum items per request for `/chat/batch` |
| `VLLM_TIMEOUT_SECONDS` | 600 | Upstream call timeout |
| `VLLM_ACQUIRE_TIMEOUT_SECONDS` | 300 | Maximum wait time for acquiring a semaphore permit(seconds). If exceeded, only that request is marked as failed → Backstop against deadlocks caused by permit leaks or half-open connections (client disconnects before receiving FIN) |

#### 3.2.3. Batch NDJSON Streaming

- `/chat/batch` receives multiple items, performs fan-out (`asyncio.create_task`), and then streams them line by line in **completion order** (`asyncio.wait(..., return_when=FIRST_COMPLETED)` ) to stream one line at a time (`application/x-ndjson`, chunked). Since this is not input order, matching is done via `id`, and even if one or two items fail, the rest continue (determined by each line’s `status`).

- **Backpressure and Deadlock Hardening:** The streaming loop checks client survival every 0.5 seconds using `request.is_disconnected()`. If the client disconnects (upon receiving a FIN), it cancels all in-flight tasks and immediately releases the semaphore permit. In cases where disconnections cannot be detected—such as with half-open(no FIN received), the **permit acquisition timeout** for `client.chat()` (`VLLM_ACQUIRE_TIMEOUT_SECONDS`, default 300s) is reached, and only that request is marked as failed → This prevents deadlocks where a disconnected thread permanently holds the permit, causing the gateway to freeze.

Request body:

```json
{"items": [
  {"id": "0001_0600-0606", "body": {&lt;vLLM chat.completions body — /chat 와 동일&gt;}},
  {"id": "0002_0606-0612", "body": {<...>}}
]}
```

Response (1 line = 1 JSON object, separated by line breaks):

```json
{"id": "0001_0600-0606", "status": 200, "elapsed_ms": 3104, "body": {&lt;vLLM 응답&gt;}}
{"id": "0002_0606-0612", "status": 500, "elapsed_ms": 0, "error": "&lt;메시지&gt;"}
```

| **Field** | **Meaning** |
| --- | --- |
| `id` | Identifier sent by the client (usually clip_id). This differs in meaning from the `body.id` (`chatcmpl-…`) issued by vLLM |
| `status` | 200=Success / vLLM 4xx·5xx as-is / 500=Server-side exception (network disconnection, etc.) |
| `elapsed_ms` | Time from semaphore acquisition to vLLM response completion (excluding queue wait). 0 in case of exception |
| `body` / `error` | vLLM response body on success / error message on failure |

- **Constraint:** `len(items) ≤ MAX_BATCH_ITEMS` (default 128). If exceeded, immediately returns **413** (NDJSON not started, single JSON error). Includes `X-Batch-Total` (number of received items) in the response header.

#### 3.2.4. Client Responsibility + Call Parameters

Since the API server acts as a pass-through, the **client must assemble** the entire request body (messages, schema, and inference parameters).

| **Item** | **Content** |
| --- | --- |
| Video Encoding | mp4 → base64 data URI → `messages[0].content[0].video_url.url` |
| Prompt Assembly | Text prompt (Korean/English, script usage, A/B variant, etc.) |
| Output Schema Enforcement | `AnalysisResult.model_json_schema()` (strict) in `response_format.json_schema` |
| vLLM Extension Keys | `mm_processor_kwargs` (fps, use_audio_in_video), `chat_template_kwargs` (`enable_thinking: false` — disable thinking tokens) — Body **top-level** |
| Response validation | Enforces 4 fields (`summary/objects/actions/audio`) via `AnalysisResult.model_validate(...)` |

**Call parameters (framework)** — Inference parameters are specified directly in the client’s request body, not in server settings.

| **Parameter** | **Role** | **Value range** |
| --- | --- | --- |
| `temperature` | Sampling temperature; lower values are more deterministic, higher values are more diverse and creative | `[0, 2]` · 0=greedy (argmax) |
| `top_p` | Nucleus cutoff; only tokens in the top k cumulative probability are candidates | `[0, 1]` · Only when `temp>0` (inert if temp=0) |
| `top_k` | Limits candidates to the top k by probability | `-1` = inactive / `≥1` (1=argmax) · Only when `temp>0` |
| `max_tokens` | Upper limit on completion tokens (output length) | `>0` · Within remaining context |
| `frequency_penalty` | Additive repetition penalty, proportional to the number of occurrences in the generated text | `[-2, 2]` · Positive = Suppress / 0 = Inactive |
| `repetition_penalty` | Multiplicative repetition penalty (vLLM/HF extension) | `>0` · `<1` = encouraged / `1` = disabled / `>1` = suppressed (`0` is vLLM 400) |
| `seed` | Reproducibility; same input → same output when fixed | Integer · `<0` = disabled(randomized each time) |
| `mm_processor_kwargs.fps` | Video frame sampling rate (↑ tokens·details↑) | `>0` (e.g., 0.5–2.0) · Note: High fps may exceed 16k context |
| `mm_processor_kwargs.use_audio_in_video` | Enable/disable simultaneous audio decoding from MP4 | `true` / `false` (bool) |
| `chat_template_kwargs.enable_thinking` | Enable/disable "thinking" token generation — This PoC uses "off" | `true` / `false` (bool, default false) |

> 📌 `frequency_penalty` **vs** `repetition_penalty` - Both suppress repetition, but their methods differ.
>
> - **frequency** (additive/subtractive)
>   - The **more** a token has already appeared, the **more** it is penalized (proportional to frequency/cumulative) → Strong resistance to runaway loops(`ball ball ball…`) Strong at preventing runaway loops. Counts **only output tokens**. Inactive `0`, range `[-2, 2]`.
>
> - **repetition** (multiplication/division)
>   - Reduces by a **fixed ratio** if it appears even once (based on presence only, regardless of frequency). Since vLLM considers both **prompt + output**, even prompt vocabulary can be suppressed (potential for recall loss ↑). Inactive `1.0`, range `>0` (`>1` = suppression, `0` is vLLM 400).
>
> - Example: After 'ball' appears 3 times, the next logit is 5.0 → frequency 0.5 = 5.0 − 0.5×3 = **3.5**, repetition 1.2 = 5.0 ÷ 1.2 ≈ **4.17**.
>
> - ⚠️ Enabling both results in **double suppression (overkill)**

- **⚠️ Final values, rationale, and operational issues are covered in 3.3:** The final adopted values for the above parameters, the rationale for their selection, and issues discovered during operation (output degeneration, retry strategy, vLLM multimodal cache) are discussed along with numerical data in the **Results section (3.3)**. This section describes only the framework of "who determines which knobs."

### 3.3. Inference Parameter Tuning (Step 1: Form and Iterative Screening)

- **Procedure:** First, set the inference parameters (in this section) → then run the baseline with those settings and compare it to the Gemini ground truth (**3.4**, to determine optimal values). Experiment directory: `experiments/01_param_sweep`.

- **Motivation:** Intermittent abnormal patterns in the output—**repetition** of the same words, **fragmentation** of sentences, and **spam of heterogeneous characters**—occur. We investigate whether these can be controlled via inference parameters by significantly adjusting each knob one at a time (OFAT, one-factor-at-a-time) to determine how each knob alters the output.

#### 3.3.1. Methodology — What to Define in Phase 1

- **Conclusion:** Using 7 genres × 10 equally spaced clips = **70 fixed samples**, we will run **18 configurations** by drastically changing one parameter at a time (OFAT) and aggregate the **form and repetition** of the output. All configurations use the same 70 samples and the same prompt.

- **Key Distinction — Phase 1 addresses only what can be measured without a reference answer key:**

| **Category** | **Evaluation Target** | **Reference Answer Key** | **Where** |
| --- | --- | --- | --- |
| **Adherence** | Is it in Korean? · Is the JSON format correct? · Are the items short? · Are there no repetitions? (All *rules specified in the prompt*) | Not required | **This section (3.3)** |
| **Quality** | Completeness (no omissions) · Accuracy (no hallucinations) | **Required** | **3.4 (Gemini Objective Function)** |

- **Reason:** Adherence is based on rules explicitly stated in the prompt, so it can be judged solely by examining the output. Quality requires a "correct answer" for scoring, so a Gemini answer key is necessary (→ 2.4, 3.4). Conformity is a necessary but not sufficient condition, so the boundary is clearly defined.

- **Degeneration frequency is for reference only:** Output collapse is a rare event, so a single pass with n=70 yields low confidence in the *frequency* (+ batch concurrency jitter is mixed into the parameter effects). Therefore, we base our conclusions at this stage solely on **patterns and repetitions** present in all outputs, and reserve precise frequency measurement for a separate track.

**Variable / Fixed Factors**

| **Category** | **Item** |
| --- | --- |
| Variable (OFAT) | temperature · top_k · top_p · frequency_penalty · repetition_penalty · fps |
| Fixed | max_tokens=512 · use_audio_in_video=on · enable_thinking=false · same 70 samples · same prompt |

- OFAT (One-Factor-At-A-Time): A method of observing the effect of a single variable
while keeping all others fixed

#### 3.3.2. Quality Degradation Patterns — 3 Failure Patterns

- **Conclusion:** Observed output anomalies can be classified into three types, and **all three can be detected without a ground truth** (and thus can be addressed in Stage 1).

| **Pattern** | **Actual Output Example (70 samples from this benchmark)** | **Detection** |
| --- | --- | --- |
| **Repetition** | `audio: ["(Dialogue)Ah","(Dialogue)Ah","(Dialogue)Ah"]` / `actions: ["Armed"×9]` | Normalization duplication·token loop |
| **Fragmentation** | A single narration is broken into 3 fragments: `(Dialogue) Narration: In conclusion` / `…Ulsan District Prosecutors’ Office` / `…Uijeongbu District Prosecutors’ Office` | (Qualitative) |
| **degeneration** | `시гля … Arial TTF … Ginseng` — mixed character types · incomplete JSON | mixed character blocks · incomplete JSON · finish=length |

#### 3.3.3. Effects by Parameter

`obj/act/aud` = average number of items, `purity` = Korean / (Korean+Latin), `repeat` = item duplication · number of token records.

**temperature** (top_p=1·top_k=-1·neutral penalty) — The lower the value, the cleaner the result

| **temp** | **ok** | **comp_p50** | **obj/act/aud** | **purity** | **repeat** |
| --- | --- | --- | --- | --- | --- |
| 0.0 | 69 | 190 | 7.5/4.6/4.7 | 0.968 | 18 |
| 0.3 | 69 | 191 | 7.5/4.6/4.8 | 0.979 | 18 |
| 0.7 | 67 | 192 | 7.8/5.0/4.7 | 0.977 | 17 *(Maximum repeat intensity: 63 remaining)* |
| **1.0** | 66 | 235 | 8.9/7.4/4.6 | **0.788** | 16 *(15 instances of mixed characters)* |

- **Patterns of quality degradation based on temperature values**
  - 0.7 = Severe repetition (`무장` repeated 9 times)

  - 1.0 = Heterogeneous character word-salad (purity 0.97→0.79). 0.0–0.3 yields the cleanest results.

**frequency_penalty / repetition_penalty** (greedy) — A lever for repetition; single items are also penalized

| **Settings** | **obj/act/aud** | **repeat** | **Remarks** |
| --- | --- | --- | --- |
| No penalty (baseline) | 7.5/4.6/4.7 | 18 | — |
| freq 0.5 | 6.2/2.8/2.8 | 6 | Restores fragmented narration to a single sentence |
| freq 1.0 | 5.4/2.3/2.4 | 4 | Actual items (sea, camera) also start to be omitted |
| freq 2.0 | 4.6/2.1/**1.6** | 1 | Audio drops sharply |
| rep 1.1 | 6.3/3.8/3.6 | 6 | Similar behavior to freq |
| rep 1.3 | 4.7/3.3/**1.3** | 1 | Audio drops sharply |

- **top_k / top_p** (temp=0.7): Narrowing down candidates *slightly* reduces repetitions (17→14, 19→15). Not decisive.

- **fps** (0.5/1.0/2.0): **Unrelated** to repetitions (16–21). Since this is a dimension of visual detail and token count, it is viewed from the perspective of accuracy (3.4), not adaptability.

#### 3.3.4. Key Findings

1. **Duplication is common — ~26% (18/70)** of items are duplicates in the default settings. Mainly in the `audio` **field** (repeated background sounds and short interjections like `ah` / `right`) and `actions`. Adjusting temp/top_k/top_p/fps has almost no effect (flat response).

1. **The pattern of quality degradation varies depending on the temperature value** (3.3.3): 0.7 = severe repetition, 1.0 = occurrence of heterophones.

1. **The frequency/repetition penalty is key to improving repetition** (in contrast to temp/top_k). Simply changing freq from 0 to 0.5 reduced repetitions from 18 to 6 + 0 failures, *actual improvement*
   - **Restored three fragmented narration segments into a single complete sentence**.

1. **However, the penalty’s ***magnitude*** **will be fine-tuned later.** Increasing the penalty value reduces the number of items, but **without a ground truth, it is impossible to distinguish whether this reduction is “removing redundancy (good)” or “deleting actual information (bad)”** . In one case (news clip), the penalty resulted in a *reduction in count by merging fragments*, so the direction is opposite. Without a recall signal, the optimal size cannot be determined → **Planned to use the Gemini model in Section 3.4 for labeling as the objective function**.

1. **Obvious exact duplicates are resolved via dedup (no penalty required).** By definition, normalized deduplication results in zero information loss → iterations 18→**4** (remaining issues are fragmentation and token loops); the number of unique items remains nearly constant at 7.5→7.4. 

#### 3.3.5. Phase 1 Conclusion — Preliminary Parameter Determination

After applying dedup, the parameter leverage was calculated based on **remaining compliance violations** (e.g., mixed characters, degeneration, token loops, etc., which cannot be deduped) (`clean%` = ratio of records with 0 violations).

| **Priority** | **Parameter** | **leverage (clean%)** | **Direction** | **Phase 1 Finalized?** |
| --- | --- | --- | --- | --- |
| 1 | **temperature** | 94 → **69%** (High) | **Low 0–0.3**, ≥0.7 prohibited | ✅ Confirmed: Low temperature |
| 2 | **freq / rep (choose one)** | 94 → 99% (Medium) | Slight residual repetition ↓ | ⚠️ Direction only — magnitude 3.4 |
| 3 | top_k / top_p | 89–94% (Small) | Negligible | Low priority |
| 3 | fps | 90–94% (Irrelevant to compliance) | Content detail axis | → 3.4 (Accuracy) |

**Preliminary input parameters** determined by the above analysis (reflected in the default values of the quality objective function baseline · `02_baseline_no_script/run.py`):

| **Parameter** | **Value** | **Rationale** | **Finalization** |
| --- | --- | --- | --- |
| `temperature` | **0.0** | Low temperature for highest purity + greedy = deterministic (reproducibility) | ✅ Final |
| `top_p` / `top_k` | 1.0 / -1 | Since temp=0, inert → neutral value | (Irrelevant) |
| `frequency_penalty` | **0.0** | Duplicates are handled by dedup → Recall is not pre-reduced by penalty | ⚠️ Tentative |
| `repetition_penalty` | 1.0 (off) | Avoid double suppression with freq | ⚠️ Tentative |
| `max_tokens` | 512 | BLAST radius cap(Normal output max approx. 335) | ✅ Final |
| `fps` | 0.5 | Token-efficient (Accuracy-fps to be re-evaluated in quality assessment) | ⚠️ Tentative |
| **dedup (post-processing)** | **ON** | Normalized exact-duplicate removal, 0 information loss (`build_record`) | ✅ Final |

- **Reason for starting the penalty at 0:** If freq is 0.5, recall drops significantly (actions 4.6→2.8). Without a ground truth, it is impossible to distinguish whether this is redundant removal (good) or actual information deletion (bad) → Do not discard information prematurely before measurement. Since duplicates are already handled by dedup, there is no additional burden from the penalty. The possibility that a small penalty may ultimately be beneficial is a hypothesis, and the quality objective function (F1) will determine this.

**Tasks for detailed tuning (3.4):** Perform a 1D sweep of a single penalty (freq 0–0.7 or rep 1.0–1.2) against the Gemini F1 objective function to determine the optimal value. Review FPS separately from an accuracy perspective.

Keep `max_tokens` at 512 as the blast-radius cap.

> 🎯 **Confidence Labels (Post Integrity)**
>
> - **Determined in Phase 1 (no answer key required)**
>   1. Obvious exact duplicates → dedup
>
>   1. Low temperature (0–0.3; ≥0.7 prohibited)
>
>   1. Parameter tuning: leverage ranking and direction. Highly effective; temp=0 is deterministic and robust.
>
> - **To be covered in Section 3.4 (requires answer key labels from a higher-level model)**
>   - Optimal penalty *magnitude* · fps · overall quality (completeness·accuracy). Since recall cannot be used as a proxy for count/compliance, no conclusion can be drawn in Phase 1 — a Gemini objective function is required.

---## 4. References

**Model — Qwen3-Omni**

- [Qwen3-Omni-30B-A3B-Instruct — Hugging Face Model Card](https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Instruct) — Modalities, context, BF16 VRAM table, license, Korean support

- [Qwen3-Omni Technical Report (arXiv:2509.17765)](https://arxiv.org/abs/2509.17765) — Thinker–Talker MoE architecture, SOTA on 32 out of 36 audio and AV tasks

- [QwenLM/Qwen3-Omni — GitHub](https://github.com/QwenLM/Qwen3-Omni) — Usage, `use_audio_in_video` for video and audio integration

**Hardware — AWS g7e**

- [Amazon EC2 G7e Instance (Product Page)](https://aws.amazon.com/ec2/instance-types/g7e/) — RTX PRO 6000 Blackwell, 96GB per GPU

- [G7e Launch Announcement (AWS News Blog)](https://aws.amazon.com/blogs/aws/announcing-amazon-ec2-g7e-instances-accelerated-by-nvidia-rtx-pro-6000-blackwell-server-edition-gpus/) — General Availability (GA) in January 2026

- [g7e.4xlarge Specs — Vantage](https://instances.vantage.sh/aws/ec2/g7e.4xlarge) — 1 GPU / 96 GiB / 16 vCPU / 128 GiB

**Serving — vLLM**

- [Qwen3-Omni vLLM Serving Guide](https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/examples/online_serving/qwen3_omni/) — `vllm serve` options (such as `--max-model-len`)

