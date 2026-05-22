---
id: poc-기획안-멀티모달-llm-한국-방송-6초-클립-영상-이해-벤치마크
title: "[PoC proposal] Multimodal LLM Korean broadcast 6-second clip video comprehension benchmark"
sidebar_position: 1
slug: "1"
---

<br /> <br

<br />

**Project Nature:** **Project Description

Multimodal LLM video understanding quality benchmark PoC for Korean broadcasting 7 genres × 100 × 6-second clips (700 clips in total)

**Validation environment:**

vLLM serving on AWS EC2 with 1 GPU (us-west-2) / Qwen3-Omni-30B-A3B-Instruct (OpenAI compliant endpoint)

<br />

## 1. Project Overview (Overview)

- **Objective:** To analyze a Korean broadcast clip (video + audio + dialog script) chopped into 6-second segments in a single call to a multimodal LLM, and to demonstrate that it can consistently generate a `{summary, objects, actions}` 3-field structured JSON that integrates visual and audio information without illusion.

- PoC validation scope:** Multimodal LLM calls - Enforcing structured responses - Evaluating results. **Footage segmentation (ffmpeg) and dialog script collection were performed separately as a preliminary step** (segmentation was pre-generated with in-house ffmpeg script, script was manually written) - to be automated in the future with SceneMaker main pipeline and external subtitles - STT system integration.

- **Key Goals:**
  1. enforce JSON Schema (vLLM guided decoding + pydantic `extra="forbid"` ) to remove post-processing-refinement step

  1. suppress hallucinations (pulling in unanalyzed content) with **pre-present-post 6-second lines** context enclosing pattern

  1. 7 genres (news, docu, talent, drama, historical drama, baseball, e-sports) × 100 clips benchmark to quantitatively evaluate the strengths and weaknesses of SceneMaker by genre

- Estimated processing process

```smalltalk
[Input original broadcast video (10 minute window)]

───── Preparation (outside the scope of this PoC - performed separately - to be automated in the future) ─────

(A) Video segmentation - in-house ffmpeg script (separate)
  Split the 00:10:00 \~ 00:20:00 segment of the original into 100 clips of 6 seconds each.
  Encoded the original absolute seconds in the filename (0001_0600-0606.mp4) so that it doesn't crash when changing windows.
  * To be integrated into the SceneMaker main pipeline in the future.

(B) Dialog scripts - scripts.json, manually written
  Provides context to the model by stringing together 3 segments of dialog: previous 6 seconds / current 6 seconds / next 6 seconds.
  Limit the analysis to the "current" 6 seconds, and specify in the prompt that the before and after are for context.
  * Automatic receipt of external subtitles and STT system is planned in the future.

───── The scope of this PoC validation ─────

[6-second MP4 clip + before-current-after dialog script]
⬇️
Step 1. Single call multimodal analysis (Qwen3-Omni via vLLM)
Send mp4 base64 data URI (video_url) + text prompts to an OpenAI-compatible chat.completions
sent in one go. Audio is enclosed in the mp4 for simultaneous decoding with the vLLM video pipeline.
For example: ⬇️
Step two. Force JSON Schema response (Guided Decoding)
Force 3 fields {summary, objects, actions} to vLLM response_format=json_schema(strict).
Block with pydantic ValidationError if additional fields appear.
⬇️
Step 3. Save results / evaluate comparisons
Save to predictions/{category}/{source name}/{clip_id}.json. Sample by category for qualitative comparison.
```

<br />

## 2. Preliminary research

#### **2.1. Analysis model: Qwen3-Omni-30B-A3B-Instruct**

- **Conclusion:** Adopted `Qwen3-Omni-30B-A3B-Instruct` for single-call unified analysis of 6-second multimodal clips.

- **Rationale:** Almost the only open source option that handles Image / Video / Audio / Text 4 modalities in a single model and is OpenAI compatible vLLM serving. MoE structure (30B total / 3B active) allows single GPU inference, vLLM guided decoding ensures JSON Schema coerced responses are received intact.

<br />

#### **2.2. Input method: ** `from_video` ** (mp4 single input) vs ** `from_frames_audio` ** (separate input).

- **Decision:** Adopt the `from_video` method, which passes a chunk of a 6-second mp4 as a single component with a `video_url` (base64 data URI). Separate input (`from_frames_audio` ) is **pending** .

- Reason:** vLLM video pipeline decodes video and audio simultaneously, so additional separation cost is 0. Separate input method is not currently running because `vllm[audio]` decoder (`av` / `soundfile` / `librosa` ) is not installed on the server vLLM venv - output (frames + audio.wav in `data/derived/`) is preserved and can be resumed immediately after server dependencies are strengthened.

| **Comparisons** | `from_video` ** (adopted)** | `from_frames_audio` ** (pending)** |
| --- | --- --- --- --- --- | --- |
| **Input organization** | 1 mp4 file → `video_url` (data URI) 1 component | 3 keyframe JPGs + 1 WAV → 4 components
| **Time alignment** | Video and audio are automatically synchronized inside the container | Client-side separate alignment must be guaranteed
| Server-side dependencies: | Only uses vLLM default video pipeline | Requires separate installation of `vllm[audio]` (`av` / `soundfile` / `librosa` )
| **Preprocessing output size** | 6 seconds mp4 (\~1\-3 MB / clip) | 3 frames JPG + wav (\~hundreds of KB / clip) |
| **Hallucinatory effects** | Video-Audio alignment - keep context natural | Possibility of missing action between keyframes |
**PoC final status** | **Main pipeline finalized** | Resumed after reinforcing server dependencies (`data/derived/` is being preserved) |

<br /> <br />

#### **2.3. Output Schema / Hallucination Guard** **2.4.

- **Conclusion:** The response is fixed to be **exactly** `{summary, objects, actions}` **3 fields**. vLLM `response_format=json_schema(strict=True)` + pydantic `extra="forbid"` double coercion.

- **Reason:** Can be stored and consumed as is, without any post-processing (parsing-refining-adding/deleting fields) code. Limit analysis to 6-second 'current' clips, attach before, during, and after lines, but specify in the prompt "before and after is for context, don't pull it into description". Two defects found in the `from_video` validation phase (summary copying vision text verbatim / prompt rule text in audio field) have been incorporated into field-specific guides.

| **Fields** | **Definitions and guides** |
| --- | --- --- |
| `summary` (string) | Combines visual + audio information and naturally compresses it into 1-3 sentences in Korean. Do not copy the wording of vision/audio verbatim. |
| `objects` (array of string) | Noun keywords such as objects, people, subtitles, logos, etc. that appear in the video (no duplicates, each item within 3 sentences). |
| `actions` (array of string) | verb phrases for actions, movements, and transitions that happen in the video (no duplicates). |

<br />

---]

<br />

## 3. Test

### 3.1. Test Methods

- **Unit of analysis:** 6-second MP4 clip (100 equal parts of `00:10:00 \~ 00:20:00` of the original, same window as in-house sister benchmark)

- **Analysis API:** Send `clip_path` + `script_prev/curr/next` to in-house FastAPI server `POST /analyze/by-clip-path` - form → response envelope `{result: {summary, objects, actions}, meta: {model, elapsed_ms, usage}}`

- **Concurrency/Backpressure:** `VLLM_CONCURRENCY=4` (`asyncio.Semaphore` ) - Excess requests are queued without rejecting (queuing)

- Save:** Save results in `predictions/{category}/{source name}/{clip_id}.json` and qualitatively compare with random sample per category

- Request tracing:** Response header `X-Request-Id` (8-character hex) is padded with the same log line prefix for 1:1 trace matching

<br />

### 3.2. Test Data

| **Category Key** | **Genre** | **Clip Count** | **Remarks** |

| `news` | News | 100 | Subtitles-Anchor Mentions High
| `docu` | Documentary | 100 | Mix of narration + nature and field sounds |
| `baseball` | Baseball broadcasting | 100 | Casters + crowd cheers + scoreboard UI |
| `entertain` | Entertainment | 100 | Multi-person dialog + subtitle effects |
| `drama` | Modern Drama | 100 | Character Dialog + BGM | 100
| `hist_drama` | Historical Drama | 100 | Period Costumes & Props + Written Dialog
| `lol` | Esports | 100 | Game UI Overlay + Casters + Game Sounds |
| **Total** | - | **700** | 7 original videos (1 per genre, divided into 100 10 minute windows) |

<br /> <br />

<br />

