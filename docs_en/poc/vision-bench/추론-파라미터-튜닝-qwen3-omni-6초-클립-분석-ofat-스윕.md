---
title: "Inference Parameter Tuning — Analysis of a 6-Second Clip Using Qwen3-Omni (OFAT Sweep)"
sidebar_position: 3
slug: "3"
---

## 1. Introduction

SceneMaker’s 6-second clip analysis examines video, audio, and dialogue simultaneously to generate a JSON object with four fields: `{summary, objects, actions, audio}`. In a benchmark test batch-processing 700 clips, **if the output fluctuates or breaks down with each run—even for the same clip and the same prompt—** the quality score itself cannot be trusted.

During operation, three or more patterns were intermittently observed.

- **Repetition** — The same item is spammed, such as `audio: ["(dialogue)ah","(dialogue)ah","(dialogue)ah"]`

- **Fragmentation** — A single narration is split into three pieces and scattered across separate items

- **Degeneration** — Mixed character types appear (e.g., `시гля … Arial TTF`) and the JSON ends incompletely

This post documents a **Phase 1 screening** in which we investigated whether these three phenomena could be **controlled via inference parameters** by significantly altering them one at a time (OFAT, one-factor-at-a-time). To state the conclusion first, the commonly accepted advice to *"slightly increase the temperature from 0 to stabilize the model"* **actually had the opposite effect** in this task (generating short guided JSON). Furthermore, the **key achievement of this stage** was *clearly distinguishing between what can be determined without a reference answer* and *what requires a reference answer from a higher-level model*.

## 2. Experimental Environment

This experiment was conducted using **the same model, serving, and invocation paths** as the production benchmark—to observe parameter effects exactly as they occur in the production environment. Detailed information on the environment configuration can be found in Part 1 of this series, “Building a Benchmark Pipeline for Multimodal LLM Understanding of 6-Second Korean Broadcast Clips”; therefore, this section covers only a key summary and the **parameters tuned** in this experiment.

### 2.1. Environment Summary

- **Model** — Qwen3-Omni-30B-A3B-Instruct (Thinker–Talker MoE, total inference core 30B, active 3B). It processes four modalities—Image, Video, Audio, and Text—using a single model; this PoC uses only text output.

- **Serving** — Served as a vLLM (OpenAI-compatible) on a single AWS g7e.4xlarge GPU (NVIDIA RTX PRO 6000 Blackwell, 96 GB). The `--max-model-len` setting in actual serving is set to 16,384 to account for context limits in terms of frames per second (fps).

- **Invocation Path** — Passes through a thin gateway (FastAPI) in front of the vLLM. It passes the inference payload without modification, adding only a concurrency gate (default 4) and batch NDJSON streaming. This sweep sends a fixed set of 70 clips in a single request to `/chat/batch`, collecting results in the order they are completed, and repeats this across 18 configurations.

> 📎 For details on model specifications, serving configurations, and gateway routes, refer to Part 1 of this series: [Building a Benchmark Pipeline for Multimodal LLM Understanding of 6-Second Korean Broadcast Clips](https://www.notion.so/368e15b4035981cb9b9bd555dbfd19e3).

### 2.2. Parameters to Be Tuned

Inference parameters are not configured on the server but are **specified directly by the client in the request body**. The parameters that this experiment varies one at a time and those kept fixed across the entire range are as follows.

| **Parameter** | **Role** | **Value Range** | **This Experiment** |
| --- | --- | --- | --- |
| `temperature` | Sampling temperature; lower values yield more deterministic results | `[0, 2]` · `0` = greedy (argmax) | **Variable** |
| `top_k` | Limits candidates to the top k by probability | `-1` = inactive / `≥1` · Only when `temp>0` | **Variable** |
| `top_p` | Nucleus cutoff; only candidates within the top cumulative probability | `[0, 1]` · Only when `temp>0` | **Variable** |
| `frequency_penalty` | Additive repetition suppression (proportional to occurrence frequency) | `[-2, 2]` · `0` = inactive | **Variable** |
| `repetition_penalty` | Multiplicative repetition suppression (presence) | `>0` · `1` = inactive · `>1` = suppressed | **Variable** |
| `mm_processor_kwargs.fps` | Video frame sampling rate (↑ tokens·details↑) | `>0` (e.g., 0.5, 1.0, 2.0) | **Variable** |
| `max_tokens` | Completion token upper limit (output length cap) | `>0` · Within remaining context | Fixed at 512 |
| `use_audio_in_video` | Simultaneous audio decoding from MP4 | `true` / `false` | Fixed on |
| `chat_template_kwargs.enable_thinking` | Enable/disable thinking token generation | `true` / `false` | Fixed off |
| `seed` | Reproducibility (same input → same output when fixed) | Integer · `<0` = disabled (randomized each time) | Fixed -1 |

## 3. Methodology

### 3.1. Samples and Design

- **Fixed 70 samples** = 7 genres × 10 equally spaced clips (index 0, 10, …, 90). All settings use **the same sample and the same prompt**.

- **OFAT (One-Factor-At-A-Time)**: Only one parameter is significantly changed while keeping all others fixed, allowing us to observe the effect of that single variable. A total of **18 configurations**.

- **Sampling Isolation**: The penalty sweep is run in greedy mode (temp=0), and the top_p·top_k sweeps are run with temp=0.7 as the anchor — This is because top_p·top_k becomes inert at temp=0, making it impossible to observe any effect.

### 3.2. What Can Be Measured Without a Ground Truth? — Conformity vs. Quality

This first stage covers **only what can be evaluated without a ground truth**. Output quality is divided into two levels, and the boundary between them marks the dividing line between this stage and the next.

| **Category** | **Evaluation Target** | **Ground Truth** | **Where** |
| --- | --- | --- | --- |
| **Adherence** | Is it in Korean? · Is the JSON format correct? · Are the items short? · Are there no repetitions? (All *rules specified in the prompt*) | Not required | **This document (Stage 1)** |
| **Quality** | Completeness (no omissions) · Accuracy (no hallucinations) | **Required** | **Next stage (Gemini objective function)** |

Adherence is based on rules explicitly stated in the prompt, so it can be judged solely by looking at the output. On the other hand, quality requires a "correct answer" to be scored, so an answer key must be created using a higher-level model (Gemini). **Adherence is a necessary but not sufficient condition**, so the boundary is clearly defined—following the rules does not guarantee that the content is correct, but an output that fails to follow the rules isn’t even worth considering.

### 3.3. Trust the Form, Treat Degeneration Frequency as a Reference

Separating the measurement targets into two categories determines the reliability of the Stage 1 conclusion.

| **Measurement** | **Nature** | **Reliability** |
| --- | --- | --- |
| **Structural Characterization** (output length, number of fields, language purity, repetition) | Present in all outputs → A single pass with n=70 is sufficient | ✅ **Reliable** — Conclusion of this stage |
| **Degeneration Frequency** (Output Collapse Rate) | Rare event; with n=70 single passes, noise + batch concurrency jitter gets mixed into the parameter effect | ⚠️ **For reference only** |

Since degeneration is a rare event, it is difficult to trust the *frequency* based on a single run of 70 samples; moreover, numerical jitter caused by batch concurrency could be misattributed to the parameters. Therefore, we will use only the **form and repetition** present in all outputs as the conclusion of this stage, and separate the precise measurement of the degeneration frequency into a separate track.

## 4. Three Types of Failure

The output anomalies foreshadowed in Section 1 are classified into three types. **All three can be detected without a reference answer** — which is why they can be addressed in Stage 1.

| **Type** | **Actual Output Example (from 70 samples)** | **Detection Method** |
| --- | --- | --- |
| **Repetition** | `audio: ["(dialogue)ah","(dialogue)ah","(dialogue)ah"]` · `actions: ["armed"×9]` | Exact duplicates after normalization · Token loop |
| **Fragmentation** | A single narration is split into three pieces: `"…In conclusion"` · `"…Ulsan District Prosecutors' Office"` · `"…Uijeongbu District Prosecutors' Office"` | (Manual — Difficult to detect automatically) |
| **Degeneration** | `시гля … Arial TTF … Ginseng` — mixed-character blocks · incomplete JSON | Mixed-character ratio · incomplete JSON · `finish_reason=length` |

These three aspects require **different approaches.** While exact duplicates—which become identical upon normalization during iteration—can be **losslessly removed** via post-processing (dedup), fragmentation, token loops, and mixed scripts cannot be restored through post-processing and must therefore be **prevented at the generation stage (parameters)**. This distinction determines "what is resolved via parameters and what is resolved via post-processing" later on.

## 5. Effects by Parameter

Table abbreviations — `obj/act/aud` = average number of objects/actions/audio items, `purity` = Korean / (Korean+Latin), `repeat` = number of records with item duplication or token loops (/70), `comp_p50` = median completion token.

### 5.1. temperature — Lower values yield the cleanest results

| **temp** | **ok** | **comp_p50** | **obj/act/aud** | **purity** | **repeat** |
| --- | --- | --- | --- | --- | --- |
| 0.0 | 69 | 190 | 7.5 / 4.6 / 4.7 | 0.968 | 18 |
| 0.3 | 69 | 191 | 7.5 / 4.6 / 4.8 | 0.979 | 18 |
| 0.7 | 67 | 192 | 7.8 / 5.0 / 4.7 | 0.977 | 17 |
| 1.0 | 66 | 235 | 8.9 / 7.4 / 4.6 | **0.788** | 16 |

As the temperature increases, the *failure mode* changes. At temp 0.7, severe repetition occurs (e.g., repeated arrays like `무장` ×9, 63 redundant items), while at temp 1.0, mixed-character word salad (e.g., `시гля` · `Arial TTF`) occurs, causing the Korean purity to drop to **0.79**. **0.0–0.3 is the cleanest**. This is the exact opposite of the common "raise temp to stabilize" recommendation — for short guided-JSON outputs, greedy (temp=0) is the most stable.

### 5.2. frequency / repetition penalty — The repetition lever; single items are also penalized

| **Setting** | **obj/act/aud** | **repeat** | **Remarks** |
| --- | --- | --- | --- |
| No penalty (baseline) | 7.5 / 4.6 / 4.7 | 18 | — |
| freq 0.5 | 6.2 / 2.8 / 2.8 | 6 | Restores fragmented narration to a single sentence |
| freq 1.0 | 5.4 / 2.3 / 2.4 | 4 | Actual items (sea, camera) also begin to be omitted |
| freq 2.0 | 4.6 / 2.1 / **1.6** | 1 | Audio drops sharply |
| rep 1.1 | 6.3 / 3.8 / 3.6 | 6 | Similar behavior to freq |
| rep 1.3 | 4.7 / 3.3 / **1.3** | 1 | Sharp drop in audio |

The penalty directly reduces repetitions. Simply lowering freq from 0 to 0.5 reduces the number of repeated records from 18 to 6, with zero failures, and even **restores scattered narration fragments into a single sentence**. However, there is a cost—as the penalty increases, the number of items decreases as well; at freq 2.0 and rep 1.3, audio drops by more than half (4.7→1.6 / 1.3). **It is impossible to determine without a ground truth whether this reduction in count constitutes "redundancy removal (good)" or "deletion of actual information (bad)"** — this is the central issue in Sections 6 and 7.

### 5.3. top_k / top_p / fps — Virtually Independent of Repetition

- **top_k / top_p** (temp=0.7 anchor): Narrowing down the candidates *slightly* reduces repetition (17→14, 19→15). This effect is not decisive.

- **fps** (0.5 / 1.0 / 2.0): The number of duplicate records ranges from 16 to 21, showing **no correlation** with changes in fps. Since fps is a factor affecting visual detail and token volume, it should be viewed from the perspective of *accuracy* (next step) rather than adaptability.

## 6. Key Findings

1. **Duplication is common — approximately 26% (18/70)** of items are duplicates in the default settings. This occurs mainly in `audio` (repeated background sounds and short interjections like `ah` / `right`) and `actions`, and is hardly reduced by adjusting temperature, top_k, top_p, or fps (flat response).

1. **Failure patterns differ by temperature range** (5.1): temp 0.7 = severe repetition, temp 1.0 = out-of-context characters. **Low temperatures (≤0.3) produce the cleanest results**.

1. **Frequency and repetition penalties are the true levers for controlling repetition** (in contrast to temperature and top_k). Just by increasing freq from 0 to 0.5, repetitions drop from 18 to 6 with 0 failures; moreover, **it doesn’t just hide the error—it actually fixes it** — restoring three fragmented pieces of narration into a single complete sentence.

1. **However, the penalty’s ***magnitude*** **is not determined in Stage 1 (the core of integrity).** Increasing the penalty reduces the number of items, but **without a ground truth, we cannot distinguish whether this reduction is “removing redundancy (good)” or “deleting actual information (bad).”** In fact, in one case (a news clip), the penalty caused the number of items to decrease *by merging fragments*, so the direction was exactly the opposite. Since there is no signal to observe recall, the optimal size is deferred to the next step (Gemini objective function) — this is not a limitation but **a principle of drawing conclusions only from what is measurable**.

1. **Obvious exact duplicates are resolved via deduplication (no penalty required).** By definition, normalized deduplication results in zero information loss — while duplicate records decrease from 18 to **4** (the remaining ones are fragments or token loops), the number of unique items remains nearly constant at 7.5 → 7.4. In other words, **most duplicates can be eliminated through post-processing without sacrificing recall via penalties.**

