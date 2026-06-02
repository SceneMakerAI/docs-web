---
id: 한국어-콘텐츠-lid-정확도-비교-whisper-vs-voxlingua107
title: "한국어 콘텐츠 LID 정확도 비교 — Whisper vs VoxLingua107"
sidebar_position: 1
slug: "1"
---

<br />

## 1. 개요

### 1.1 배경 — STT 파이프라인 LID 단계 문제

STT 는 보통 Whisper 를 쓰지만, 다국어가 섞인 영상에서는 환각과 오류가 두드러진다. 원인 중 하나는 WhisperX 의 lock-in — 영상 초반 30초만 듣고 메인 언어를 정한 뒤 전체를 그 언어로 전사하므로, 중간에 등장하는 외국어 구간이 한국어 모드로 억지 해석되어 garbled 결과가 나온다.

각 발화 구간마다 정확한 언어를 미리 알려주면 결과는 크게 개선된다. 이를 위해 LID(Language Identification, 언어 식별)  를 전사기에서 분리해 별도 단계로 실행하는 구조가 필요한데, 다음 질문이 남는다 — **어떤 모델을 쓰고, 입력은 raw 인가 denoise 인가?** 우리가 다루는 콘텐츠는 BGM·효과음·함성이 항상 깔린 한국 드라마/예능/뉴스 등이라, 일반 깨끗한 음성 기준의 모델 평가가 그대로 통하지 않는다. 정량 데이터 없이 모델도 denoise 적용 여부도 감으로 결정할 수밖에 없는 상태가 본 POC 의 출발점이다.

### 1.2 POC 목적

본 문서는 BGM 이 섞인 한국 영상에서 어떻게 언어를 식별·선택해야 할지를 정량 비교로 답한다. 비교 대상  LID 모델 두 가지(Whisper LID, VoxLingua107) × 입력 두 가지(raw, denoise) = 4-way 매트릭스이며, 동일 샘플에 네 조합을 동시 실행해 일치율과 처리 시간을 측정한다.

### 1.3 결정사항

POC 검증 도구이므로 단순함을 우선했고, 비교 결과의 신뢰성을 위해 변수를 최소화했다.

- **보정 정책 없음** — script check, override, blacklist 등 후처리 X. 네 가지 LID 결과를 그대로 비교.

- **VAD 통제** — raw audio 에 Silero VAD 를 한 번만 실행하고, 같은 시간 구간을 denoise audio 에도 동일 적용. raw / denoise 가 서로 다른 구간을 보는 일이 없도록 통제.

- **모델 사전 로드** — 네 모델을 모두 먼저 로드한 뒤 측정 시작. 처리 시간에서 모델 로딩 비용 제외.

- **denoise 강도 고정** — DeepFilterNet v3, `atten_lim_db=-30` (강도 1단). 강도 비교는 본 POC 범위 밖.

- **LID 단계만** — diarize / ASR 호출 없음. 단일 GPU(cuda:0), 단일 audio 순차 처리.

### 1.4 처리 흐름

```javascript
[Denoise 적용시]
audio → VAD → 각 발화 구간 → denoise → [Whisper | VoxLingua] → LID

[Denoise 미 적용시]
audio → VAD → 각 발화 구간 → [Whisper | VoxLingua] → LID
```

<br />

---

## 2. 비교 설계

### 2.1 모델

비교 대상은 두 가지 LID 모델이다.

**Whisper LID (baseline).** faster-whisper large-v3-turbo
(`mobiuslabsgmbh/faster-whisper-large-v3-turbo` ) 의 `detect_language()` 를 호출. Whisper 는 다국어 음성인식을 학습한 모델이며, LID 는 그 부산물로 얻는 100여 언어 분류 결과다. 입력 오디오의 처음 30초만 사용한다. 상위 STT 파이프라인이 이미 쓰고 있으므로 본 POC 의 **baseline** 으로 둔다.

**VoxLingua107 (실험군).** SpeechBrain ECAPA-TDNN 기반 LID **전용** 모델 (`speechbrain/lang-id-voxlingua107-ecapa` ). 107개 언어를 분류하도록 학습되었고, 음향이 유사한 언어 쌍(ko/ja, zh/ja, th/lo/km 등) 구분이 강한 것으로 알려져 있다. 짧은 발화에서도 비교적 안정적인 신뢰도를 낸다.

LID 전용 모델 후보는 여럿(NeMo TitaNet, ECAPA 포크 등)이지만, VoxLingua107 은 한국어가 학습 언어에 포함되어 있고 우리 환경(GPU 단일, HF 캐시)에 즉시 통합 가능하며, 비교 자료가 풍부해 결과 해석이 쉽다.
따라서 본 POC 의 대안으로 채택했다.

### 2.2 변수

입력 변수로 **raw vs denoise** 를 함께 본다. denoise 는 BGM·효과음·함성을 제거해 음성을 도드라지게 만들지만, enhance 모델은 LID 학습 시 본 적 없는 신호 변형을 만들 수도 있어 LID 정확도에 미치는 효과가 한쪽으로 단정되지 않는다. 상위 STT 파이프라인은 "denoise 가 LID 를 망친다" 는 경험적 가정 아래 raw chunk 로 LID 를 호출하고 있으나, 이 가정 자체를 본 POC 의 검증 대상으로 둔다.

따라서 비교 매트릭스는 **모델 2 × 입력 2 = 4-way** 다.

|  | raw audio | denoise audio |
| --- | --- | --- |
| Whisper LID | W-raw | W-den |
| VoxLingua107 | V-raw | V-den |

같은 발화 구간에 네 결과를 동시 산출하고 일치/불일치를 비교한다.

### 2.3 측정 지표

#### 일치율 (정확도 proxy)

콘텐츠에 ground truth 레이블이 없어 정확도를 직접 잴 수 없다. 대신 네 결과(W-raw / V-raw / W-den / V-den)의 **상호 일치 여부** 를 proxy 로 쓴다. 모두 같으면 안전한 발화, 불일치는 어느 한쪽이 틀렸다는 신호다.


산출 항목:

- **4-way 일치율** — 네 결과 전부 일치

- **W-raw vs V-raw / W-den vs V-den** — 같은 입력에서 모델 간 일치

- **W-raw vs W-den / V-raw vs V-den** — denoise 가 각 모델에 주는 영향

#### 처리 시간

모델 로딩 시간은 제외하고 audio 한 건의 순수 처리 시간만 단계별로 기록한다.

| 단계 | 범위 |
| --- | --- |
| `denoise` | DeepFilterNet 호출 + 16k 리샘플 |
| `vad` | Silero VAD 호출 |
| `whisper_lid` | 모든 segment 의 Whisper LID 호출 합 (raw+denoise) |
| `voxlingua_lid` | 모든 segment 의 VoxLingua107 호출 합 (raw+denoise) |
| `total` | run() 진입부터 완료까지 |

산출물: 세그먼트별 `output/<stem>.csv` + 파일별 `output/timings.csv` .

### 2.4 데이터셋

한국 영상 콘텐츠 6종 (장르별 한 편씩) 을 사용했다. 16kHz mono WAV 전처리 완료, 길이 30분\~2시간대, 정답 레이블 없음(2.3 의 일치율 proxy 방식). 

한국어가 메인이지만 장르별로 외국어 / 배경 소음 양상이 다르다.

| 구분 | 방송 | 재생시간 | URL |
| --- | --- | --- | --- |
| 뉴스 | KBS 9 뉴스 | 48:30 | [https://www.youtube.com/watch?v=rX1P-jOoNmM](https://www.youtube.com/watch?v=rX1P-jOoNmM) |
| 다큐 | 슈퍼피쉬 1부 | 58:40 | [https://www.youtube.com/watch?v=iNbWqC1iqKw](https://www.youtube.com/watch?v=iNbWqC1iqKw) |
| 드라마 | KBS 겨울 연가 | 1:04:52 | [https://www.youtube.com/watch?v=irVKEhb9g8M](https://www.youtube.com/watch?v=irVKEhb9g8M) |
| 사극 | 태조 왕건 | 54:10 | [https://www.youtube.com/watch?v=nmlE2iPWLGM](https://www.youtube.com/watch?v=nmlE2iPWLGM) |
| 예능 | 출장십오야 X 스타쉽 전국체전 풀버전 | 1:00:06 | [https://www.youtube.com/watch?v=6wJGpi1nkCg](https://www.youtube.com/watch?v=6wJGpi1nkCg) |
| 스포츠 | 2009 프로야구 한국시리즈 7차전 | 1:55:22 | [https://www.youtube.com/watch?v=fP1QEs1Uj5U](https://www.youtube.com/watch?v=fP1QEs1Uj5U) |

장르별로 한 편씩 택한 것은 한 장르에 치우친 결론을 피하고, 콘텐츠 특성(BGM 강도, 외국어 양상)과 LID 결과 사이의 패턴을 보기 위함이다.

<br />

---

## 3. 구현

소스코드는 아래 URL 참고

- [https://github.com/SceneMakerAI/poc-lid-bench](https://github.com/SceneMakerAI/poc-lid-bench)

### 3.1 디렉토리/흐름

#### 디렉토리 구조

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

<br />

#### 외부 환경 노트 (git 사용자 대상)

- **데이터 경로** — `main.py` 의 `test_files` 는 사내 경로
(`/stg/vod/scenemaker/sound_full/*.wav` ) 를 하드코딩한 상태. 외부에서 사용 시 본인 환경의 WAV 파일 경로로 교체할 것.

- **모델 캐시** — Whisper LID 는 HF 캐시(`HF_HOME` ) 자동 사용, VoxLingua107 은 `conf.MODEL_DIR` 하위(`voxlingua107/` ) 에 SpeechBrain 이 자동 다운로드. 사전 다운로드가 필요하지 않다.

- **GPU** — cuda:0 고정. 멀티 GPU 환경에서는 `whisper_lid.py` /`voxlingua_lid.py` 의 device 지정을 조정.

<br />

### 3.2 환경 / 모델 / 의존성

#### 환경

- Python **3.11** (`>=3.11,&lt;3.12` — DeepFilterNet 공식 패키지가 3.11까지만 안정 지원)

- 패키지 관리 **uv** (`.venv` + `uv.lock` )

- GPU **RTX 4090 24GB** , cuda:0 단일 사용

#### 의존성 (`pyproject.toml` )

| 패키지 | 버전 | 용도 |
| --- | --- | --- |
| `faster-whisper` | `&gt;=1.0` | Whisper LID (`detect_language` ) |
| `speechbrain` | `>=1.0` | VoxLingua107 LID |
| `deepfilternet-py312` | `>=0.5.7` | DeepFilterNet v3 모델 |
| `deepfilterlib` | `>=0.5.6` | DF 런타임 라이브러리 |
| `soundfile` | `>=0.13` | wav 로드 |
| `torch` | `>=2.4,&lt;2.9` | cu128 wheel, 상한은 DF 호환성 |
| `torchaudio` | `&gt;=2.4,&lt;2.9` | 동일 |

&gt; torch/torchaudio 상한 `&lt;2.9` 는 `torchaudio.backend.common.AudioMetaData`
가 2.9 에서 제거되며 DF 의 import 가 깨지는 문제 회피용. 검증된 조합:
`torch==2.8.0+cu128` .

#### 모델

| 모델 | 다운로드 위치 | 식별자 |
| --- | --- | --- |
| Whisper LID (large-v3-turbo) | HF 캐시 (`HF_HOME` ) | `mobiuslabsgmbh/faster-whisper-large-v3-turbo` |
| VoxLingua107 (ECAPA-TDNN) | `conf.MODEL_DIR/voxlingua107/` | `speechbrain/lang-id-voxlingua107-ecapa` |
| DeepFilterNet v3 | pip 패키지 내장 | `init_df()` 호출 시 자동 |
| Silero VAD | `~/.cache/torch/hub/` | `snakers4/silero-vad` (torch.hub) |

모든 모델은 첫 실행 시 자동 다운로드 (네트워크 필요), 사전 준비 작업 없음.

#### git 사용자 대상 노트

- `HF_HOME` 미설정 시 기본(`~/.cache/huggingface/` ) 으로 다운로드된다.

- `conf.MODEL_DIR` 는 사내 캐시(`/stg/models` )로 설정되어 있음. 외부 환경에선
본인 경로로 변경하거나 SpeechBrain 기본 캐시(`~/.cache/huggingface/` ) 사용으로
코드 수정.

<br />

### 3.3 실행 방법

```javascript
# log.py 에서 로그파일 위치 적절히 수정
> .venv/bin/python main.py
```

<br />

<br />

---

## 4. 결과

### 4.1 정확도

모든 발화 구간의 언어를 구분하여 가장 정확하게 언어를 구분한 것들에 대한 결과는 아래 URL 에서 자세히 나와 있다.

[https://docs.google.com/spreadsheets/d/1zARHI1l5UfJ_pU1VY61xOOtvmteHLZ-QPHjSbRIoZpI/edit?gid=759070170#gid=759070170](https://docs.google.com/spreadsheets/d/1zARHI1l5UfJ_pU1VY61xOOtvmteHLZ-QPHjSbRIoZpI/edit?gid=759070170#gid=759070170)

<br />

간단하게 최종 결과를 이야기 하면

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

- 정확도는 (가장정확) Whisper raw > Whisper denoise > voxlingua raw > voxlingua denoise (가장 부정확) 순서로 나온다.

- **(중요) denoise 를 한다고 해서 언어 구분에서는 좋와 지는 것이 없다.**

<br />

### 4.2 비용 (처리시간)

| file | duration | model | vad | denoise | lid | total | total_hour | 차이 |
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

- **처리속도 순위: (가장빠름) voxlingua raw > voxlingua denoise > Whisper raw > Whisper denoise (가장느림)**

<br />

<br />

<br />

<br />

<br />

<br />

