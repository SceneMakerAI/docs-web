---
title: "[PoC Proposal] Benchmark for Multimodal LLM Understanding of 6-Second Clips from Korean Broadcasts"
sidebar_position: 4
slug: "4"
---

<br />

<br />

**Project Overview:**

PoC for benchmarking the video understanding quality of multimodal LLMs using 7 genres of Korean broadcasts × 100 clips × 6-second clips (700 clips total)

**Test Environment:**

vLLM serving on 1 AWS EC2 GPU (us-west-2) / Qwen3-Omni-30B-A3B-Instruct (OpenAI-compatible endpoint)

<br />

## 1. Project Overview

- **Objective:** To demonstrate, via a single multimodal LLM call, whether it is possible to consistently generate a structured JSON with three fields—`{summary, objects, actions}`—that integrates visual and auditory information without hallucinations, using Korean broadcast clips (video + audio + dialogue script) segmented into 6-second segments.

- **Scope of PoC Validation:** Limited to multimodal LLM invocation, enforced structured responses, and result evaluation. **Video segmentation (ffmpeg) and dialogue script collection were performed separately as preliminary preparation steps** (segmentation was pre-generated using an in-house ffmpeg script; scripts were written manually) — automation is planned for the future through integration with the SceneMaker main pipeline and external subtitle/STT systems.

- **Key Objectives:**
  1. Eliminate post-processing and refinement stages by enforcing JSON Schema (vLLM guided decoding + pydantic `extra="forbid"`)

  1. Suppress hallucinations (mixing descriptions of preceding or subsequent scenes) by using a pattern that includes a 6-second context (6 seconds before, during, and after the target clip)

  1. Quantitatively evaluate the strengths and weaknesses of SceneMaker by genre using a benchmark of 7 genres (news, documentaries, variety shows, dramas, historical dramas, baseball, and esports) × 100 clips

- Expected Processing Workflow

```smalltalk
[Input original broadcast video (10-minute window)]

───── Preliminary Preparation (Outside the scope of this PoC · Performed separately · Scheduled for future automation) ─────

(A) Video Segmentation  — In-house FFmpeg script (separate)
  Splits the 00:10:00 to 00:20:00 segment of the original video into 100 clips, each 6 seconds long.
  File names are encoded with the absolute timestamp of the original (e.g., 0001_0600-0606.mp4) to prevent conflicts even if the window changes.
  ※ Planned for future integration into the SceneMaker pipeline.

(B) Dialogue Script  — scripts.json, manually created
  Groups dialogue from the previous 6 seconds, current 6 seconds, and next 6 seconds into three segments to provide context to the model.
  Specifies in the prompt that the analysis is limited to the 'current' 6 seconds, while the preceding and following segments are for context.
  ※ Planned for automatic retrieval via integration with external subtitle and STT systems in the future.

───── Scope of this PoC Validation ─────

[6-second MP4 clip + dialogue scripts for before, during, and after]
⬇️
Step 1. Single-call multimodal analysis (Qwen3-Omni via vLLM)
Send the MP4 base64 data URI (video_url) and text prompt as OpenAI-compatible `chat.completions`
in a single request. Audio is embedded within the MP4 and decoded simultaneously via the vLLM video pipeline.
⬇️
Step 2. Enforce JSON Schema Response (Guided Decoding)
Enforce the three fields {summary, objects, actions} using vLLM response_format=json_schema(strict).
Block any additional fields with a pydantic ValidationError.
⬇️
Step 3. Save Results / Comparative Evaluation
Save to `predictions/{category}/{original_name}/{clip_id}.json`. Perform qualitative comparison by sampling across categories.
```

<br />

## 2. Preliminary Investigation

#### **2.1. Analysis Model: Qwen3-Omni-30B-A3B-Instruct**

- **Conclusion:** Adopted `Qwen3-Omni-30B-A3B-Instruct` for integrated analysis of 6-second multimodal clips via a single API call.

- **Reason:** It is nearly the only open-source option capable of processing all four modalities (Image / Video / Audio / Text) with a single model and supporting OpenAI-compatible vLLM serving. Its MoE architecture (30B total / 3B active) enables single-GPU inference, and vLLM guided decoding ensures that JSON Schema-compliant responses are received as-is.

<br />

#### **2.2. Input Method: ** `from_video` ** (single MP4 input) vs ** `from_frames_audio` ** (separate inputs)**

- **Conclusion:** Adopted the `from_video` method, which passes a single 6-second MP4 file as a single `video_url` (base64 data URI) component. Separate input (`from_frames_audio`) is **on hold**.

- **Reason:** Since the vLLM video pipeline decodes video and audio simultaneously, there is zero additional cost for separation. The separate input method is currently inoperable because the `vllm[audio]` decoders (`av` / `soundfile` / `librosa`) are not installed in the server vLLM venv. — The output (frames + audio.wav in `data/derived/`) is preserved, allowing immediate resumption once server dependencies are strengthened.

| **Comparison Items** | `from_video` ** (Adopted)** | `from_frames_audio` ** (On Hold)** |
| --- | --- | --- |
| **Input Configuration** | 1 mp4 file → 1 component `video_url` (data URI) | 3 keyframe JPGs + 1 WAV file → 4 components |
| **Timing Alignment** | Video and audio automatically synchronized within the container | Separate alignment must be ensured on the client side |
| **Server-side dependencies** | Uses only the default vLLM video pipeline | Requires separate installation of `vllm[audio]` (`av` / `soundfile` / `librosa`) |
| **Preprocessing Output Size** | 6-second MP4 (~1–3 MB per clip) | 3 JPG frames + WAV (~hundreds of KB per clip) |
| **Hallucination Impact** | Natural preservation of video/audio alignment and context | Potential loss of motion between keyframes |
| **PoC Final Status** | **Main Pipeline Finalized** | Resuming after strengthening server dependencies (preserving `data/derived/`) |####

<br />

**2.3. Output Schema / Hallucination Guard**

- **Conclusion:** Responses are strictly fixed to the **3 fields**: `{summary, objects, actions}`. Double enforcement via vLLM `response_format=json_schema(strict=True)` + pydantic `extra="forbid"`.

- **Reason:** Can be stored and consumed as-is without post-processing (parsing, cleaning, adding/removing fields) code. Analysis is limited to a 6-second 'current' clip, with preceding, current, and following dialogue attached; however, the prompt explicitly states, "The preceding and following dialogue are for context only; do not incorporate them into the description." The two defects discovered during the `from_video` validation phase (summary copying vision text verbatim / prompt rule text mixed into the audio field) have been addressed through field-specific guidelines.

| **Field** | **Definition and Guidelines** |
| --- | --- |
| `summary` (string) | Naturally condense visual and audio information into 1–3 sentences in Korean. Do not copy expressions from `vision` or `audio` verbatim. |
| `objects` (array of string) | Noun keywords for objects, people, subtitles, logos, etc., appearing in the video (no duplicates; each entry within 3 words). |
| `actions` (array of string) | Verb phrases describing actions, movements, and scene transitions occurring in the video (no duplicates).

<br />

<br />

---

<br />

## 3. Testing

### 3.1. Testing Method

- **Analysis Unit:** 6-second MP4 clip (the original `00:10:00 \~ 00:20:00` segment divided into 100 equal parts; same window as our internal benchmark)

- **Analysis API:** Internal FastAPI server `POST /analyze/by-clip-path` — Submit `clip_path` + `script_prev/curr/next` via form → Response envelope `{result: {summary, objects, actions}, meta: {model, elapsed_ms, usage}}`

- **Concurrency / Backpressure:** `VLLM_CONCURRENCY=4` (`asyncio.Semaphore`) — Excess requests are queued without being rejected

- **Storage:** Results are saved to `predictions/{category}/{original_name}/{clip_id}.json`, followed by qualitative comparison using random samples per category

- **Request Tracking:** The response header `X-Request-Id` (8-character hex) is embedded identically to the log line prefix for 1:1 trace matching

<br />

### 3.2. Test Data

| **Category Key** | **Genre** | **Number of Clips** | **Remarks** |
| --- | --- | --- | --- |
| `news` | News | 100 | High proportion of subtitles and anchor commentary |
| `docu` | Documentary | 100 | Narration mixed with natural and on-site sounds |
| `baseball` | Baseball Broadcast | 100 | Commentator + Crowd Cheers + Scoreboard UI |
| `entertain` | Variety Show | 100 | Group Conversation + Subtitle Effects |
| `drama` | Modern Drama | 100 | Character Dialogue + BGM |
| `hist_drama` | Historical Drama | 100 | Period Costumes & Props + Formal Dialogue |
| `lol` | Esports | 100 | Game UI overlay + Commentator + Game sounds |
| **Total** | — | **700** | 7 original videos (1 per genre, 10-minute window divided into 100 segments) |

<br />

<br />

