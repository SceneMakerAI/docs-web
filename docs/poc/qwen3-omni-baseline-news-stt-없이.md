---
id: qwen3-omni-baseline-news-stt-없이
title: "Qwen3-Omni baseline — news (STT 없이)"
sidebar_position: 5
slug: "5"
---

> **news 카테고리 100 클립** 을 STT(Speech-to-Text) 컨텍스트 없이 Qwen3-Omni 로 분석한 baseline 결과.

> 추후 STT 컨텍스트 추가 시 비교군으로 사용.

### 1. 실행 환경

| 항목 | 값 |
| --- | --- |
| 모델 | Qwen3-Omni-30B-A3B-Instruct |
| 서빙 | vLLM (OpenAI 호환 엔드포인트, 단일 GPU) |
| 클라이언트 | FastAPI 서버 (`POST /analyze/by-clip-path` ) |
| 동시성 | 4 (서버 측 `asyncio.Semaphore` ) |
| STT 컨텍스트 | **없음** — prompt 의 대사 섹션 자체 제거 (baseline 측정용) |
| 측정 일자 | 2026-05-22 |

### 2. 데이터

- 카테고리: `news` / 클립 수: **100개**

- 각 클립 **6초** → 영상 합계 600초 (10분)

- 클립 명명: `0001_0600-0606` \~ `0100_1194-1200` (원본 영상의 절대초 인코딩)

### 3. 처리 결과

| 결과 | 건수 |
| --- | --- |
| ok (HTTP 200) | **97** |
| fail (HTTP 500 Internal Server Error) | **3** |
| 합계 | 100 |

Fail 은 vLLM 측 일시 에러로 추정. 재시도 시 보통 해결.

### 4. 시간 통계

파이프라인 wall-time, Qwen 추론 시간, 네트워크 오버헤드를 분리해 측정.

| 측정 항목 | n | 합계 (s) | 평균 (ms) | p50 (ms) | p95 (ms) | min / max (ms) |
| --- | --- | --- | --- | --- | --- | --- |
| **Pipeline wall** (배치 클라이언트 전체) | 100 | **191.13** | 1,911.3 | — | — | — |
| **Qwen 추론** (서버 측 `meta.elapsed_ms` ) | 97 | 690.20 | **7,115.5** | 7,171.0 | 7,985.4 | 5,268 / 9,058 |
| 클라이언트 elapsed (HTTPX) | 100 | 761.73 | 7,617.3 | 7,188.5 | 8,811.2 | 5,279 / 24,139 |
| 네트워크 + 서버 오버헤드 (클라이언트 − Qwen) | 97 | 50.09 | 516.4 | 12.0 | 1,603.2 | -2,140 / 17,312 |

각 측정 의미:

- **Pipeline wall** : 배치 클라이언트 시작 \~ 종료 wall clock — 운영 관점 "총 처리 시간"

- **Qwen 추론** : 서버 라우트가 측정한 vLLM `chat.completions.create()` 호출 단독 시간 — 모델 자체 처리 비용

- **클라이언트 elapsed** : 클라이언트의 HTTPX 호출 elapsed — Qwen 추론 + 네트워크 왕복 + 서버 직렬화 + Semaphore 대기 모두 포함

- **네트워크 + 서버 오버헤드** : 클라이언트 elapsed − Qwen 추론 — 통신·직렬화·파일 read·prompt 빌드 등 부수 비용

### 5. 토큰 사용량

| 종류 | 합계 | 평균/클립 |
| --- | --- | --- |
| prompt | 1,143,727 | 11,791 |
| completion | 14,843 | 153 |

Prompt 토큰의 거의 전부가 6초 mp4 base64 인코딩 (영상 프레임 + 오디오) 으로 채워짐. 텍스트 프롬프트 자체는 약 200 토큰 분량.

### 6. 실시간 대비 처리 속도

| 항목 | 값 |
| --- | --- |
| 영상 합계 | 600 초 (10 분) |
| 처리 wall-time | 191 초 (3 분 11 초) |
| **실시간 대비 속도** | **3.14×** real-time |

동시 4 호출 환경에서 Qwen 추론 합계(690s) ÷ 4 ≈ 172s 가 이론 한계. 실측 191s 로 **약 91% 효율** (큐잉 대기 + 네트워크 손실 약 9%).

### 7. 분석 품질 (정성 관찰)

STT 컨텍스트 없이도 Qwen3-Omni 가:

- 화면 자막의 OCR(Optical Character Recognition) 텍스트를 정확히 읽어 묘사에 반영

- 인물 의상·배경·장면 전환 같은 시각 요소 일관 묘사

- `objects` / `actions` 명사·동사 키워드를 중복 없이 정돈된 형태로 추출

baseline 수준에서도 자막·로고 인식 능력이 의미 있게 높음. STT 컨텍스트 추가 시 어떤 부분에서 추가 개선이 나타나는지가 다음 측정의 관전 포인트.

### 8. 다음 단계

- [ ] 나머지 6 카테고리 (`docu` , `baseball` , `entertain` , `drama` , `hist_drama` , `lol` ) 동일 조건 측정

- [ ] Fail 케이스 재시도 + 원인 분석 (vLLM 측 로그 확인)

- [ ] STT 컨텍스트 추가 후 동일 100 클립 재측정 → baseline 대비 품질 개선 정량 비교

- [ ] Gemini 동일 입력 평행 측정 → 모델 간 정성·정량 비교

### 9. 재현 명령 (요약)

```bash
# FastAPI 서버 기동
./script/start.sh

# 배치 실행 (STT 컨텍스트 없음)
PYTHONPATH=src uv run script/run_batch.py news news --no-script --model qwen_no_script

# 사람 보기용 markdown 생성
PYTHONPATH=src uv run script/render_summary.py qwen_no_script news news
```

산출물:

- `predictions/qwen_no_script/news/news/{clip_id}.json` — 요청별 envelope

- `predictions/qwen_no_script/news/news/_meta.json` — 시간·토큰 통계 raw

- `predictions/qwen_no_script/news/news/summary.md` — 사람 보기용 요약

