---
id: poc-기획안-초고속초고품질-다국어-ai-자막-생성-시스템-구축
title: "[PoC 기획안] 초고속·초고품질 다국어 AI 자막 생성 시스템 구축"
sidebar_position: 1
slug: "1"
last_update:
  date: 2026-06-05
---

## 1. 개요

### 1.1 목적

영상 콘텐츠를 다국어 자막으로 자동 생성하기 위한 **STT(Speech-to-Text) 시스템 비교** Proof of Concept.

**핵심 질문** : 다양한 도메인의 한국어 영상 콘텐츠에 대해, 어떤 오픈소스 STT 시스템이 자막 production 에 가장 적합한가?

**비교 대상 시스템**

| 시스템 | 모델 | 비고 |
| --- | --- | --- |
| Whisper | `Systran/faster-whisper-large-v3` | OpenAI Whisper large-v3 의 CTranslate2 변환 (faster-whisper 백엔드) |
| Qwen | `Qwen3-ASR-1.7B`  + `Qwen3-ForcedAligner-0.6B` | 알리바바, ASR + word timestamp 분리 |

> 초기에는 Gemini STT 도 비교 대상이었으나, timestamp 정확도가 분 단위로 drift 되는 이슈로 자막 용도 부적합 판정 후 제외. Gemini 는 judge (평가자) 역할로만 사용.

**평가 방식**

- Gemini 3.5 Flash 가 audio 와 각 시스템의 STT 결과 segment 를 비교하여 -3 \~ 3점 채점
- 콘텐츠/시스템별 점수 분포 + 자막 사용 가능률 (≥0점) 집계
- 도메인별 시스템 권장안 도출

**산출물**

- 콘텐츠 × 시스템 비교 리포트 (`output/report.csv` )
- 환각/오인식 처리 게이트 구성 (whisper 측 5종)
- Production 단계 architecture 권장안

---

### 1.2 범위

#### 포함 (POC 본 범위)

- mono WAV 입력 → 자막 segments (text + 시간 구간 + 언어 코드)
- 노이즈 제거 (DeepFilterNet v3, atten_lim_db = -30)
- 발화 구간 검출 (Silero VAD)
- 다국어 자동 감지 (Whisper LID)
- 다국어 ASR (Whisper / Qwen, 28 / 11개 언어)
- 환각 처리 게이트 (자세히 5장 참조)
- Gemini judge 평가 + 점수 집계 리포트

#### 미포함 (Production 단계 작업)

| 항목 | 사유 / 향후 처리 |
| --- | --- |
| 영상 → WAV 추출 | 외부 전처리로 가정. POC 범위 밖 |
| 화자분리 (diarize) | PyAnnote 별도 통합 가능 (audio 공통 → 1회 호출 후 segment 매칭). 현재 `speaker = None` |
| SRT / VTT 출력 포맷 | 내부 `transcript_md`  포맷만. 변환 단순 |
| Gemini 교정 (correct) 단계 | 평가만 함. 교정은 production 그림 (8장 참조) |
| FastAPI / HTTP API | 배치 처리만 (`main.py`  / `main_qwen.py`  직접 실행) |
| Job queue (asyncio.Queue 등) | 단일 process 순차 처리 |
| 동시 요청 / 다중 클라이언트 | Production 그림에서 dynamic batching 으로 해결 (8장) |

---

### 1.3 평가 콘텐츠 셋

한국 영상 콘텐츠 6종 (장르별 한 편씩) 을 사용했다. 16kHz mono WAV 전처리 완료, 길이 30분\~2시간대, 정답 레이블 없음(2.3 의 일치율 proxy 방식). 

한국어가 메인이지만 장르별로 외국어 / 배경 소음 양상이 다르다.

| 구분 | 방송 | 재생시간 | 특징 | URL |
| --- | --- | --- | --- | --- |
| 뉴스 | KBS 9 뉴스 | 48:30 | 빠른 발화, 강한 BGM/관중 함성, 가장 긴 콘텐츠 | [https://www.youtube.com/watch?v=rX1P-jOoNmM](https://www.youtube.com/watch?v=rX1P-jOoNmM) |
| 다큐 | 슈퍼피쉬 1부 | 58:40 | 차분한 내레이션, 외국어 인터뷰 일부 | [https://www.youtube.com/watch?v=iNbWqC1iqKw](https://www.youtube.com/watch?v=iNbWqC1iqKw) |
| 드라마 | KBS 겨울 연가 | 1:04:52 | 일반 대사, BGM 있음 | [https://www.youtube.com/watch?v=irVKEhb9g8M](https://www.youtube.com/watch?v=irVKEhb9g8M) |
| 사극 | 태조 왕건 | 54:10 | 다화자, 자막 효과음, 빠른 톤 변화 | [https://www.youtube.com/watch?v=nmlE2iPWLGM](https://www.youtube.com/watch?v=nmlE2iPWLGM) |
| 예능 | 출장십오야 X 스타쉽 전국체전 풀버전 | 1:00:06 | 격식체/고어 표현, 한자어 빈도 ↑ | [https://www.youtube.com/watch?v=6wJGpi1nkCg](https://www.youtube.com/watch?v=6wJGpi1nkCg) |
| 스포츠 | 2009 프로야구 한국시리즈 7차전 | 1:55:22 | 또렷한 발음, 외국어 인터뷰/리포트 섞임 | [https://www.youtube.com/watch?v=fP1QEs1Uj5U](https://www.youtube.com/watch?v=fP1QEs1Uj5U) |

#### 콘텐츠별 challenge 요약

- **baseball**  — 환각 위험 최대 (BGM/관중 함성), 짧은 추임새 빈번
- **docu / news**  — 외국어 인터뷰 → 짧은 발화에서 LID 오인 위험
- **hist_drama**  — 한자어/격식체 → 모델이 한자/일본어 토큰 환각 경향
- **drama / entertain**  — 다화자 + BGM → 정상 발화 false positive 위험


**프로젝트 성격:**

방송, 영화, 예능, 스포츠 등 복잡한 미디어 오디오 환경 맞춤형 자막 파이프라인 검증

**검증 환경:**

NVIDIA RTX 4090 (24GB) 1장 기반 기본 가속 환경


---

## 2. 파이프라인 구조

### 2.1 전체 흐름

`원본 wav (mono, 16kHz)
   │
   ▼
[1] denoise — DeepFilterNet v3
   │   ↳ output/1_denoise/<stem>.wav  (캐시, 양쪽 시스템 공유)
   ▼
[2] transcribe — 시스템별 (Whisper / Qwen)
   │   ↳ output/{system}/2_transcribe/<stem>.md
   ▼
[3] evaluate — Gemini judge
   │   ↳ output/{system}/evaluate/<stem>.csv
   ▼
[4] report — 시스템 비교 집계
       ↳ output/report.csv`

진입점:

| 단계 | 명령 |
| --- | --- |
| transcribe — Whisper | `.venv/bin/python main.py` |
| transcribe — Qwen | `.venv-qwen/bin/python main_qwen.py` |
| evaluate | `.venv/bin/python evaluate.py [whisper|qwen|all]` |
| report | `.venv/bin/python report.py` |


### 2.2 디렉토리 / 출력 구조

`output/
├── 1_denoise/<stem>.wav          # DF 결과 (양쪽 공유, 캐시)
├── whisper/
│   ├── 2_transcribe/<stem>.md    # STT 결과
│   ├── evaluate/<stem>.csv       # Gemini 채점
│   └── timings.csv               # duration / transcribe time / RTF
├── qwen/
│   └── (동일 구조)
└── report.csv                    # 시스템 × 콘텐츠 종합 비교`

**transcribe MD** — 1줄 = 1 segment, 자체 포맷:

`[00:02:57.1~00:02:58.4|S???|ko] 넌 가가멜이 무섭지도 않아?`

`S???` 은 화자 (현재 미통합 placeholder). lang 은 ISO 639-1.


---

## 3. 핵심 컴포넌트

5개 컴포넌트로 구성. 모두 GPU (cuda:0) 사용. 시스템 시작 시 한 번 워밍업.

| 컴포넌트 | 역할 | 라이브러리 / 모델 |
| --- | --- | --- |
| Denoise | BGM/잡음 제거 | DeepFilterNet v3 |
| VAD | 발화 구간 검출 | Silero VAD |
| LID | 언어 자동 감지 | Whisper `detect_language`  (large-v3) |
| ASR (Whisper) | 한국어/다국어 전사 | faster-whisper large-v3 (Systran) |
| ASR (Qwen) | 한국어/다국어 전사 + word timestamp | Qwen3-ASR-1.7B + ForcedAligner-0.6B |
| Judge | 정확도 채점 (-3\~3) | Gemini 3.5 Flash |

---

### 3.1 Denoise — DeepFilterNet v3

| 항목 | 값 |
| --- | --- |
| 모델 | DeepFilterNet v3 (pip 패키지 내장) |
| 입출력 sample rate | 입력 무관 → 출력 48kHz int16 |
| `atten_lim_db` | **-30**  (강도 약화 — 노래 가창/일반 발화 보존) |
| 청크 처리 | 30초 단위 분할 (긴 audio 의 spectrogram VRAM OOM 회피) |
| 캐시 | `output/1_denoise/<stem>.wav`  — 양쪽 시스템 공유, 동일 stem 재실행 시 재사용 |

**왜 atten_lim_db = -30?**
풀파워 (`None` ) 면 노래 가창이나 작은 발화도 잡음으로 잘려 ASR 누락 발생. -30dB 로 강도 제한 = 음성 보존 ↑.

---

### 3.2 VAD — Silero VAD

| 항목 | 값 |
| --- | --- |
| 모델 | Silero VAD (`snakers4/silero-vad` , torch.hub) |
| 입력 | **raw audio**  (방안 2 — denoise 변형 영향 회피) |
| 출력 | 발화 구간 리스트 `[(start_s, end_s), ...]` |
| 환경 공유 | Whisper / Qwen 양쪽 venv 동일 |

**역할** — 환각 사전 차단의 1차 방어선. 침묵/BGM 구간을 ASR 에 안 보내기만 해도 환각 큰 폭으로 ↓ (업계 표준 패턴).

---

### 3.3 LID — Whisper `detect_language`

| 항목 | 값 |
| --- | --- |
| 모델 | Whisper large-v3 (multilingual, `mobiuslabsgmbh/faster-whisper-large-v3-turbo` ) |
| 입력 | **raw audio chunk**  (VAD 가 자른 발화 단위) |
| 출력 | `(lang_code, prob, all_probs)`  — 1등 lang + 확률 + 모든 lang 확률 dict |
| 호출 단위 | 발화 chunk 마다 1회 (전체 audio 가 아님) |

**POC 정확도 비교**

| LID 방식 | raw | denoised |
| --- | --- | --- |
| Whisper `detect_language` | **95.2%**  ✅ | 93.4% |
| VoxLingua107 | 88.9% | 87.0% |

→ **Whisper LID 채택** . 추가 VRAM \~1.5GB but `detect_language` 만 호출 (encoder forward + decoder 1 step) 이라 가볍다.

**Qwen 측에서도 동일 LID 사용** — Voxlingua107 보다 정확.

---

### 3.4 ASR

#### 3.4.1 Whisper 측 — faster-whisper large-v3

| 항목 | 값 |
| --- | --- |
| 모델 | `Systran/faster-whisper-large-v3`  (OpenAI Whisper large-v3 의 CT2 변환) |
| 백엔드 | faster-whisper (CTranslate2) |
| 지원 lang | 99개 중 **Tier 1+2+3 (28개)**  만 허용 — 그 외 skip |
| 입력 | denoised audio chunk |
| 호출 옵션 | `beam_size=5` , `condition_on_previous_text=False` , `repetition_penalty=1.2` , `no_repeat_ngram_size=3` |
| 환각 후처리 | 게이트 5종 (5장 참조) |

> turbo (4-layer decoder) 대신 **non-turbo (32-layer)** 사용. 정확도 ↑, 속도 2-3배 ↓. POC 단계에서 정확도 우선.

#### 3.4.2 Qwen 측 — Qwen3-ASR-1.7B + ForcedAligner-0.6B

| 항목 | 값 |
| --- | --- |
| ASR 모델 | `Qwen3-ASR-1.7B` |
| Timestamp 모델 | `Qwen3-ForcedAligner-0.6B`  — word 단위 timestamp 분리 |
| 백엔드 | qwen-asr (transformers 4.57, torch 2.8) |
| 지원 lang | **ALIGNER_LANGS (11개)**  — ko/en/ja/zh/yue/it/es/fr/de/pt/ru |
| 입력 | denoised audio chunk |
| LID | Whisper detect_language (자체 LID 안 씀 — Voxlingua107 88.9% 보다 정확) |
| 짧은 발화 처리 | `main_lang = "ko"`  하드코딩 + 짧은 발화 인접 lang override |

> Whisper 와 Qwen 의존성 충돌 회피 위해 venv 분리 (`.venv` / `.venv-qwen` ).

---

### 3.5 Judge — Gemini 3.5 Flash

| 항목 | 값 |
| --- | --- |
| 모델 | `gemini-3.5-flash` |
| Reference | audio 직접 (시스템 독립) |
| 점수 체계 | -3 \~ 3 (교정 가능성 기반 — 6장 참조) |
| Audio 처리 | 1회 업로드 + **caching**  (TTL 1시간, 비용 75% 절감) |
| Chunk 단위 | 한 호출당 segment 20개 (응답 token 한계 회피) |
| Retry | 응답 segment 수 불일치 시 1회 재시도 (Flash 응답 끝부분 누락 보정) |
| 응답 schema | `list[ScoreItem]`  (TypedDict) — JSON schema 강제 |
| 비용 추정 | 6 콘텐츠 × 2 시스템 ≈ $1-2 |

**왜 Gemini judge 인가?**

- 시스템 간 비교의 객관성 확보 — 같은 평가자 (Gemini) 가 같은 audio 를 듣고 양쪽 STT 결과를 채점
- text 매칭 (WER 등) 보다 의미 기반 채점이 자막 사용성에 가까움
- audio 가 ground truth — STT 시스템마다 segment 분할이 달라도 평가 가능


---

## 4. 시스템 설계 + 환각 처리

POC 의 핵심 시행착오는 거의 Whisper 측 환각 처리. Qwen 측은 lang 정정 패턴 위주.

### 4.1 Whisper 측

#### 모델 / 기본 설정

| 항목 | 값 |
| --- | --- |
| 모델 | `Systran/faster-whisper-large-v3`  (단일 multilingual) |
| 지원 lang 게이트 | `ALLOWED_LANGS`  — Tier 1+2+3 (28개), 그 외 skip |
| 한국어 fine-tune 분기 | **제거**  — 다큐 도메인 정확도 낮음 확인 |
| Decode 옵션 | `beam_size=5` , `condition_on_previous_text=False` , `repetition_penalty=1.2` , `no_repeat_ngram_size=3` |

#### 지원 언어 (Tier 분류)

Whisper 는 언어마다 훈련시킨 데이터 양이 다르기 때문에 Tier가 낮을 수록 환각이 심하게 나타난다. Tier4로 가면 거의 번역이 안되며, 해당 Tier는 과감히 Skip 

- Tier-1 (Word Error Rate &lt; 5%)
  -   영어,  스페인어, 이탈리아어, 프랑스어, 독일어, 포르투칼어

- Tier-2 (WER <5-8%)
  -  한국어,  일본어, 중국어, 러시아어, 폴란드어, 네덜란드어, 폴란드어, 터키어, 카탈루냐어, 우크라이나어

- Tier-3 (WER < 10-20%)
  - 아랍어 (방언별 편차 큼), 히브리어, 힌디어, 인도네시아어, 말레이어, 베트남어 (성조 약함), 그리스어,  헝가리어,  체코어, 핀란드어, 스웨덴어,  덴마크어, 노르웨이어

- Tier-4 (DROP)
  - 태국어, 라오어, 크메르어, 룩셈부르크어, 몰타어등


#### 발견된 환각 패턴 3가지

##### 게이트 1 — VAD pre-filter

| 약어 | **VAD = Voice Activity Detection**  (음성 활동 감지) |
| --- | --- |
| 도구 | Silero VAD (`snakers4/silero-vad` , torch.hub) |
| 입력 | raw audio (전체) |
| 출력 | 발화 구간 `[(start_s, end_s), ...]` |
| 동작 | 발화 외 구간 (침묵/BGM/효과음) 은 ASR 에 안 보냄 |

**왜 효과적?** — Whisper 환각의 가장 큰 원인은 **침묵/BGM 구간에서 학습된 자막 패턴을 생성하는 것** (`ご視聴ありがとうございました` , `Thanks for watching` 등). 발화 구간만 입력하면 이 문제 자체가 사라짐. WhisperX/stable-ts 등 업계 표준 도구도 동일 패턴.

#### 게이트 2 — MIN_LOGPROB (-1.0)

| 정의 | `avg_logprob`  = transcribe 한 각 토큰의 log probability 평균 (segment 단위) |
| --- | --- |
| 의미 | 0 에 가까울수록 모델이 확신, 음수로 멀어질수록 자신 없음 |
| 임계 | `< -1.0`  → segment drop |
| 잡는 케이스 | 환각 catch-all (게이트 1/3/4 가 못 잡은 환각의 최종 방어선) |

**임계값 -1.0 의 의미** — log probability 환산:

| `avg_logprob` | 평균 토큰 확률 | 해석 |
| --- | --- | --- |
| -0.3 | 74% | 정상 발화 (확신) |
| -0.5 | 61% | 정상 발화 |
| -0.7 | 50% | 어림짐작 |
| **-1.0** | **37%** | **환각 영역**  ← 임계 |
| -1.5 | 22% | 거의 확실한 환각 |

- `1.0` 미만 = 각 토큰 평균 확률 37% 미만 = 모델이 자신 없는 상태로 토큰 토함 = 환각 위험.

&gt; 폐지된 게이트 `no_speech_prob` 와 달리, `avg_logprob` 는 BGM/denoise 잔여에 덜 민감 → false positive 적음.

#### 게이트 3 — LID_TRUST_PROB (0.5)

| 약어 | **LID = Language Identification**  (언어 자동 감지) |
| --- | --- |
| 함수 | Whisper `detect_language()`  → `(lang_code, prob, all_probs)`  반환 |
| 임계 | `prob &lt; 0.5`  + 감지된 lang 이 `MAIN_LANG (ko)`  가 아닐 때 |
| 동작 | `lang_code`  를 `MAIN_LANG (ko)`  로 **강제 변경** . 이후 단일 ko transcribe |

**왜 0.5?** — LID 확률 0.23 같은 케이스 = "ko/de/ja/zh 어디든 비슷하게 들림" = LID 자체가 신뢰 못 함. 한국어 콘텐츠 가정 → ko 가정이 자연스러움.

**예시 — 실제 baseball.wav 로그**

`[01:18:43.3\~01:18:44.4] LID de=0.23 → pass
    LID de=0.23 < 0.5 → ko 강제      ← 게이트 3 발동`

원본 LID 결과 그대로 갔으면 독일어로 transcribe → 환각. ko 강제로 정상화.

---

#### 게이트 4 — dual transcribe + MIN_DUAL_LOGPROB (-0.6)

| 조건 | 발화 길이 `< 3초`  + LID 가 비-ko (게이트 3 통과 후) |
| --- | --- |
| 동작 1 | ko 와 LID lang 두 번 transcribe → 각각 `avg_logprob`  계산 |
| 동작 2 | `max(lp_ko, lp_lid)`  가 더 큰 (확신 높은) lang 채택 |
| 동작 3 (drop 조건) | **양쪽 lp 모두** `< -0.6`  **→ 둘 다 환각 의심 → drop** |
| 잡는 케이스 | ja/zh 짧은 환각 (1-2초짜리 LID 오인 케이스) |

**왜 -0.6?** — log probability 50% 수준. 양쪽 다 50% 미만이면 모델이 어느 lang 으로도 자신 없음 = 짧은 음향이 garbled/노이즈일 가능성 ↑.

**예시 — 실제 baseball.wav 로그**

`dual [00:15:26.8~00:15:27.9|1.1s] lp(ko)=-0.89, lp(zh)=-0.71 → 양쪽 약함, drop`

`max(-0.71, -0.89) = -0.71 < -0.6` → drop. 원래 LID=zh 였으면 `一观测者来交换` 같은 환각이 됐을 case.

---

#### 게이트 5 — 한글 char 비율 게이트 (30%)

| 조건 | `chosen_lang == "ko"`  + 결과 text 의 한글 비율 `< 30%` |
| --- | --- |
| 동작 | segment drop |
| 잡는 케이스 | ko 강제 transcribe 했는데 결과가 일본어 토큰 (Whisper 한계) |

**왜 30%?** — 정상 한국어 발화는 보통 한글 비율 70%+ (숫자/영문 약자 섞여도). 30% 미만 = 사실상 일본어/한자 토큰 환각.

**한글 비율 계산** — 공백/문장부호 제외한 글자/숫자 중 한글 음절 (가-힣) 비율.

| text | 한글 비율 | 결과 |
| --- | --- | --- |
| `生涯ゲスト` | 0% | drop |
| `ちょうちょだが。` | 0% | drop |
| `투수는 이승호, 오늘 투런홈런` | 100% | pass |
| `FA컵 결승` | 33% (FA=2, 컵결승=3) | pass (3% 마진) |
| `MVP 수상` | 40% | pass |

&gt; 이 게이트가 잡는 환각 = Whisper 모델 자체의 한계. 외부 코드로 막을 수 있는 가장 가까운 방법 (drop only, 정정 불가).

#### Drop 정책 (살리기 불가능한 케이스)

**케이스** — 음향이 ko 인데 Whisper 가 ko 모드에서도 일본어 토큰 출력
**원칙** — "**잘못된 자막보다 누락이 낫다** " → drop

---

#### 최종 흐름

`audio_raw + audio_denoised
   │
   ▼  16kHz resample
   │
[VAD 게이트]  raw audio → 발화 구간 [(start, end), ...]
   │
   ▼  각 발화 chunk 마다
[LID]  Whisper.detect_language(raw chunk) → (lang, prob)
   │
   ▼  ALLOWED_LANGS 게이트 (Tier 1+2+3 외 skip)
   │
[LID_TRUST_PROB]  prob<0.5 + 비-ko → ko 강제
   │
   ▼
[transcribe 분기]
   ├─ 짧음(<3s) + 비-ko → dual (ko + lid)
   │   └─ max lp 채택. 양쪽 < -0.6 → drop
   └─ 그 외 → single (lid 그대로)
   │
   ▼  결과 segment loop
[후처리 게이트]
   ├─ avg_logprob < -1.0 → drop
   ├─ duration < 0.2s → drop
   └─ chosen=ko + 한글 < 30% → drop
   │
   ▼
segment 저장 (transcribe MD)`

---

### 4.2 Qwen 측

#### 모델 / 기본 설정

| 항목 | 값 |
| --- | --- |
| ASR 모델 | `Qwen3-ASR-1.7B` |
| Timestamp 모델 | `Qwen3-ForcedAligner-0.6B` |
| 지원 lang 게이트 | `ALIGNER_LANGS`  (11개) — ko/en/ja/zh/yue/it/es/fr/de/pt/ru |
| LID | **Whisper LID 채택**  (POC 95.2% vs Voxlingua107 88.9%) |
| Batch | `max_inference_batch_size=8`  (4090 안전치) |

#### main_lang 하드코딩 + 짧은 발화 override

| 항목 | 동작 |
| --- | --- |
| `MAIN_LANG = "ko"` | 하드코딩 (Whisper 측과 일관성). 외국어 메인 콘텐츠는 production 시 다수결로 복귀 가능 |
| 짧은 발화 (< 3s) override | LID 부정확 → 앞/뒤 발화 lang 동일하면 그 lang, 다르면 `MAIN_LANG` |
| ALIGNER_LANGS 게이트 | 11개 외 lang → skip (timestamp 불가) |

#### Script 기반 lang 자동 정정

transcribe 결과 text 의 **문자 종류로 lang 후처리 정정** — LID/Qwen 의 lang 오류 보정.

| 감지된 script | 정정 lang |
| --- | --- |
| 한글 (가-힣) | ko |
| 가나 (히라가나/가타카나) | ja |
| 키릴 | ru |
| 한자만 (가나/한글 없음) | zh |
| 라틴만 + 원래 라틴 lang | 그대로 유지 |
| 라틴만 + 원래 ko/ja/zh/ru | en |
| 어느 script 도 안 잡힘 (숫자/기호) | 원래 lang 유지 |

→ Whisper 측의 "한글 char 비율 게이트" 와 비슷한 발상이지만, **drop 대신 정정** (Qwen 은 LID 오류를 ko 강제로 처리 안 함, 단순히 lang 만 바로잡음).


---
















## 1. 프로젝트 개요 (Overview)

- **목적:** 배경음악, 효과음, 관중 함성 등이 섞인 미디어 파일에서 인간의 대사(Dialogue)만 고립시켜, 자막의 오인식 및 AI 환각(Hallucination) 현상을 원천 차단하고 단 3분 만에 1시간짜리 영상을 완벽한 다국어 자막으로 변환하는 시스템 검증.
- **핵심 목표:** 
  -  음성 향상(Speech Enhancement)을 통한 단어 오차율(WER) 최소화

  -  문장별/구간별 실시간 다국어 교차 인식(Code-switching) 및 공백 처리 구현

  -  LLM을 통한 문맥 기반 고유명사 및 맞춤형 오타 최종 교정

- 예상 처리 프로세스

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


## 2. 사전 조사

#### **2.1. 음성 인식 엔진: WhisperX (Turbo vs Large-v3)**


- **결론:** 전사(Transcription) 중심의 초고속 시스템을 위해 `Turbo (Large-v3-Turbo)` 모델 채택.
- **이유:** Large-v3 가 최고 성능을 내지만 정확도 손실은 1% 내외 이고 속도는 Turbo 가 3배 이상 빠름. 음성 데이터를 전처리를 해서 원본 품질을 높이는게 정확도+속도 면에서 유리하다고 판단

| **비교 항목** | **WhisperX Large-v3** | **WhisperX Turbo** | **비고 및 비즈니스 영향** |
| --- | --- | --- | --- |
| **매개변수 (Parameters)** | 1,550M (15.5억 개) | **809M (8.09억 개)** | 구조 슬림화로 가벼운 구동 가능 |
| **디코더 레이어 수** | 32개 | **4개** | 레이어를 1/8로 줄여 추론 속도 극대화 |
| **실구동 VRAM** *(FP16 기준)* | 약 4.5 GB \~ 5.0 GB | **약 2.5 GB \~ 3.0 GB** | GPU 메모리 절약으로 동시 처리량(Batch) 확대 가능 |
| **1시간 오디오 처리 시간** *(RTX 4090 / WhisperX 배치 기준)* | 약 45초 \~ 1분 내외 | **약 15초 \~ 20초 내외** | **Turbo가 약 3배 이상 빠름** (I/O 속도 제외 순수 연산) |
| **정확도 지표** *(LibriSpeech WER)* | 기준점 (\~2.7%) | **미세 하락 (\~3.0%)** | **오차율 차이 약 0.3%** 수준으로 실전 체감 불가 |
| **번역 기능** *(--task translate)* | **지원** (다국어 ➡️ 영어 번역) | **미지원** (오직 들리는 언어 그대로 전사) | 다국어 '받아쓰기'는 둘 다 완벽 지원 |

#### 2.2 노이즈 제거

- **결론:** 방송, 영화, 스포츠 해설 등 다채로운 소음 환경에서 대사(Dialogue)만 초고속으로 고립시키기 위해 `DeepFilterNet v3` 를 전처리 메인 엔진으로 채택.
- **이유:** BGM 제거에 특화된 음악 분리 모델(RoFormer, MDX)과 달리, 인간의 성대 구조 주파수 외의 모든 소리(효과음, 함성, 배경음)를 '잡음'으로 인지해 완벽히 제거함. 특히 RTX 4090 환경에서 1시간 분량을 단 10초대에 끊어내는 압도적인 인프라 비용 절감 효과를 가짐.

| **비교 대상 모델** | **DeepFilterNet v3 (채택)** | **BS-RoFormer (Vocal)** | **MDX23C (Kim Vocal 2)** | **HTDemucs v4** |
| --- | --- | --- | --- | --- |
| **모델 분류** | **음성 향상 (Speech Enhancement)** | 음악 소스 분리 (SOTA) | 주파수 분리 (전통 강호) | 하이브리드 소스 분리 |
| RTX 4090 기준 1시간 처리 시간 | **🚀 약 10초 \~ 15초** | 약 1분 30초 \~ 2분 | 약 45초 \~ 1분 | 약 1분 \~ 1분 30초 |
| **연산 소요 VRAM** | **⚡ 1 GB 미만 (극도로 가벼움)** | 약 4 GB \~ 8 GB | 약 4 GB \~ 6 GB | 약 4 GB 내외 |
| **주요 필터링 타겟** | **현장 소음, 관중 함성, 울림(에코), 효과음, BGM** | 배경음악(OST), 악기 반주 | 배경음악, 스튜디오 잡음 | 드럼, 베이스, 기타 악기군 |
| **최대 장점** | 연산 속도가 압도적으로 빠르며, 배우들의 웅얼거림이나 속삭임 등 극적 대사 보존력이 우수함. | 배경음악(BGM) 차단 능력이 현존 오픈소스 중 세계 최고 수준. | 목소리의 선명도(Clarity)가 높아 딕션이 또렷해짐. | 오디오를 4개 트랙으로 분리하여 현장감 조절이 가능함. |
| **단점 및 한계** | 대사보다 BGM 볼륨이 극도로 큰 일부 예능에서는 음악 소리가 미세하게 새어 나올 수 있음. | 모델이 무거워 대량 처리 시 병목 우려. 대사가 왜곡되어 Whisper가 씹을 가능성 존재. | 영화 효과음이나 스포츠 관중 소리를 '악기'로 인지하지 못해 걸러내지 못함. | 속삭이는 작은 대사를 '소음'으로 오인해 통째로 지워버리는 경우가 있음. |
| **PoC 최종 지위** | **메인 파이프라인 확정** | 특수 장르(예능)용 서브 픽 | 대량 고속 처리용 후보 픽 | 스포츠 중계용 검증 픽 |


---


## 3. 테스트

### 3.1 테스트 방법



### 3.2 테스트 데이터

테스트 데이터는 아래와 같다. 가능한 실제 방송 영상과 비슷한 50분\~2시간 사이로 영상

| 방송 | 재생시간 | URL |
| --- | --- | --- |
| KBS 9 뉴스 | 48:30 | [https://www.youtube.com/watch?v=rX1P-jOoNmM](https://www.youtube.com/watch?v=rX1P-jOoNmM) |
| 슈퍼피쉬 1부 | 58:40 | [https://www.youtube.com/watch?v=iNbWqC1iqKw](https://www.youtube.com/watch?v=iNbWqC1iqKw) |
| KBS 겨울 연가 | 1:04:52 | [https://www.youtube.com/watch?v=irVKEhb9g8M](https://www.youtube.com/watch?v=irVKEhb9g8M) |
| 태조 왕건 | 54:10 | [https://www.youtube.com/watch?v=nmlE2iPWLGM](https://www.youtube.com/watch?v=nmlE2iPWLGM) |
| 출장십오야 X 스타쉽 전국체전 풀버전 | 1:00:06 | [https://www.youtube.com/watch?v=6wJGpi1nkCg](https://www.youtube.com/watch?v=6wJGpi1nkCg) |
| 2009 프로야구 한국시리즈 7차전 | 1:55:22 | [https://www.youtube.com/watch?v=fP1QEs1Uj5U](https://www.youtube.com/watch?v=fP1QEs1Uj5U) |

#### 3.2.1 영상 다운로드 및 포멧 변환

##### 영상 다운로드)

- 영상은 720p 사이즈로 받는다.
  - 너무 클 경우: 분석시 시간이 오래 걸림

  - 너무 작은 경우: 이미지 분석에 정밀도가 떨어짐

```yaml
> yt-dlp -f "bv*[height<=720]+ba/b[height<=720]" "<URL">
```


##### 영상 변환)

- 다운로드 받은 영상으로 부터 음성만 분리 한다.
- 음성은 압축이 되지 않는 wav 파일 형태로 받고 Noise 제거를 위해서 아래 옵션은 중요함
  - -vn : 비디오 제외(Video No)

  - -ac 1 : Audio Channel 수 (2: 스테레오, 1: Mono)
    - WhisperX 와 DeepFilterNet 은 내부적으로 Mono 로 처리 한다. (스테레오가 들어오면 Mono로 변환 함)

  - -ar 48000 : DeepFilterNet 의 native 샘플레이트는 48KHz
    - 만약 16KHz 가 들어오면 내부적으로 업샘플을 거치는데 이때 정보 손실이 발생한다.

  - -c:a pcm_s16le : 음성 압축 없이 원본 그대로 출력

```yaml
ffmpeg -y -i <input.mp4> -vn -ac 1 -ar 48000 -c:a pcm_s16le <audio.wav>
```




