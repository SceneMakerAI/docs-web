---
title: "[Part 1] Benchmark for Multimodal LLM Understanding of 6-Second Clips from Korean Broadcasts — Pipeline Development"
sidebar_position: 1
slug: "1"
last_update:
  date: 2026-06-09
---


**Testing Environment:**

AWS g7e.4xlarge (96 GB VRAM) vLLM serving / Qwen3-Omni-30B-A3B-Instruct (Qwen multimodal model)

## 1. Project Overview

- Video Analysis Pipeline
  - **Client →** `poc-vision-bench` **(API Server) → vLLM (Qwen3-Omni)**

  - Verify **whether the above flow operates normally**.
    - Analysis quality, parameter tuning, and quantitative evaluation will be addressed later

- **Verification Flow:**

```mermaid
graph LR
    A["클라이언트<br/>(클립·프롬프트 조립)"] -->|POST| B["poc-vision-bench<br/>(API 게이트웨이)<br/>(passthrough·동시성·배치)"] -->|중계| C["vLLM<br/>(Qwen3-Omni)<br/>(멀티모달 추론)"]
```

- **What is verified in this section — 3 types of APIs:**
  1. **Status Query** — `/healthz`

  1. **Single Call** — `/chat` (Verification of text inference, video inference, and audio analysis during screen blackout)

  1. **Batch Processing** — `/chat/batch`

## 2. Preliminary Investigation

#### **2.1. Analysis Model: Qwen3-Omni-30B-A3B-Instruct**

- Adopted `Qwen3-Omni-30B-A3B-Instruct` for integrated analysis of a 6-second multimodal clip via a single call.
- The nearly only open-source option capable of processing 4 modalities (Image / Video / Audio / Text) with a single model and supporting OpenAI-compatible vLLM serving. **Thinker–Talker MoE** architecture. The inference core (Thinker) has a total of 30B / active 3B, while the total checkpoint, including the Talker (speech), audio, and vision encoders, is ≈ **35B** (this PoC uses only text output → Talker not used).

**Model Specs**

| Item | Value |
| --- | --- |
| Architecture | Thinker–Talker MoE (native omnimodal end-to-end) |
| Parameters | Inference core (Thinker): 30B total / 3B active · Total including Talker and encoders ≈ 35B |
| Input | Text · Image · Audio · Video |
| Output | Text (+Voice) — This PoC uses text only (Talker not used) |
| Context | Native 32,768 tokens (16,384 used in actual service) |
| Multilingual Support | 119 languages for text / 19 for voice input / 10 for voice output → Full support for Korean |
| License | Apache 2.0 (Commercial use permitted) |

**VRAM / Production Settings (g7e.4xlarge · 1 GPU)**

| **Item** | **Value** | **Notes** |
| --- | --- | --- |
| GPU | NVIDIA RTX PRO 6000 Blackwell × 1 (96 GB) | Oregon us-west-2 |
| BF16 Memory(Official Card) | 15 sec 78.85 GB / 30 sec 88.52 / 60 sec 107.74 | 96 GB is sufficient for a 6-second clip |
| `--dtype` | bfloat16 | Original precision(not quantized, 66 GiB full checkpoint) |
| `--gpu-memory-utilization` | 0.85 (≈ 81.6 GB allocated) |  |
| `--tensor-parallel-size` | 1 | Single GPU |
| `--max-num-seqs` | 8 | More than app concurrency (4), so plenty of headroom |

**Description of each item**

- **GPU - RTX PRO 6000 Blackwell × 1 (96 GB):** Blackwell-generation server GPU. Running a 30B model at full precision (BF16) on a single card—including the KV cache and multimodal encoder—requires significant VRAM, which the 96 GB capacity handles.
- **BF16 Memory (Official Card):** VRAM requirements *by input video length* as stated by the Qwen model card. As the video length increases, the number of video tokens grows, leading to higher memory usage. Since this PoC uses a **6-second clip**, there is ample room within the 96 GB.
- `--dtype bfloat16` **:** Serving at full original precision without quantization (full checkpoint ≈ 66 GiB). There is no loss in quality, but it consumes a lot of memory.
- `--gpu-memory-utilization 0.85` **:** The ratio at which the vLLM preempts 85% (≈ 81.6 GB) of GPU memory for weights and KV cache. Increasing this boosts concurrent throughput(KV cache) increases, but the risk of OOM rises; lowering it ensures safety but reduces throughput.
- `--tensor-parallel-size 1` **:** The model is loaded entirely onto a single GPU rather than being split across multiple GPUs.
- `--max-num-seqs 8` **:** The maximum number of requests (sequences) that vLLM can process simultaneously = internal batch size limit. Since this is larger than the gateway (API Server) concurrency (4), vLLM has some headroom.

:::note
📍 **Where are these settings located? - Distinguish between two locations**

- The `--dtype`, `--gpu-memory-utilization`, `--tensor-parallel-size`, and `--max-num-seqs` above are **vLLM server startup arguments** → They are found in the `vllm serve …` command of the service that launches vLLM on the serving host (Not in our gateway repo, but on the **vLLM serving side**).
- Our gateway’s (`poc-vision-bench`) own settings (`VLLM_BASE_URL`, `VLLM_CONCURRENCY`, etc.) are separate and located in `.env` **→** `src/config.py` **’s** `Settings`.
:::

#### **2.2. Input Method:** `from_video` **(single MP4 input) vs** `from_frames_audio` **(separate inputs)**

- Adopted the method of passing a single 6-second mp4 file as-is to a component via `video_url` (base64 data).
- Since Qwen3-Omni natively supports the integrated interpretation of video and audio via `use_audio_in_video`, passing a single MP4 file as-is via `from_video` is the model’s recommended input method and results in the simplest pipeline. Separate inputs increase the number of components to four and introduce the risk of motion loss between keyframes and alignment issues, so this approach is on hold.

| **Comparison Items** | `from_video` **(Adopted)** | `from_frames_audio` **(On Hold)** |
| --- | --- | --- |
| **Input Configuration** | Single MP4 file → `video_url` (data URI) 1 component | N keyframe JPGs + 1 WAV file → 4 components |
| **Timing Alignment** | Video and audio automatically synchronized within the container | Requires separate client-side alignment |
| **Preprocessing Output Size** | 6-second MP4 (~1–3 MB per clip) | 3 JPG frames + WAV (~hundreds of KB per clip) |
| **Impact on Visual Quality** | Video and audio alignment and context naturally maintained | Possible motion loss between keyframes |


## 3. Testing

### 3.0. Testing Method

Verify the **basic operation** of Client → API Server → vLLM through the following 6 steps. (Analysis *quality* evaluation will follow later.)

1. **Prepare Sample Data**
   - Prepare test video data and split a 10-minute segment into 100 clips of 6 seconds each.

   - Use ffmpeg to create clips that **retain the audio but black out the video** (for voice-only analysis verification).

2. **Run the Analysis Server**
   - Launch the API gateway (`poc-vision-bench` ) that receives clips and relays them to the vLLM.

3. **Single Inference Call** (`/chat` )
   1. Text only

   1. Video + prompt 

   1. Screen blacked out only (same prompt as ⓑ) — Verify voice recognition

4. **Batch inference call** (`/chat/batch` )
   - Send multiple clips (video + prompt) in a single request to verify batch processing.

5. **Save Results**
   - Record responses and processing statistics (success/failure, elapsed time) for each call.

6. **Summary and Evaluation**
   - Summarize at a glance whether each API functioned normally.


### 3.1. Test Data

The source data used for testing is as follows. Videos ranging from 50 minutes to 2 hours in length, as similar as possible to actual broadcast footage.

| **Broadcast** | **Duration** | **URL** |
| --- | --- | --- |
| KBS 9 News | 48:30 | [https://www.youtube.com/watch?v=rX1P-jOoNmM](https://www.youtube.com/watch?v=rX1P-jOoNmM) |
| Superfish Part 1 | 58:40 | [https://www.youtube.com/watch?v=iNbWqC1iqKw](https://www.youtube.com/watch?v=iNbWqC1iqKw) |
| KBS Winter Sonata | 1:04:52 | [https://www.youtube.com/watch?v=irVKEhb9g8M](https://www.youtube.com/watch?v=irVKEhb9g8M) |
| King Taejo Wang Geon | 54:10 | [https://www.youtube.com/watch?v=nmlE2iPWLGM](https://www.youtube.com/watch?v=nmlE2iPWLGM) |
| Chuljang Sipo-ya X Starship National Sports Festival Full Version | 1:00:06 | [https://www.youtube.com/watch?v=6wJGpi1nkCg](https://www.youtube.com/watch?v=6wJGpi1nkCg) |
| 2009 KBO League Korean Series Game 7 | 1:55:22 | [https://www.youtube.com/watch?v=fP1QEs1Uj5U](https://www.youtube.com/watch?v=fP1QEs1Uj5U) |
| **2024 LCK Summer Finals: GEN vs HLE** | 2:11:23 | [https://www.youtube.com/watch?v=_A_I75nJMF8](https://www.youtube.com/watch?v=_A_I75nJMF8) |

**Download Original (Reproduction Procedure)**

The original files listed in the table above can be downloaded using the procedure below and placed in `data/raw/{category}/`.

- **Prerequisites**: Install `uv` (→ `uvx` ) and `ffmpeg` (ffmpeg is required for merging video and audio streams)
1. **Download the original** — Save each URL from the table to its corresponding category folder

```bash
cd "$(git rev-parse --show-toplevel)"   # 작업 루트(레포 최상위)로 이동
CAT=<카테고리>; NAME=<원본명>; URL=<테스트 대상 URL>
uvx yt-dlp -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b" \
--merge-output-format mp4 \
-o "data/raw/$CAT/$NAME.%(ext)s" "$URL"
```

2. **Split into 6-second clips** (Preliminary Preparation)
- `00:10:00~00:20:00` Split the original (600–1200s) segment into 100 clips of 6 seconds each. Encode the absolute seconds of the original into the filename
- `data/clips/{category}/{원본명}/{seq}_{start}-{end}.mp4`

```bash
cd "$(git rev-parse --show-toplevel)"
CAT=<카테고리>; NAME=<원본명>
SRC="data/raw/$CAT/$NAME.mp4"
OUT="data/clips/$CAT/$NAME"; mkdir -p "$OUT"
for i in $(seq 0 99); do
  start=$((600 + i*6)); end=$((start + 6))  # 절대초 600,606,…,1194
  name=$(printf "%04d_%04d-%04d" $((i+1)) "$start" "$end")  # 0001_0600-0606
  ffmpeg -nostdin -ss "$start" -i "$SRC" -t 6 -c:v libopenh264 -b:v 1500k -c:a aac -movflags +faststart "$OUT/$name.mp4"
done
```

3. **Screen Blackout** (For audio-only verification)
   - Create one clip where only the screen of the first split clip is blacked out, leaving the audio intact

   - `data/blackout/{category}/{원본명}/`

```bash
cd "$(git rev-parse --show-toplevel)"
CAT=<카테고리>; NAME=<원본명>
OUT="data/clips/$CAT/$NAME"
FIRST=$(ls "$OUT"/*.mp4 | head -1)          # 분할된 클립 한 개만
BLACK="data/blackout/$CAT/$NAME"; mkdir -p "$BLACK"
ffmpeg -nostdin -i "$FIRST" \
  -vf "drawbox=0:0:iw:ih:color=black:t=fill" \
  -c:v libopenh264 -b:v 300k -c:a copy "$BLACK/$(basename "$FIRST")"
```

:::note
⚡ **Run All at Once** 

- Script that automates the above tasks

`./script/prepare_data.sh <카테고리> <파일명> <URL>`

- Skips downloading if the original already exists (to protect the original).
:::


**Final Test Clip Data**

| **Category Key** | **Genre** | **Number of Clips** | **Resolution** | **fps** | **Average Size** | **Remarks** |
| --- | --- | --- | --- | --- | --- | --- |
| `news` | News | 100 | 1920×1080 | 30 | 1.17 MB | Subtitles·High proportion of anchor commentary |
| `docu` | Documentary | 100 | 1920×1080 | 30 | 1.62 MB | Narration + mix of nature and on-site sounds |
| `baseball` | Baseball Broadcast | 100 | 640×360 | 29.97 | 1.13 MB | Commentator + Crowd Cheers + Scoreboard UI |
| `entertain` | Variety Show | 100 | 1920×1080 | 29.97 | 1.15 MB | Group conversation + subtitle effects |
| `drama` | Contemporary Drama | 100 | 720×480 | 29.97 | 1.10 MB | Character Dialogue + BGM |
| `hist_drama` | Historical Drama | 100 | 1920×1080 | 29.97 | 1.23 MB | Period Costumes & Props + Formal Dialogue |
| `esports` | Esports | 100 | 1920×1080 | **60** | 1.35 MB | Game UI overlay + Caster + Game audio |
| **Total** | — | **700** | — | — | ≈ 1.25 MB | 7 original videos (1 per genre, 10-minute window divided into 100 segments) |

:::warning
🔒 **Data Handling Principles**

- Videos are used **solely for internal quality assessment (PoC) purposes** and will not be distributed or republished externally.
- Videos and analysis results **will not be included** in the code repository
- Do not store processed copies separately.
- After evaluation concludes, local videos and deliverables must be **disposed of** in accordance with retention policies.
:::


### 3.2. Analysis Server (vLLM Frontend API Gateway)

A lightweight server that receives analysis requests and relays them to the vLLM. The entry points are `src/app.py` (`PYTHONPATH=src uv run uvicorn app:app --port 8001`). Interactive API documentation is provided via `/docs` (Swagger), `/redoc`, and `/openapi.json`.

#### 3.2.1. Design

- Server `poc-vision-bench` is a **thin gateway** (FastAPI) in front of the vLLM `/v1/chat/completions`.
- Inference is handled exclusively by the vLLM; the server passes the request body through without modification, adding **only three things**.
  1. Semaphore concurrency gate

  1. Batch NDJSON streaming (real-time verification)

  1. Logging the request_id (`X-Request-Id` header). Prompt assembly, base64 encoding, `response_format` schema enforcement, and response validation are **all performed on the client**.

- If the gateway is set to passthrough, experimental variations (prompt, schema, fps, sampling) can be **modified only on the client** .
- The server guarantees only vLLM protection (concurrency cap) and multi-request efficiency (fan-out streaming).
- Upstream calls are provided directly to vLLM inference as raw `httpx`, not via the OpenAI SDK.

#### 3.2.2. Concurrency · Backpressure

- vLLM upstream calls are gated by `asyncio.Semaphore(VLLM_CONCURRENCY)` (default 4). Excess requests are **not rejected but queued**.
- `/chat` and `/chat/batch` **share the same semaphore** → Ensures that the number of active tasks across both routes remains below the limit.
- The semaphore is created once during the FastAPI lifespan and injected into `app.state` (no runtime changes).
- **After** `VLLMClient.chat()` acquires the semaphore, it is measured by `time.monotonic()` → The returned `elapsed_ms` value represents the **round-trip time for the vLLM call (network + inference), excluding queue wait time**.

**Server Configuration (** `.env` **→** `Settings` **)**

| **Key** | **Default** | **Role** |
| --- | --- | --- |
| `VLLM_BASE_URL` | — | vLLM `/v1` endpoint |
| `VLLM_CONCURRENCY` | 4 | Concurrent call limit (Semaphore). Recommended 1–8 |
| `MAX_BATCH_ITEMS` | 128 | `/chat/batch` Maximum items per request |
| `VLLM_TIMEOUT_SECONDS` | 600s | Upstream call timeout |
| `VLLM_ACQUIRE_TIMEOUT_SECONDS` | 300s | Maximum wait time (seconds) for acquiring a semaphore permit. If exceeded, only that request is marked as failed → Deadlock backstop due to permit leakage or half-open (unreceived client FIN) |

#### 3.2.3. Batch NDJSON Streaming

- `/chat/batch` receives multiple records, performs fan-out (`asyncio.create_task`), and then streams them one line at a time in **completion order** (`asyncio.wait(..., return_when=FIRST_COMPLETED)`) (`application/x-ndjson`, chunked). Since this is not input order, it matches using `id`; even if one or two items fail, the rest continue(determined by the `status` on each line).
- **Backpressure and Deadlock Hardening:** The streaming loop checks client survival via `request.is_disconnected()` every 0.5 seconds; if the client disconnects (FIN received), it cancels all in-flight tasks and immediately releases the semaphore permit. In cases where a disconnection cannot be detected, such as with a half-open connection (where a FIN has not been received), the system waits until the **permit acquisition timeout** (`VLLM_ACQUIRE_TIMEOUT_SECONDS`, default 300s) expires, and only that request is marked as failed → This prevents deadlocks where a disconnected connection permanently holds the permit, causing the gateway to freeze.

Request Body:

```json
{"items": [
  {"id": "0001_0600-0606", "body": {<vLLM chat.completions body — /chat 와 동일>}},
  {"id": "0002_0606-0612", "body": {<...>}}
]}
```

Response (1 line = 1 JSON object, separated by line breaks):

```json
{"id": "0001_0600-0606", "status": 200, "elapsed_ms": 3104, "body": {<vLLM 응답>}}
{"id": "0002_0606-0612", "status": 500, "elapsed_ms": 0, "error": "<메시지>"}
```

| **Field** | **Meaning** |
| --- | --- |
| `id` | Identifier sent by the client (usually clip_id). Different from the `body.id` (`chatcmpl-…`) issued by vLLM |
| `status` | 200=Success / vLLM 4xx·5xx as-is / 500=Server-side exception (network disconnection, etc.) |
| `elapsed_ms` | Time from semaphore acquisition to completion of vLLM response (excluding queue wait). 0 in case of exception |
| `body` / `error` | vLLM response body on success / error message on failure |

- **Constraint:** `len(items) ≤ MAX_BATCH_ITEMS` (default 128). If exceeded, immediately return **413** (NDJSON not started, single JSON error). Include `X-Batch-Total` (number of received items) in the response header.

#### 3.2.4. Server Execution

The gateway is managed via `script/service.sh`.

```bash
./script/service.sh start      # 백그라운드 기동 (healthz OK 까지 대기)
./script/service.sh status     # PID·healthz·포트 확인
./script/service.sh restart    # stop → start
./script/service.sh stop
```

- Direct execution: `PYTHONPATH=src uv run uvicorn app:app --host 0.0.0.0 --port 8001`
- vLLM connection and concurrency: `.env` (→ 3.2.2). Interactive Documentation: `/docs` (Swagger)

#### 3.2.5. API Input/Output Examples

| **Method** | **Path** | **Role** | **Remarks** |
| --- | --- | --- | --- |
| GET | `/healthz` | Health Check | Always returns 200 after the lifespan expires. Does not check if the upstream is reached |
| POST | `/chat` | Single-item passthrough | vLLM body as-is → Response as-is. Returns 502 if upstream cannot be reached |
| POST | `/chat/batch` | Multi-item NDJSON streaming | Streams line by line in completion order (Details in 3.2.3) |

1. `/healthz`

```json
{"ok": true}
```

2. `/chat` (Single)
- Input: vLLM body assembled by the client (base64 image + prompt + strict schema). Multimodal options are **separated into two keys** — frame sampling is `media_io_kwargs.video` (`fps` or `num_frames`, vLLM I/O loader), audio integration is `mm_processor_kwargs.use_audio_in_video` (HF processor).

```json
{
  "model": "qwen",
  "messages": [{"role": "user", "content": [
    {"type": "video_url", "video_url": {"url": "data:video/mp4;base64,<...>"}},
    {"type": "text", "text": "<프롬프트>"}
  ]}],
  "temperature": 0.3, "max_tokens": 1024,
  "response_format": {"type": "json_schema", "json_schema": {"name": "clip_analysis", "strict": true, "schema": "<AnalysisResult 4필드>"}},
  "media_io_kwargs": {"video": {"fps": 2.0}},
  "mm_processor_kwargs": {"use_audio_in_video": true},
  "chat_template_kwargs": {"enable_thinking": false}
}
```

- Output: vLLM response as-is — strict JSON string in `choices[0].message.content`:

```json
{
  "id": "chatcmpl-...",
  "choices": [{"message": {"role": "assistant", "content": "<아래 JSON>"}, "finish_reason": "stop"}]
}
```

> Execution: `./script/curl_examples.sh chat`

3. `/chat/batch` (multiple) — Input: `{items:[{id, body}, …]}` (each body = same as ②)

```json
{"items": [
  {"id": "0001_0600-0606", "body": {"<②와 동일>"}},
  {"id": "0002_0606-0612", "body": {"..."}}
]}
```

Output: `application/x-ndjson` — One line per completion order (field details 3.2.3):

```javascript
{"id":"0001_0600-0606","status":200,"elapsed_ms":3104,"body":{<vLLM 응답>}}
{"id":"0002_0606-0612","status":500,"elapsed_ms":0,"error":"<메시지>"}
```

> Execution: `./script/curl_examples.sh batch`


### 3.3. Test Execution and Results

Verify by making an actual call to the client → API server → vLLM pipeline following the flow in §3.0. (Reproduction: `experiments/01_pipeline/api_check.py` )

#### 3.3.1. Status Check (`GET /healthz` )

Verify gateway availability. Always returns 200 after the lifespan expires (does not check whether the upstream vLLM was reached).

```bash
$ curl -i http://localhost:8001/healthz
HTTP/1.1 200 OK
content-type: application/json
x-request-id: 6da1b40a

{"ok":true}
```

→ **PASS** — Server startup and routing normal; confirmed that all responses include `X-Request-Id`.

#### 3.3.2. Single Inference (`POST /chat` )

1. **Text Inference**
   <details>
   <summary>Request</summary>

   ```bash
   curl -sS -X POST http://localhost:8001/chat \
     -H "Content-Type: application/json" \
     -d '{
       "model": "qwen",
       "messages": [{"role": "user", "content": [
         {"type": "text", "text": "한국어로 자기소개를 한 문장으로 해줘."}
       ]}]
     }' | jq
   ```


   </details>

   <details>
   <summary>Response</summary>

   ```json
   {
     "id": "chatcmpl-a4e66116bd600be3",
     "object": "chat.completion",
     "created": 1780911108,
     "prompt_routed_experts": null,
     "model": "qwen",
     "choices": [
       {
         "index": 0,
         "message": {
           "role": "assistant",
           "content": "안녕하세요, 저는 한국어 모국어 화자이며 다양한 주제에 대해 자연스럽고 흥미로운 대화를 나누는 것을 좋아합니다.",
           "refusal": null,
           "annotations": null,
           "audio": null,
           "function_call": null,
           "tool_calls": [],
           "reasoning": null
         },
         "logprobs": null,
         "finish_reason": "stop",
         "stop_reason": null,
         "token_ids": null,
         "routed_experts": null
       }
     ],
     "service_tier": null,
     "system_fingerprint": "vllm-0.21.0-955d20dc",
     "usage": {
       "prompt_tokens": 23,
       "total_tokens": 63,
       "completion_tokens": 40,
       "prompt_tokens_details": null
     },
     "prompt_logprobs": null,
     "prompt_token_ids": null,
     "prompt_text": null,
     "kv_transfer_params": null
   }
   ```


   </details>2. **Video + Prompt**
   <details>
   <summary>Request (curl)</summary>

   Since the video base64 is large, build the payload into a file and send it (`--data-binary`). A **temperature** of **0.3** is recommended for the video (higher values cause out-of-range character degeneration).

   ```bash
   REPO_DIR=$(git rev-parse --show-toplevel)
   CLIP=${REPO_DIR}/data/clips/baseball/baseball/0001_0600-0606.mp4
   PYTHONPATH=src uv run python - "$CLIP" <<'PY'
   import base64, json, sys
   b = base64.b64encode(open(sys.argv[1],"rb").read()).decode()
   json.dump({"model":"qwen","messages":[{"role":"user","content":[
       {"type":"video_url","video_url":{"url":"data:video/mp4;base64,"+b}},
       {"type":"text","text":"이 영상의 시각과 음성을 한국어로 분석해줘."}]}],
     "temperature":0.3,
     "mm_processor_kwargs":{"use_audio_in_video":True},
     "chat_template_kwargs":{"enable_thinking":False}}, open("/tmp/req.json","w"), ensure_ascii=False)
   PY
   curl -sS -X POST http://localhost:8001/chat -H "Content-Type: application/json" --data-binary @/tmp/req.json | jq
   ```


   </details>

   <details>
   <summary>Response (JSON)</summary>

   ```json
   {
     "id": "chatcmpl-be4589ee14d26f36",
     "object": "chat.completion",
     "created": 1780911130,
     "prompt_routed_experts": null,
     "model": "qwen",
     "choices": [
       {
         "index": 0,
         "message": {
           "role": "assistant",
           "content": "assistant>\n이 영상은 야구 경기 중 한 장면을 담고 있습니다. 경기장 내부에서 촬영되었으며, 주로 투수와 타자, 그리고 포수의 위치가 보입니다. 투수와 포수는 모두 빨간색 유니폼을 입고 있으며, 타자도 빨간색 유니폼을 입고 있습니다. 배경에는 광고판이 보이며, \"Pocari Sweat\"와 \"Super Dong\" 등의 광고가 있습니다. 경기장의 분위기는 활기차며, 관중들의 함성 소리가 들립니다. \n\n음성은 한국어로 진행되며, 경기 중계 방송의 목소리가 들립니다. 중계 방송에서는 경기의 진행 상황을 설명하고 있으며, 특정 선수의 활약에 대해 언급합니다. \"MVP를 줄 수밖에 없지 않나\"라는 말이 들리며, 이는 특정 선수의 훌륭한 활약에 대한 평가로 보입니다. 또한 \"기아의 반격이 또 나왔습니다\"라는 말이 들리며, 이는 경기 중 상대 팀이 반격을 시도하고 있음을 나타냅니다. \n\n전반적으로 이 영상은 야구 경기의 긴박한 순간을 포착한 것으로, 팀의 활약과 경기의 흐름을 중계 방송을 통해 관객들에게 전달하고 있습니다.",
           "refusal": null,
           "annotations": null,
           "audio": null,
           "function_call": null,
           "tool_calls": [],
           "reasoning": null
         },
         "logprobs": null,
         "finish_reason": "stop",
         "stop_reason": null,
         "token_ids": null,
         "routed_experts": null
       }
     ],
     "service_tier": null,
     "system_fingerprint": "vllm-0.21.0-955d20dc",
     "usage": {
       "prompt_tokens": 3633,
       "total_tokens": 3974,
       "completion_tokens": 341,
       "prompt_tokens_details": null
     },
     "prompt_logprobs": null,
     "prompt_token_ids": null,
     "prompt_text": null,
     "kv_transfer_params": null
   }
   ```


   </details>3. **Blackout Video + Prompt** (Control Experiment — Screen only blacked out, audio maintained)
   <details>
   <summary>Request (curl)</summary>

   **Completely identical** to [**2. Video + Prompt**] above (same prompt·`temperature 0.3`), with only the clip replaced by one where the screen is blacked out. If audio remains in the output even after the screen is blanked → the model is actually processing the audio

   ```bash
   REPO_DIR=$(git rev-parse --show-toplevel)
   CLIP=${REPO_DIR}/data/blackout/baseball/baseball/0001_0600-0606.mp4
   PYTHONPATH=src uv run python - "$CLIP" <<'PY'
   import base64, json, sys
   b = base64.b64encode(open(sys.argv[1],"rb").read()).decode()
   json.dump({"model":"qwen","messages":[{"role":"user","content":[
       {"type":"video_url","video_url":{"url":"data:video/mp4;base64,"+b}},
       {"type":"text","text":"이 영상의 시각과 음성을 한국어로 분석해줘."}]}],
     "temperature":0.3,
     "mm_processor_kwargs":{"use_audio_in_video":True},
     "chat_template_kwargs":{"enable_thinking":False}}, open("/tmp/req.json","w"), ensure_ascii=False)
   PY
   curl -sS -X POST http://localhost:8001/chat -H "Content-Type: application/json" --data-binary @/tmp/req.json | jq
   ```


   </details>

   <details>
   <summary>Response (content)</summary>

   ```javascript
   {
     "id": "chatcmpl-afbd596bbaba2f3b",
     "object": "chat.completion",
     "created": 1780911151,
     "prompt_routed_experts": null,
     "model": "qwen",
     "choices": [
       {
         "index": 0,
         "message": {
           "role": "assistant",
           "content": "assistant\n이 영상은 흑백으로 전환된 장면을 보여줍니다. 화면에는 아무런 시각적 정보가 없으며, 오직 검은색 배경만 존재합니다. 이는 아마도 비디오의 일부가 손상되었거나, 또는 의도적으로 흑백으로 처리된 것으로 보입니다. \n\n음성은 한국어로 되어 있으며, 두 명의 남성이 대화를 나누고 있습니다. 첫 번째 남성은 \"MVP를 줄 수밖에 없지 않나?\"라고 말하며, 두 번째 남성은 \"그렇죠.\"라고 동의합니다. 이 대화는 아마도 스포츠 경기에 대한 논의일 수 있습니다. \n\n그러나 이 대화는 비디오의 시각적 정보와 연결되지 않으며, 시청자가 비디오의 내용을 이해하기 위해 음성 정보에만 의존해야 합니다. 이는 비디오의 시각적 정보가 부족하거나, 의도적으로 시청자의 주의를 음성 정보에 집중시키기 위한 전략일 수 있습니다.",
           "refusal": null,
           "annotations": null,
           "audio": null,
           "function_call": null,
           "tool_calls": [],
           "reasoning": null
         },
         "logprobs": null,
         "finish_reason": "stop",
         "stop_reason": null,
         "token_ids": null,
         "routed_experts": null
       }
     ],
     "service_tier": null,
     "system_fingerprint": "vllm-0.21.0-955d20dc",
     "usage": {
       "prompt_tokens": 3633,
       "total_tokens": 3885,
       "completion_tokens": 252,
       "prompt_tokens_details": null
     },
     "prompt_logprobs": null,
     "prompt_token_ids": null,
     "prompt_text": null,
     "kv_transfer_params": null
   }
   ```


   </details>#### 3.3.3. Batch Inference (`POST /chat/batch` )

Using the same 12 clips and identical parameters (`temperature 0.3`, server default samples at the time of measurement), we compare the processing times for **① one at a time** `/chat` **sequential** vs **②** `/chat/batch` **batch** processing. (Reproduction: `experiments/01_pipeline/batch_throughput.py` )

<details>
<summary>Reproduction summary code (<code>batch_throughput.py</code> Core Section)</summary>

```python
# experiments/01_pipeline/batch_throughput.py — 핵심부 (같은 items 로 순차 vs 배치 비교)
import os, base64, json, time, httpx
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_DATA = Path(os.environ.get("DATA_DIR") or _HERE.parent.parent / "data")
CLIPS_ROOT = _DATA / "clips"

SVR = "http://localhost:8001"
_SCENE = CLIPS_ROOT / "baseball/baseball"
CLIPS = [str(p.relative_to(CLIPS_ROOT)) for p in sorted(_SCENE.glob("*.mp4"))[:12]]  # 연속 12클립 (0001~0012)

def chat_body(clip):
    b64 = base64.b64encode(clip.read_bytes()).decode()
    return {"model": "qwen", "temperature": 0.3,
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64}"}},
                {"type": "text", "text": "이 영상의 시각과 음성을 한국어로 분석해줘."}]}],
            "mm_processor_kwargs": {"use_audio_in_video": True},
            "chat_template_kwargs": {"enable_thinking": False}}

items = [{"id": Path(c).name, "body": chat_body(CLIPS_ROOT / c)} for c in CLIPS]  # base64 1회 인코딩 → 양 모드 재사용

with httpx.Client(timeout=600) as cli:
    # ① 순차: 한 건씩 /chat (앞 건 완료 후 다음)
    t = time.monotonic()
    for it in items:
        cli.post(f"{SVR}/chat", json=it["body"])
    seq_ms = int((time.monotonic() - t) * 1000)

    # ② 배치: /chat/batch 일괄 → 완료순 NDJSON 스트리밍
    t = time.monotonic()
    with cli.stream("POST", f"{SVR}/chat/batch", json={"items": items}) as r:
        for line in r.iter_lines():
            if line:
                json.loads(line)  # 라인 = {id, status, elapsed_ms, body|error}
    batch_ms = int((time.monotonic() - t) * 1000)

print(f"순차 {seq_ms}ms · 배치 {batch_ms}ms · {seq_ms / batch_ms:.2f}×")
```


</details>| Mode | Total Processing Time | Success |
| --- | --- | --- |
| Sequential (one at a time `/chat` ) | 37536ms | 12/12 |
| Batch (`/chat/batch` batch) | 22,603 ms | 12/12 |

Batch is faster than sequential (approx. **1.7 times** faster; fan-out parallelism limited by gateway concurrency `VLLM_CONCURRENCY=4` — the multiplier varies per execution due to empty output/overflow jitter). Arrival order ≠ input order (**completion-order streaming**), `X-Batch-Total=12`. Multiple requests in a single request, completion-order streaming, and each request being independent `status` all function normally.

#### 3.3.4. Summary

§3.3 Call results at a glance. (Based on **normal pipeline operation**, not output quality or accuracy)

| Item | Route | Verification Details | Key Result | Verdict |
| --- | --- | --- | --- | --- |
| Status Check | GET /healthz | Gateway availability·X-Request-Id | X-Request-Id assigned | ✅ PASS |
| Single·Text | POST /chat | Basic text inference operation | Normal 1 sentence (prompt 23·completion 25) | ✅ PASS |
| Single·Video | POST /chat | Integrated video and audio analysis | Korean scene analysis | ✅ PASS |
| Single·Blackout | POST /chat | Audio reflected even when screen is obscured (controlled) | Black screen recognition + capture of broadcast audio | ✅ PASS |
| Batch | POST /chat/batch | Simultaneous multi-item processing · Streaming in order of completion | Order of completion ≠ order of input; batch processing is approximately 1.7 times faster | ✅ PASS |

Confirmed that all core mechanisms of the client → `poc-vision-bench` → vLLM pipeline (text pass-through, concurrency gate, completion-order batch streaming, and integrated video-audio processing) are functioning normally.

---

##  4. Reference Documents

**Model — Qwen3-Omni**

- [Qwen3-Omni-30B-A3B-Instruct — Hugging Face Model Card](https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Instruct) — Modalities, Context, BF16 VRAM Table, License, Korean Support
- [Qwen3-Omni Technical Report (arXiv:2509.17765)](https://arxiv.org/abs/2509.17765) — Thinker–Talker MoE architecture, 32 out of 36 audio and AV models are open-source SOTA
- [QwenLM/Qwen3-Omni — GitHub](https://github.com/QwenLM/Qwen3-Omni) — Usage, `use_audio_in_video` Video and Audio Integration

**Hardware — AWS g7e**

- [Amazon EC2 G7e Instance (Product Page)](https://aws.amazon.com/ec2/instance-types/g7e/) — RTX PRO 6000 Blackwell, 96GB per GPU
- [G7e Launch Announcement (AWS News Blog)](https://aws.amazon.com/blogs/aws/announcing-amazon-ec2-g7e-instances-accelerated-by-nvidia-rtx-pro-6000-blackwell-server-edition-gpus/) — General Availability (GA) in January 2026
- [g7e.4xlarge Specifications — Vantage](https://instances.vantage.sh/aws/ec2/g7e.4xlarge) — 1 GPU / 96 GiB / 16 vCPU / 128 GiB

**Serving — vLLM**

- [Qwen3-Omni vLLM Serving Guide](https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/examples/online_serving/qwen3_omni/) — `vllm serve` options (`--max-model-len`, etc.)
- [vLLM — OpenAI-Compatible Server](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html) — `/v1/chat/completions` protocol·`response_format` ·extra body(`mm_processor_kwargs` ·`chat_template_kwargs` ). The gateway passes this body as-is


