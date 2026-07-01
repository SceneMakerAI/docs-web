---
title: "[Part 3] Analysis of a 6-Second Clip Using the Qwen3-Omni Inference Parameter Combination (Optimal Configuration Determined)"
sidebar_position: 4
slug: "4"
last_update:
  date: 2026-06-29
---

## 1. Introduction

SceneMaker’s 6-second clip analysis aims to **reliably generate** audiovisual information as a `{summary, ocr, actions, sounds}` 4-field JSON object. Part 2 (OFAT Sweep) varied the inference parameters **one at a time** to identify the independent effects of each axis based on an **adherence** criterion that can be determined solely from the output.

The results objectively narrowed down by Part 2 are as follows.

| **Parameter** | **Part 2 Conclusion** |
| --- | --- |
| temperature | Confirmed at 0.7 (avoids greedy runaway and simultaneous heteroglyph occurrence at 1.0) |
| top_p / top_k | Maintain 1.0 / -1 · top_k: 10 candidates that completed the run |
| frequency penalty | Range of 0–0.5 (improves completion and repetition, but reduces sounds) |
| repetition penalty | Excluded (causes mixed characters) |

OFAT considers only one axis. However, actual operational values apply **multiple axes simultaneously**. This part **combines** the candidates narrowed down in Part 2 to verify behavior when individual effects overlap and to determine the optimal configuration.

However, **changing the prompt and sampling simultaneously disrupts the effects**. Therefore, we **separate the process into two stages**, addressing one factor at a time.

1. **Sampling Combinations**: We fix the **same prompt** used in Part 2 and vary only the sampling parameters to find the optimal sampling
2method. **Prompt Combinations**: We fine-tune the prompt based on the optimal sampling method from Step 1 to finalize the configuration.

As in Part 2, we evaluate the combinations based on **metrics that can be determined solely from the output**: completion rate, degeneration (heterogeneous characters, incompleteness, repetition), coverage, and inference cost.

## 2. Experimental Design

### 2.1. Two-Stage Structure

| **Stage** | **Fixed** | **Variable** | **Purpose** |
| --- | --- | --- | --- |
| Stage 1 (Sampling Combination) | Part 2 prompts · temp 0.7 · top_p 1.0 · rep off · fps 0.5 | frequency penalty {0, 0.3, 0.5} × top_k {-1, 10} | Derive optimal sampling |
| **Stage 2 (** Prompt Combination) | Optimal Sampling from Stage 1 | Prompt (structure, count limits, etc.) | Final Configuration Determined |

Common Fixed Settings: max_tokens 512 · audio on · same 70 clips (7 genres × 10) · 4-field strict schema.

### 2.2. Output Schema (4 Fields)

Responses are strictly limited to `{summary, ocr, actions, sounds}` fields (vLLM `response_format=json_schema(strict)` + pydantic `extra="forbid"` dual enforcement).

| **Field** | **Definition** |
| --- | --- |
| `summary` (string) | A single Korean sentence summarizing both visual and auditory elements |
| `ocr` (array) | On-screen text (subtitles, logos) |
| `actions` (array) | Actions, movements, and scene transitions |
| `sounds` (array) | Background music and sound effects (excluding dialogue) |

### 2.3. Evaluation Metrics

Evaluation is based on the same output-based metrics as in Part 2.

| **Metric** | **Definition** |
| --- | --- |
| `ok` / `fail` | Number of records that passed/failed schema validation (completion rate) |
| `infer_ms` | Inference time per clip (cost·20-minute budget) |
| `penalty` | (`repeat`  + `finish_length`  + `foreign`  + `replacement` ) ÷ 4 |
| `field` | (`summary`  + `ocr`  + `actions`  + `sounds` ) ÷ 4 |

## 3. Sampling Combinations

### 3.0. Test Data and Execution

The sample, prompts, and preparation procedures are all **the same as in Part 2**. 7 genres × 10 clips per category = a fixed set of 70 clips (`make_sample.py` collects the original MP4 files in `data/sample70/` using only symlinks, without re-encoding), and the prompts are the same as those used in Part 2. All 6 combinations use the same input.

Execution is run in a single line from `experiments/03_param_combo/` to `bash sweep.sh 3` (cumulative results for all 6 combinations C1–C6 × 3 runs → N=3), followed by `python analyze.py` (tabulating the run averages). Subsequent runs after `sweep_out/` are automatically accumulated.

### 3.1. Combinations

Only values objectively narrowed down in Part 2 are cross-referenced (frequency range 0–0.5, top_k -1/10). 3 levels of frequency penalty × 2 levels of top_k = 6 combinations.

|   | **top_k -1** | **top_k 10** |
| --- | --- | --- |
| **freq 0** | C1 (Part 2 baseline) | C4 |
| **freq 0.3** | C2 | C5 |
| **freq 0.5** | C3 | C6 |

### 3.2. Results

Average across 6 combinations (N=3 · 70 clips per combination). Using the same prompts and samples as in Part 2, we reproduced the finding that **freq is a key factor for completion**. As freq increased from 0 to 0.3, the completion rate rose from 90.5% to 99.5%, and finish_length decreased from 9.5% to 0.5%. **Best result in Stage 1 = C2 (freq 0.3 · top_k - 1)**.

| **Combination** | **freq** | **top_k** | **Completion (ok)** | infer_ms | **penalty** | **field** |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | 0 | -1 | 90.5% | 2719 | 6.2% | **95.6%** |
| **C2 (Best)** | **0.3** | **-1** | **99.5%** | 2080 | 3.2% | 93.7% |
| C3 | 0.5 | -1 | 99.0% | 1936 | **2.6%** | 90.6% |
| C4 | 0 | 10 | 89.5% | 2695 | 8.0% | 94.9% |
| C5 | 0.3 | 10 | 100% | 2022 | 2.7% | 93.3% |
| C6 | 0.5 | 10 | 100% | 1966 | 2.9% | 91.8% |

<details>
<summary>📊 History by Iteration (N=3 · 1st, 2nd, and 3rd iterations per combination)</summary>

| **Iteration** | **Combination** | ok/fail | infer_ms | repeat | finish_len | foreign | penalty | field |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | C1 (f0·k-1) | 65/5 | 2743 | 20.0% | 7.1% | 1.4% | 7.1% | 94.6% |
| 2 | C1 (f0·k-1) | 64/6 | 2528 | 12.9% | 8.6% | 0.0% | 5.4% | 94.9% |
| 3 | C1 (f0·k-1) | 61/9 | 2887 | 11.4% | 12.9% | 0.0% | 6.1% | 97.1% |
| 1 | C2 (f0.3·k-1) | 69/1 | 2110 | 14.3% | 1.4% | 1.4% | 4.3% | 93.1% |
| 2 | C2 (f0.3·k-1) | 70/0 | 2110 | 8.6% | 0.0% | 1.4% | 2.5% | 94.7% |
| 3 | C2 (f0.3·k-1) | 70/0 | 2021 | 11.4% | 0.0% | 0.0% | 2.9% | 93.2% |
| 1 | C3 (f0.5·k-1) | 69/1 | 1986 | 5.7% | 1.4% | 0.0% | 1.8% | 91.0% |
| 2 | C3 (f0.5·k-1) | 70/0 | 1889 | 11.4% | 0.0% | 0.0% | 2.9% | 90.0% |
| 3 | C3 (f0.5·k-1) | 69/1 | 1932 | 11.4% | 1.4% | 0.0% | 3.2% | 91.0% |
| 1 | C4 (f0·k10) | 61/9 | 2721 | 18.6% | 12.9% | 0.0% | 7.9% | 94.2% |
| 2 | C4 (f0·k10) | 66/4 | 2539 | 15.7% | 5.7% | 0.0% | 5.3% | 95.5% |
| 3 | C4 (f0·k10) | 61/9 | 2825 | 27.1% | 12.9% | 2.9% | 10.7% | 95.1% |
| 1 | C5 (f0.3·k10) | 70/0 | 2053 | 12.9% | 0.0% | 1.4% | 3.6% | 93.2% |
| 2 | C5 (f0.3·k10) | 70/0 | 2075 | 7.1% | 0.0% | 0.0% | 1.8% | 93.2% |
| 3 | C5 (f0.3·k10) | 70/0 | 1938 | 11.4% | 0.0% | 0.0% | 2.9% | 93.6% |
| 1 | C6 (f0.5·k10) | 70/0 | 1929 | 8.6% | 0.0% | 0.0% | 2.1% | 91.0% |
| 2 | C6 (f0.5·k10) | 70/0 | 1959 | 12.9% | 0.0% | 0.0% | 3.2% | 93.2% |
| 3 | C6 (f0.5·k10) | 70/0 | 2009 | 11.4% | 0.0% | 1.4% | 3.2% | 91.1% |

</details>

### 3.3. Analysis

#### 1. Frequency is the key to completion

As freq increased from 0 to 0.3, completion rate rose from 90.5% to 99.5%, finish_length decreased from 9.5% to 0.5%, and penalty decreased from 6.2% to 3.2%. The single-axis conclusion from Part 2 was confirmed exactly as is with the same prompts and samples. top_k 10 alone (C4) fails to improve completion rates (89.5%). Completion rates depend on freq.

#### 2. top_k results in a tie

At freq ≥ 0.3, the difference between top_k -1 and top_k 10 (C2 vs. C5) is 99.5% vs. 100% completion rate (1 clip), mixed penalties, and identical coverage—all within the jitter range for each round. **Keep the default value at -1**.

#### 3. Field coverage is the only consistent trade-off; cannot be determined

As freq increases, coverage monotonically decreases (95.6→93.7→90.6%, reproduced in every run). **Whether this decrease represents redundancy removal (good) or information loss (bad) cannot be determined without a definitive answer key.**

#### Conclusion on Sampling Combinations

In the freq ≥ 0.3 range where completion and penalty are saturated, field coverage is the only factor distinguishing combinations, and freq 0.3 is consistently superior to 0.5. The optimal settings for Stage 1 are **temp 0.7 · frequency 0.3 · top_p 1.0 · top_k -1 · rep off**, and we proceed with the following prompt combinations based on these settings.

## 4. Prompt Combinations

### 4.0. Data and Execution

We **fix** the best setting from Stage 1 (temp 0.7 · freq 0.3 · top_p 1.0 · top_k -1 · rep off) and adjust only the prompts. The data and number of runs are the same as in Step 1 (fixed at 70 clips · N=3). Execution consists of `bash sweep_p2.sh 3` (two prompts × 3 runs) followed by `python analyze_p2.py`. In addition to `infer_ms`, which fluctuates based on server load, **the number of generated tokens (completion_tokens)** is measured as a fixed cost metric.

Two prompts (arm):

- **Comprehensive**: Same prompt as in Phase 1. “Analyze in detail,” no limit on the number of items.
- **Core-First**: “Condense to essentials only,” with count limits (OCR 5 · actions 5 · sounds 3), fragment combination rules, mandatory verb phrases, and only confirmed facts (no speculation).

### 4.1. Why tweak the prompts? Structural Noise in Comprehensive-Type Outputs

In Phase 1, completion, degeneration, and cost were stabilized via sampling parameters. However, when examining the **content** of the same output, the comprehensive-type prompt leaves behind noise that cannot be corrected by sampling alone.

| **Exhaustive-Type Flaws** | **Data Evidence** | **Rules Imposed by Core-First** |
| --- | --- | --- |
| OCR Overabundance/Fragmentation | Average of 5.0 OCR items, maximum of 28 items, 20.6% with ≥8 items, fragments (empty strings, single digits, etc.) 18.0% | Fragment merging rule + count limit of 5 |
| Sentence-like actions | 12.9% of entries are sentence-like rather than verb phrases | Require verb phrases (1–5 words) · Prohibit sentences |
| Minor Duplication (Padding) | Clips where one item is a substring of another: 18.2% | Focus on Essentials · Bold Omissions + Count Limit |

As a representative example, an esports clip scraped up to 28 items via OCR—listing HUD numbers, the game clock, and KDA fragments (`GEN`, `1`, `25.7K`, `4:53`, `4:52`, `4:51` …) in their entirety. This is not an issue with the sampling axis (complete run·degen) but rather a **prompt-level problem**. → We verify whether the “core-first” prompt suppresses this noise using the same sampling (C2).

### 4.2. Results

With the same sampling (C2) fixed and only the prompt as the variable (N=3 average · 70 clips per arm). Completion rates are equivalent; core-first outperforms in terms of cost and repetition noise, while field coverage narrows due to its design.

| **arm** | **Completion Rate** | **Penalty** | **Generated Tokens** | infer_ms | **Field Coverage** |
| --- | --- | --- | --- | --- | --- |
| Comprehensive | 99.5% | 3.7% | 141 | 2058 | **93.8%** |
| **Core-First (Final)** | **100%** | **0.8%** | **103** | **1662** | 82.1% |

Detailed analysis of degeneration: the difference in penalty is almost entirely due to `repeat`.

| **arm** | repeat | finish_length | foreign |
| --- | --- | --- | --- |
| Comprehensive | 13.3% | 0.5% | 1.0% |
| Core-First | **1.4%** | 0.0% | 1.9% |

Coverage by field: The by-design differences created by the count limit for "Core-First" and the "leave blank when in doubt" rule.

| **arm** | ocr | actions | sounds |
| --- | --- | --- | --- |
| Comprehensive | 89.5% | 99.5% | 86.1% |
| Core-First | 65.7% | 100% | 62.9% |

<details>
<summary>📊 History by Iteration (N=3 · 1st, 2nd, and 3rd iterations per arm)</summary>

| Iteration | arm | Completion (ok/fail) | penalty | generated tokens | infer_ms | coverage |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Exhaustive | 100% (70/0) | 5.00% | 135 | 1922 | 94.30% |
| 2 | Exhaustive | 100% (70/0) | 2.90% | 141 | 2080 | 93.20% |
| 3 | Exhaustive | 98.6% (69/1) | 3.20% | 147 | 2,171 | 93.80% |
| 1 | Core-First | 100% (70/0) | 0.40% | 102 | 1,655 | 82.20% |
| 2 | Core-Priority | 100% (70/0) | 1.40% | 105 | 1,688 | 82.50% |
| 3 | Core-First | 100% (70/0) | 0.70% | 103 | 1642 | 81.80% |

</details>

### 4.3. Analysis

#### 1. Completion rates are tied

Comprehensive: 99.5% vs. Core-First: 100%; this is within the jitter range, differing by only one clip. In Stage 1, a freq of 0.3 already saturates completion rates, so there is nothing more to be gained from the prompt. Completion rate is not a distinguishing factor.

#### 2. Core-Priority Is Cheaper

Generated tokens: 141 → 103 (-27%); infer_ms: 2058 → 1662 (-19%). The “core-only, count limit” approach directly reduces output length, which is immediately advantageous for a 20-minute-per-video budget. Cost is the true distinguishing factor between the two prompts.

#### 3. “Core-first” also has the advantage in terms of degeneration, and this is not due to reduced coverage

Penalty: 3.7% → 0.8%. Breaking this down, almost all of the reduction stems from `repeat` (13.3% → 1.4%), and this trend is consistent across all runs (Comprehensive: 5.0/2.9/3.2 vs. Core-First: 0.4/1.4/0.7). The benefit of the core-first approach stems not from using less information, but from **suppressing repetition and excessive listing**.

## 5. Conclusion

### 5.1. Finalization of the Optimal Configuration

Final configuration for the 6-second clip analysis, synthesizing both stages:

| **Item** | **Value** |
| --- | --- |
| temperature | 0.7 |
| frequency penalty | 0.3 |
| top_p | 1.0 |
| top_k | -1 (inactive) |
| repetition penalty | off (1.0) |
| **Prompt** | **Key Priorities** (count limit · token combination rules · verb phrases · established facts) |
| Common | fps 0.5 · max_tokens 512 · audio on · 4-field strict schema |

### 5.2. Summary

- **Step 1:** Frequency is the key to completion (reproducing Part 2 of OFAT). top_k results in a tie; completion and degeneration are saturated at freq ≥ 0.3. Best sampling = C2.
- **Stage 2**: With the same sampling, the core-first prompt simultaneously reduces cost (generation tokens -27%) and repetition noise (repeats 13% → 1%), while maintaining the same completion rate. However, coverage narrows due to the design.
- **20-minute/video budget**: The -27% reduction in tokens from the core-first approach directly increases budget flexibility (allowing for improved concurrency and higher fps).

### 5.3. Limitations and Remaining Challenges

- Since C2 sampling is optimal for an exhaustive approach, it may differ from the optimal sampling for the core-first approach itself. In Phase 2, sampling was intentionally fixed to isolate the effect of the prompt alone.
- Whether the narrowed coverage results from the removal of redundancy or information loss cannot be definitively determined based on output metrics alone. This loop is closed through human quality verification (§6).

## 6. Human Quality Verification (Final Configuration)

Human evaluators directly scored the outputs of the final configuration (Core-First prompt + C2 sampling). They used human judgment to determine whether the narrowed coverage—a loop that could not be closed by the output metrics in §3 and §4 alone—was **the result of redundancy removal or information loss**. The evaluation set consisted of a broader dataset separate from the 70-clip sample used in Stages 1 and 2: 6 categories × 100 clips = 600 clips. Scores were assigned on a 5-point scale ranging from -2 to 2 for each field.

| **Score** | **Meaning** |
| --- | --- |
| 2 | Accurate (almost entirely correct) |
| 1 | Similar (Roughly correct / Some omissions) |
| 0 | Poor (Lacks key information / Barely outputted) |
| -1 | Misinformation (Content different from reality) |
| -2 | Hallucination (Complete error / Outputs non-existent information) |

### 6.1. Category-wise Averages

Scores are on a -2 to 2 scale. The far-right column and bottom row show values normalized to 0–1 ((raw score + 2) ÷ 4).

| **Category** | summary | ocr | sound | action | **Overall (0–1)** |
| --- | --- | --- | --- | --- | --- |
| Baseball | 1.70 | 1.76 | 1.37 | 1.73 | 0.91 |
| Documentary | 1.67 | 1.94 | 1.12 | 1.75 | 0.91 |
| Drama | 1.47 | 1.87 | 1.45 | 1.69 | 0.91 |
| Variety | 1.74 | 1.65 | 1.68 | 1.81 | 0.93 |
| Historical Dramas | 1.78 | 1.83 | 1.82 | 1.92 | 0.96 |
| News | 1.82 | 2.00 | 1.93 | 1.97 | 0.98 |
| **Overall Field (0–1)** | **0.92** | **0.96** | **0.89** | **0.95** | **0.93** |

### 6.2. Score Distribution

| **Score** | summary | ocr | sound | action | **Average** |
| --- | --- | --- | --- | --- | --- |
| 2 (Accurate) | 81.3% | 87.2% | 79.8% | 89.8% | **84.5%** |
| 1 (Similar) | 12.8% | 11.5% | 9.2% | 5.8% | 9.8% |
| 0 (Poor) | 0.8% | 0.2% | 1.3% | 0.5% | 0.7% |
| -1 (Misinformation) | 4.2% | 0.7% | 6.7% | 3.3% | 3.7% |
| -2 (Hallucination) | 0.8% | 0.5% | 3.0% | 0.5% | 1.2% |

### 6.3. Conclusion

- Overall normalized quality **0.93**. 2-point ratio **84.5%**, total negative (-1·-2) **4.9%**.
- The narrow, core-priority output is **high quality** by human standards. The reduction in coverage is largely due to **removing redundancy** rather than information loss (misinformation and hallucination rates are less than 5%). This closes a loop that could not be addressed by output metrics alone.
- By field, OCR has the highest score (0.96), while sound has the lowest (0.89; negative 9.7%). Non-speech audio is a relative weakness. By genre, news and historical dramas perform best (0.98 and 0.96, respectively), while dramas perform worst (0.91).

