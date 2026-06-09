---
title: "Comparison of LID Accuracy for Korean Content — Whisper vs. VoxLingua107"
sidebar_position: 2
slug: "2"
last_update:
  date: 2026-06-04
---


## 1. Overview

### 1.1 Background — Issues with the LID Stage in the STT Pipeline

While Whisper is commonly used for STT, hallucinations and errors are particularly noticeable in videos containing a mix of languages. One cause is the lock-in effect of WhisperX—it determines the main language based on the first 30 seconds of the video and transcribes the entire clip in that language, resulting in garbled output when foreign language segments appear later in the video because they are forced into Korean mode.

If the exact language is provided in advance for each speech segment, the results improve significantly. To achieve this, a structure is needed where LID (Language Identification) is separated from the transcription engine and executed as a separate step, which raises the following questions — **Which model should be used, and should the input be raw or denoised?** Since the content we handle—such as Korean dramas, variety shows, and news—always contains background music, sound effects, and cheering, standard model evaluations based on clean audio do not apply directly. The starting point of this POC is a situation where we have no choice but to decide on the model and whether to apply denoising based on intuition, without any quantitative data.

### 1.2 Purpose of the POC

This document answers the question of how to identify and select speech from Korean videos mixed with BGM through quantitative comparison. The comparison involves two LID models (Whisper LID, VoxLingua107) × two input types (raw, denoise) = a 4-way matrix. We simultaneously run all four combinations on the same sample to measure match rates and processing times.

### 1.3 Design Decisions

As this is a proof-of-concept (POC) validation tool, simplicity was prioritized, and variables were minimized to ensure the reliability of the comparison results.

- **No Calibration Policy** — No post-processing such as script checks, overrides, or blacklists. The results of the four LID models are compared as-is.
- **VAD Control** — Silero VAD is applied to the raw audio only once, and the same time interval is applied identically to the denoised audio. This ensures that the raw and denoised audio do not cover different time intervals.
- **Model Preloading** — All four models were loaded first before starting the measurement. Model loading time was excluded from the processing time.
- **Fixed Denoising Strength** — DeepFilterNet v3, `atten_lim_db=-30` (strength level 1). Strength comparisons are outside the scope of this POC.
- **LID stage only** — No calls to diarize or ASR. Single GPU (cuda:0), sequential processing of a single audio stream.

### 1.4 Processing Flow

```javascript
[Denoise 적용시]
audio → VAD → 각 발화 구간 → denoise → [Whisper | VoxLingua] → LID

[Denoise 미 적용시]
audio → VAD → 각 발화 구간 → [Whisper | VoxLingua] → LID
```


---

## 2. Comparison Design

### 2.1 Models

The comparison targets are two LID models.

**Whisper LID (baseline).** Calls `detect_language()` from  
(`mobiuslabsgmbh/faster-whisper-large-v3-turbo`) calls `detect_language()`. Whisper is a model trained for multilingual speech recognition, and LID is the language classification result for over 100 languages obtained as a byproduct. Only the first 30 seconds of the input audio are used. Since it is already being used by the upper-level STT pipeline, we set it as the **baseline** for this POC.

**VoxLingua107 (experimental group).** A **dedicated** LID model based on SpeechBrain ECAPA-TDNN (`speechbrain/lang-id-voxlingua107-ecapa` ). It was trained to classify 107 languages and is known for its strong ability to distinguish between language pairs with similar acoustic characteristics (e.g., ko/ja, zh/ja, th/lo/km). It produces relatively stable confidence scores even for short utterances.

Although there are several candidate LID-specific models (NeMo TitaNet, ECAPA fork, etc.), VoxLingua107 includes Korean in its training languages, can be immediately integrated into our environment (single GPU, HF cache), and has abundant comparative data, making it easy to interpret results.  
Therefore, we adopted it as the alternative for this POC.

### 2.2 Variables

We examine both **raw** and **denoised** inputs. While denoising removes background music, sound effects, and cheering to make the speech stand out, the enhance model may introduce signal modifications not encountered during LID training, so its effect on LID accuracy cannot be definitively determined. While the top-level STT pipeline calls LID using raw chunks under the empirical assumption that "denoise ruins LID," this POC aims to verify this assumption itself.

Therefore, the comparison matrix is **Model 2 × Input 2 = 4-way**.

|  | raw audio | denoise audio |
| --- | --- | --- |
| Whisper LID | W-raw | W-den |
| VoxLingua107 | V-raw | V-den |

We simultaneously generate the four results for the same speech segment and compare their agreement or disagreement.

### 2.3 Evaluation Metrics

#### Agreement Rate (Accuracy Proxy)

Since the content lacks ground truth labels, we cannot directly measure accuracy. Instead, we use the **degree of mutual agreement** among the four results (W-raw / V-raw / W-den / V-den) as a proxy. If all four match, the utterance is considered reliable; a discrepancy indicates that one of them is incorrect.

  
Calculated metrics:

- **4-way agreement rate** — All four results match
- **W-raw vs V-raw / W-den vs V-den** — Agreement between models for the same input
- **W-raw vs W-den / V-raw vs V-den** — The effect of denoising on each model

#### Processing Time

Excluding model loading time, we record only the pure processing time per audio sample for each step.

| Step | Range |
| --- | --- |
| `denoise` | DeepFilterNet call + 16k resampling |
| `vad` | Silero VAD call |
| `whisper_lid` | Total Whisper LID calls for all segments (raw+denoise) |
| `voxlingua_lid` | Sum of VoxLingua107 calls for all segments (raw+denoise) |
| `total` | From entry into run() to completion |

Output: `output/<stem>.csv` per segment + `output/timings.csv` per file.

### 2.4 Dataset

We used six types of Korean video content (one per genre). The data consists of 16 kHz mono WAV files that have been preprocessed, with durations ranging from 30 minutes to 2 hours, and no ground-truth labels (using the match rate proxy method described in Section 2.3). 

Although Korean is the primary language, the presence of foreign languages and background noise varies by genre.

| Category | Broadcast | Duration | URL |
| --- | --- | --- | --- |
| Category | Broadcast | Duration | URL | | --- | --- | --- | --- |
| Documentary | Superfish Part 1 | 58:40 | [https://www.youtube.com/watch?v=iNbWqC1iqKw](https://www.youtube.com/watch?v=iNbWqC1iqKw) |
| Drama | KBS Winter Sonata | 1:04:52 | [https://www.youtube.com/watch?v=irVKEhb9g8M](https://www.youtube.com/watch?v=irVKEhb9g8M) |
| Historical Drama | Taejo Wang Geon | 54:10 | [https://www.youtube.com/watch?v=nmlE2iPWLGM](https://www.youtube.com/watch?v=nmlE2iPWLGM) |
| Variety | Business Trip 15 Days X Starship National Sports Festival Full Version | 1:00:06 | [https://www.youtube.com/watch?v=6wJGpi1nkCg](https://www.youtube.com/watch?v=6wJGpi1nkCg) |
| Sports | 2009 KBO League Korean Series Game 7 | 1:55:22 | [https://www.youtube.com/watch?v=fP1QEs1Uj5U](https://www.youtube.com/watch?v=fP1QEs1Uj5U) |

The reason for selecting one example per genre is to avoid conclusions biased toward a single genre and to observe patterns between content characteristics (BGM intensity, foreign language usage) and LID results.


---

## 3. Implementation

See the URL below for the source code

- [https://github.com/SceneMakerAI/poc-lid-bench](https://github.com/SceneMakerAI/poc-lid-bench)

### 3.1 Directories/Flow

#### Directory Structure

```javascript
poc-lid-bench/
├── CLAUDE.md
├── pyproject.toml
├── conf.py                # MODEL_DIR 등 경로 상수
├── log.py                 # 파일 로거 (lid_bench.log)
├── main.py                # 진입점: wav 목록 순회 + 결과 저장
├── lib/
│   ├── denoise.py         # DeepFilterNet v3 wrapper
│   ├── vad.py             # Silero VAD wrapper
│   ├── whisper_lid.py     # faster-whisper detect_language wrapper
│   ├── voxlingua_lid.py   # SpeechBrain VoxLingua107 wrapper
│   └── bench.py           # 4-way 비교 실행 + 결과 출력/저장
└── output/                   # 산출물 (gitignore 권장)
    ├── denoise/
    │   └── <stem>.wav        # denoise 결과 (48kHz int16) — 입력 wav 1개당 1개
    ├── <stem>.csv            # per-segment LID 결과 — 입력 wav 1개당 1개
    └── timings.csv           # 모든 입력 파일의 단계별 처리 시간 통합 1개
```


#### External Environment Notes (for Git users)

- **Data Path** — The `test_files` in `main.py` is hardcoded to an internal path
(`/stg/vod/scenemaker/sound_full/*.wav`). When using externally, replace it with the WAV file path in your own environment.

- **Model Cache** — Whisper LID automatically uses the HF cache (`HF_HOME`), and VoxLingua107 automatically downloads SpeechBrain to the `conf.MODEL_DIR` subdirectory (`voxlingua107/`). No prior download is required.
- **GPU** — Fixed to cuda:0. In multi-GPU environments, adjust the device specification in `whisper_lid.py` /`voxlingua_lid.py`.


### 3.2 Environment / Model / Dependencies

#### Environment

- Python **3.11** (`>=3.11,<3.12` — The official DeepFilterNet package only provides stable support up to 3.11)
- Package manager **uv** (`.venv` + `uv.lock` )
- GPU **RTX 4090 24GB**, single-GPU configuration with CUDA 0

#### Dependencies (`pyproject.toml` )

| Package | Version | Purpose |
| --- | --- | --- |
| `faster-whisper` | `>=1.0` | Whisper LID (`detect_language` ) |
| `speechbrain` | `>=1.0` | VoxLingua107 LID |
| `deepfilternet-py312` | `>=0.5.7` | DeepFilterNet v3 model |
| `deepfilterlib` | `>=0.5.6` | DF runtime library |
| `soundfile` | `>=0.13` | WAV loading |
| `torch` | `>=2.4,<2.9` | cu128 wheel, upper limit is DF compatibility |
| `torchaudio` | `>=2.4,<2.9` | Same |

> torch/torchaudio upper limit `<2.9` is removed in `torchaudio.backend.common.AudioMetaData`
will be removed in 2.9; this is to avoid issues with broken DF imports. Verified combination:
`torch==2.8.0+cu128` .

#### Models

| Model | Download Location | Identifier |
| --- | --- | --- |
| Whisper LID (large-v3-turbo) | HF Cache (`HF_HOME` ) | `mobiuslabsgmbh/faster-whisper-large-v3-turbo` |
| VoxLingua107 (ECAPA-TDNN) | `conf.MODEL_DIR/voxlingua107/` | `speechbrain/lang-id-voxlingua107-ecapa` |
| DeepFilterNet v3 | Built-in pip package | Automatic upon `init_df()` call |
| Silero VAD | `~/.cache/torch/hub/` | `snakers4/silero-vad` (torch.hub) |

All models are automatically downloaded upon first execution (network required); no preparation required.

#### Note for Git Users

- If `HF_HOME` is not set, the default (`~/.cache/huggingface/`) is downloaded.
- `conf.MODEL_DIR` is set to the internal cache (`/stg/models`). In external environments,
modify the code to change the path to your own or use the SpeechBrain default cache (`~/.cache/huggingface/`).


### 3.3 How to Run

```javascript
# log.py 에서 로그파일 위치 적절히 수정
> .venv/bin/python main.py
```



---

## 4. Results

### 4.1 Accuracy

Detailed results for the most accurate language classifications across all speech segments are available at the URL below.

[https://docs.google.com/spreadsheets/d/1zARHI1l5UfJ_pU1VY61xOOtvmteHLZ-QPHjSbRIoZpI/edit?gid=759070170#gid=759070170](https://docs.google.com/spreadsheets/d/1zARHI1l5UfJ_pU1VY61xOOtvmteHLZ-QPHjSbRIoZpI/edit?gid=759070170#gid=759070170)


To summarize the final results briefly

|  | Total | whisper_raw | voxlingua_raw | whisper_denoise | voxlingua_denoise |
| --- | --- | --- | --- | --- | --- |
| baseball.wav | 1092 | 1073 | 1026 | 1072 | 1020 |
| docu.wav | 383 | 349 | 330 | 349 | 332 |
| drama.wav | 314 | 282 | 256 | 279 | 251 |
| entertain.wav | 502 | 464 | 398 | 438 | 366 |
| hist_drama.wav | 437 | 411 | 382 | 386 | 363 |
| news.wav | 387 | 385 | 377 | 384 | 379 |
| Correct | 3115 | 2964 | 2769 | 2908 | 2711 |
| Accuracy rate | 100 | **95.2** | 88.9 | 93.4 | 87.0 |

- Accuracy is highest for Whisper raw, followed by Whisper denoise, then Voxlingua raw, and lowest for Voxlingua denoise.
- **(Important) Applying denoise does not improve language classification performance.**


### 4.2 Cost (Processing Time)

| file | duration | model | vad | denoise | lid | total | total_hour | difference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| docu.wav | 00:58:41  | whisper | 9.97 | - | 20.13 | 30.1 | 30.78 |  |
|  | (3520.7) | voxlingua | 9.97 | - | 3.26 | 13.23 | 13.53 | 2.3 |
|  |  | whisper | 9.97 | 10.39 | 20.4 | 40.76 | 41.67 |  |
|  |  | voxlingua | 9.97 | 10.39 | 1.98 | 22.33 | 22.84 | 1.8 |
| baseball.wav | 01:55:23  | whisper | 19.35 | - | 57.75 | 77.1 | 40.1 |  |
|  | (6922.5) | voxlingua | 19.35 | - | 7.68 | 27.03 | 14.06 | 2.9 |
|  |  | whisper | 19.35 | 19.5 | 58.18 | 97.03 | 50.46 |  |
|  |  | voxlingua | 19.35 | 19.5 | 6.02 | 44.87 | 23.33 | 2.2 |
| drama.wav | 01:04:53  | whisper | 10.86 | - | 14.95 | 25.81 | 23.87 |  |
|  | (3892.8) | voxlingua | 10.86 | - | 1.88 | 12.74 | 11.78 | 2.0 |
|  |  | whisper | 10.86 | 10.73 | 14.96 | 36.55 | 33.8 |  |
|  |  | voxlingua | 10.86 | 10.73 | 1.64 | 23.24 | 21.49 | 1.6 |
| entertain.wav | 01:00:06  | whisper | 9.95 | - | 26.11 | 36.06 | 36 |  |
|  | (3606.3) | voxlingua | 9.95 | - | 3.45 | 13.4 | 13.38 | 2.7 |
|  |  | whisper | 9.95 | 9.92 | 26.24 | 46.12 | 46.04 |  |
|  |  | voxlingua | 9.95 | 9.92 | 2.81 | 22.69 | 22.65 | 2.0 |
| hist_drama.wav | 00:54:10  | whisper | 9.02 | - | 21.52 | 30.54 | 33.83 |  |
|  | 00:54:10 | voxlingua | 9.02 | - | 2.41 | 11.43 | 12.66 | 2.7 |
|  |  | whisper | 9.02 | 9.02 | 21.85 | 39.89 | 44.18 |  |
|  |  | voxlingua | 9.02 | 9.02 | 2.1 | 20.14 | 22.31 | 2.0 |
| news.wav | 00:48:30 | whisper | 7.81 | - | 20.54 | 28.35 | 35.07 |  |
|  | (2910.3) | voxlingua | 7.81 | - | 2.44 | 10.25 | 12.68 | 2.8 |
|  |  | whisper | 7.81 | 8.13 | 20.84 | 36.77 | 45.48 |  |
|  |  | voxlingua | 7.81 | 8.13 | 2.03 | 17.96 | 22.22 | 2.0 |

- **Processing Speed Ranking: (Fastest) voxlingua raw > voxlingua denoise > Whisper raw > Whisper denoise (Slowest)**







