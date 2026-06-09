---
title: "[Part 2] Inference Parameter Tuning — Analysis of a 6-Second Clip Using Qwen3-Omni (OFAT Sweep)"
sidebar_position: 3
slug: "3"
last_update:
  date: 2026-06-09
---

## 1. Introduction

SceneMaker's clip analysis aims to **reliably extract visual and auditory information** from video clips. It takes a single 6-second clip as input and structures the information into a 6-field JSON format.

- **Comprehensive Analysis** 
  - `summary` : A one-sentence summary combining visual and auditory information

- **Visual Analysis** 
  - `objects` (Key objects/people)

  - `ocr` (On-screen text: subtitles/logos)

  - `actions` (Actions/movements/scene transitions)

- **Auditory Analysis**
  - `bgm` (Background sounds, music, atmosphere)

  - `sfx` (Sound effects: applause, typing, etc.)

The key issue here is **stability**. In a benchmark test batch-processing 700 clips, if the output fluctuates or breaks down with each run—even when using the same clip and the same prompt—the quality score itself cannot be trusted. Part 1(Pipeline Construction) During the validation process, four patterns of quality degradation were intermittently identified.

1. **Premature EOS**: Outputs EOS (End of Sentence) from the very first token, resulting in content ending as an empty string. This occurs when the model “runs out of things to say” and shuts down immediately, often due to excessive constraints from a strict JSON schema.
2. **Text Degeneration**: The model loses its normal probability distribution, spews out random characters and system tokens, and crashes before completing the JSON (Gibberish Generation).
3. **Repetition Loop**: The model gets stuck in a probability trap, endlessly looping and generating the same words, items, or JSON structures.
4. **Latency Jitter**: Due to runaway generation—where collapse and repetition block normal EOS, causing output to stretch all the way to `max_tokens`—the minimum-to-maximum variance in inference time per clip is extreme.

These patterns were merely **observed and identified** in Part 1; **whether they can be controlled via inference parameters was not addressed**. This part (Part 2) assumes that the output is fixed to a strict JSON Schema. It documents the results of a **Phase 1 Screening** that systematically investigated, one by one (OFAT, one-factor-at-a-time), whether prominent phenomena such as **repetition and degeneration** can be controlled by inference parameters. This is a record of the **Phase 1 Screening**, in which we investigated this by significantly varying each factor one at a time (OFAT, one-factor-at-a-time).

## 2. Experimental Environment

The experiments were conducted using **the same model, serving environment, and invocation path** as the benchmark. This was done to observe the effects of parameters in that exact environment. Since the details of the environment configuration are provided in Part 1, “Building a Benchmark Pipeline for Multimodal LLM Understanding of 6-Second Korean Broadcast Clips,” this section covers only the key summary and the **parameters tuned** in this experiment.

### 2.1. Environment Summary

- **Model** 
  - Qwen3-Omni-30B-A3B-Instruct (Thinker–Talker MoE, total inference core 30B, active 3B). 

  - Processes four modalities (Image, Video, Audio, Text) with a single model; this PoC uses only text output.

- **Serving**
  - vLLM serving on a single AWS g7e.4xlarge GPU (NVIDIA RTX PRO 6000 Blackwell, 96 GB).

  - The actual serving size `--max-model-len` is 16,384; be mindful of context overflow when dealing with high resolution or high frame rates.

- **Call Path**
  - Client (inference request) → Gateway (same as the gateway in Part 1) → vLLM → Qwen 3 Omni

  - Passes through a lightweight gateway (FastAPI) in front of the vLLM. Passes the inference payload without modification and adds only concurrency gate(default 4) and batch NDJSON streaming. This sweep sends a fixed set of 70 clips in a single request and collects results in the order they are completed.

:::note
📎 For details on model specifications, serving settings, and gateway routes, refer to Part 1 of this series: [Building a Benchmark Pipeline for Multimodal LLM Understanding of 6-Second Korean Broadcast Clips](/docs/poc/vision-bench/1).
:::

### 2.2. Parameters for Tuning

Inference parameters are not configured on the server but are **specified directly by the client in the request body**. Parameters are divided into two categories based on the operational layer — **vLLM input processing** (preparation before feeding media into the model) and **Qwen3-Omni generative sampling** (decoding where the model produces output). In this experiment, the OFAT sweep applies variations to only the *generative sampling* group one at a time , while the rest are fixed across the entire range.

1. **Qwen3-Omni Generative Sampling Parameters** (*Autoregressive Decoding · Sampling Strategies*) (OFAT Variation)

| **Parameter** | **Role** | **Value Range** | **This Experiment** |
| --- | --- | --- | --- |
| `temperature` | Sampling temperature; lower values are more deterministic | `[0, 2]` (default 1.0) | **Variable** |
| `top_k` | Limits candidates to the top k by probability | `-1` =Disabled / Works only when `≥1` (default -1) `0 < temperature` | **Variable** |
| `top_p` | Nucleus cutoff; only top candidates by cumulative probability | `(0, 1]` (default 1.0) `0 < temperature` | **Variation** |
| `frequency_penalty` | Suppress additive iterations (proportional to occurrence count) | `[-2, 2]` · `0` =Disabled (default 0.0) | **Variation** |
| `repetition_penalty` | Multiplicative repetition suppression (based on occurrence) | `>0` · `1` = Inactive · `>1` = Suppressed | **Variable** |
| `max_tokens` | Completion token upper limit (output length cap) | `>0` · within remaining context | fixed 512 |
| `chat_template_kwargs.enable_thinking` | thinking token generation on/off | `true` / `false` | **separate measurement** (quality·latency) |
| `seed` | Reproducibility (same input → same output when fixed) | Integer · `<0` = Disabled (random each time) | Fixed -1 |

1. **vLLM Input Processing Parameters** (*Multimodal Ingestion · Context Conditioning*) Token·Latency Axis (Not OFAT)

| **Parameter** | **Role** | **Value Range** | **This Experiment** |
| --- | --- | --- | --- |
| `media_io_kwargs.video.fps` | Video frame extraction rate | `>0` (e.g., 0.5, 1.0, 2.0) | **Measured separately** (Quality · Latency) |
| `use_audio_in_video` | Simultaneous audio decoding within MP4 | `true` / `false` | Fixed on |

:::note
📌 `frequency_penalty` **vs** `repetition_penalty` → Both suppress repetition, but the methods differ.

- **frequency** (addition·subtraction): The **more** a token has appeared, the **greater** the penalty (proportional to frequency·cumulative) → Strong at suppressing repetition (`공 공 공…`). Counts **only output tokens**.
- **repetition** (multiplication/division): If a token appears even once, it is reduced by a **fixed ratio** (based on presence only, regardless of frequency). Since vLLMs examine both **prompt + output**, prompt vocabulary may also be suppressed (potential increase in recall loss).
- ⚠️ Enabling both results in **double suppression (overkill)**
:::

### 2.3. Output Schema / Hallucination Guard

This experiment **fixes** the output contract below **without modification** and only varies the parameters (the prompt remains the same). Responses are **strictly** fixed to `{summary, objects, ocr, actions, bgm, sfx}` **6 fields**

- vLLM `response_format=json_schema(strict=True)`
- pydantic `extra="forbid"` 

Since this is a dual constraint, the output can be saved and consumed as-is without any post-processing (parsing, cleaning, or adding/removing fields). 

In the SceneMaker project, **dialogue (STT) analysis is handled by a separate WhisperX module**, while the Qwen3 Omini model is designed with a **split** between `bgm` **/** `sfx` to add analysis of background noise and sound effects.

| **Field** | **Definition and Guidelines** |
| --- | --- |
| `summary` (string) | A single-sentence summary of the video in Korean, integrating visual and auditory information. Do not copy the exact wording of individual fields. |
| `objects` (array of string) | Keywords for key objects and characters in the video (no duplicates; each entry must be within 3 words). On-screen text should be entered in `ocr`. |
| `ocr` (array of string) | On-screen text (subtitles, logos, titles) as written in the original. |
| `actions` (array of string) | Verbal phrases describing actions, movements, and scene transitions in the video (no duplicates). |
| `bgm` (array of string) | Background sounds, music, and overall atmosphere. |
| `sfx` (array of string) | Discrete sound effects (applause, typing, footsteps, etc.). |

:::note
🎙️ Dialogue (speech) transcription is handled by a separate WhisperX audio module and is therefore excluded from this schema. The model listens to the audio (`use_audio_in_video` on) it does not transcribe it, but only describes the non-speech soundscape (`bgm` ·`sfx` ).
:::

## 3. Methodology

### 3.1. Samples and Design

- **Fixed 70 samples** = 7 genres × 10 clips at 6-second intervals. All settings use **the same sample and the same prompt**.
- **OFAT Sweep→** Vary only one parameter across multiple levels while keeping all others fixed to observe the influence of that variable alone.
- **Sampling Isolation**: Penalty sweeps are run in greedy mode (temperature=0), while top_p and top_k sweeps are run with temp=0.7 as the anchor. (If temp=0, top_p and top_k have no effect.)

:::note
📖 **Glossary**

- **Sweep**: The process of measuring the output at each step while scanning through multiple values of a single parameter (e.g., `temperature` 0 → 0.3 → 0.7 → 1.0). The **OFAT sweep** in this experiment sweeps only one axis while keeping other parameters fixed to isolate the effect of that single parameter.
- **Greedy Decoding** : Decoding that selects only the single token with the highest probability (argmax) at each step. `temperature=0` is an example of greedy decoding; since it lacks randomness, the same input yields the same output (deterministic). The opposite is **sampling**, which selects candidates randomly based on probability (`top_k` ·`top_p` ·`temperature`).
:::

### 3.2. What Can Be Measured Without a Ground Truth — Conformity vs. Quality

This experiment deals only with **what can be evaluated without a reference answer key**. Output quality is divided into two levels, and the boundary between them marks the dividing line between Stage 1 and the next stage.

| **Category** | **Evaluation Target** | **Reference Answer Key** | **Where** |
| --- | --- | --- | --- |
| **Adherence** | Is it in Korean? · Is the JSON format correct? · Are the items short? · Are there no repetitions? (All *rules specified in the prompt*) | Not required | **This document (Stage 1)** |
| **Quality** | Completeness (no omissions) · Accuracy (no hallucinations) | **Required** | **Next stage (Gemini objective function)** |

Adherence is based on rules explicitly stated in the prompt, so it can be judged simply by looking at the output. In contrast, quality can only be evaluated if there is a "correct answer." **Compliance is a necessary but not sufficient condition**, so the distinction is clear. Following the rules does not guarantee that the content is correct, but we establish compliance first and then improve quality.

### 3.3. Metrics

To detect and quantify the four quality degradation patterns identified in Part 1 (**premature termination, collapse, repetition, and inference time variance**) **based solely on output without a reference answer**, we aggregate the following metrics from 70 outputs for each configuration. Each metric targets one or more of the anomalies listed above and consists of conformance and structural metrics that can be reliably captured in a single pass (n=70).

| **Metric** | **Definition** | **What it measures** |
| --- | --- | --- |
| `ok` | Number of records passing schema validation (parsing and validation successful) (/70) | Format compliance |
| `lat_p50` / `lat_p95` /`lat_avg` | Median, 95th percentile, and Average | Inference Latency · Time Variance |
| `items` | Average number of items per array field (`objects` ·`ocr` ·`actions` ·`bgm` ·`sfx` ) | Information Density |
| `purity` | Ratio of Hangul / (Hangul + Latin) characters (closer to 1.0 indicates pure Hangul) | Language purity(Mixed-character contamination) |
| `repeat` | Number of records with duplicate entries or token loops (/70) | Repetition |

The measured anomalies **require different approaches.** Exact duplicates, which become identical upon normalization during iteration, can be **losslessly removed** via post-processing (dedup), but token loops and mixed-character collapses cannot be restored through post-processing and must therefore be **prevented at the generation stage (parameters)** . This distinction determines "what to solve via parameters and what to solve via post-processing" in the subsequent sections on parameter effects and conclusions. However, **collapse frequency** itself is a rare event that occurs infrequently; since it is susceptible to batch concurrency jitter, it is treated only as a reference count in this stage and is not used as a basis for conclusions.

## 4. Effects by Parameter

This section lists the target parameters that were varied one at a time (OFAT). The brackets indicate an anchor for isolation.

- `temperature` : 0.0 / 0.3 / 0.7 / 1.0
- `top_k` : 1 / 10 / 50 / -1 (temp=0.7)
- `top_p` : 0.5 / 0.8 / 0.95 / 1.0 (temp=0.7)
- `frequency_penalty` : 0.0 / 0.5 / 1.0 / 2.0 (greedy)
- `repetition_penalty` : 1.0 / 1.05 / 1.1 / 1.3 (greedy)
- `fps` : 0.5 / 1.0 / 2.0 (separate measurement · tokens/delay)

Table abbreviations — `obj/act/aud` = average number of items for objects/actions/audio, `purity` = Korean / (Korean+Latin), `repeat` = number of duplicate entries and token loop records (/70), `comp_p50` = median completion token.

### 4.0. Preparing Test Data

### 4.1. Temperature — The lower the value, the cleaner the data

| **temp** | **ok** | **comp_p50** | **obj/act/aud** | **purity** | **repeat** |
| --- | --- | --- | --- | --- | --- |
| 0.0 | 69 | 190 | 7.5 / 4.6 / 4.7 | 0.968 | 18 |
| 0.3 | 69 | 191 | 7.5 / 4.6 / 4.8 | 0.979 | 18 |
| 0.7 | 67 | 192 | 7.8 / 5.0 / 4.7 | 0.977 | 17 |
| 1.0 | 66 | 235 | 8.9 / 7.4 / 4.6 | **0.788** | 16 |

As the temperature rises, the *pattern* of failure changes. At temp 0.7, severe repetition (`무장` ×9-style array flooding, 63 redundant items) occurs, while at temp 1.0, mixed-character word salad (`시гля` ·`Arial TTF` ) triggers, causing the Korean purity to **0.79**. **The range of 0.0 to 0.3 is the cleanest**. This is the exact opposite of the common "raise temp to stabilize" recommendation — for short guided-JSON output, the greedy method (temp=0) is the most stable.

### 4.2. Frequency / Repetition Penalty — The lever of repetition; even single items are penalized

| **Setting** | **obj/act/aud** | **repeat** | **Remarks** |
| --- | --- | --- | --- |
| No penalty (baseline) | 7.5 / 4.6 / 4.7 | 18 | — |
| freq 0.5 | 6.2 / 2.8 / 2.8 | 6 | Restores fragmented narration into a single sentence |
| freq 1.0 | 5.4 / 2.3 / 2.4 | 4 | Actual items (sea, camera) also begin to be omitted |
| freq 2.0 | 4.6 / 2.1 / **1.6** | 1 | Audio drops sharply |
| rep 1.1 | 6.3 / 3.8 / 3.6 | 6 | Behavior similar to freq |
| rep 1.3 | 4.7 / 3.3 / **1.3** | 1 | Sharp drop in audio |

The penalty directly reduces the number of repetitions. Simply changing freq from 0 to 0.5 reduces the number of repeated records from 18 to 6, with zero failures, and even **restores scattered narration fragments into a single sentence** . However, there is a cost—as the penalty increases, the number of items decreases as well; at freq 2.0 and rep 1.3, audio drops by more than half (4.7→1.6 / 1.3). **It is impossible to determine without a ground truth whether this reduction in count constitutes "redundancy removal (good)" or "deletion of actual information (bad)"** — this is the central issue in Sections 5 and 6.

### 4.3. top_k / top_p / fps — Virtually Independent of Duplicates

- **top_k / top_p** (temp=0.7 anchor): Reducing the number of candidates *slightly* decreases duplicates(17→14, 19→15). This is not decisive.
- **fps** (0.5 / 1.0 / 2.0): The number of iterations ranges from 16 to 21, and this is **unrelated** . Since fps is a parameter for vision detail and token volume, it should be viewed from the perspective of *accuracy* (next step) rather than adaptability.

## 5. Key Findings

1. **Iterations are common — approximately 26% (18/70)** of items are duplicates under default settings. This occurs mainly in `audio` (repeated background sounds and short interjections `아` /`그렇죠` ) and `actions`, and is hardly reduced by adjusting temperature, top_k, top_p, or fps (flat).
2. **Failure modes differ by temperature range** (4.1): temp 0.7 = severe repetition, temp 1.0 = out-of-order characters. **Low temperatures (≤0.3) are the cleanest**.
3. **Frequency / repetition penalty is the real lever for repetition** (in contrast to temperature·top_k). Just changing freq from 0 to 0.5 reduces repetitions from 18 to 6 with 0 failures; moreover, **it doesn’t just hide the problem—it actually fixes it**—restoring three fragmented pieces of narration into a single complete sentence.
4. **However, the penalty** ***magnitude*** **is not determined in Phase 1 (the core of integrity).** Increasing the penalty reduces the number of items, but **without a reference, it is impossible to distinguish whether this reduction is “removing redundancy (good)” or “deleting actual information (bad).”** In one actual case (a news clip), the penalty resulted in a decrease in count *by merging fragments*, so the direction was exactly the opposite. Since there is no signal to evaluate recall, the optimal size is passed to the next step (Gemini objective function) — this is not a limitation but **a principle of drawing conclusions only from what is measurable** .
5. **Obvious exact duplicates are resolved via deduplication (no penalty required).** Normalized deduplication, by definition, results in zero information loss — duplicate records decrease from 18 to **4** (remaining issues are fragmentation and token loops), but the number of unique items remains nearly constant at 7.5 → 7.4. In other words, **most duplicates can be eliminated through post-processing without sacrificing recall via penalties.**

## 6. Conclusion

### 6.1. Parameter Leverage Ranking and Direction

We calculated parameter leverage based on **remaining compliance violations** (such as mixed characters, degeneration, and token loops—issues that cannot be resolved by dedup) after applying dedup. `clean%` = the ratio of records with zero violations.

| **Priority** | **Parameter** | **Leverage (clean%)** | **Direction** | **Phase 1 Finalized?** |
| --- | --- | --- | --- | --- |
| 1 | **temperature** | 94 → **69%** (high) | Low 0–0.3, ≥0.7 prohibited | ✅ Confirmed: Low temperature |
| 2 | **freq / rep (choose one)** | 94 → 99% (medium) | Slight residual repetition ↓ | ⚠️ Direction only — magnitude in next step |
| 3 | top_k / top_p | 89–94% (Small) | Negligible | Low priority |
| 3 | fps | 90–94% (independent of compliance) | Content detail axis | → Next step (accuracy) |

### 6.2. Tentative Input Parameters

Based on the above analysis, this is the **baseline(Next Step)**.

| **Parameter** | **Value** | **Rationale** | **Finalized** |
| --- | --- | --- | --- |
| `temperature` | **0.0** | Low temperature is cleanest + greedy = determinism (reproducibility) | ✅ Final |
| `top_p` / `top_k` | 1.0 / -1 | temp=0 means inert → neutral value | (Irrelevant) |
| `frequency_penalty` | **0.0** | Iteration is lossless deduplication → Recall is not pre-reduced as a penalty before measurement | ⚠️ Tentative (size to be determined in next step) |
| `repetition_penalty` | 1.0 (off) | Avoids double suppression with freq | ⚠️ Tentative |
| `max_tokens` | 512 | BLAST radius cap (normal output max approx. 335) | ✅ Final |
| `fps` | 0.5 | Token-efficient (accuracy-fps to be re-evaluated in next step) | ⚠️ Tentative |
| **dedup (post-processing)** | **ON** | Normalized exact deduplication, 0 information loss | ✅ Final |

**Reason for starting the penalty at 0:** If freq is 0.5, recall drops significantly (actions 4.6→2.8). Since we cannot distinguish without a ground truth whether this is redundant removal (good) or actual information loss (bad), **we do not discard information in advance before measurement.** Since duplicates are already handled by dedup, there is no additional burden from the penalty. The possibility that a small penalty may ultimately be advantageous is a hypothesis, and the quality objective function (F1) determines this.

:::info
🎯 **Confidence Labels (Data Integrity)**

- ✅ **Step 1 Confirmation** (No ground truth required): dedup · low temperature (0–0.3, ≥0.7 prohibited) · parameter leverage ranking and direction
- ⚠️ **Next Stage** (Requires answer set from higher-level model): Penalty *magnitude* · fps · Overall quality (completeness·accuracy)
:::

### 6.3. Handoff to the Next Stage

After establishing the quality objective function(Gemini ground truth) is established, and only the search narrowed down by Stage 1 is performed.

1. **Low temperature fixed** (0.0–0.3) · **dedup ON** — Values finalized here.
2. **Perform a 1D sweep against the Gemini F1 objective function using only one penalty** (freq 0–0.7 *or* rep 1.0–1.2) → Determine the optimal size. Do not enable both.
3. **top_k / top_p** has a minor impact on convergence and is a lower priority; **fps** relates to accuracy (detail) and will be reviewed separately.
4. **max_tokens 512** is maintained as the blast-radius cap.

Phase 1 established the boundaries of "what can be determined without a ground truth" — **low-temperature and dedup are finalized**, while **penalty size and quality are deferred to the next phase (Gemini objective function)**. This reflects the principle of this phase: to draw conclusions only on what is measurable.

