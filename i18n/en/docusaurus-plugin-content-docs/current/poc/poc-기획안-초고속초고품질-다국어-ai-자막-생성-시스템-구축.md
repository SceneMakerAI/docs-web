---
id: poc-기획안-초고속초고품질-다국어-ai-자막-생성-시스템-구축
title: "[PoC Proposal] Ultra-Fast, High-Quality Multilingual AI Subtitle Generation System"
sidebar_position: 1
---

<br />

<br />

**Project nature:**

Validating a subtitle pipeline tailored for complex media audio environments — broadcast, film, variety shows, sports, and more.

**Validation environment:**

Single NVIDIA RTX 4090 (24 GB) baseline GPU environment.

<br />

## 1. Project Overview

- **Objective:** Isolate only human dialogue from media files mixed with background music, sound effects, and crowd noise — eliminating subtitle misrecognition and AI hallucination at the source — and convert a 1-hour video into perfect multilingual subtitles in just 3 minutes.

- **Core goals:**
  - Minimize Word Error Rate (WER) through Speech Enhancement

  - 2. Implement real-time multilingual code-switching recognition and silence handling at the sentence/segment level

  - Final context-aware correction of proper nouns and custom typos via LLM

- Expected processing pipeline

```smalltalk
[Video file input]
⬇️
Step 1. Audio extraction (ffmpeg)
High-quality audio track is rapidly separated from the source video for deep learning engine analysis.
⬇️
Step 2. AI Speech Enhancement (DeepFilterNet v3)
Background music (BGM), film sound effects, sports crowd noise, etc. are classified as "noise"
and completely removed in ~10 seconds, leaving only pure voice.
⬇️
Step 3. Multilingual transcription engine (WhisperX)
Silences are cleaned up via the built-in Silero VAD, followed by per-chunk language auto-detection,
producing hallucination-free high-speed text output.
⬇️
Step 4. Speaker diarization matching (PyAnnote Audio)
Timestamps of extracted text are cross-referenced with speaker voice segments,
and [Speaker 1], [Speaker 2] tags are assigned automatically.
⬇️
Step 5. LLM context correction (LLM Engine)
Using surrounding context, the LLM corrects Whisper's proper noun errors, typos, and spacing,
and outputs a standardized final SRT subtitle file.
```

<br />

## 2. Background Research

#### **2.1. Speech Recognition Engine: WhisperX (Turbo vs Large-v3)**

- **Conclusion:** Adopting `Turbo (Large-v3-Turbo)` for a transcription-focused ultra-fast system.

- **Rationale:** Large-v3 delivers peak accuracy, but the accuracy loss is within ~1% while Turbo is over 3× faster. Improving source quality through audio preprocessing is judged to be more advantageous in terms of both accuracy and speed.

| **Comparison** | **WhisperX Large-v3** | **WhisperX Turbo** | **Notes & Business Impact** |
| --- | --- | --- | --- |
| **Parameters** | 1,550M (1.55B) | **809M (0.81B)** | Slimmer architecture enables lighter deployment |
| **Decoder layers** | 32 | **4** | 1/8 the layers → maximized inference speed |
| **Actual VRAM** *(FP16)* | ~4.5–5.0 GB | **~2.5–3.0 GB** | GPU memory savings allow higher batch throughput |
| **1-hour audio processing time**<br/>*(RTX 4090 / WhisperX batch)* | ~45s–1min | **~15–20s** | **Turbo is ~3× faster** (pure compute, excluding I/O) |
| **Accuracy** *(LibriSpeech WER)* | Baseline (~2.7%) | **Slight drop (~3.0%)** | **~0.3% WER difference** — imperceptible in practice |
| **Translation** *(--task translate)* | **Supported** (multilingual → English) | **Not supported** (transcribes the spoken language as-is) | Multilingual transcription ("dictation") is fully supported in both |

#### 2.2 Noise Reduction

- **Conclusion:** Adopting `DeepFilterNet v3` as the main preprocessing engine for ultra-fast isolation of dialogue from diverse noise environments — broadcast, film, sports commentary, etc.

- **Rationale:** Unlike music source separation models specialized in BGM removal (RoFormer, MDX), DeepFilterNet recognizes all sounds outside the human vocal frequency range (sound effects, crowd noise, ambient sound) as "noise" and eliminates them completely. On RTX 4090, it processes 1 hour of content in as little as 10 seconds, providing a dramatic infrastructure cost reduction.

| **Model** | **DeepFilterNet v3 (selected)** | **BS-RoFormer (Vocal)** | **MDX23C (Kim Vocal 2)** | **HTDemucs v4** |
| --- | --- | --- | --- | --- |
| **Category** | **Speech Enhancement** | Music source separation (SOTA) | Frequency separation (classical) | Hybrid source separation |
| RTX 4090<br/>1-hour processing time | **🚀 ~10–15s** | ~1m 30s–2m | ~45s–1m | ~1m–1m 30s |
| **VRAM usage** | **⚡ Under 1 GB (extremely light)** | ~4–8 GB | ~4–6 GB | ~4 GB |
| **Primary filtering target** | **On-site noise, crowd noise, reverb/echo, sound effects, BGM** | Background music (OST), instrument accompaniment | Background music, studio noise | Drums, bass, guitar instrument groups |
| **Key strength** | Overwhelmingly fast; excellent at preserving dramatic dialogue including mumbling and whispers. | BGM blocking capability is among the best in open-source. | High voice clarity (diction sharpness). | Can separate audio into 4 tracks for ambience control. |
| **Limitations** | In some variety shows where BGM volume greatly exceeds dialogue, faint music bleed may occur. | Heavy model; batch processing bottleneck risk. Possible Whisper misread due to voice distortion. | Cannot identify film sound effects or sports crowd noise as "instruments" — fails to filter them. | May misclassify quiet whispered dialogue as "noise" and remove it entirely. |
| **PoC final status** | **Main pipeline — confirmed** | Sub-pick for special genres (variety) | Candidate pick for high-volume fast processing | Validation pick for sports broadcasting |

<br />

---

<br />

<br />

<br />

<br />

<br />
