---
id: use-case음성분석-단위테스트-결과-언어-식별lid-whisper-vs-voxlingua107-rawdenoise
title: "[Use Case][음성분석] 단위테스트 결과 — 언어 식별(LID) Whisper vs VoxLingua107 × raw/denoise"
sidebar_position: 7
slug: "7"
description: "언어 식별(LID) Whisper vs VoxLingua107 × raw/denoise"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

GitHub Discussion: [https://github.com/SceneMakerAI/docs-web/discussions/35](https://github.com/SceneMakerAI/docs-web/discussions/35)

월별 계획 8월 항목 "Use Case Report 단위테스트 결과 (음성분석)"에 해당하는 글입니다. BGM 이 깔린 한국 방송에서 발화 구간의 언어를 어떻게 식별할지 비교한 [`poc-lid-bench`](https://github.com/SceneMakerAI/poc-lid-bench) 의 결과를 공유합니다.

### 질문

STT 앞단에서 발화 구간마다 언어를 먼저 식별(LID)하면 다국어가 섞인 영상의 전사 품질이 올라갑니다. 정해야 할 것은 두 가지였습니다.

1. 어떤 모델을 쓸 것인가
2. 입력은 원본(raw)인가, 잡음 제거(denoise)한 오디오인가

### 비교 설계

모델 2 × 입력 2 = 4 조합을 같은 발화 구간에 동시에 돌렸습니다.

|  | raw | denoise |
| --- | --- | --- |
| Whisper LID (`faster-whisper-large-v3-turbo` 의 `detect_language` ) | W-raw | W-den |
| VoxLingua107 (`speechbrain/lang-id-voxlingua107-ecapa` ) | V-raw | V-den |

- VAD 는 raw 오디오에 Silero VAD 를 한 번만 돌리고, 같은 시간 구간을 denoise 오디오에도 적용했습니다. 두 입력이 서로 다른 구간을 보지 않게 하기 위해서입니다.
- denoise 는 DeepFilterNet v3, `atten_lim_db=-30` 고정.
- 후처리 보정은 넣지 않고 네 결과를 그대로 비교했습니다.
- 데이터: 한국 방송 6종(뉴스·다큐·드라마·사극·예능·스포츠), 편당 48분 \~ 1시간 55분, 발화 구간 3,115개
- 장비: RTX 4090 24GB

### 결과: 정확도

| 콘텐츠 | 구간 수 | W-raw | V-raw | W-den | V-den |
| --- | --- | --- | --- | --- | --- |
| 야구 | 1092 | 1073 | 1026 | 1072 | 1020 |
| 다큐 | 383 | 349 | 330 | 349 | 332 |
| 드라마 | 314 | 282 | 256 | 279 | 251 |
| 예능 | 502 | 464 | 398 | 438 | 366 |
| 사극 | 437 | 411 | 382 | 386 | 363 |
| 뉴스 | 387 | 385 | 377 | 384 | 379 |
| **합계** | 3115 | 2964 | 2769 | 2908 | 2711 |
| **정확도** |  | **95.2%** | 88.9% | 93.4% | 87.0% |

- 구간별 판정 내역은 상세 보고서에 링크된 스프레드시트에 있습니다. 리포에는 비교 코드만 있고 결과 파일은 포함돼 있지 않습니다.
- 순서는 Whisper raw > Whisper denoise > VoxLingua raw > VoxLingua denoise 였습니다.
- **denoise 는 언어 식별에 도움이 되지 않았습니다.** 두 모델 모두 raw 가 더 정확했고, 예능과 사극에서 차이가 컸습니다.

### 결과: 처리 시간

LID 단계만 보면 VoxLingua107 이 훨씬 빠릅니다. 예를 들어 58분짜리 다큐에서 Whisper LID 는 20.1초, VoxLingua107 은 3.3초였습니다. VAD 까지 합친 전체 시간으로는 VoxLingua 쪽이 2 \~ 3배 빨랐습니다.

### 결론

- 정확도를 우선해 **Whisper LID + raw 입력** 을 골랐습니다.
- 그래서 STT 파이프라인은 입력을 둘로 나눕니다. VAD·LID 는 raw, ASR 만 denoised 입니다.

### 설치하다 막힌 점

- DeepFilterNet 공식 패키지 때문에 Python 은 `>=3.11,<3.12` 로 고정했습니다.
- `torch` /`torchaudio` 는 2.9 미만으로 고정했습니다. 2.9 에서 `torchaudio.backend.common.AudioMetaData` 가 제거되어 DeepFilterNet import 가 깨집니다.

### 증적

- 소스: https://github.com/SceneMakerAI/poc-lid-bench (MIT)
- 상세 보고서: https://doc.scenemaker.solbox.com/docs/poc/audio-bench/2
- 모델: https://huggingface.co/speechbrain/lang-id-voxlingua107-ecapa

