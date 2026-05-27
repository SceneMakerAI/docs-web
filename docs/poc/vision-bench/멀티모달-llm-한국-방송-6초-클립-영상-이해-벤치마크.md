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

- **이유:** Image / Video / Audio / Text 4 모달리티를 단일 모델로 처리하며 OpenAI 호환 vLLM 서빙이 가능한 거의 유일한 오픈소스 옵션. MoE 구조(총 30B / 활성 3B)로 단일 GPU 추론 가능, vLLM guided decoding 으로 JSON Schema 강제 응답이 그대로 받힘.

<br />

#### **2.2. 입력 방식:** `from_video` **(mp4 단일 입력) vs** `from_frames_audio` **(분리 입력)**

- **결론:** 6초 mp4 한 덩어리를 `video_url` (base64 data URI) 한 컴포넌트로 그대로 넘기는 `from_video` 방식 채택. 분리 입력(`from_frames_audio` )은 **보류** .

- **이유:** vLLM video pipeline 이 영상·오디오를 동시 디코딩하므로 추가 분리 비용 0. 분리 입력 방식은 서버 vLLM venv 에 `vllm[audio]` 디코더 (`av` / `soundfile` / `librosa` ) 가 설치되어 있지 않아 현재 구동 불가 — 산출물 (`data/derived/` 의 frames + audio.wav) 은 보존하여 서버 의존성 보강 후 즉시 재개 가능.

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

<br />

---

<br />

## 3. 테스트

### 3.1. 테스트 방법

- **분석 단위:** 6초 mp4 클립 (원본의 `00:10:00 ~ 00:20:00` 구간을 100 등분하여 클립 데이터 파일을 준비한다.

- **분석 API:** 

- **동시성 / 백프레셔:** `VLLM_CONCURRENCY=4` (`asyncio.Semaphore` ) — 초과 요청은 거부 없이 대기 (큐잉)

- **저장:** `predictions/{category}/{원본명}/{clip_id}.json` 에 결과 저장 후 카테고리별 무작위 샘플로 정성 비교

- **요청 추적:** 응답 헤더 `X-Request-Id` (8자 hex) 가 로그 라인 prefix 와 동일하게 박혀 1:1 trace 매칭

<br />

### 3.2. 테스트 데이터

테스트에 사용된 원본 데이터는 아래와 같다. 가능한 실제 방송 영상과 비슷한 50분\~2시간 사이로 영상.

| **방송** | **재생시간** | **URL** |
| --- | --- | --- |
| KBS 9 뉴스 | 48:30 | [https://www.youtube.com/watch?v=rX1P-jOoNmM](https://www.youtube.com/watch?v=rX1P-jOoNmM) |
| 슈퍼피쉬 1부 | 58:40 | [https://www.youtube.com/watch?v=iNbWqC1iqKw](https://www.youtube.com/watch?v=iNbWqC1iqKw) |
| KBS 겨울 연가 | 1:04:52 | [https://www.youtube.com/watch?v=irVKEhb9g8M](https://www.youtube.com/watch?v=irVKEhb9g8M) |
| 태조 왕건 | 54:10 | [https://www.youtube.com/watch?v=nmlE2iPWLGM](https://www.youtube.com/watch?v=nmlE2iPWLGM) |
| 출장십오야 X 스타쉽 전국체전 풀버전 | 1:00:06 | [https://www.youtube.com/watch?v=6wJGpi1nkCg](https://www.youtube.com/watch?v=6wJGpi1nkCg) |
| 2009 프로야구 한국시리즈 7차전 | 1:55:22 | [https://www.youtube.com/watch?v=fP1QEs1Uj5U](https://www.youtube.com/watch?v=fP1QEs1Uj5U) |
| **2024 LCK SUMMER 결승전 GEN vs HLE** | 2:11:23 | [https://www.youtube.com/watch?v=_A_I75nJMF8](https://www.youtube.com/watch?v=_A_I75nJMF8) |

<br />

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

