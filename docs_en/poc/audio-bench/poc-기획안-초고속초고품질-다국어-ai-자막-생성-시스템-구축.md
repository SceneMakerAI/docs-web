---
title: "[PoC Proposal] Development of a High-Speed, High-Quality Multilingual AI Subtitling System"
sidebar_position: 1
slug: "1"
last_update:
  date: 2026-06-05
---



**Project Nature:**

Validation of a subtitle pipeline tailored to complex media audio environments, including broadcasting, film, variety shows, and sports

**Validation Environment:**

Basic accelerated environment based on a single NVIDIA RTX 4090 (24GB)


## 1. Project Overview

- **Objective:** Validation of a system that isolates human dialogue from media files containing background music, sound effects, and crowd noise, thereby preventing subtitle misrecognition and AI hallucination at the source, and converting a one-hour video into perfect multilingual subtitles in just three minutes.
- **Key Objectives:** 
  -  Minimize Word Error Rate (WER) through Speech Enhancement

  -  Implementation of real-time multilingual code-switching and whitespace handling on a sentence-by-sentence and segment-by-segment basis

  -  Final correction of proper nouns and customized typos based on context using an LLM

- Expected Processing Workflow

```smalltalk
[영상 파일 입력]
⬇️
1단계. 오디오 추출 (ffmpeg)
원본 영상에서 딥러닝 엔진이 분석할 수 있는 고음질 오디오 트랙을 고속으로 분리합니다.
⬇️
2단계. AI 음성 향상 (DeepFilterNet v3)
배경음악(BGM), 영화 효과음, 스포츠 관중 함성 등을 '소음'으로 규정하여 10초 
만에 완벽히 소거하고 순수 목소리만 고립시킵니다.
⬇️
3단계. 다국어 전사 엔진 (WhisperX)
내장된 Silero VAD로 공백을 청소하고, 조각별 언어 자동 감지를 거쳐 환각 없이 
고속으로 텍스트를 타이핑합니다.
⬇️
4단계. 화자 분리 매칭 (PyAnnote Audio)
추출된 텍스트의 타임스탬프와 목소리 주인공의 시간대를 대조하여 
[화자 1], [화자 2] 태그를 자동으로 부여합니다.
⬇️
5단계. LLM 문맥 교정 (LLM Engine)
앞뒤 문맥을 파악하여 Whisper가 틀린 고유명사, 오타, 띄어쓰기를 최종 교정하고 
규격화된 최종 SRT 자막을 출력합니다.
```


## 2. Preliminary Research

#### **2.1. Speech Recognition Engine: WhisperX (Turbo vs Large-v3)**


- **Conclusion:** Adopted the `Turbo (Large-v3-Turbo)` model for a transcription-focused ultra-high-speed system.
- **Reason:** While Large-v3 delivers the best performance, the accuracy loss is only around 1%, and Turbo is more than three times faster. We determined that preprocessing the audio data to improve the original quality would be advantageous in terms of both accuracy and speed.

| **Comparison Item** | **WhisperX Large-v3** | **WhisperX Turbo** | **Remarks and Business Impact** |
| --- | --- | --- | --- |
| **Parameters** | 1,550M (1.55 billion) | **809M (809 million)** | Slimmed-down architecture enables lightweight operation |
| **Number of Decoder Layers** | 32 | **4** | Maximizes inference speed by reducing layers to 1/8 |
| **Actual VRAM Usage** *(FP16 basis)* | Approx. 4.5 GB – 5.0 GB | **Approx. 2.5 GB – 3.0 GB** | GPU memory savings enable increased batch processing capacity |
| **Audio processing time per hour** *(based on RTX 4090 / WhisperX batch)* | Approx. 45 seconds to 1 minute | **Approx. 15 seconds to 20 seconds** | **Turbo is approximately 3 times faster** (pure computation excluding I/O speed) |
| **Accuracy metric** *(LibriSpeech WER)* | Baseline (~2.7%) | **Slight decrease (~3.0%)** | **Error rate difference of approx. 0.3%**—imperceptible in practical use |
| **Translation Feature** *(--task translate)* | **Supported** (multilingual ➡️ English translation) | **Not supported** (transcribes only the language heard) | Both fully support multilingual 'dictation' |

#### 2.2 Noise Removal

- **Conclusion:** To isolate dialogue at ultra-high speeds from diverse noisy environments such as broadcasts, movies, and sports commentary, we adopted `DeepFilterNet v3` as the main preprocessing engine.
- **Reason:** Unlike music separation models (RoFormer, MDX) specialized in removing background music, it recognizes all sounds other than those within the frequency range of the human vocal cords (sound effects, cheering, background noise) as 'noise' and completely removes them. In particular, it delivers overwhelming infrastructure cost savings, processing one hour of content in just over 10 seconds on an RTX 4090 system.

| **Comparison Models** | **DeepFilterNet v3 (Selected)** | **BS-RoFormer (Vocal)** | **MDX23C (Kim Vocal 2)** | **HTDemucs v4** |
| --- | --- | --- | --- | --- |
| **Model Category** | **Speech Enhancement** | Music Source Separation (SOTA) | Frequency Separation (Traditional Powerhouse) | Hybrid Source Separation |
| Processing time (1 hour on RTX 4090) | **🚀 Approx. 10–15 seconds** | Approx. 1 min 30 sec–2 min | Approx. 45 sec–1 min | Approx. 1 min–1 min 30 sec |
| **VRAM Required** | **⚡ Less than 1 GB (Extremely Light)** | Approx. 4 GB ~ 8 GB | Approx. 4 GB ~ 6 GB | Approx. 4 GB |
| **Main Filtering Targets** | **On-site noise, audience cheers, reverberation (echo), sound effects, BGM** | Background music (OST), instrumental accompaniment | Background music, studio noise | Drums, bass, other instruments |
| **Key Advantages** | Overwhelmingly fast processing speed and excellent preservation of dramatic dialogue, such as actors’ mumbling or whispering. | World-class background music (BGM) suppression capability among existing open-source solutions. | High voice clarity results in crisp diction. | Audio is separated into 4 tracks, allowing for adjustment of the sense of presence. |
| **Disadvantages and Limitations** | In some variety shows where the BGM volume is extremely loud compared to dialogue, music may leak through slightly. | The model is resource-intensive, raising concerns about bottlenecks during bulk processing. There is a possibility that dialogue may be distorted and not recognized by Whisper. | Fails to recognize movie sound effects or sports crowd noise as "instruments," so they are not filtered out. | Sometimes misidentifies whispered dialogue as "noise" and deletes it entirely. |
| **PoC Final Status** | **Main Pipeline Confirmed** | Sub-pick for special genres (variety shows) | Candidate pick for high-volume, high-speed processing | Verified pick for sports broadcasts |


---## 3. Testing

### 3.1 Testing Method



### 3.2 Test Data

The test data is as follows. Videos ranging from 50 minutes to 2 hours that closely resemble actual broadcast footage

| Broadcast | Duration | URL |
| --- | --- | --- |
| KBS 9 News | 48:30 | [https://www.youtube.com/watch?v=rX1P-jOoNmM](https://www.youtube.com/watch?v=rX1P-jOoNmM) |
| Superfish Part 1 | 58:40 | [https://www.youtube.com/watch?v=iNbWqC1iqKw](https://www.youtube.com/watch?v=iNbWqC1iqKw) |
| KBS Winter Sonata | 1:04:52 | [https://www.youtube.com/watch?v=irVKEhb9g8M](https://www.youtube.com/watch?v=irVKEhb9g8M) |
| Taejo Wang Geon | 54:10 | [https://www.youtube.com/watch?v=nmlE2iPWLGM](https://www.youtube.com/watch?v=nmlE2iPWLGM) |
| Chuljang Sippoya X Starship National Sports Festival Full Version | 1:00:06 | [https://www.youtube.com/watch?v=6wJGpi1nkCg](https://www.youtube.com/watch?v=6wJGpi1nkCg) |
| 2009 KBO League Korean Series Game 7 | 1:55:22 | [https://www.youtube.com/watch?v=fP1QEs1Uj5U](https://www.youtube.com/watch?v=fP1QEs1Uj5U) |

#### 3.2.1 Video Download and Format Conversion

##### Video Download)

- Download videos in 720p resolution.
  - If the file is too large: Analysis takes a long time.

  - If the file is too small: Image analysis accuracy decreases.

```yaml
> yt-dlp -f "bv*[height<=720]+ba/b[height<=720]" "<URL">
```


##### Video Conversion)

- Extract only the audio from the downloaded video.
- Save the audio as an uncompressed WAV file. The following options are important for noise removal:
  - -vn : Exclude video (Video No)

  - -ac 1 : Number of audio channels (2: Stereo, 1: Mono)
    - WhisperX and DeepFilterNet process audio internally as Mono. (If stereo input is received, it is converted to Mono)

  - -ar 48000: DeepFilterNet’s native sample rate is 48 kHz
    - If 16 kHz input is received, it undergoes internal upsampling, which results in data loss.

  - -c:a pcm_s16le : Output the original audio without compression

```yaml
ffmpeg -y -i <input.mp4> -vn -ac 1 -ar 48000 -c:a pcm_s16le <audio.wav>
```




