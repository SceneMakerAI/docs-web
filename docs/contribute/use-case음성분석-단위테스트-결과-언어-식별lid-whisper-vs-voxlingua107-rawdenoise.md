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

STT 앞에서 발화 구간마다 언어를 먼저 판별하려고 하는데, 모델을 뭘로 할지와 입력을 원본으로 줄지 denoise 해서 줄지가 정해지지 않아 재 봤다. 도구는 [`poc-lid-bench`](https://github.com/SceneMakerAI/poc-lid-bench) .

방송 오디오에는 BGM·효과음·함성이 늘 깔려 있어서, denoise 를 하면 당연히 좋아질 거라고 생각하기 쉽다. 결과는 반대였다.

#### 비교한 것

|  | raw | denoise |
| --- | --- | --- |
| Whisper LID (`faster-whisper-large-v3-turbo` ) | W-raw | W-den |
| VoxLingua107 (`speechbrain/lang-id-voxlingua107-ecapa` ) | V-raw | V-den |

- VAD 는 원본에 Silero VAD 를 한 번만 돌리고, 같은 시간 구간을 denoise 오디오에도 그대로 썼다. 두 입력이 다른 구간을 보면 비교가 안 된다.
- denoise 는 DeepFilterNet v3, `atten_lim_db=-30`
- 후처리 보정 없음
- 한국 방송 6종(편당 48분 \~ 1시간 55분), 발화 구간 3,115개, RTX 4090

#### 정확도

|  | 구간 | W-raw | V-raw | W-den | V-den |
| --- | --- | --- | --- | --- | --- |
| 야구 | 1092 | 1073 | 1026 | 1072 | 1020 |
| 다큐 | 383 | 349 | 330 | 349 | 332 |
| 드라마 | 314 | 282 | 256 | 279 | 251 |
| 예능 | 502 | 464 | 398 | 438 | 366 |
| 사극 | 437 | 411 | 382 | 386 | 363 |
| 뉴스 | 387 | 385 | 377 | 384 | 379 |
| 합계 | 3115 | 2964 | 2769 | 2908 | 2711 |
|  |  | **95.2%** | 88.9% | 93.4% | 87.0% |

두 모델 모두 원본이 더 정확했다. 예능과 사극에서 denoise 손해가 컸다. 모델로는 Whisper 가 VoxLingua107 보다 6%p 정도 높다.

구간별 판정은 [상세 보고서](https://doc.scenemaker.solbox.com/docs/poc/audio-bench/2) 에 링크된 스프레드시트에 있다. 리포에는 코드만 있고 결과 파일은 아직 안 올라가 있다([poc-lid-bench#1](https://github.com/SceneMakerAI/poc-lid-bench/issues/1) ).

#### 속도

LID 만 보면 VoxLingua107 이 훨씬 빠르다. 58분짜리 다큐에서 Whisper 20.1초, VoxLingua107 3.3초. VAD 까지 합치면 2 \~ 3배 차이다.

#### 그래서

느려도 Whisper LID 에 원본을 넣기로 했다. STT 파이프라인이 입력을 둘로 나누는 이유가 이것이다. VAD 와 LID 는 원본, ASR 만 denoise.

#### 설치할 때

- Python 은 3.11 로 고정(`>=3.11,<3.12` ). DeepFilterNet 공식 패키지가 거기까지만 안정적이다.
- `torch` /`torchaudio` 는 2.9 미만. 2.9 에서 `torchaudio.backend.common.AudioMetaData` 가 없어져 DeepFilterNet import 가 깨진다.

