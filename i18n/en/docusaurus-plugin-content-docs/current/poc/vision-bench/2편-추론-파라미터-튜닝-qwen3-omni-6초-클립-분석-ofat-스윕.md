---
title: "[Part 2] Inference Parameter Tuning: Analysis of a 6-Second Clip Using Qwen3-Omni (OFAT Sweep)"
sidebar_position: 3
slug: "3"
last_update:
  date: 2026-06-29
---

## 1. Introduction

SceneMaker’s video clip analysis aims to **reliably extract visual and auditory information** from video clips. It takes a 6-second clip as input and structures the audiovisual information into four fields in `{summary, ocr, actions, sounds}` JSON format.

- **Comprehensive Analysis** 
  - `summary`: A one-sentence summary combining visual and auditory information

- **Visual Analysis** 
  - `ocr` (On-screen text: subtitles, logos)

  - `actions` (Actions, movements, etc.)

- **Auditory Analysis**
  - `sounds` (Sound effects: applause, typing, etc.)

**Stability is key**. If the output is inconsistent, the quality score cannot be trusted. During the first round of validation, four patterns of quality degradation that threaten this were intermittently detected.

1. **Premature EOS**: Outputs an EOS (end-of-sentence) token right from the first token, causing the content to end as an empty string. This occurs when the model “runs out of things to say” and closes immediately
2, often due to excessive constraints from a strict JSON schema. **Text Degeneration**: The model loses its normal probability distribution, spews out random characters and system tokens, and crashes before completing the JSON.(Gibberish Generation)
3... **Repetition Loop**: The model gets stuck in a probability trap, repeatedly generating the same words,
4items, or JSON structures... **Runaway / Incomplete**: Fails to produce a termination token and continues generating up to `max_tokens` (512), resulting in the JSON being truncated before completion (`finish_length`). This is the exact opposite failure of early termination.

This part investigates whether these patterns can be controlled via inference parameters. This is because Part 1 merely observed and identified the four patterns, without addressing whether they could be controlled via parameters.  
The premise is that the output is fixed to strict JSON Schema. Focusing on prominent issues such as loops and degeneration that occur even under these conditions, this is the initial adjustment phase where we significantly vary the parameters one at a time (OFAT) to determine which ones can be controlled.

## 2. Experimental Environment

The experiments were conducted using **the same model, serving environment, and invocation path** as the benchmark. This was done to observe the effects of the parameters in that exact environment. Detailed information on the environment configuration can be found in Part 1, “Building a Benchmark Pipeline for Multimodal LLM Understanding of 6-Second Korean Broadcast Video Clips”; therefore, this section covers only a key summary and the **parameters targeted for tuning** in this experiment.

### 2.1. Environment Summary

- **Model** 
  - Qwen3-Omni-30B-A3B-Instruct (Thinker–Talker MoE, total inference core size: 30B, active: 3B). 

  - Processes four modalities—Image, Video, Audio, and Text—using a single model; this PoC uses only text output.

- **Serving**
  - vLLM serving on a single AWS g7e.4xlarge GPU (NVIDIA RTX PRO 6000 Blackwell, 96 GB).

  - The actual serving size `--max-model-len` is 16,384; be mindful of context overflow when dealing with high resolution or high fps.

- **Call Path**
  - Client (inference request) → Gateway (same as the gateway in Part 1) → vLLM → Qwen 3 Omni

  - The request passes through a lightweight gateway (FastAPI) in front of the vLLM. It passes the inference payload without modification, adding only concurrency gates (default 4) and batch NDJSON streaming. This sweep sends a fixed set of 70 clips in a single request and collects results in the order they are completed.

:::note
📎 For details on model specifications, serving settings, and gateway routes, refer to Part 1 of this series: [Building a Benchmark Pipeline for Multimodal LLM Understanding of 6-Second Clips from Korean Broadcasts](/docs/poc/vision-bench/1).
:::

### 2.2. Parameters for Tuning

Inference parameters are not configured on the server but are **specified directly by the client in the request body**. Parameters are divided into two categories based on the operational layer: **vLLM input processing** (preparation before feeding media into the model) and **Qwen3-Omni generation sampling** (decoding, where the model generates output). In this experiment, the OFAT sweep varies only the *generative sampling* group one parameter at a time, while keeping the rest fixed across the entire range.

##### **1. Qwen3-Omni Generative Sampling Parameters** (*Autoregressive Decoding · Sampling Strategies*).

| **Parameter** | **Role** | **Value Range** | **This Experiment** |
| --- | --- | --- | --- |
| `temperature` | Sampling temperature; lower values are more deterministic | `[0, 2]` (default 1.0) | **Variable** |
| `top_k` | Limits candidates to the top k by probability | Works only when `-1` = disabled / `≥1` (default -1) `0 < temperature` | **Variability** |
| `top_p` | Nucleus cutoff; only top candidates by cumulative probability | Works only when `(0, 1]` (default 1.0) and `0 < temperature` | **Variable** |
| `frequency_penalty` | Additive iteration suppression (proportional to occurrence count) | Works only when `[-2, 2]` · `0` = Disabled (default 0.0) | **Variable** |
| `repetition_penalty` | Suppresses multiplicative repetition (based on occurrence) | `>0` · `1` = Disabled · `>1` = Suppressed | **Variable** |
| `max_tokens` | Upper limit on completion tokens (output length cap) | `>0` · within remaining context | Fixed at 512 |
| `chat_template_kwargs.enable_thinking` | Thinking token generation on/off | `true` / `false` | Fixed at false  |
| `seed` | Reproducibility (same input → same output when fixed) | Integer · `<0` = Disabled (random each time) | Fixed at -1  |

##### **2. vLLM Input Processing Parameters** (*Multimodal Ingestion · Context Conditioning*)

| **Parameter** | **Role** | **Value Range** | **This Experiment** |
| --- | --- | --- | --- |
| `media_io_kwargs.video.fps` | Video frame extraction rate | `>0`  | Fixed at `0.5` |
| `use_audio_in_video` | Simultaneous audio decoding from MP4 | `true` / `false`  | Fixed at `true` |

:::note
📌 `frequency_penalty` **vs** `repetition_penalty` → Both suppress repetition, but their methods differ.

- **frequency (addition/subtraction)**
The more a token has already appeared, the greater the penalty (proportional to frequency, cumulative) → Strong at suppressing repetition (`공 공 공…`). **Only output tokens** are counted.

- **repetition (multiplication/division)**
If a token appears even once, it is reduced by a **fixed ratio** (based solely on presence, regardless of frequency). Since vLLMs examine both the **prompt and output**, even prompt vocabulary can be suppressed.

- Enabling both results in **double over-suppression**.
:::

### 2.3. Output Schema / Hallucination Guard

This experiment **keeps the output contract fixed without modification** while varying only the parameters. The response is fixed to **exactly** `{summary, ocr, actions, sounds}` **fields**.

- vLLM `response_format=json_schema(strict=True)`
- pydantic `extra="forbid"` 

Since this is a dual constraint, the output can be saved as-is without any post-processing (parsing, cleaning, or adding/removing fields). 

In the SceneMaker project, dialogue (STT) analysis is handled by a separate WhisperX module; for the Qwen3 Omini model, it is designed as `sounds` to include analysis of background noise and sound effects.

| **Field** | **Definition and Guidelines** |
| --- | --- |
| `summary` (string) | A single-sentence summary in Korean that integrates visual and auditory information. Do not copy the expressions from individual fields verbatim. |
| `ocr` (array of string) | Text visible on screen, exactly as it appears in the original. |
| `actions` (array of string) | Verb phrases describing actions, movements, and scene transitions in the video (without duplication). |
| `sounds` (array of string) | Sound effects other than dialogue (e.g., applause, typing, footsteps). |

:::note
🎙️ Dialogue (speech) transcription is handled by a separate WhisperX audio module and is therefore excluded from this schema. The model listens to the audio (`use_audio_in_video` on) but does not transcribe it; it only describes non-speech(`sounds` ) only.
:::

## 3. Methodology

### 3.1. Samples and Design

- **Fixed 70 samples**: 10 clips across 7 genres, each 6 seconds long. All settings use **the same sample and the same prompt**.
- **OFAT Sweep:** Only one parameter is varied across multiple levels while keeping all others fixed, allowing us to observe the effect of that variable alone.
- **Sampling Isolation**: top_p, top_k, and penalty sweeps are all run at temp=0.7 (since top_p and top_k have no effect at temp=0, and the baseline is also set to 0.7, the penalty is evaluated at 0.7 as well).

:::note
📖 **Glossary**

- **Sweep**: The process of stepping through the values of a single parameter in multiple stages (e.g., `temperature` 0 → 0.3 → 0.7 → 1.0) and measuring the output at each stage. The **OFAT sweep** in this experiment sweeps only one axis while keeping other parameters fixed, thereby isolating the effect of that single parameter.
- **greedy (greedy decoding)**: Decoding that selects only the single token with the highest probability (argmax) at each step. `temperature=0` This is the greedy approach; since it lacks randomness, the same input yields the same output (deterministic). The opposite is **sampling** (`top_k` ·`top_p` ·`temperature`), which selects candidates randomly based on probabilities.
:::

### 3.2. What Can Be Measured by Output Alone? Adherence vs. Quality

The evaluation of analysis output is divided into two distinct categories. To use an exam analogy, one is whether the answer is disqualified, and the other is the score for the answer.

- Adherence = Disqualification axis. No matter how excellent the answer may be, it is disqualified if the paper is blank, written in a foreign language, or violates the specified format. Only the rules are considered, regardless of the quality of the content.
- Quality = The scoring axis. Once disqualification is avoided, the analysis is actually graded based on how accurate and comprehensive it is.

| **Category** | **Evaluation Target** | Determined by Output Alone |
| --- | --- | --- |
| **Adherence** | Is it in Korean? · Is the JSON format correct? · Are the items concise? · Are there any repetitions? | Possible |
| **Quality** | Completeness (Are there any omissions?) · Accuracy (Are there any hallucinations?) | Not possible |

Adherence is a necessary but not sufficient condition. It merely ensures the submission is not disqualified; it does not guarantee that the content is correct. Establish the rules first, and improve quality later.

### 3.3. Metrics

The following metrics are aggregated to detect and quantify the four patterns of quality degradation. Each metric targets one or more of the anomalies listed above. `fields` and `score` (repeat·degen) are converted to a ratio between 0 and 1 (1.0 = 100%) and evaluated as such.

| **Metric** | **Definition** | **What It Measures** |
| --- | --- | --- |
| `ok` / `fail` | Number of records passing/failing schema validation | Format compliance · Premature termination |
| `inference_ms` (avg·p50·p95·min·max) | Inference time per clip (ms) | Inference time variance |
| `fields`  | Percentage of fields with values (`summary` ·`ocr` ·`actions` ·`sounds` ) | Information coverage |
| `score.repeat` | Percentage of records containing identical items within the array. | Duplication |
| `score.degen` | Ratio by failure signal. `foreign` (heterogeneous characters) · `finish_length` (max_tokens reached = incomplete/aborted) · `replacement` (broken multibyte) | Failure |

## **4. Effects by Parameter**

This section covers the target parameters that were adjusted one at a time (OFAT).

- `temperature` : 0.0 / 0.3 / 0.7 / 1.0
- `top_k / top_p`
  - `top_k` : 1 / 10 / 50 / -1 (temp=0.7)

  - `top_p` : 0.5 / 0.8 / 0.95 / 1.0 (temp=0.7)

- `frequency_penalty / repetition_penalty` (temp=0.7)
  - `frequency_penalty` : 0.0 / 0.5 / 1.0 / 2.0

  - `repetition_penalty` : 1.0 / 1.05 / 1.1 / 1.3

The evaluation criteria for this section are not "richly expressed configurations" but rather "**configurations with the fewest obvious defects (incompleteness, mixed characters, repetition, or runaway values)** ." Increased coverage or the number of items may be the result of hallucinations (overgeneration) and will not be counted as bonus points.

### 4.0. Test Data Preparation and Execution Method

All configurations examine **the same 70 clips**: 7 genres × 10 clips per category. 

`make_sample.py` collects them in `data/sample70/` **using only symlinks**, without copying or re-encoding the original MP4 files. Video derivatives are managed **in a single location** at `data/`, so for copyright purposes, deleting just one file at `data/` clears them all at once (symlinks are `*.mp4` and are not committed via `gitignore`).

1. Sample Preparation
   ```bash
   # 10 items per category, evenly spaced → symlinks to data/sample70/ (70 in total)
   python make_sample.py
   ```

2. Single-run test (to verify normal server and schema operation)
   ```bash
   # Send only one clip to check the server and schema responses (single clip, no batch)
   python run.py ../../data/sample70/news__0001_0600-0606.mp4 --no-batch --verbose
   ```

3. Main OFAT sweep execution
   ```bash
   Call #run.py one line at a time for each setting (temperature, top_pk, freq_repe, fps, thinking).
   # Automatically detects the next episode number in the #sweep_out/ directory. Specify the number of episodes as an argument (default is 1).
   bash sweep.sh 4   # Cumulative total for the next 4 rounds → N=4
   ```

### 4.1. Temperature

**Average per run** (Runs 1, 2, 3, and 4 · n=70 each)

:::note
📐 `penalty` = (`repeat` + `finish_length` + `foreign` + `replacement`) ÷ 4 → Average

`field` = (`summary` + `ocr` + `actions` + `sounds`) ÷ 4 → Average coverage.
:::

| **temp** | **ok/fail** | infer_ms | **penalty** | **field** |
| --- | --- | --- | --- | --- |
| 0.0 | 83.21% | 2731 | 8.9% | 95.7% |
| 0.3 | 83.93% | 2735 | 8.9% | 95.3% |
| 0.7 | 87.50% | 2818 | **7.5%** | **96.0%** |
| 1.0 | **92.14%** | 2863 | 14.4% | 93.4% |

<details>
<summary>📊 History by Round (Rounds 1, 2, 3, 4)</summary>

| **Episode** | **temp** | ok | infer_ms | repeat | foreign | finish_len | replacement | penalty | summary | ocr | actions | sounds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.0 | 81.43% | 2834.1 | 17.10% | 0.00% | 18.60% | 0.00% | 8.93% | 100.00% | 91.20% | 100.00% | 91.20% |
| 2 | 0.0 | 82.86% | 2751.9 | 17.10% | 0.00% | 17.10% | 0.00% | 8.55% | 100.00% | 91.40% | 100.00% | 93.10% |
| 3 | 0.0 | 84.29% | 2653.5 | 21.40% | 0.00% | 15.70% | 0.00% | 9.28% | 100.00% | 91.50% | 100.00% | 91.50% |
| 4 | 0.0 | 84.29% | 2685.3 | 20.00% | 0.00% | 15.70% | 0.00% | 8.93% | 100.00% | 91.50% | 100.00% | 89.80% |
| 1 | 0.3 | 85.71% | 2656.7 | 18.60% | 0.00% | 14.30% | 0.00% | 8.22% | 100.00% | 90.00% | 100.00% | 90.00% |
| 2 | 0.3 | 81.43% | 2781.2 | 18.60% | 0.00% | 18.60% | 0.00% | 9.30% | 100.00% | 87.70% | 100.00% | 93.00% |
| 3 | 0.3 | 87.14% | 2665.1 | 25.70% | 0.00% | 12.90% | 0.00% | 9.65% | 100.00% | 88.50% | 100.00% | 90.20% |
| 4 | 0.3 | 81.43% | 2,838.7 | 15.70% | 0.00% | 18.60% | 0.00% | 8.57% | 100.00% | 89.50% | 100.00% | 96.50% |
| 1 | 0.7 | 91.43% | 2718.6 | 27.10% | 1.40% | 8.60% | 0.00% | 9.28% | 100.00% | 90.60% | 100.00% | 95.30% |
| 2 | 0.7 | 84.29% | 3086.3 | 10.00% | 0.00% | 15.70% | 0.00% | 6.43% | 100.00% | 89.80% | 100.00% | 93.20% |
| 3 | 0.7 | 85.71% | 2763.9 | 14.30% | 0.00% | 14.30% | 0.00% | 7.15% | 100.00% | 90.00% | 100.00% | 93.30% |
| 4 | 0.7 | 88.57% | 2702.9 | 17.10% | 0.00% | 11.40% | 0.00% | 7.13% | 100.00% | 90.30% | 100.00% | 93.50% |
| 1 | 1.0 | 88.57% | 2924.9 | 11.40% | 35.70% | 11.40% | 1.40% | 14.98% | 100.00% | 88.70% | 100.00% | 88.70% |
| 2 | 1.0 | 94.29% | 3085.7 | 17.10% | 38.60% | 5.70% | 0.00% | 15.35% | 100.00% | 89.40% | 98.50% | 90.90% |
| 3 | 1.0 | 91.43% | 2758.1 | 12.90% | 35.70% | 8.60% | 0.00% | 14.30% | 100.00% | 90.60% | 98.40% | 81.20% |
| 4 | 1.0 | 94.29% | 2683.7 | 14.30% | 31.40% | 5.70% | 0.00% | 12.85% | 100.00% | 84.80% | 98.50% | 84.80% |

</details>

#### **Key Metrics Comparison Table (Benchmark Matrix)**

| **Evaluation Metric** | **Greedy (0.0)** | **Sweet Spot (0.7)** | **High Temp (1.0)** |
| --- | --- | --- | --- |
| **Completion Rate (ok)** | 83.21% | 87.50% | **92.14% (Best)** |
| Penalty | 8.9% | **7.5% (Lowest)** | 14.4% (Worst) |
| **Foreign Characters** | 0% | 0.35% | **35.4% (Surge)** |

#### 1. Trade-off Between Completion Rate and Penalty

- Temperature and completion rate are directly proportional
  - As the value increases, the metrics for runaways and incomplete runs (`finish_length`) decrease from 16.8% to 7.9%, leading to a rise in the completion rate

- The Pitfall of High Temperature (1.0)
  - While the completion rate reached its peak, it was accompanied by output corruption, causing the penalty to surge to 14.4%.

- Optimization at Temperature 0.7
  - Achieved a completion rate of 87.5% while recording the lowest penalty (7.5%) across all temperature ranges.

#### 2. Foreign Characters and Repetition

- **Temperature 1.0 resulted in severe defects**
  - Foreign character occurrence rate surged to 35.4%

- **Temperature 0.7 is within the safe range**
  - The foreign character occurrence rate in the Temp 0.0–0.7 range is very stable at 0–0.35%

- **Temperature is not a “loop control lever”**
  - The repetition rate remains stable at 14%–20% without significant fluctuation

:::note
💡 **Conclusion = Temperature 0.7**
Greedy (0.0) yields inconsistent results from run to run, so it lacks even the advantage of “determinism,” and its penalty (8.9%) is higher than that of 0.7. 1.0 has the highest completion rate, but the penalty doubles (14.4%) due to the occurrence of out-of-type characters. In contrast, 0.7 has the lowest penalty (7.5%) and virtually no out-of-class characters, making it the optimal balance with the fewest defects.
:::

### 4.2. top_k / top_p

**Average per Round** (Rounds 1, 2, 3, 4 · anchor temperature=0.7 · n=70 for each)

| **Setting** | **ok/fail** | infer_ms | **penalty** | **field** |
| --- | --- | --- | --- | --- |
| top_k 1 | 82.14% | 2804 | 7.9% | 95.9% |
| top_k 10 | **92.50%** | 2447 | **6.7%** | 94.5% |
| top_k 50 | 90.71% | 2566 | 8.4% | 95.3% |
| top_k -1 | 87.86% | 2677 | 7.6% | 94.6% |
| top_p 0.5 | **78.57%** | 2958 | 8.9% | 95.4% |
| top_p 0.8 | 85.00% | 2,773 | 7.5% | 95.6% |
| top_p 0.95 | 87.50% | 2,627 | 7.2% | 95.4% |
| top_p 1.0 | 90.36% | 2572 | 7.2% | 94.7% |

<details>
<summary>📊 History by Round (Rounds 1, 2, 3, 4)</summary>

| **Iteration** | **Settings** | ok | infer_ms | repeat | foreign | finish_len | replacement | penalty | summary | ocr | actions | sounds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | top_k 1 | 82.86% | 2859.7 | 11.40% | 0.00% | 17.10% | 0.00% | 7.13% | 100.00% | 91.40% | 100.00% | 94.80% |
| 2 | top_k 1 | 81.43% | 2825.5 | 12.90% | 0.00% | 18.60% | 0.00% | 7.88% | 100.00% | 91.20% | 100.00% | 93.00% |
| 3 | top_k 1 | 84.29% | 2690.4 | 17.10% | 0.00% | 15.70% | 0.00% | 8.20% | 100.00% | 91.50% | 100.00% | 89.80% |
| 4 | top_k 1 | 80.00% | 2842 | 12.90% | 0.00% | 20.00% | 0.00% | 8.23% | 100.00% | 91.10% | 100.00% | 91.10% |
| 1 | top_k 10 | 92.86% | 2438.9 | 20.00% | 0.00% | 7.10% | 0.00% | 6.78% | 100.00% | 86.20% | 100.00% | 89.20% |
| 2 | top_k 10 | 91.43% | 2458.6 | 18.60% | 0.00% | 8.60% | 0.00% | 6.80% | 100.00% | 89.10% | 100.00% | 93.80% |
| 3 | top_k 10 | 94.29% | 2377.5 | 14.30% | 0.00% | 5.70% | 0.00% | 5.00% | 100.00% | 86.40% | 100.00% | 90.90% |
| 4 | top_k 10 | 91.43% | 2512.1 | 24.30% | 0.00% | 8.60% | 0.00% | 8.22% | 100.00% | 89.10% | 100.00% | 87.50% |
| 1 | top_k 50 | 91.43% | 2511.2 | 17.10% | 2.90% | 8.60% | 0.00% | 7.15% | 100.00% | 84.40% | 100.00% | 89.10% |
| 2 | top_k 50 | 90.00% | 2559.5 | 25.70% | 0.00% | 10.00% | 0.00% | 8.93% | 100.00% | 88.90% | 100.00% | 95.20% |
| 3 | top_k 50 | 91.43% | 2554.7 | 28.60% | 0.00% | 8.60% | 0.00% | 9.30% | 100.00% | 89.10% | 100.00% | 90.60% |
| 4 | top_k 50 | 90.00% | 2640 | 22.90% | 0.00% | 10.00% | 0.00% | 8.23% | 100.00% | 92.10% | 100.00% | 95.20% |
| 1 | top_k -1 | 85.71% | 2800.3 | 14.30% | 1.40% | 14.30% | 0.00% | 7.50% | 100.00% | 85.00% | 100.00% | 86.70% |
| 2 | top_k -1 | 87.14% | 2715 | 21.40% | 0.00% | 12.90% | 0.00% | 8.57% | 100.00% | 86.90% | 100.00% | 90.20% |
| 3 | top_k -1 | 88.57% | 2682 | 17.10% | 0.00% | 11.40% | 0.00% | 7.13% | 100.00% | 88.70% | 100.00% | 96.80% |
| 4 | top_k -1 | 90.00% | 2508.9 | 18.60% | 0.00% | 10.00% | 0.00% | 7.15% | 100.00% | 90.50% | 100.00% | 88.90% |
| 1 | top_p 0.5 | 75.71% | 3144 | 11.40% | 0.00% | 24.30% | 0.00% | 8.93% | 100.00% | 90.60% | 100.00% | 86.80% |
| 2 | top_p 0.5 | 80.00% | 2901.2 | 17.10% | 0.00% | 20.00% | 0.00% | 9.28% | 100.00% | 91.10% | 100.00% | 96.40% |
| 3 | top_p 0.5 | 81.43% | 2825.9 | 12.90% | 0.00% | 18.60% | 0.00% | 7.88% | 100.00% | 91.20% | 100.00% | 91.20% |
| 4 | top_p 0.5 | 77.14% | 2962.4 | 15.70% | 0.00% | 22.90% | 0.00% | 9.65% | 100.00% | 90.70% | 100.00% | 88.90% |
| 1 | top_p 0.8 | 87.14% | 2817.3 | 18.60% | 1.40% | 12.90% | 0.00% | 8.23% | 100.00% | 91.80% | 100.00% | 95.10% |
| 2 | top_p 0.8 | 88.57% | 2563.2 | 15.70% | 0.00% | 11.40% | 0.00% | 6.78% | 100.00% | 91.90% | 100.00% | 90.30% |
| 3 | top_p 0.8 | 84.29% | 2826.6 | 14.30% | 0.00% | 15.70% | 0.00% | 7.50% | 100.00% | 89.80% | 100.00% | 91.50% |
| 4 | top_p 0.8 | 80.00% | 2883.2 | 10.00% | 0.00% | 20.00% | 0.00% | 7.50% | 100.00% | 85.70% | 100.00% | 92.90% |
| 1 | top_p 0.95 | 87.14% | 2699.7 | 20.00% | 0.00% | 12.90% | 0.00% | 8.23% | 100.00% | 88.50% | 100.00% | 93.40% |
| 2 | top_p 0.95 | 90.00% | 2542.2 | 18.60% | 0.00% | 10.00% | 0.00% | 7.15% | 100.00% | 88.90% | 100.00% | 93.70% |
| 3 | top_p 0.95 | 88.57% | 2559.9 | 12.90% | 0.00% | 11.40% | 0.00% | 6.08% | 100.00% | 87.10% | 100.00% | 93.50% |
| 4 | top_p 0.95 | 84.29% | 2707.3 | 14.30% | 0.00% | 15.70% | 0.00% | 7.50% | 100.00% | 89.80% | 100.00% | 91.50% |
| 1 | top_p 1.0 | 88.57% | 2609.7 | 15.70% | 0.00% | 11.40% | 0.00% | 6.78% | 100.00% | 90.30% | 100.00% | 91.90% |
| 2 | top_p 1.0 | 90.00% | 2612.3 | 22.90% | 0.00% | 10.00% | 0.00% | 8.23% | 100.00% | 87.30% | 100.00% | 92.10% |
| 3 | top_p 1.0 | 87.14% | 2724 | 15.70% | 1.40% | 12.90% | 0.00% | 7.50% | 100.00% | 86.90% | 100.00% | 91.80% |
| 4 | top_p 1.0 | 95.71% | 2341.5 | 18.60% | 2.90% | 4.30% | 0.00% | 6.45% | 100.00% | 83.60% | 100.00% | 91.00% |

</details>

detailsop_k and top_p are fine-tuning knobs applied on top of temperature. The results fall into three categories: **over-tightening is detrimental, unrestricted (default) is safe, and top_k 10 yields the single best completion rate**. In contrast, iterations and coverage remain unaffected by any of these knobs.

#### **Key Metrics Comparison Table**

| **Evaluation Metrics** | **Overfitting (top_k 1 / top_p 0.5)** | **Default (top_k -1 / top_p 1.0)** | **top_k 10 (Candidate)** |
| --- | --- | --- | --- |
| **Completion Rate (ok)** | 82.1% **/** 78.6% | 87.9% / 90.4% | **92.5% (Best)** |
| **Penalty** | 7.9% / 8.9% | 7.6% / 7.2% | **6.7% (Best)** |
| **Incomplete (finish_len)** | 17.9% / 21.5% | 12.2% / 9.7% | **7.5% (Best)** |
| **Repeat** | 13.6% / 14.3% | 17.8% / 18.2% | 19% |
| **Coverage (field)** | 95.9% / 95.4% | 94.6% / 94.7% | 94.5% |
| **Foreign characters** | 0% / 0% | 0.4% / 1.1% | 0% |

#### 1. The completion rate is highest when the settings are “moderately loose”—neither too strict nor too lenient

- **Backfire of Over-Tightening**
  - With top_k = 1 and top_p = 0.5, finish_len is 18 / 21%, and the completion rates are 82% / 79%—the worst results. This causes runaway behavior similar to the Greedy algorithm.

- **Internal Optimization**
  - As top_k varies from 1→10→50→-1, the completion rate peaks at k=10 (92.5%) and then declines again as it approaches the unlimited setting (-1, 87.9%). It appears that a mild top-k cut filters out tail noise, making completion rates more stable.

#### 2. Not adjustment values for repetition or coverage

- **repeat: flat, no trend**
  - No trend across the entire range (14–24%; even top_k 10 is 19%) → This is not a repeat control (repeat is driven by deduplication and frequency penalty).

- **Coverage remains intact**
  - Field remains flat at 94–96% across all intervals → No setting trims the content (even the truncation in top_k 10 shows no visible loss).

#### 3. top_k 10 = Candidate for completion rate

- **Single Best**
  - OK 92.5% (91%+ in all 4 runs · floor 91.4% · lowest variance ±1.2) · penalty 6.7% — both ranked 1st out of 8 settings, with a +2–5p improvement over the default, so this is not noise.

- **Cost of verification**
  - It is not possible to determine from the output alone whether the top-10 cut misses rare correct tokens (unusual OCR, rare sound effects) (flat coverage)

### 4.3. Frequency / Repetition Penalty

**Average per run** (Runs 1, 2, 3, 4 · anchor temperature=0.7 · n=70 for each)

| **Setting** | **ok/fail** | infer_ms | **penalty** | **field** |
| --- | --- | --- | --- | --- |
| freq 0.0 | 90.00% | 2589 | 7.0% | 94.0% |
| freq 0.5 | **99.64%** | 2012 | **2.0%** | 92.0% |
| freq 1.0 | 100% | 1934 | 1.6% | 88.2% |
| freq 2.0 | 98.57% | 1988 | 2.0% | 81.6% |
| rep 1.0 | 90.00% | 2646 | 8.2% | 94.6% |
| rep 1.05 | 96.07% | 2217 | 4.0% | 93.9% |
| rep 1.1 | 99.64% | 1950 | 3.7% | 92.7% |
| rep 1.3 | 99.64% | 1,629 | 2.0% | **82.4%** |

<details>
<summary>📊 History by Round (Rounds 1, 2, 3, 4)</summary>

| **Iteration** | **Settings** | ok | infer_ms | repeat | foreign | finish_len | replacement | penalty | summary | ocr | actions | sounds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | freq 0.0 | 90.00% | 2585.3 | 14.30% | 0.00% | 10.00% | 0.00% | 6.08% | 100.00% | 88.90% | 100.00% | 84.10% |
| 2 | freq 0.0 | 88.57% | 2731.5 | 17.10% | 0.00% | 11.40% | 0.00% | 7.13% | 100.00% | 87.10% | 100.00% | 88.70% |
| 3 | freq 0.0 | 91.43% | 2550.6 | 22.90% | 1.40% | 8.60% | 0.00% | 8.23% | 100.00% | 87.50% | 100.00% | 90.60% |
| 4 | freq 0.0 | 90.00% | 2487.4 | 14.30% | 1.40% | 10.00% | 0.00% | 6.43% | 100.00% | 87.30% | 100.00% | 88.90% |
| 1 | freq 0.5 | 100.00% | 1945.9 | 8.60% | 0.00% | 0.00% | 0.00% | 2.15% | 100.00% | 91.40% | 100.00% | 78.60% |
| 2 | freq 0.5 | 100.00% | 2033.3 | 7.10% | 1.40% | 0.00% | 0.00% | 2.12% | 100.00% | 88.60% | 100.00% | 78.60% |
| 3 | freq 0.5 | 98.57% | 2044.2 | 10.00% | 0.00% | 1.40% | 0.00% | 2.85% | 100.00% | 85.50% | 100.00% | 79.70% |
| 4 | freq 0.5 | 100.00% | 2023.8 | 2.90% | 0.00% | 0.00% | 0.00% | 0.73% | 100.00% | 90.00% | 100.00% | 80.00% |
| 1 | freq 1.0 | 100.00% | 1997.3 | 5.70% | 2.90% | 0.00% | 0.00% | 2.15% | 100.00% | 90.00% | 98.60% | 68.60% |
| 2 | freq 1.0 | 100.00% | 1909.7 | 1.40% | 1.40% | 0.00% | 0.00% | 0.70% | 100.00% | 88.60% | 95.70% | 67.10% |
| 3 | freq 1.0 | 100.00% | 1893.7 | 2.90% | 1.40% | 0.00% | 0.00% | 1.08% | 100.00% | 91.40% | 100.00% | 62.90% |
| 4 | freq 1.0 | 100.00% | 1935.4 | 10.00% | 0.00% | 0.00% | 0.00% | 2.50% | 100.00% | 87.10% | 100.00% | 61.40% |
| 1 | freq 2.0 | 98.57% | 1984.1 | 8.60% | 5.70% | 1.40% | 0.00% | 3.93% | 100.00% | 85.50% | 95.70% | 44.90% |
| 2 | freq 2.0 | 98.57% | 2046.9 | 0.00% | 2.90% | 1.40% | 1.40% | 1.43% | 100.00% | 88.40% | 98.60% | 37.70% |
| 3 | freq 2.0 | 98.57% | 1968.1 | 2.90% | 1.40% | 1.40% | 0.00% | 1.43% | 100.00% | 85.50% | 95.70% | 44.90% |
| 4 | freq 2.0 | 98.57% | 1951.4 | 2.90% | 0.00% | 1.40% | 0.00% | 1.08% | 100.00% | 84.10% | 98.60% | 44.90% |
| 1 | rep 1.0 | 94.29% | 2534.6 | 24.30% | 4.30% | 5.70% | 0.00% | 8.57% | 100.00% | 87.90% | 100.00% | 92.40% |
| 2 | rep 1.0 | 87.14% | 2718.6 | 20.00% | 0.00% | 12.90% | 0.00% | 8.23% | 100.00% | 86.90% | 100.00% | 95.10% |
| 3 | rep 1.0 | 91.43% | 2557.9 | 17.10% | 1.40% | 8.60% | 0.00% | 6.78% | 100.00% | 87.50% | 100.00% | 90.60% |
| 4 | rep 1.0 | 87.14% | 2771.5 | 22.90% | 1.40% | 12.90% | 0.00% | 9.30% | 100.00% | 85.20% | 100.00% | 88.50% |
| 1 | rep 1.05 | 94.29% | 2251.1 | 7.10% | 0.00% | 5.70% | 0.00% | 3.20% | 100.00% | 83.30% | 100.00% | 84.80% |
| 2 | rep 1.05 | 95.71% | 2243.5 | 8.60% | 0.00% | 4.30% | 0.00% | 3.23% | 100.00% | 89.60% | 100.00% | 88.10% |
| 3 | rep 1.05 | 98.57% | 2087.9 | 11.40% | 1.40% | 1.40% | 0.00% | 3.55% | 100.00% | 85.50% | 100.00% | 92.80% |
| 4 | rep 1.05 | 95.71% | 2285.4 | 17.10% | 2.90% | 4.30% | 0.00% | 6.08% | 100.00% | 89.60% | 100.00% | 88.10% |
| 1 | rep 1.1 | 100.00% | 2035.8 | 14.30% | 4.30% | 0.00% | 0.00% | 4.65% | 100.00% | 91.40% | 98.60% | 85.70% |
| 2 | rep 1.1 | 100.00% | 1949 | 15.70% | 0.00% | 0.00% | 0.00% | 3.93% | 100.00% | 85.70% | 100.00% | 82.90% |
| 3 | rep 1.1 | 100.00% | 1827.6 | 12.90% | 2.90% | 0.00% | 0.00% | 3.95% | 100.00% | 91.40% | 100.00% | 78.60% |
| 4 | rep 1.1 | 98.57% | 1988.5 | 7.10% | 0.00% | 1.40% | 0.00% | 2.12% | 100.00% | 87.00% | 100.00% | 81.20% |
| 1 | rep 1.3 | 100.00% | 1641.3 | 1.40% | 8.60% | 0.00% | 0.00% | 2.50% | 100.00% | 87.10% | 80.00% | 68.60% |
| 2 | rep 1.3 | 98.57% | 1711.9 | 0.00% | 8.60% | 1.40% | 0.00% | 2.50% | 100.00% | 91.30% | 75.40% | 59.40% |
| 3 | rep 1.3 | 100.00% | 1654.8 | 0.00% | 5.70% | 0.00% | 1.40% | 1.78% | 100.00% | 88.60% | 77.10% | 61.40% |
| 4 | rep 1.3 | 100.00% | 1509.3 | 0.00% | 5.70% | 0.00% | 0.00% | 1.43% | 100.00% | 90.00% | 78.60% | 61.40% |

</details>

detailsenalty was confirmed to be a lever that significantly boosts completion rates at temperature 0.7. Simply changing freq from 0.0 to 0.5 increased the completion rate from 90% to 99.6% and reduced penalty from 7.0% to 2.0%. However, as the intensity increases, sound coverage decreases proportionally (88% → 79% → 65% → 43%), and it is impossible to determine from the numbers alone whether this reduction represents the removal of redundancy or the loss of information.

#### **Key Metrics Comparison Table**

| **Evaluation Metric** | **Baseline (freq 0.0)** | **freq 0.5 (Candidate)** | **freq 2.0** | **rep 1.3** |
| --- | --- | --- | --- | --- |
| **Completion Rate (ok)** | 90.0% | **99.6%** | 98.6% | 99.6% |
| **Penalty** | 7.0% | **2.0%** | 2.0% | 2.0% |
| **Sound Coverage** | **88%** | 79% | 43% (Collapse) | 63% (collapse) |
| **Foreign characters** | 0.7% | 0.4% | 2.5% | **7.2% (explosion)** |

#### 1. Benefits: Completion Rate and Repetitive Braking

- **Normalization of completion rate**
  - With a frequency of 0.5 alone: OK 90% → 99.6%, finish_len 10% → 0.4%, penalty 7.0% → 2.0%. Reproduced in all 4 runs.

- **Repetition Suppression and Delay Reduction**
  - Repeat rate: 17% → 7% (freq 0.5) → 5% (freq 1.0). As the output duration shortened, infer_ms also decreased from 2589 to 2012 ms.

#### 2. Trade-off: Concomitant reduction in auditory information (sounds)

- **Intensity-Proportional Reduction**
  - Sound coverage drops from 88% to 79% (0.5) to 65% (1.0) to 43% (2.0)

- **Uninterpretable barrier**
  - It is impossible to distinguish whether this is “redundancy removal (good)” or “information deletion (bad)”

- *(Note: summary and actions remain at ~100% across all intervals; OCR also remains at 85–89%)*

#### 3. New defect in Repetition Penalty: Induction of foreign characters

- **Dose-response foreign**
  - In the rep series, the number of foreign characters increases as the intensity is raised.

:::note
💾 **Frequency Penalty 0.5 Candidate · Exclude Repetition Penalty**
The temp 0.7 baseline achieves 90% completion and 10% finish_len—not ideal—but freq 0.5 boosts completion to 99.6%. However, the trade-off involving reduced sound coverage cannot be assessed without a correct answer key. The repetition penalty was excluded because it induces out-of-type characters.
:::

## 5. Summary and Conclusion

Parameter characteristics fall into three types: early-stage optimal/late-stage collapse (penalty—slightly weak or excessive is detrimental), mid-stage optimal (temperature·top_k—the middle is optimal), and late-stage optimal (top_p—one end is optimal). The characteristics of each interval on each axis, based on the average across runs, are as follows.

#### Characteristic Intervals by Parameter

| **Parameter** | **Characteristic** | **Characteristics by Interval** | **Conclusion** |
| --- | --- | --- | --- |
| **temperature** | Mid-stage Optimal Type | 0.0–0.3 Stagnation (OK ~83%·foreign 0) **0.3–0.7: Improvement** (penalty 7.5%—lowest) 0.7–1.0: Completion rate ↑·foreign 35% surge·penalty doubled | **0.7 confirmed** · 0.3 accuracy comparison serves as a safety measure |
| **top_k** | Mid-term Optimal | k=1 Overfitting (ok 82%·finish 18%) **k≈10 Peak** (OK 92.5%·Penalty 6.7%) k=50–Unlimited: Gradual decline (OK 88–91%) | Default -1 · **k=10 Candidate** |
| **top_p** | Late-stage optimal | 0.5 Worst-case (ok 79%·finish 21%) 0.8–0.95 Gradual improvement (ok 85→87.5%) **1.0 Best** (ok 90%·finish 10%), no internal vertices | **1.0 (off)** |
| **frequency_penalty** | Initial Optimal·Late Collapse Type | **0–0.5 Rapid Improvement** (ok 90→99.6%·penalty 7→2%) 0.5–1.0 Conformity saturation (gain noise)·sounds 79→65% 1.0–2.0 Collapse (sounds 43%) | **0–0.5 Candidates** · >1.0 Loss |
| **repetition_penalty** | Early optimization·late collapse type | 1.0–1.1 Completion rate improvement (ok 90→99.6%) **1.1–1.3 foreign 1.8→7.2%·actions 100→78% collapse** | **Excluded** |

#### 1. The completion rate indicates the presence of a convergence interval for Temperature

- **Greedy(0.0) is the weakest**
  - 83% completion (≈58/70) · 17% incomplete (finish_len); gets stuck in a loop and runs amok up to `max_tokens`.

  - **temp 0.7 is the optimal point at 88% (≈61/70)·12.5%**.

  - In the current server configuration, the same settings fluctuate from run to run, so the “stability”—supposedly an advantage of low temperatures—is not guaranteed

- **The trade-off for **High Temperature** is heterogeneous characters**
  - It skyrockets to 35% only at 1.0, while ranging from 0% to 0.35% sporadically between 0.0 and 0.7

  - The equilibrium point with the lowest penalty (7.5%) was **temperature 0.7.**

#### 2. The Frequency Penalty parameter is key to iterative improvements

- **Confirmed improvement in completion rate**
  - At freq 0.5, the completion rate increased from 90% to 99.6%

  - Reduced the penalty from 7.0% to 2.0%

- **The trade-off is sound coverage**
  - Decreased from 88% to 43% in proportion to intensity; however, without a ground truth, it is difficult to determine whether this represents the removal of redundant data or the loss of information

## 6. Conclusion

We narrowed the scope using OFAT to the limit of what can be determined **solely by output**. The finalized values and fine-tuning ranges are as follows.

| **Parameter** | **Conclusion** | **Status** |
| --- | --- | --- |
| **temperature** | 0.7 — avoids greedy runaway; 1.0 avoids mixed characters (room for future improvement) | Finalized |
| **top_p / top_k** | Maintain 1.0 / -1 (top_k 10 completion candidates) | Finalized |
| **frequency penalty** | 0–0.5 — Simultaneous improvement in completion and repetition, but reduction in sounds | Range |
| **repetition penalty** | Causes mixed characters | Excluded |

**In the next document**, we will use the confirmed values as a starting point and determine the final values by synthesizing the numerical characteristics revealed by the parameters (frequency penalty, top_k, temperature) and OFAT.

