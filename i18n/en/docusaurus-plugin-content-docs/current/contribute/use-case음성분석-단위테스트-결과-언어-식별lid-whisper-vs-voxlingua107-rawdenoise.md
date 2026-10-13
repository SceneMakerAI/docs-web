---
title: "[Use Case][Speech Analysis] Unit Test Results — Language Identification (LID): Whisper vs. VoxLingua107 × raw/denoise"
sidebar_position: 7
slug: "7"
description: "Language Identification (LID): Whisper vs. VoxLingua107 × raw/denoise"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

GitHub Discussion: [https://github.com/speechbrain/speechbrain/discussions/3092](https://github.com/speechbrain/speechbrain/discussions/3092)

I’m trying to determine the language for each speech segment before running STT, but since I hadn’t decided on a model or whether to use the raw input or denoised input, I ran some tests. The tool used was [`poc-lid-bench`](https://github.com/SceneMakerAI/poc-lid-bench).

Since broadcast audio always contains background music, sound effects, and cheering, it’s easy to assume that denoising would naturally improve the results. The results, however, showed the opposite.

#### Comparison

|  | raw | denoise |
| --- | --- | --- |
| Whisper LID (`faster-whisper-large-v3-turbo` ) | W-raw | W-den |
| VoxLingua107 (`speechbrain/lang-id-voxlingua107-ecapa` ) | V-raw | V-den |

- For VAD, Silero VAD was applied to the original audio only once, and the same time interval was used for the denoised audio as well. If the two inputs cover different intervals, the comparison is invalid.
- Denoising uses DeepFilterNet v3, `atten_lim_db=-30`
- No post-processing correction
- 6 Korean broadcasts (48 minutes to 1 hour 55 minutes per episode), 3,115 speech segments, RTX 4090

#### Accuracy

|  | Segment | W-raw | V-raw | W-den | V-den |
| --- | --- | --- | --- | --- | --- |
| Baseball | 1092 | 1073 | 1026 | 1072 | 1020 |
| Documentary | 383 | 349 | 330 | 349 | 332 |
| Drama | 314 | 282 | 256 | 279 | 251 |
| Variety | 502 | 464 | 398 | 438 | 366 |
| Historical Dramas | 437 | 411 | 382 | 386 | 363 |
| News | 387 | 385 | 377 | 384 | 379 |
| Total | 3115 | 2964 | 2769 | 2908 | 2711 |
|  |  | **95.2%** | 88.9% | 93.4% | 87.0% |

The original text was more accurate for both models. The denoising penalty was significant in variety shows and historical dramas. In terms of model performance, Whisper outperforms VoxLingua107 by about 6 percentage points.

Segment-by-segment results are available in the spreadsheet linked in the [detailed report](https://doc.scenemaker.solbox.com/docs/poc/audio-bench/2). The report contains only the code; the result files have not yet been uploaded ([poc-lid-bench#1](https://github.com/SceneMakerAI/poc-lid-bench/issues/1)).

#### Speed

Looking at LID alone, VoxLingua107 is much faster. For a 58-minute documentary, Whisper took 20.1 seconds, while VoxLingua107 took 3.3 seconds. When VAD is included, the difference is 2 to 3 times.

#### Therefore,

even though it’s slower, I decided to feed the original audio into Whisper’s LID. This is why the STT pipeline splits the input into two parts: VAD and LID use the original audio, while ASR uses the denoised version.

#### During installation:

- Python is fixed at version 3.11 (`>=3.11,<3.12`). The official DeepFilterNet package is only stable up to that version.
- `>=3.11,<3.12` /`torch` are for versions below 2.9. In 2.9, `torchaudio` was removed, causing the DeepFilterNet import to fail.

