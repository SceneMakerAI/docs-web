---
title: "[Part 2] Inference Parameter Tuning — Analysis of a 6-Second Clip from Qwen3-Omni (OFAT Sweep)"
sidebar_position: 3
slug: "3"
last_update:
  date: 2026-06-10
---

## 1. Introduction

SceneMaker’s video clip analysis aims to **reliably extract visual and auditory information** from video clips. Given a single 6-second clip as input, it structures three types of information into a `{summary, objects, ocr, actions, bgm, sfx}` 6-field JSON format.

- **Comprehensive Analysis** 
  - `summary` : A one-sentence summary combining visual and auditory information

- **Visual Analysis** 
  - `objects` (Key objects and people)

  - `ocr` (On-screen text: subtitles and logos)

  - `actions` (Actions, movements, and scene transitions)

- **Auditory Analysis**
  - `bgm` (Background sounds, music, atmosphere)

  - `sfx` (Sound effects: applause, typing, etc.)

The key factor here is **stability**. In a benchmark batch-processing 700 clips, if the output fluctuates or breaks down from run to run—even with the same clip and the same prompt—the quality score itself cannot be trusted. During the validation process in Part 1 (Pipeline Construction), four patterns of quality degradation were intermittently identified.

1. **Premature EOS**: The model outputs EOS (end-of-sentence) starting with the very first token, resulting in content that ends as an empty string. This occurs when the model “runs out of things to say” and shuts down immediately, often due to excessive constraints imposed by a strict JSON schema.
2. **Text Degeneration**: The model loses its normal probability distribution, spews out random characters and system tokens, and crashes before completing the JSON (Gibberish Generation).
3. **Repetition Loop**: The model gets trapped in a probability loop, repeatedly generating the same words, items, or JSON structures.
4. **Inference Time Variation (Latency Jitter)**: Due to runaway generation—where collapse and repetition prevent the model from reaching a normal EOS, causing the output to extend all the way to `max_tokens`—there is an extreme disparity between the minimum and maximum inference times per clip.

These patterns were merely **observed and identified** in Part 1; **whether they can be controlled via inference parameters was not addressed**. This part (Part 2) assumes that the output is fixed to a strict JSON Schema. This is a record of the **Phase 1 Screening**, in which we investigated whether **notable phenomena such as repetition and degeneration** can be controlled via inference parameters by significantly varying them one at a time (OFAT, one-factor-at-a-time).

## 2. Experimental Environment

The experiments were conducted using **the same model, serving environment, and invocation path** as the benchmark. This was done to observe the effects of parameters in that exact environment. Detailed information on the environment configuration can be found in Part 1 “Building a Benchmark Pipeline for Multimodal LLM Understanding of 6-Second Korean Broadcast Video Clips,” so this section covers only a key summary and the **parameters tuned** in this experiment.

### 2.1. Environment Summary

- **Model** 
  - Qwen3-Omni-30B-A3B-Instruct (Thinker–Talker MoE, total inference core size: 30B, active: 3B). 

  - Processes four modalities—Image, Video, Audio, and Text—using a single model; this PoC uses only text output.

- **Serving**
  - vLLM serving on a single GPU(NVIDIA RTX PRO 6000 Blackwell, 96 GB).

  - The actual serving size `--max-model-len` is 16,384; be mindful of context overflow when dealing with high resolution or high fps.

- **Call Path**
  - Client (inference request) → Gateway (same as the gateway in Part 1) → vLLM → Qwen 3 Omni

  - Passes through a lightweight gateway (FastAPI) in front of the vLLM. It passes the inference payload without modification, adding only concurrency gates (default 4) and batch NDJSON streaming. This sweep sends a fixed set of 70 clips in a single request and collects results in the order they are completed.

:::note
📎 For details on model specifications, serving settings, and gateway routes, refer to Part 1 of this series: [Building a Benchmark Pipeline for Multimodal LLM Understanding of 6-Second Clips from Korean Broadcasts](/docs/poc/vision-bench/1).
:::

### 2.2. Parameters for Tuning

Inference parameters are not configured on the server but are **specified directly by the client in the request body**. The parameters are divided into two categories based on the operational layer — **vLLM input processing** (preparation before feeding media into the model) and **Qwen3-Omni generation sampling** (decoding, where the model generates output). In this experiment, the OFAT sweep varies only the *generative sampling* group one at a time, while keeping the rest fixed across the entire range.

**1. Qwen3-Omni Generative Sampling Parameters** (*Autoregressive Decoding · Sampling Strategies*) — OFAT Variation

| **Parameter** | **Role** | **Value Range** | **This Experiment** |
| --- | --- | --- | --- |
| `temperature` | Sampling temperature; lower values result in more deterministic behavior | `[0, 2]` (default 1.0) | **Variable** |
| `top_k` | Limits candidates to the top k by probability | `-1` = Disabled / `≥1` (default -1) Works only when `0 < temperature` is set | **Variation** |
| `top_p` | Nucleus cutoff; only top candidates by cumulative probability | `(0, 1]` (default 1.0) Works only when `0 < temperature` is set | **Variation** |
| `frequency_penalty` | Additive iteration suppression (proportional to occurrence count) | `[-2, 2]` · `0` = Disabled (default 0.0) | **Variable** |
| `repetition_penalty` | Multiplicative repetition suppression (based on occurrence) | `>0` · `1` = Inactive · `>1` = Suppressed | **Variable** |
| `max_tokens` | Completion token upper limit (output length cap) | `>0` · Within remaining context | Fixed at 512 |
| `chat_template_kwargs.enable_thinking` | Thinking token generation on/off | `true` / `false` | **Measured separately** (quality·latency) |
| `seed` | Reproducibility (same input → same output when fixed) | Integer · `<0` = Disabled (random each time) | Fixed -1 |

**2. vLLM Input Processing Parameters** (*Multimodal Ingestion · Context Conditioning*) — Token·Latency Axis (Not OFAT)

| **Parameter** | **Role** | **Value Range** | **This Experiment** |
| --- | --- | --- | --- |
| `media_io_kwargs.video.fps` | Video frame extraction rate | `>0` (e.g., 0.5, 1.0, 2.0) | **Measured separately** (quality · latency) |
| `media_io_kwargs.video.fps` | Simultaneous audio decoding within MP4 | `>0` / `use_audio_in_video` | Fixed on |

:::note
📌 `true` **vs** `false` → Both suppress repetition, but their methods differ.

- **frequency** (addition·subtraction): The **more** a token has already appeared, the **greater** the penalty (proportional to frequency·cumulative) → Strong at suppressing repetition (`공 공 공…`). **Only output tokens** are counted.
- **repetition** (multiplication/division): If a token appears even once, it is reduced by a **fixed ratio** (based solely on presence, regardless of frequency). Since vLLMs consider both the **prompt and output**, even prompt vocabulary may be suppressed(potential increase in recall loss).
- ⚠️ Enabling both results in **double suppression (over-suppression)**
:::

### 2.3. Output Schema / Hallucination Guard

This experiment **fixes** the output contract below **without modification** and only varies the parameters (the prompt remains the same). Responses are **strictly** fixed to `{summary, objects, ocr, actions, bgm, sfx}` **6 fields**

- vLLM `response_format=json_schema(strict=True)`
- pydantic `extra="forbid"` 

Since this is a dual constraint, the output can be stored and consumed as-is without any post-processing (parsing, cleaning, or adding/removing fields). 

In the SceneMaker project, **dialogue (STT) analysis is handled by a separate WhisperX module**; for the Qwen3 Omini model, it is designed with a `bgm` **/** `sfx` **split** to include analysis of background noise and sound effects.

| **Field** | **Definition and Guidelines** |
| --- | --- |
| `summary` (string) | A one-sentence summary in Korean that integrates visual and auditory information. Do not copy the exact wording from individual fields. |
| `objects` (array of string) | Key noun keywords for objects and characters in the video (no duplicates; each entry must be within 3 syllables). On-screen text should be entered as `ocr`. |
| `ocr` (array of string) | Text visible on screen (subtitles, logos, titles) must be reproduced exactly as in the original. |
| `actions` (array of string) | Verbal phrases describing actions, movements, and scene transitions in the video (no duplicates). |
| `bgm` (array of string) | Background sounds, music, and overall atmosphere. |
| `sfx` (array of string) | Discrete sound effects (applause, typing, footsteps, etc.). |

:::note
🎙️ Dialogue (speech) transcription is handled by a separate WhisperX audio module and is therefore excluded from this schema. The model listens to the audio (`use_audio_in_video` on) but does not transcribe it; it describes only the non-speech soundscape (`bgm` ·`sfx`).
:::

## 3. Methodology

### 3.1. Sample and Design

- **Fixed 70 samples** = 10 clips across 7 genres, each 6 seconds long. All settings use **the same sample and the same prompt**.
- **OFAT Sweep→** Vary only one parameter across multiple levels while keeping all others fixed to observe the effect of that variable alone.
- **Sampling Isolation**: The penalty sweep is run in greedy mode (temperature=0), while the top_p·top_k sweeps are run at temp=0.7 anchor.(When temp=0, top_p and top_k have no effect)

:::note
📖 **Glossary**

- **Sweep**: The process of scanning through a parameter value in multiple steps (e.g., `temperature` 0 → 0.3 → 0.7 → 1.0) and measuring the output at each step. The **OFAT sweep** in this experiment in this experiment sweeps only one axis while keeping other parameters fixed, isolating the effect of that single parameter.
- **Greedy decoding**: A decoding method that selects only the single token with the highest probability (argmax) at each step. `temperature=0` is an example of greedy decoding; since it lacks randomness, the same input always produces the same output (deterministic). The opposite is **sampling** (`top_k` ·`top_p` ·`temperature`), which selects candidates randomly based on probabilities.
:::

### 3.2. What Can Be Measured Without a Ground Truth — Conformity vs. Quality

This experiment deals only with **what can be evaluated without a ground truth**. Output quality is divided into two levels, and the boundary between them marks the dividing line between Stage 1 and the next stage.

| **Category** | **Evaluation Target** | **Reference Answer** | **Where** |
| --- | --- | --- | --- |
| **Adherence** | Is it in Korean? · Is the JSON format correct? · Are the items short? · Are there no repetitions? (All *rules specified in the prompt*) | Not required | **This document (Stage 1)** |
| **Quality** | Completeness (no omissions) · Accuracy (no hallucinations) | **Required** | **Next stage (Gemini objective function)** |

Adherence is based on rules explicitly stated in the prompt, so it can be assessed simply by looking at the output. In contrast, quality can only be evaluated if there is a “correct answer.” **Compliance is a necessary but not sufficient condition**, so the distinction is clear-cut. Following the rules does not guarantee that the content is correct, but we establish compliance first and then improve quality.

### 3.3. Metrics

To detect and quantify the four quality degradation patterns identified in Part 1 (**premature termination, collapse, repetition, and inference time variance**) **using only the output, without a reference answer** , we aggregate the following metrics from the 70 outputs of each configuration. Each metric targets one or more of the anomalies listed above; all are compliance and structural metrics that can be reliably captured in a single pass (n=70), and `fields` ·`score` (repeat·degen) are expressed as decimal ratios between 0 and 1 (1.0 = 100%).

| **Metric** | **Definition** | **What it measures** |
| --- | --- | --- |
| `ok` / `fail` | Number of schema-passing / failing records (/70) | Format compliance · Premature termination |
| `inference_ms` (avg·p50·p95·min·max) | Inference time per clip (ms) | Inference time variance |
| `fields` | Percentage of fields with "values" (`summary` ·`objects` ·`ocr` ·`actions` ·`bgm` ·`sfx`, based on "ok" criteria) | Information coverage |
| `score.repeat` | Percentage of records with exact duplicates within the array — since near-duplicates and partial matches are not measured, this represents the **lower bound** of actual duplicates | Duplicates |
| `score.degen` | Ratio by breakdown signal — `foreign` (end character) · `finish_length` (reached max_tokens = incomplete/aborted) · `replacement` (broken multibyte) | Breakdown |

`score.repeat` and `score.degen` are aggregated values of `flags` (signals) per record, so **the metric calculation and debugging (identifying which clips are corrupted) use the same source**. Furthermore, the solutions for the observed anomalies **differ** — exact duplicates within an array (`repeat`) are **losslessly removed** via post-processing (dedup), but **corruptions** such as mixed characters or incomplete data (`degen`) cannot be restored via post-processing → they must be prevented at the generation stage (parameters). This distinction determines, in the subsequent “Parameter Effects” and “Conclusions” sections, “what is resolved via parameters and what is resolved via post-processing.” However, since collapses are rare events that occur infrequently, the frequency observed in a single pass with n=70 is provided for reference only.

## 4. Effects by Parameter

This section lists the target parameters that were varied one at a time (OFAT). The parentheses serve as isolation anchors.

- `temperature` : 0.0 / 0.3 / 0.7 / 1.0
- `top_k / top_p`
  - `top_k` : 1 / 10 / 50 / -1 (temp=0.7)

  - `top_p` : 0.5 / 0.8 / 0.95 / 1.0 (temp=0.7)

- `frequency_penalty / repetition_penalty` 
  - `frequency_penalty`: 0.0 / 0.5 / 1.0 / 2.0 (greedy)

  - `repetition_penalty`: 1.0 / 1.05 / 1.1 / 1.3 (greedy)

- `fps`: 0.5 / 1.0 / 2.0 (separate measurement · tokens/latency)
- `enable_thinking` : True / False (**separate measurement** · quality/latency)

The evaluation criteria for this section are not "expressive settings" but **"settings with the fewest obvious defects (incompleteness, mixed characters, repetition, or runaway)**. Increased coverage or the number of items may indicate hallucinations (overgeneration) and will not be counted as bonus points—even if the expression is somewhat lacking, the more accurate option is chosen, and the determination of whether it is a hallucination is left to the next stage, where the correct answers are provided.

### 4.0. Test Data Preparation

All configurations view the **same set of 70 clips**: 7 genres × 10 clips per category. 

`make_sample.py` collects the original MP4 files in `data/sample70/` **using only symlinks**, without copying or re-encoding them. Video derivatives are managed **in one place only** at `data/` , so for copyright purposes, `data/` deleting just one file cleans up the entire set (symlinks are `*.mp4` and are not committed via `.gitignore`).

```bash
# 10 items per category, evenly spaced → symlinks to data/sample70/ (70 in total)
python make_sample.py
# Single-run/batch testing using that sample (from experiments/02_param_sweep/)
python run.py ../../data/sample70 -o out.json
```

### 4.1. temperature

**Episode Average** (Episodes 1, 2, 3 · n=70 each)

| **temp** | **ok/fail** | **repeat** | **foreign** | **finish_len** | **summary** | **objects** | **ocr** | **actions** | **bgm** | **sfx** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.0 | 61/9 | 13% | – | 13% | 100% | 100% | 72% | 100% | 41% | 44% |
| 0.3 | 63/7 | 11% | – | 10% | 100% | 100% | 72% | 100% | 40% | 44% |
| 0.7 | **68/2** | 13% | – | 1% | 100% | 100% | 75% | 100% | 45% | 55% |
| 1.0 | **69/1** | 13% | **26%** | 1% | 100% | 100% | 77% | 100% | 57% | 60% |

<details>
<summary>📊 History by Episode (Episodes 1, 2, and 3 – Original)</summary>

| **Episode** | **temp** | **ok/fail** | **repeat** | **foreign** | **finish_len** | **ocr** | **bgm** | **sfx** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.0 | 61/9 | 17% | – | 13% | 72% | 39% | 43% |
| 2 | 0.0 | 60/10 | 9% | – | 14% | 72% | 42% | 43% |
| 3 | 0.0 | 61/9 | 13% | – | 13% | 72% | 43% | 46% |
| 1 | 0.3 | 63/7 | 10% | – | 10% | 73% | 40% | 41% |
| 2 | 0.3 | 61/9 | 13% | – | 13% | 70% | 33% | 41% |
| 3 | 0.3 | 64/6 | 11% | – | 9% | 73% | 48% | 50% |
| 1 | 0.7 | 68/2 | 17% | – | 3% | 75% | 46% | 57% |
| 2 | 0.7 | 69/1 | 6% | – | – | 75% | 48% | 59% |
| 3 | 0.7 | 68/2 | 16% | – | – | 75% | 43% | 48% |
| 1 | 1.0 | 68/2 | 6% | 30% | 3% | 76% | 59% | 68% |
| 2 | 1.0 | 69/1 | 17% | 19% | 1% | 77% | 56% | 54% |
| 3 | 1.0 | 70/0 | 16% | 29% | – | 79% | 57% | 60% |

</details>

The existing hypothesis that "low temperature (temp 0.0) is safe" was refuted by the average data from three cross-validations. Greedy does not operate deterministically, and the **optimal morphological sweet spot** is `Temperature 0.7`.

####

**Key Metrics Comparison Table**

| **Evaluation Metric** | **Greedy (0.0)** | **Sweet Spot (0.7)** | **High Temp (1.0)** |
| --- | --- | --- | --- |
| **Completion Rate** | 61% (Worst) | **68% (Good)** | 69% (Best) |
| **P95 / Max Latency** | 8.9k / 9.4k ms | **5.8k / 7.4k ms** | - |
| **Mismatch Rate** | 0% | **0%** (sporadic cross-series 0–1%) | 26% (explosive) |

#### 1. Completion Rate and Latency: The “Runaway” Phenomenon in Greedy

- **Critical flaw in Greedy (0.0):** A “runaway” phenomenon frequently occurred, where the algorithm got trapped in an infinite loop (repeated generation) and failed to reach `max_tokens`. (Termination rate due to length limit: `finish_len` 13%)
- **Reduction in Tail Latency:** In `temp 0.7`, these runaway incidents decreased sharply, with the P95 latency improving from **8.9k ms ➡️ 5.8k ms** and the maximum latency significantly improving from **9.4k ms ➡️ 7.4k ms**.
- **Consistency of P50 (Median):** The P50 latency remained consistent at approximately 3.5k ms, unaffected by temperature. In other words, while the typical speed remains the same, **outliers (runaway phenomena) are better controlled at higher temperatures**.

#### 2. Misconceptions Regarding the Explosion of Non-Standard Characters and Repetition Rates

- **Risks of Temp 1.0:** In a 1.0 high-temperature environment, the outlier character occurrence rate skyrockets to 26%, making it impossible to deploy in live service.
- **Stability at 0.7:** This series recorded 0%. However, in tests on a cross-series with identical settings (top_k -1, top_p 1.0, 840 records), sporadic outliers at the 0–1% level were found; nevertheless, this is a safe level that differs from 1.0 by an order of magnitude.
- **Repeat Rate is Independent of Temperature:** Contrary to the intuition that lowering the temperature would reduce repetition, the rate remained **flat at 11–13%** across the entire range. In other words, repetition cannot be controlled by temperature.

#### 3. The Pitfall of BGM/SFX Coverage

- Although coverage increased as temperature rose (44% ➡️ 60%), this cannot be considered a positive factor.
- There is a directional hypothesis that **the risk of overgeneration and hallucinations** increases at higher temperatures, but it is difficult to trust this in the absence of ground truth data.
- Therefore, the rationale for choosing `0.7` lies not in increased coverage, but in “minimizing defects” (increasing completion rates and suppressing mixed characters).
- *(Note: The Summary, Objects, and Actions metrics achieved a fixed 100% across all intervals)*

> 

**Temperature set to 0.7**
Greedy(0.0) has the highest rate of incomplete runs and a long tail of latency; given the current serving structure, results fluctuate significantly from run to run, meaning even the benefit of low temperature—namely, “deterministic stability”—cannot be guaranteed. In contrast, `0.7` is the most balanced option, simultaneously achieving a top-tier completion rate, minimized latency, and protection against foreign characters.

###

4.2. Frequency / Repetition Penalty

**Average per Run** (Runs 1, 2, 3 · greedy temp=0.0 · n=70 each)

| **Settings** | **ok/fail** | **repeat** | **foreign** | **finish_len** | **summary** | **objects** | **ocr** | **actions** | **bgm** | **sfx** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| freq 0.0  | 62/8 | 14% | – | 11% | 100% | 100% | 72% | 100% | 44% | 41% |
| freq 0.5 | **70/0** | 9% | – | – | 100% | 100% | 74% | 100% | 17% | 21% |
| freq 1.0 | **70/0** | 8% | 1% | – | 100% | 100% | 73% | 100% | 8% | 14% |
| freq 2.0 | **70/0** | **2%** | 1% | – | 100% | 100% | 73% | 100% | **7%** | **8%** |
| rep 1.05 | 64/6 | 10% | – | 9% | 100% | 100% | 70% | 100% | 23% | 37% |
| rep 1.1 | 66/4 | 6% | – | 6% | 100% | 100% | 70% | 100% | 14% | 30% |
| rep 1.3 | 68/2 | **1%** | 2% | 3% | 100% | 100% | 66% | 100% | **4%** | 30% |

<details>
<summary>History by Episode (Episodes 1, 2, and 3 – Original)</summary>

| **Episode** | **Settings** | **ok/fail** | **repeat** | **foreign** | **finish_len** | **ocr** | **bgm** | **sfx** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | freq 0.0 | 61/9 | 13% | – | 13% | 72% | 44% | 43% |
| 2 | freq 0.0 | 62/8 | 16% | – | 11% | 73% | 44% | 44% |
| 3 | freq 0.0 | 64/6 | 14% | – | 9% | 72% | 45% | 38% |
| 1 | freq 0.5 | 69/1 | 7% | – | – | 74% | 16% | 20% |
| 2 | freq 0.5 | 70/0 | 13% | – | – | 73% | 16% | 21% |
| 3 | freq 0.5 | 70/0 | 6% | – | – | 74% | 19% | 21% |
| 1 | freq 1.0 | 70/0 | 6% | 1% | – | 73% | 7% | 11% |
| 2 | freq 1.0 | 70/0 | 9% | 1% | – | 73% | 9% | 14% |
| 3 | freq 1.0 | 70/0 | 9% | – | – | 73% | 7% | 16% |
| 1 | freq 2.0 | 70/0 | 1% | 1% | – | 73% | 7% | 9% |
| 2 | freq 2.0 | 69/1 | 1% | 1% | 1% | 74% | 9% | 6% |
| 3 | freq 2.0 | 70/0 | 3% | 1% | – | 73% | 6% | 9% |
| 1 | rep 1.05 | 64/6 | 9% | – | 9% | 70% | 23% | 36% |
| 2 | rep 1.05 | 64/6 | 13% | – | 9% | 70% | 23% | 39% |
| 3 | rep 1.05 | 63/7 | 10% | – | 9% | 70% | 22% | 35% |
| 1 | rep 1.1 | 66/4 | 7% | – | 6% | 70% | 15% | 29% |
| 2 | rep 1.1 | 67/3 | 7% | – | 4% | 72% | 12% | 27% |
| 3 | rep 1.1 | 64/6 | 4% | – | 7% | 69% | 14% | 33% |
| 1 | rep 1.3 | 68/2 | 1% | 3% | 3% | 68% | 4% | 29% |
| 2 | rep 1.3 | 68/2 | 1% | 1% | 3% | 66% | 4% | 28% |
| 3 | rep 1.3 | 67/3 | 1% | 3% | 3% | 66% | 4% | 31% |

</details>

detailshe penalty has been confirmed to be the most powerful lever for controlling repetition and runaway behavior in a greedy environment. However, as the penalty strength increases, auditory information (BGM and SFX) is lost proportionally, and in the temperature 0.7 reinforcement experiment, the utility itself disappears. **The conclusion is to turn the penalty OFF**, and when exploring the penalty magnitude, only the *freq* axis is advanced to the next step.

####

**Key Metrics Comparison Table** (based on greedy algorithm)

| **Evaluation Metric** | **Baseline (Penalty OFF)** | **freq 0.5** | **freq 2.0** | **rep 1.3** |
| --- | --- | --- | --- | --- |
| **Completion Rate** | 62/70 (worst case) | **70/70** | 70/70 | 68/70 |
| **Repetition Rate (repeat)** | 14% | 9% | **2%** | **1%** |
| **BGM / SFX Coverage** | **44% / 41%** | 17% / 21% | 7% / 8% (crash) | 4% / 30% (crash) |
| **P95 Latency** | 8.8k ms | **4.0k ms** | - | - |

####

1. Benefits: Prevention of repetition and runaway (based on greedy algorithm)

- **Normalized completion rate:** With a freq of just 0.5, fails dropped from 8 to 0, and runaway behavior was eliminated, improving P95 latency from **8.8k ms to 4.0k ms**. Reproduced in all three runs.
- **Repetition Suppression:** The repetition rate decreases from 14% to 2% at freq 2.0, and from 1.3% to 1%.
- **Actual Correction Effect:** There was a case where three fragmented pieces of narration were restored to a single complete sentence, confirming that the effect is not merely “hiding” repetitions but actually “correcting” them.

####

2. Trade-off: Concurrent Degradation of Auditory Information (BGM/SFX)

- **Loss Proportional to Intensity:** BGM and SFX coverage drops from 44%/41% ➡️ to 7%/8% at freq 2.0 and 4%/30% at rep 1.3. OCR accuracy also drops from 72% to 66% at rep.
- **The barrier of indecipherability:** Without a reference answer key, it is impossible to distinguish whether this reduction represents “redundancy removal (good)” or “information loss (bad).” ➡️ The penalty magnitude is determined by the quality objective function (next step).
- *(Note: The Summary, Objects, and Actions metrics consistently achieve 100% across all intervals)*

####

3. Reinforcement Metrics: Utility disappears in the baseline (temp 0.7)

- **Utility Disappearance:** The utility mentioned above (fail ➡️ 0·runaway elimination) is based on the greedy criterion. When remeasured at temp 0.7 (average across runs, n=70 for each of runs 1, 2, and 3), the baseline has already reached 69/1·finish_len 1% completion, meaning **there are almost no defects left for the penalty to eliminate.**
- **The only remaining effect is repeat suppression:** repeat decreases from 17% ➡️ 7–8%, but this is handled by deduplication post-processing without any information loss. Only the trade-off (halving of BGM and SFX: 49%/51% ➡️ 21%/25% at freq 0.5) remains.
- **New defects introduced by rep:** When the rep series is combined with temp 0.7, it **introduces new foreign characters** that were not present in the greedy algorithm (base 0% ➡️ rep 1.05 2% ➡️ rep 1.1 4%; dose-response relationship; reproduced 3 times) ➡️ **rep eliminated**.

> 

**Penalty OFF (freq 0.0 · rep 1.0)**
The benefits observed in the greedy algorithm are already negligible at temperature 0.7, and the remaining repetition suppression is replaced by lossless deduplication. There is no reason to accept the loss of auditory information or the introduction of heterogeneous characters by rep. We will only verify in the next step whether a small amount of freq (0–0.5) might be advantageous in terms of quality.

###

4.3. top_k / top_p

**Average per Iteration** (Iterations 1, 2, 3 · anchor temp=0.7 · n=70 each)

| **Settings** | **ok/fail** | **repeat** | **foreign** | **finish_len** | **summary** | **objects** | **ocr** | **actions** | **bgm** | **sfx** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| top_k 1 | 62/8 | 13% | – | 11% | 100% | 100% | 73% | 100% | 41% | 45% |
| top_k 10 | 67/3 | 18% | – | 3% | 100% | 100% | 75% | 100% | 44% | 51% |
| top_k 50 | 67/3 | 16% | – | 4% | 100% | 100% | 74% | 100% | 47% | 52% |
| top_k -1 | 67/3 | 14% | 1% | 3% | 100% | 100% | 74% | 100% | 46% | 50% |
| top_p 0.5 | 62/8 | 17% | – | 11% | 100% | 100% | 73% | 100% | 42% | 45% |
| top_p 0.8 | 65/5 | 18% | – | 7% | 100% | 100% | 72% | 100% | 43% | 47% |
| top_p 0.95 | 68/2 | 17% | – | 3% | 100% | 100% | 73% | 100% | 50% | 52% |
| top_p 1.0 | 67/3 | 18% | 1% | 4% | 100% | 100% | 72% | 100% | 49% | 51% |

<details>
<summary>Episode History (Episodes 1, 2, and 3 – Original)</summary>

| **Episode** | **Settings** | **ok/fail** | **repeat** | **foreign** | **finish_len** | **ocr** | **bgm** | **sfx** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | top_k 1 | 61/9 | 9% | – | 13% | 72% | 41% | 43% |
| 2 | top_k 1 | 63/7 | 16% | – | 10% | 73% | 41% | 48% |
| 3 | top_k 1 | 63/7 | 16% | – | 10% | 73% | 41% | 44% |
| 1 | top_k 10 | 67/3 | 13% | – | 4% | 73% | 43% | 52% |
| 2 | top_k 10 | 65/5 | 19% | – | 6% | 72% | 43% | 52% |
| 3 | top_k 10 | 70/0 | 23% | – | – | 79% | 44% | 49% |
| 1 | top_k 50 | 66/4 | 14% | – | 6% | 76% | 48% | 58% |
| 2 | top_k 50 | 68/2 | 17% | – | 3% | 75% | 47% | 48% |
| 3 | top_k 50 | 67/3 | 16% | – | 3% | 72% | 46% | 49% |
| 1 | top_k -1 | 66/4 | 13% | 1% | 6% | 74% | 44% | 42% |
| 2 | top_k -1 | 68/2 | 16% | 1% | 1% | 75% | 40% | 46% |
| 3 | top_k -1 | 68/2 | 13% | – | 3% | 74% | 53% | 62% |
| 1 | top_p 0.5 | 61/9 | 17% | – | 13% | 72% | 41% | 44% |
| 2 | top_p 0.5 | 63/7 | 11% | – | 10% | 73% | 41% | 46% |
| 3 | top_p 0.5 | 63/7 | 23% | – | 10% | 73% | 43% | 46% |
| 1 | top_p 0.8 | 66/4 | 23% | – | 6% | 73% | 39% | 42% |
| 2 | top_p 0.8 | 65/5 | 17% | – | 7% | 72% | 46% | 48% |
| 3 | top_p 0.8 | 65/5 | 13% | – | 7% | 72% | 43% | 51% |
| 1 | top_p 0.95 | 69/1 | 21% | – | 3% | 72% | 49% | 54% |
| 2 | top_p 0.95 | 67/3 | 17% | 1% | 4% | 72% | 49% | 51% |
| 3 | top_p 0.95 | 68/2 | 11% | – | 3% | 74% | 50% | 53% |
| 1 | top_p 1.0 | 67/3 | 19% | 1% | 4% | 73% | 54% | 55% |
| 2 | top_p 1.0 | 64/6 | 19% | 3% | 7% | 72% | 47% | 55% |
| 3 | top_p 1.0 | 69/1 | 17% | – | 1% | 72% | 48% | 42% |

</details>

detailsop_k and top_p are **secondary parameters** that are largely unaffected by iteration and collapse. In fact, as the number of candidates is narrowed down, they behave like a greedy algorithm, causing only the completion rate to drop. **The conclusion is to keep the default values —** `top_p 1.0 · top_k -1`.

####

**Key Metrics Comparison Table** (anchor temp=0.7)

| **Evaluation Metric** | **Tight (top_k 1 · top_p 0.5)** | **Loose (top_k -1 · top_p 0.95–1.0)** |
| --- | --- | --- |
| **Completion Rate** | 62/70 (similar to greedy) | **67–68/70** |
| **Incompletion (finish_len)** | 11% | **3–4%** |
| **Repetition Rate (repeat)** | 13–17% | 14–18% (no difference) |
| **Foreign Characters (foreign)** | 0% | 0–1% (negligible) |

#### 1. Tightening the criteria causes the algorithm to revert to a greedy approach

- **Decrease in completion rate:** Narrowing down candidates—such as top_k = 1 and top_p = 0.5—worsens the results to finish_len 11% and 62/8 completions — This is the same runaway pattern as the greedy algorithm in §4.1. Reproduced in all three runs.
- **Safe range:** The looser settings (k ≥ 10, p ≥ 0.95) are safe, and within that range, there are no significant differences between the settings.

####

2. Not a means of controlling repetition

- **repeat: flat, no trend:** It remains flat across the entire range at 13–18% (no trend in all three runs), so repetition cannot be controlled using top_k or top_p. The lever for controlling repetition is the penalty (§4.2).
- *(Note: “foreign” is negligible at 0–1% across the entire range; the “Summary,” “Objects,” and “Actions” items consistently achieve 100% across the entire range)*

> 

**top_p 1.0 · top_k -1 (maintain default values)**
If you narrow down candidates at temp 0.7 anchor, you only lose completion rate and gain nothing. Maintain the default full sampling settings, and unify diversity control using temperature alone.

##

5. Key Findings

Five key findings emerged from the three sweeps and validation runs. Findings 1 and 2 challenge conventional wisdom; 3 and 4 are recommendations; and 5 is a decision principle.

####

1. Completion rate increases with temperature (challenging conventional wisdom)

- **greedy(0.0) is the weakest:** 61/70 completions, 13% runaway — it gets stuck in an infinite loop and runs away up to `max_tokens`. **temp 0.7 yields 68/70 completions and 1% runaway**.
- **greedy is not even deterministic:** In the current implementation, the same settings fluctuate from run to run, so it lacks even the “stability” that was supposed to be a benefit of low temperatures.
- **The only cost of high temperature is mixed characters:** It spikes to 26% only at 1.0, while 0.0–0.7 shows sporadic fluctuations of 0–1% ➡️ The structural sweet spot is **temp 0.7** (98% clean after deduplication).

#### 2. Repetition is not controlled by sampling parameters

- **Flat across all ranges:** No matter how much you change temperature, top_k, or top_p, the repetition rate remains constant at 13–18% (no trend observed in all three runs).
- **Main sources:** `ocr` (repeated subtitles and logos) and `objects` (duplicate object names).
- **The metric is a lower bound:** Since it counts only exact duplicates, the estimated +23% for near-duplicates and partial inclusions is not included in the metric.

#### 3. The primary solution for repetition is deduplication, not penalties

- **Lossless removal:** Exact duplicates are removed via normalization, resulting in zero information loss.
- **Role of penalties:** Penalties remain only as a secondary option for residual cases (fragmentation and token loops) that dedup cannot resolve.

####

4. The utility of penalties disappears at the baseline (temp 0.7)

- **Loss of benefit:** The benefit in the greedy algorithm (fail ➡️ 0, elimination of runaway behavior) is meaningless at 0.7 because there are no defects to remove, and the remaining iteration suppression is handled by dedup. Only the trade-off (halving of BGM and SFX) remains.
- **Rep elimination:** When the rep series encounters 0.7, it **introduces new heterogeneous characters** that were not present in the greedy algorithm (0% ➡️ 2% ➡️ 4%, dose-response·replicated 3 times).
- **Remaining suppression:** Only one potential quality improvement at low frequencies (0–0.5) remains to be verified in the next phase.

####

5. Increased coverage is not a bonus (accuracy takes priority)

- **Possibility of hallucination:** While BGM and SFX coverage increases under high-temperature, no-penalty conditions, this could be overgeneration; therefore, it is treated as neutral at this stage where there is no definitive answer.
- **Evaluation Principle:** The criterion is not “expressiveness” but **“minimizing obvious defects”** — even if the expression is somewhat lacking, we choose the more accurate option.
- **Final Judgment:** Determining whether hallucination occurred is the responsibility of the next stage (Gemini F1’s precision).

## 6. Conclusion

###

6.1. Parameter Leverage Rankings and Directions

We calculated the leverage of each parameter based on compliance violations (mixed characters, incompleteness, token loops) that remain even after applying dedup. `clean%` = Percentage of records with 0 violations; the range represents the worst ➡️ best on that axis.

| **Priority** | **Parameter** | **Leverage (clean%)** | **Conclusion** |
| --- | --- | --- | --- |
| 1 | **temperature** | 74 ➡️ **98%** (high) | **0.7 confirmed** — simultaneously avoids greedy runaway and 1.0 mixed characters |
| 2 | **freq / rep penalty** | 89 ➡️ 100% (medium) | **OFF confirmed** — No benefit at 0.7; rep is eliminated due to causing mixed characters. Only a small amount of freq will be verified in the next step |
| 3 | top_k / top_p | 89 ➡️ 96% (low) | **Keep default values (1.0 / -1)** — Tightening settings only lowers completion rate |
| - | fps · enable_thinking | (measured separately) | Decide after re-measuring with temp fixed at 0.7 (to be done last) |

### 6.2. Finalized Input Parameters (Baseline)

This is the **baseline**, finalized based on the above analysis, prior to the quality objective function (next step).

| **Parameter** | **Value** | **Rationale** | **Finalized** |
| --- | --- | --- | --- |
| `temperature` | **0.7** | Highest completion rate (68/70) · finish_len 1% · mixed characters 0–1% · clean 98%. Greedy does not guarantee determinism | ✅ Confirmed |
| `top_p` / `top_k` | **1.0 / -1** | Tightening parameters causes regression to greedy, resulting in a drop in completion rate — maintain full sampling | ✅ Confirmed |
| `frequency_penalty` | **0.0** | At temp 0.7, there are no defects to remove (reinforced measurement in §4.2-3). Iterations are handled losslessly by dedup | ✅ Confirmed OFF (only a small quality gain of 0–0.5 will be carried over to the next stage) |
| `repetition_penalty` | **1.0 (off)** | Causes character corruption when combined with temp 0.7 (0 ➡️ 2 ➡️ 4% capacity-response) | ✅ Confirmed to be eliminated |
| `max_tokens` | 512 | BLAST-radius cap — Normal (unflagged) output max 460 tokens, approx. 10% margin | ✅ Confirmed |
| **dedup (post-processing)** | **ON** | Normalized exact deduplication, 0 information loss | ✅ Confirmed |
| `fps` | 0.5 (provisional) | Token-efficient. Re-evaluate after separate measurement of temp 0.7 anchor | ⚠️ Tentative |

**Reason for setting the penalty to 0:** The benefits observed in the greedy method disappear in the baseline (temp 0.7) (supplementary measurements in §4.2-3), leaving only auditory information loss (BGM·SFX 49%/51% ➡️ 21%/25% at freq 0.5) and the introduction of heterophones in rep. Repetitions are handled losslessly by dedup. While we leave open the hypothesis that a small amount of freq may be advantageous in terms of quality (F1), we do not discard information in advance before measurement.

:::info
🎯 **Confidence Label (Post Integrity)**

- ✅ **This Stage Finalized** (No answer key required): temperature 0.7 · default top_p/top_k values · penalty OFF (including rep elimination) · dedup ON · max_tokens 512
- ⚠️ **Next Step** (Answer Key Required): Determine whether there is a quality gain with low freq (0–0.5) · Cross-validation of hallucination (precision) at temp 0.3 vs. 0.7 · fps · thinking · Overall quality (completeness · accuracy)
:::

###

6.3. Handoff to the Next Step

After defining the quality objective function (Gemini ground truth), we only perform the search narrowed down by this step.

1

. **Start with fixed baseline:** `temp 0.7 · top_p 1.0 · top_k -1 · 페널티 OFF · dedup ON · max_tokens 512` — This is the confirmed value for this
2

stage.. **1D sweep on only the freq axis:** Determine the optimal size by testing freq 0–0.5 against Gemini F1. Since rep was eliminated due to heteroglyph-induced issues, it is not re-enabled (including the prohibition on double suppression)
3

.. **Cross-validation of temp 0.3 vs. 0.7:** We use F1 precision to test the directional hypothesis that “higher temperatures lead to increased hallucinations.” This serves as a safeguard to verify whether the
4

performance advantage at 0.7 comes at the cost of accuracy. **Separate measurements for fps and enable_thinking:** Re-measure using temp 0.7 as the anchor and add the results to §4. The trade-off between tokens/latency and detail is evaluated using the ground truth.

This stage has drawn conclusions up to the limit of what can be determined without an answer key—**the baseline has been established**, and the trade-offs between quality (hallucinations and completeness) and minor penalties and fps will be addressed in the next stage. The principle of drawing conclusions only on measurable factors remains unchanged.

