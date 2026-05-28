---
id: 멀티모달-llm-한국-방송-6초-클립-영상-이해-벤치마크
title: "멀티모달 LLM 한국 방송 6초 클립 영상 이해 벤치마크"
sidebar_position: 1
slug: "1"
---

<br />

<br />

**프로젝트 성격:**

한국 방송 7개 장르(뉴스, 다큐, 야구, 예능, 드라마, 사극, e-스포츠) × 100개 × 6초 클립(총 700개)에 대한 멀티모달 LLM 영상 이해 품질 벤치마크 PoC

**검증 환경:**

AWS g7e.4xlarge(VRAM 96G) vLLM 서빙 / Qwen3-Omni-30B-A3B-Instruct (OpenAI 호환 엔드포인트)

<br />

## 1. 프로젝트 개요 (Overview)

- **목적:** 6초 단위로 잘게 분할된 한국 방송 클립(영상 + 오디오 + 대사 스크립트)을 멀티모달 LLM 단일 호출로 분석하여, 시각·청각 정보를 통합한 `{summary, objects, actions}` 3 필드 구조화 JSON 을 환각 없이 일관 생성할 수 있는지 PoC.

- **PoC 검증 범위:** 멀티모달 LLM 호출 · 구조화 응답 강제 · 결과 평가로 한정. **영상 분할(ffmpeg)은 사전 준비 단계로 별도 수행** (분할은 사내 ffmpeg 스크립트로 사전 생성, 스크립트는 수동 작성)

- **핵심 목표:**
  1. JSON Schema 강제 (vLLM guided decoding + pydantic `extra="forbid"` ) 로 후처리·정제 단계 제거

  1. 7 장르(뉴스·다큐·예능·드라마·사극·야구·e스포츠) × 100 클립 벤치마크로 SceneMaker 적용 시 장르별 강·약점 정량 평가

- 예상 처리 프로세스

```smalltalk
[원본 방송 영상 입력 (10분 윈도우)]

───── 사전 준비 (본 PoC 범위 외 · 별도 수행 · 추후 자동화 예정) ─────

(A) 영상 분할  — 사내 ffmpeg 스크립트 (별도)
  원본의 00:10:00 ~ 00:20:00 구간을 6초 단위 100 클립으로 분할.
  파일명에 원본 절대초를 인코딩(0001_0600-0606.mp4)하여 윈도우 변경에도 충돌 없음.
  ※ 추후 SceneMaker 본 파이프라인에 통합 예정.

(B) 대사 스크립트  — scripts.json, 수동 작성
  이전 6초 / 현재 6초 / 다음 6초 3 구간 대사를 함께 묶어 모델에 컨텍스트 제공.
  분석 대상은 '현재' 6초로 한정, 전후는 맥락 파악용임을 프롬프트에 명시.
  ※ 추후 외부 자막 · STT 시스템 연동으로 자동 수급 예정.

───── 본 PoC 검증 범위 ─────

[6초 mp4 클립 + 전·현·후 대사 스크립트]
⬇️
1단계. 단일 호출 멀티모달 분석 (Qwen3-Omni via vLLM)
mp4 base64 data URI (video_url) + 텍스트 프롬프트를 OpenAI 호환 chat.completions 로
한 번에 전송. 오디오는 mp4 안에 묶여 vLLM video pipeline 으로 동시 디코딩.
⬇️
2단계. JSON Schema 강제 응답 (Guided Decoding)
{summary, objects, actions} 3 필드를 vLLM response_format=json_schema(strict) 로 강제.
추가 필드 출현 시 pydantic ValidationError 로 차단.
⬇️
3단계. 결과 저장 / 비교 평가
predictions/{category}/{원본명}/{clip_id}.json 에 저장. 카테고리별 샘플링하여 정성 비교.
```

<br />

## 2. 사전 조사

#### **2.1. 분석 모델: Qwen3-Omni-30B-A3B-Instruct**

- **결론:** 6초 멀티모달 클립의 단일 호출 통합 분석을 위해 `Qwen3-Omni-30B-A3B-Instruct` 채택.

- **이유:** Image / Video / Audio / Text 4 모달리티를 단일 모델로 처리하며 OpenAI 호환 vLLM 서빙이 가능한 거의 유일한 오픈소스 옵션. **Thinker–Talker MoE** 구조. 추론 코어(Thinker)가 총 30B / 활성 3B, Talker(음성)·오디오/비전 인코더 포함 전체 체크포인트 ≈ **35B** (본 PoC는 텍스트 출력만 사용 → Talker 미사용).

**모델 스펙**

| 항목 | 값 |
| --- | --- |
| 구조 | Thinker–Talker MoE (네이티브 옴니모달 end-to-end) |
| 파라미터 | 추론 코어(Thinker) 총 30B / 활성 3B · Talker·인코더 포함 전체 ≈ 35B |
| 입력 | 텍스트 · 이미지 · 오디오 · 비디오 |
| 출력 | 텍스트(+음성) — 본 PoC는 텍스트만 사용 (Talker 미사용) |
| 컨텍스트 | 네이티브 32,768 토큰 (실서빙은 16,384 운용 → 아래 표) |
| 다국어 지원 | 텍스트 119개 / 음성입력 19개 / 음성출력 10개 → 한국어 모두 지원 |
| 라이선스 | Apache 2.0 (상용 가능) |

**VRAM / 실서빙 설정 (g7e.4xlarge · 1 GPU)**

| **항목** | **값** | **메모** |
| --- | --- | --- |
| GPU | NVIDIA RTX PRO 6000 Blackwell × 1 (96 GB) | 오레곤 us-west-2 |
| BF16 메모리(공식 카드) | 15초 78.85 GB / 30초 88.52 / 60초 107.74 | 6초 클립이라 96 GB에 충분 |
| `--dtype` | bfloat16 | 원본 정밀도(양자화 아님, 66 GiB 풀 체크포인트) |
| `--gpu-memory-utilization` | 0.85 (≈ 81.6 GB 할당) |  |
| `--tensor-parallel-size` | 1 | 단일 GPU |
| `--max-num-seqs` | 8 | 앱 동시성(4)보다 커서 여유 |

**서빙 컨텍스트 한계**

| **항목** | **값** | **영향** |
| --- | --- | --- |
| 실서빙 `--max-model-len` | **16,384** (네이티브 32,768의 절반) | 컨텍스트 예산 제한 |
| 관측 `prompt_tokens` | ≈ 11,887 (약 73% 소진) | 이미 상당 부분 사용 |
| 리스크 | 고 fps 시 비디오 토큰 급증 → 16k 천장 초과 | 30fps 실험 시 주의 |
| 대응 | `--max-model-len` 상향(KV캐시 VRAM 트레이드오프) 또는 fps 제약 | — |

#### **2.2. 입력 방식:** `from_video` **(mp4 단일 입력) vs** `from_frames_audio` **(분리 입력)**

- **결론:** 6초 mp4 한 덩어리를 `video_url` (base64 data URI) 한 컴포넌트로 그대로 넘기는 `from_video` 방식 채택. 분리 입력(`from_frames_audio` )은 **보류** .

- **이유:** Qwen3-Omni 는 use_audio_in_video 로 영상+오디오 통합 이해를 네이티브 지원하므로, mp4 한 덩어리를 그대로 넘기는 from_video가 모델 권장 입력 방식이자 파이프라인이 가장 단순하다. 분리 입력은 컴포넌트가 4개로 늘고 키프레임 사이 동작 누락·정렬 부담이 있어 보류.

| **비교 항목** | `from_video` **(채택)** | `from_frames_audio` **(보류)** |
| --- | --- | --- |
| **입력 구성** | mp4 1 파일 → `video_url` (data URI) 1 컴포넌트 | 키프레임 JPG 3 장 + WAV 1 개 → 컴포넌트 4 개 |
| **시간 정렬** | 영상·오디오가 컨테이너 안에서 자동 동기 | 클라이언트 측 별도 정렬 보장 필요 |
| **서버 측 의존성** | vLLM 기본 video pipeline 만 사용 | `vllm[audio]` (`av` / `soundfile` / `librosa` ) 별도 설치 필요 |
| **전처리 산출물 용량** | 6초 mp4 (\~1\~3 MB / 클립) | frames JPG 3 장 + wav (\~수백 KB / 클립) |
| **환각 영향** | 영상·오디오 정렬·맥락 자연 유지 | 키프레임 사이 동작 누락 가능성 |
| **PoC 최종 지위** | **메인 파이프라인 확정** | 서버 의존성 보강 후 재개 (`data/derived/` 보존 중) |

<br />

#### **2.3. 출력 스키마 / 환각 가드**

- **결론:** 응답은 **정확히** `{summary, objects, actions}` **3 필드** 로 고정. vLLM `response_format=json_schema(strict=True)` + pydantic `extra="forbid"` 이중 강제.

- **이유:** 후처리(파싱·정제·필드 추가/삭제) 코드 없이 그대로 저장·소비 가능. 분석 대상은 6초 '현재' 클립으로 한정하고 전·현·후 대사를 함께 첨부하되, 프롬프트에 "전후는 맥락용, 묘사에 끌어들이지 말 것"을 명시. `from_video` 검증 단계에서 발견한 두 결함(summary 가 vision 텍스트를 그대로 복사 / audio 필드에 프롬프트 규칙 텍스트 혼입)은 필드별 가이드로 반영 완료.

| **필드** | **정의 및 가이드** |
| --- | --- |
| `summary` (string) | 시각 + 음향 정보를 합쳐 한국어 1\~3 문장으로 자연스럽게 압축. vision/audio 의 표현을 그대로 복사 금지. |
| `objects` (array of string) | 영상에 등장하는 객체·인물·자막·로고 등 명사 키워드 (중복 없이, 각 항목 3 어절 이내). |
| `actions` (array of string) | 영상에서 일어나는 행동·움직임·장면 전환 동사구 (중복 없이). |

#### **2.4. 결과 검증 / 평가 기준**

- **결론:** 출력은 **2단으로 검증** 한다
  1. **형식 검증** : 스키마·pydantic 으로 3필드 구조를 기계적으로 강제(→ 2.3, 자동 100%)

  1. **품질 평가** : 기준 모델(Gemini)로 정답지를 만들어 필드별 자동 지표로 **일치도** 를 측정하고, 표본은 사람이 정성 점검.

- **이유:** 정답 라벨이 없어 절대 정확도의 자동 채점은 불가 → 현재 가장 우수한 **Gemini 출력을 기준(reference)** 으로 삼아 Qwen 출력의 일치도를 정량화한다. 문자열 정확 일치 대신 **의미 기반 매칭** (임베딩 유사도)을 써 동의어(예: "앵커"≈"뉴스 앵커")를 동일 처리. 단, 점수는 절대 정답이 아니라 **"Gemini 대비 일치도"** 이며, **표본 10\~20클립은 사람이 직접 점검** 해 Gemini 라벨 신뢰도를 보정한다.

**품질 평가 지표 (Gemini 정답지 대비)**

| **필드** | **지표** | **측정 방식** | **잡아내는 것** |
| --- | --- | --- | --- |
| `objects` | Precision / Recall / **F1** | 항목 임베딩 코사인 ≥ 임계값 매칭 후 집합 비교 | Precision=환각·오탐, Recall=누락 |
| `actions` | Precision / Recall / **F1** | 위와 동일 | 동작·장면전환 포착력 |
| `summary` | **BERTScore** (P/R/F1) | Gemini 요약과 의미 유사도 | 내용 일치·왜곡·환각 |
| 전 필드 | 코사인 유사도 (0\~1) | 문장 임베딩 코사인 | 전체 의미 일치도 점수 |

**정량 지표 (운영, 자동 집계 → 실제 수치는 3장)**

| **지표** | **설명** |
| --- | --- |
| 처리 성공률 | ok / fail (HTTP 에러 비율) |
| 추론 평균 시간 | Qwen 추론 평균 (ms) |
| 토큰 평균 사용량 | prompt / completion avg per clip |

**⚠️ 주의:** 점수는 "정답"이 아니라 **기준 모델(Gemini)과의 일치도** . Gemini 자체 오류 가능성은 표본 사람 점검으로 보정.

---

<br />

## 3. 테스트

### 3.1. 테스트 방법

1. **6초 클립 생성** (원본 데이터는 사전 준비) — 원본 방송에서 분석 대상 10분 구간을 6초짜리 100개로 잘라 둔다.

1. **분석 서버 실행** — 클립을 받아 모델에 분석을 맡길 API 서버를 켠다.

1. **클립 일괄 요청** — 준비된 클립을 하나씩 서버로 보내 분석을 요청한다. 이때 해당 클립의 대사와 전·현·후 맥락 대사도 함께 첨부.

1. **모델 분석** — 모델(Qwen3-Omni)이 6초 영상·오디오·대사를 한 번에 보고 `{summary, objects, actions}` 3필드 JSON 을 생성.

1. **결과 저장** — 클립별 분석 결과와 처리 통계(소요 시간·토큰 수)를 파일로 저장.

1. **요약·평가** — 저장 결과를 사람이 보기 좋은 표로 정리하고 2.4 기준으로 품질 평가.

### 3.2. 테스트 데이터

테스트에 사용된 원본 데이터는 아래와 같다. 가능한 실제 방송 영상과 비슷한 50분\~2시간 사이로 영상.

| **방송** | **재생시간** | **URL** |
| --- | --- | --- |
| KBS 9 뉴스 | 48:30 | [https://www.youtube.com/watch?v=rX1P-jOoNmM](https://www.youtube.com/watch?v=rX1P-jOoNmM) |
| 슈퍼피쉬 1부 | 58:40 | [https://www.youtube.com/watch?v=iNbWqC1iqKw](https://www.youtube.com/watch?v=iNbWqC1iqKw) |
| KBS 겨울 연가 | 1 :04:52 | [https://www.youtube.com/watch?v=irVKEhb9g8M](https://www.youtube.com/watch?v=irVKEhb9g8M) |
| 태조 왕건 | 54:10 | [https://www.youtube.com/watch?v=nmlE2iPWLGM](https://www.youtube.com/watch?v=nmlE2iPWLGM) |
| 출장십오야 X 스타쉽 전국체전 풀버전 | 1 :00:06 | [https://www.youtube.com/watch?v=6wJGpi1nkCg](https://www.youtube.com/watch?v=6wJGpi1nkCg) |
| 2009 프로야구 한국시리즈 7차전 | 1 :55:22 | [https://www.youtube.com/watch?v=fP1QEs1Uj5U](https://www.youtube.com/watch?v=fP1QEs1Uj5U) |
| **2024 LCK SUMMER 결승전 GEN vs HLE** | 2 :11:23 | [https://www.youtube.com/watch?v=_A_I75nJMF8](https://www.youtube.com/watch?v=_A_I75nJMF8) |

| **카테고리 키** | **장르** | **클립 수** | **비고** |
| --- | --- | --- | --- |
| `news` | 뉴스 | 100 | 자막·앵커 멘트 비중 높음 |
| `docu` | 다큐 | 100 | 내레이션 + 자연·현장음 혼합 |
| `baseball` | 야구 중계 | 100 | 캐스터 + 관중 함성 + 전광판 UI |
| `entertain` | 예능 | 100 | 다인 대화 + 자막 효과 |
| `drama` | 현대 드라마 | 100 | 인물 대사 + BGM |
| `hist_drama` | 사극 | 100 | 시대 의상·소품 + 문어체 대사 |
| `lol` | e스포츠 | 100 | 게임 UI 오버레이 + 캐스터 + 게임음 |
| **합계** | — | **700** | 원본 영상 7편 (장르당 1편, 10분 윈도우 100 등분) |

<br />

<br />

<br />

<br />

---

## 4. 참조 문서

**모델 — Qwen3-Omni**

- [Qwen3-Omni-30B-A3B-Instruct — Hugging Face 모델 카드](https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Instruct) — 모달리티·컨텍스트·BF16 VRAM 표·라이선스·한국어 지원

- [Qwen3-Omni Technical Report (arXiv:2509.17765)](https://arxiv.org/abs/2509.17765) — Thinker–Talker MoE 구조, 오디오·AV 36개 중 32개 오픈소스 SOTA

- [QwenLM/Qwen3-Omni — GitHub](https://github.com/QwenLM/Qwen3-Omni) — 사용법, `use_audio_in_video` 영상·오디오 통합

**하드웨어 — AWS g7e**

- [Amazon EC2 G7e 인스턴스 (제품 페이지)](https://aws.amazon.com/ec2/instance-types/g7e/) — RTX PRO 6000 Blackwell, GPU당 96GB

- [G7e 출시 발표 (AWS News Blog)](https://aws.amazon.com/blogs/aws/announcing-amazon-ec2-g7e-instances-accelerated-by-nvidia-rtx-pro-6000-blackwell-server-edition-gpus/) — 2026-01 GA

- [g7e.4xlarge 스펙 — Vantage](https://instances.vantage.sh/aws/ec2/g7e.4xlarge) — 1 GPU / 96 GiB / 16 vCPU / 128 GiB

**서빙 — vLLM**

- [Qwen3-Omni vLLM 서빙 가이드](https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/examples/online_serving/qwen3_omni/) — `vllm serve` 옵션 (`--max-model-len` 등)

