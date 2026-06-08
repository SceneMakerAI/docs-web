---
id: poc-기획안-초고속초고품질-다국어-ai-자막-생성-시스템-구축
title: "[PoC 기획안] 초고속·초고품질 다국어 AI 자막 생성 시스템 구축"
sidebar_position: 1
slug: "1"
last_update:
  date: 2026-06-08
---

## 1. 개요

### 1.1 목적

영상 콘텐츠를 다국어 자막으로 자동 생성하기 위한 **STT(Speech-to-Text) 시스템 비교** Proof of Concept.

**핵심 질문** : 다양한 도메인의 한국어 영상 콘텐츠에 대해, 어떤 오픈소스 STT 시스템이 자막 production 에 가장 적합한가?

**비교 대상 시스템**

<table>
<thead><tr>
<th>시스템</th>
<th>모델</th>
<th>비고</th>
</tr></thead>
<tbody>
<tr>
<th>Whisper</th>
<td><code>Systran/faster-whisper-large-v3</code></td>
<td>OpenAI Whisper large-v3 의 CTranslate2 변환 (faster-whisper 백엔드)</td>
</tr>
<tr>
<th>Qwen</th>
<td><code>Qwen3-ASR-1.7B</code> + <code>Qwen3-ForcedAligner-0.6B</code></td>
<td>알리바바, ASR + word timestamp 분리</td>
</tr>
</tbody></table>

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

```
원본 wav (mono, 16kHz)
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
       ↳ output/report.csv
```

진입점:

<table>
<thead><tr>
<th>단계</th>
<th>명령</th>
</tr></thead>
<tbody>
<tr>
<td>transcribe — Whisper</td>
<td><code>.venv/bin/python main.py</code></td>
</tr>
<tr>
<td>transcribe — Qwen</td>
<td><code>.venv-qwen/bin/python main_qwen.py</code></td>
</tr>
<tr>
<td>evaluate</td>
<td><code>.venv/bin/python evaluate.py [whisper|qwen|all]</code></td>
</tr>
<tr>
<td>report</td>
<td><code>.venv/bin/python report.py</code></td>
</tr>
</tbody></table>


### 2.2 디렉토리 / 출력 구조

```
output/
├── 1_denoise/<stem>.wav          # DF 결과 (양쪽 공유, 캐시)
├── whisper/
│   ├── 2_transcribe/<stem>.md    # STT 결과
│   ├── evaluate/<stem>.csv       # Gemini 채점
│   └── timings.csv               # duration / transcribe time / RTF
├── qwen/
│   └── (동일 구조)
└── report.csv                    # 시스템 × 콘텐츠 종합 비교
```

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

<table&gt;
<tbody>
<tr>
<th>약어</th>
<td><strong>VAD = Voice Activity Detection</strong> (음성 활동 감지)</td>
</tr>
<tr>
<th>도구</th>
<td>Silero VAD (<code>snakers4/silero-vad</code>, torch.hub)</td>
</tr>
<tr>
<th>입력</th>
<td>raw audio (전체)</td>
</tr>
<tr>
<th>출력</th>
<td>발화 구간 <code>[(start_s, end_s), ...]</code></td>
</tr>
<tr>
<th>동작</th>
<td>발화 외 구간 (침묵/BGM/효과음) 은 ASR 에 안 보냄</td>
</tr>
</tbody></table>


**왜 효과적?** — Whisper 환각의 가장 큰 원인은 **침묵/BGM 구간에서 학습된 자막 패턴을 생성하는 것** (`ご視聴ありがとうございました` , `Thanks for watching` 등). 발화 구간만 입력하면 이 문제 자체가 사라짐. WhisperX/stable-ts 등 업계 표준 도구도 동일 패턴.

#### 게이트 2 — MIN_LOGPROB (-1.0)

<table>
<tbody>
<tr>
<th>정의</th>
<td><code>avg_logprob</code> = transcribe 한 각 토큰의 log probability 평균 (segment 단위)</td>
</tr>
<tr>
<th>의미</th>
<td>0 에 가까울수록 모델이 확신, 음수로 멀어질수록 자신 없음</td>
</tr>
<tr>
<th>임계</th>
<td><code>&lt; -1.0</code> → segment drop</td>
</tr>
<tr>
<th>잡는 케이스</th>
<td>환각 catch-all (게이트 1/3/4 가 못 잡은 환각의 최종 방어선)</td>
</tr>
</tbody></table>

**임계값 -1.0 의 의미** — log probability 환산:

| `avg_logprob` | 평균 토큰 확률 | 해석 |
| --- | --- | --- |
| -0.3 | 74% | 정상 발화 (확신) |
| -0.5 | 61% | 정상 발화 |
| -0.7 | 50% | 어림짐작 |
| **-1.0** | **37%** | **환각 영역**  ← 임계 |
| -1.5 | 22% | 거의 확실한 환각 |

- `1.0` 미만 = 각 토큰 평균 확률 37% 미만 = 모델이 자신 없는 상태로 토큰 토함 = 환각 위험.

> 폐지된 게이트 `no_speech_prob` 와 달리, `avg_logprob` 는 BGM/denoise 잔여에 덜 민감 → false positive 적음.

#### 게이트 3 — LID_TRUST_PROB (0.5)

<table>
<tbody>
<tr>
<th>약어</th>
<td><strong>LID = Language Identification</strong> (언어 자동 감지)</td>
</tr>
<tr>
<th>함수</th>
<td>Whisper <code>detect_language()</code> → <code>(lang_code, prob, all_probs)</code> 반환</td>
</tr>
<tr>
<th>임계</th>
<td><code>prob &lt; 0.5</code> + 감지된 lang 이 <code>MAIN_LANG (ko)</code> 가 아닐 때</td>
</tr>
<tr>
<th>동작</th>
<td><code>lang_code</code> 를 <code>MAIN_LANG (ko)</code> 로 <strong>강제 변경</strong>. 이후 단일 ko transcribe</td>
</tr>
</tbody></table>

**왜 0.5?** — LID 확률 0.23 같은 케이스 = "ko/de/ja/zh 어디든 비슷하게 들림" = LID 자체가 신뢰 못 함. 한국어 콘텐츠 가정 → ko 가정이 자연스러움.

**예시 — 실제 baseball.wav 로그**

```
[01:18:43.3~01:18:44.4] LID de=0.23 → pass
    LID de=0.23 < 0.5 → ko 강제      ← 게이트 3 발동
```

원본 LID 결과 그대로 갔으면 독일어로 transcribe → 환각. ko 강제로 정상화.

---

#### 게이트 4 — dual transcribe + MIN_DUAL_LOGPROB (-0.6)

<table>
<tbody>
<tr>
<th>조건</th>
<td>발화 길이 <code>&lt; 3초</code> + LID 가 비-ko (게이트 3 통과 후)</td>
</tr>
<tr>
<th>동작 1</th>
<td>ko 와 LID lang 두 번 transcribe → 각각 <code>avg_logprob</code> 계산</td>
</tr>
<tr>
<th>동작 2</th>
<td><code>max(lp_ko, lp_lid)</code> 가 더 큰 (확신 높은) lang 채택</td>
</tr>
<tr>
<th>동작 3 (drop 조건)</th>
<td><strong>양쪽 lp 모두 </strong><code>&lt; -0.6</code><strong> → 둘 다 환각 의심 → drop</strong></td>
</tr>
<tr>
<th>잡는 케이스</th>
<td>ja/zh 짧은 환각 (1-2초짜리 LID 오인 케이스)</td>
</tr>
</tbody></table>

**왜 -0.6?** — log probability 50% 수준. 양쪽 다 50% 미만이면 모델이 어느 lang 으로도 자신 없음 = 짧은 음향이 garbled/노이즈일 가능성 ↑.

**예시 — 실제 baseball.wav 로그**

`dual [00:15:26.8~00:15:27.9|1.1s] lp(ko)=-0.89, lp(zh)=-0.71 → 양쪽 약함, drop`

`max(-0.71, -0.89) = -0.71 < -0.6` → drop. 원래 LID=zh 였으면 `一观测者来交换` 같은 환각이 됐을 case.

---

#### 게이트 5 — 한글 char 비율 게이트 (30%)

<table>
<tbody>
<tr>
<th>조건</th>
<td><code>chosen_lang == &quot;ko&quot;</code> + 결과 text 의 한글 비율 <code>&lt; 30%</code></td>
</tr>
<tr>
<th>동작</th>
<td>segment drop</td>
</tr>
<tr>
<th>잡는 케이스</th>
<td>ko 강제 transcribe 했는데 결과가 일본어 토큰 (Whisper 한계)</td>
</tr>
</tbody></table>

**왜 30%?** — 정상 한국어 발화는 보통 한글 비율 70%+ (숫자/영문 약자 섞여도). 30% 미만 = 사실상 일본어/한자 토큰 환각.

**한글 비율 계산** — 공백/문장부호 제외한 글자/숫자 중 한글 음절 (가-힣) 비율.

| text | 한글 비율 | 결과 |
| --- | --- | --- |
| `生涯ゲスト` | 0% | drop |
| `ちょうちょだが。` | 0% | drop |
| `투수는 이승호, 오늘 투런홈런` | 100% | pass |
| `FA컵 결승` | 33% (FA=2, 컵결승=3) | pass (3% 마진) |
| `MVP 수상` | 40% | pass |

> 이 게이트가 잡는 환각 = Whisper 모델 자체의 한계. 외부 코드로 막을 수 있는 가장 가까운 방법 (drop only, 정정 불가).

#### Drop 정책 (살리기 불가능한 케이스)

**케이스** — 음향이 ko 인데 Whisper 가 ko 모드에서도 일본어 토큰 출력
**원칙** — "**잘못된 자막보다 누락이 낫다** " → drop

---

#### 최종 흐름

```
audio_raw + audio_denoised
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
segment 저장 (transcribe MD)
```

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

#### 지원 언어

Qwen 은 약 30개 언어가 가능하지만, Timestamp 를 지원하는  **Qwen3-ForcedAligner 가 11 개 언어만 구분 가능**

- 한국어, 일본어, 중국어 (보통화), 광둥어, 영어, 이탈리아어, 스페인어, 프랑스어, 독일어, 포르투갈어, 러시아어

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

## 5. 평가 방법

Gemini 3.5 Flash 가 audio (ground truth) 와 STT 결과 segment 를 비교해서 채점. 시스템 독립 (Whisper / Qwen 각각 같은 audio 로 평가).


### 5.1 점수 체계 (-3 \~ 3, 교정 가능성 기반)

단순 일치/불일치가 아니라 **"이 segment 가 추후 교정 단계 (Gemini correct 등) 에서 살릴 수 있는가"** 를 점수에 반영.

| 점수 | 이름 | 설명 | 예시 |
| --- | --- | --- | --- |
| **3** | OK | 의미 동일, 사소한 차이 (띄어쓰기/오타/조사 미세 차이) | "넌 가가멜이 무섭지도 않아?" 정답 일치 |
| **2** | 의미동일 | 의미 같음, 표현 다름 (동의어/어순 변화) | 정답 "갔다" → STT "갔어요" |
| **1** | 절반/추임새 | 핵심 의미 절반, 또는 짧은 추임새 (1-2글자, 무해) | "어", "음", "아" / 교정 가능성 50%+ |
| **0** | 교정가능 | 문장은 잘못됐지만 추후 교정 가능성 20%+ | "투수" → "제수" 같은 오인식 — 문맥으로 복원 가능 |
| **-1** | 일부맞음 | 일부 단어만 맞음, 의미 대부분 다름 (교정 어려움) |  |
| **-2** | 환각 | audio 발화 없는데 자막처럼 보이는 text 생성 | 침묵 + "Thank you for watching" / 아랍어 자막 크레딧 |
| **-3** | 완전다름 | audio 발화는 있지만 text 와 완전히 무관 | ja 인터뷰인데 garbled ko text |

#### -2 vs -3 의 차이

| 구분 | audio 발화 여부 | text |
| --- | --- | --- |
| **-2 환각** | ❌ 발화 없음 (침묵/BGM) | 자막처럼 자연스러운 문장 생성 |
| **-3 완전다름** | ✅ 발화 있음 | 발화 내용과 완전히 다른 text |


---

### 5.2 외국어 +1 보정

한국어 외 (lang ≠ ko) segment 는 점수를 **+1점 후하게** (max 3 cap).

| 보정 전 | 보정 후 (외국어) |
| --- | --- |
| 2점 | 3점 |
| 1점 | 2점 |
| 0점 | 1점 |
| -1점 | 0점 |
| -2점 | -1점 |
| -3점 | -2점 |

#### 이유

- ASR 시스템의 외국어 정확도가 한국어 대비 낮음 — 우리 시스템 (한국어 콘텐츠 가정) 의 외국어 처리는 best-effort
- 영어 인터뷰가 일부 단어 누락 / 미세 어색 → 그래도 시청자가 자막으로 이해 가능
- 한국어 자막의 표준 잣대를 그대로 외국어에 적용하면 너무 가혹

#### 예시

```
audio: "I go to school"
STT  : "I go to the school"   ← 사소한 단어 추가
원래 점수: 2 (의미동일, 표현 다름)
보정 후 : 3 (외국어 +1)
```

### 5.3 자막 사용 가능률 (≥0점)

**기준** — segment 점수가 0점 이상이면 "자막으로 사용 가능"

| 점수 | 자막 처리 (production 시) |
| --- | --- |
| 3, 2 | ✅ 그대로 자막 사용 |
| 1 | ✅ Gemini 교정으로 다듬어 사용 |
| 0 | ✅ Gemini 교정 시도 (가능성 20%+) |
| -1, -2, -3 | ❌ Drop (잘못된 자막보다 누락이 낫다) |

#### 정량 지표

`자막 사용 가능률 = (점수 ≥ 0 인 segment 수) / 전체 segment 수 × 100%`

POC 결과 (7장 참조) 에서 모든 시스템 × 콘텐츠가 90%+ 달성. = 우리 환각 게이트가 효과적으로 -1 \~ -3 케이스를 사전 차단했음을 시사.

#### 왜 0점 기준?

- "잘못됐지만 교정 가능 (가능성 20%+)" 까지를 자막 후보로 인정
- production 시 Gemini correct 단계에서 가능성 20%+ segment 를 실제로 살릴 시도
- 0점 미만은 교정 비용 > 가치 → drop


---

## 6. 결과

실행 소스 : [https://github.com/SceneMakerAI/poc-stt-bench](https://github.com/SceneMakerAI/poc-stt-bench)

### 6.1 실행 명령어

```javascript
cd /usr/service/source/scenemaker/poc/poc-stt-bench

# (필요시) 기존 결과 정리 — denoise 캐시는 유지
\rm -rf output/whisper/2_transcribe output/whisper/evaluate output/whisper/timings.csv
\rm -rf output/qwen/2_transcribe output/qwen/evaluate output/qwen/timings.csv

# 1. Whisper STT
.venv/bin/python main.py

# 2. Qwen STT (별도 venv)
.venv-qwen/bin/python main_qwen.py

# 3. Gemini judge 평가 (whisper + qwen)
.venv/bin/python evaluate.py all

# 4. 종합 비교 리포트
.venv/bin/python report.py
```


처리 단계별 출력

| 단계 | 출력 |
| --- | --- |
| (1) Whisper | `output/whisper/2_transcribe/*.md`  + `timings.csv` |
| (2) Qwen | `output/qwen/2_transcribe/*.md`  + `timings.csv` |
| (3) evaluate | `output/{whisper,qwen}/evaluate/*.csv` |
| (4) report | `output/report.csv`   |


### 6.2 처리 시간 비교

#### 6.2.1 콘텐츠별 transcribe 시간 (denoise 제외)

| 콘텐츠 | 길이 | Whisper (RTF) | Qwen (RTF) | Qwen 속도 비교 |
| --- | --- | --- | --- | --- |
| baseball | 1h 55m | 345.9s (0.050) | 309.0s (0.045) | 1.12× ↑ |
| docu | 58m | 118.2s (0.034) | 54.4s (0.015) | **2.17× ↑** |
| drama | 1h 5m | 88.3s (0.023) | 49.1s (0.013) | **1.80× ↑** |
| entertain | 1h | 159.8s (0.044) | 193.9s (0.054) | 0.82× (Whisper 우세) |
| hist_drama | 54m | 111.5s (0.034) | 54.1s (0.017) | **2.06× ↑** |
| news | 48m | 149.5s (0.051) | 80.5s (0.028) | 1.86× ↑ |


#### 6.2.2 관찰

- **Qwen 이 대체로 1.8 \~ 2.2배 빠름**  — Qwen3-ASR 이 chunk 들을 batch 처리 (`max_inference_batch_size=8` )
- **entertain**  만 Whisper 우세 — Qwen 의 ForcedAligner 가 효과음/추임새 많은 콘텐츠에서 word timestamp 부정확 → 재처리 비용 ↑ 추정
- **baseball**  은 두 시스템 비슷 — Whisper 측 segment 수가 Qwen 보다 1.6배 많아 처리 부담 분산 (1983 vs 1250)
- RTF &lt; 0.06 → 둘 다 실시간보다 **20배 이상 빠름**  (production 처리량 여유 충분)


### 6.3 vRAM 사용량 비교

| 컴포넌트 | Whisper 측 | Qwen 측 | 비고 |
| --- | --- | --- | --- |
| **ASR 모델** | 3 GB<br&gt;(`Systran/faster-whisper-large-v3` , CT2 float16) | 3.5 GB<br>(`Qwen3-ASR-1.7B` , bfloat16, batch=8) |  |
| **Timestamp 모델** | — (ASR 에 포함) | 1.5 GB<br>(`Qwen3-ForcedAligner-0.6B` ) | word 단위 timestamp |
| **LID 모델** | — (ASR 과 동일 인스턴스 재사용) | 1.5 GB<br>(`large-v3-turbo` , float16) | Whisper 측은 ASR 모델이 LID 까지 처리 |
| **Denoise** | 0.5 GB (DeepFilterNet v3) | 0.5 GB (DeepFilterNet v3) | 양쪽 공통 |
| **VAD** | 10 MB (Silero VAD) | 10 MB (Silero VAD) | 양쪽 공통 |
| **합계** | **\~3.5 GB** | **\~7 GB** |  |
| **GPU 점유율 (4090 24GB)** | 15% | 30% |  |


### **6.4 품질 결과 비교**

#### 종합 점수표

| 콘텐츠 | Whisper (avg / 사용%/-3%) | Qwen (avg / 사용%/-3%) | 승자 |
| --- | --- | --- | --- |
| **baseball** | 2.72 / 98.6% / 0.7% | 2.74 / 99.4% / 0.2% | Qwen (미세) |
| **docu** | **2.73**  / **97.6%**  / 1.6% | 2.41 / 92.3% / **6.0%** | 🏆 **Whisper**  (큰 차이) |
| **drama** | 2.69 / 98.0% / 1.5% | 2.69 / 98.5% / 1.2% | 동률 |
| **entertain** | 2.64 / 97.1% / 1.7% | 2.55 / 97.3% / 1.3% | Whisper (미세) |
| **hist_drama** | 2.58 / 96.1% / 2.4% | 2.52 / 96.1% / 1.1% | 동률 |
| **news** | 2.92 / 99.5% / 0.4% | 2.85 / 98.7% / 0.8% | Whisper (미세) |


#### Segment 수 비교

| 콘텐츠 | Whisper | Qwen | Whisper / Qwen |
| --- | --- | --- | --- |
| baseball | 1983 | 1250 | 1.59× |
| docu | 371 | 401 | 0.93× |
| drama | 402 | 336 | 1.20× |
| entertain | 1150 | 848 | 1.36× |
| hist_drama | 460 | 459 | 1.00× |
| news | 731 | 471 | 1.55× |


### 6.5 전체 평가

1. **단일 시스템 선택 시 → Whisper 권장**
   - 안정적인 정확도 (5/6 콘텐츠 우세 or 동률)

   - VRAM 절반 (3.5 GB vs 7 GB)

   - 환각 게이트 5종으로 production-ready

   - docu 같은 위험 콘텐츠에서 명확한 우위

2. **Qwen 의 강점**
   - **속도**  — Whisper 대비 1.8-2.2배 (batch 처리) (단, Whisper 도 일부 Batch 처리 가능)

   - **baseball**  같은 BGM 강한 빠른 발화 콘텐츠

#### 의사결정 매트릭스

| 우선순위 | 선택 |
| --- | --- |
| 정확도 + 단순함 | **Whisper 단독** |
| 처리량 최대 + 정확도 양호 | Qwen 단독 + batch tuning |
| 비용 최소 (단일 GPU, 작은 모델) | Whisper turbo 도 검토 (정확도 trade-off) |




