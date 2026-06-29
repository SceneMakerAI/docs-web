---
id: 3편-추론-파라미터-조합-qwen3-omni-6초-클립-분석-최적-구성-확정
title: "[3편] 추론 파라미터 조합 Qwen3-Omni 6초 클립 분석 (최적 구성 확정)"
sidebar_position: 4
slug: "4"
last_update:
  date: 2026-06-29
---

## 1. 들어가며

SceneMaker 의 6초 클립 분석은 시청각 정보를 `{summary, ocr, actions, sounds}` 4필드 JSON 으로 **안정적으로 생성** 하는 것을 목표로 한다. 2편(OFAT 스윕)은 추론 파라미터를 **한 번에 하나씩** 흔들어, 출력만으로 판정 가능한 **순응(adherence)** 기준에서 각 축의 단독 효과를 규명했다.

2편이 객관적으로 좁힌 결과는 다음과 같다.

| **파라미터** | **2편 결론** |
| --- | --- |
| temperature | 0.7 확정 (greedy 폭주·1.0 이종문자 동시 회피) |
| top_p / top_k | 1.0 / -1 유지 · top_k 10 완주 후보 |
| frequency penalty | 0\~0.5 구간 (완주·반복 개선, 단 sounds 감소) |
| repetition penalty | 제외 (이종문자 유발) |

OFAT 는 한 축만 본다. 그러나 실제 운영값은 **여러 축을 동시에** 적용한다. 본 편은 2편이 좁힌 후보들을 **조합** 해, 단독 효과가 겹칠 때의 거동을 확인하고 **최적 샘플링 구성** 을 확정한다. 확정한 구성은 이후 미세조정으로 다듬는다.

조합 평가는 2편과 동일하게 **출력만으로 판정 가능한 축** 으로 한다. 완주율·degeneration(이종문자·미완·반복)·커버리지·추론 비용. 내용 정확성(환각·완전성)은 자동 채점 대상이 아니며 본 편 범위 밖이다.

## 2. 실험 설계

### 2.1. 고정 · 변동

- **고정** : temperature 0.7 · top_p 1.0 · repetition penalty off · max_tokens 512 · `media_io_kwargs.video.fps` 0.5 · 오디오 on · 동일 70클립(7장르 × 10) · 동일 프롬프트 · 4필드 strict 스키마
- **변동(조합 축)** : frequency penalty {0, 0.3, 0.5} × top_k {-1, 10}

### 2.2. 출력 스키마 (4필드)

응답은 정확히 `{summary, ocr, actions, sounds}` 필드로 고정한다 (vLLM `response_format=json_schema(strict)` + pydantic `extra="forbid"` 이중 강제).

| **필드** | **정의** |
| --- | --- |
| `summary` (string) | 시각·청각을 종합한 한국어 한 문장 요약 |
| `ocr` (array) | 화면 텍스트 (자막·로고) |
| `actions` (array) | 행동·움직임·장면 전환 |
| `sounds` (array) | 대사를 제외한 배경음·효과음 |

### 2.3. 조합 셀 (2 × 3)

2편·2.5편이 객관적으로 정한 값만 교차한다. frequency penalty 3수준 × top_k 2수준 = 6 셀.

|   | **top_k -1** | **top_k 10** |
| --- | --- | --- |
| **freq 0** | C1 (2편 baseline) | C4 |
| **freq 0.3** | C2 | C5 |
| **freq 0.5** | C3 | C6 |

### 2.4. 측정 지표

2편과 동일한 출력 기반 지표로 평가한다.

| **지표** | **정의** |
| --- | --- |
| `ok` / `fail` | 스키마 통과 / 실패 레코드 수 (완주율) |
| `infer_ms` | 클립당 추론 시간 (비용·20분 예산) |
| `penalty` | (`repeat`  • `finish_length`  • `foreign`  • `replacement` ) ÷ 4 — degeneration 종합 |
| `field` | (`summary`  • `ocr`  • `actions`  • `sounds` ) ÷ 4 — 정보 커버리지 |

## 3. 결과

> ⏳ 테스트(C1\~C6 · 회차 누적) 후 작성 — 조합별 완주·degen·비용·커버리지

## 4. 분석

> ⏳ 테스트 후 작성 — frequency × top_k 상호작용 · 최적 셀 · 최적 샘플링 구성 도출

## 5. 결론

> ⏳ 테스트 후 작성 — 최적 샘플링 구성 확정 · 미세조정 방향 · 운영(vision-cognition) 핸드오프

