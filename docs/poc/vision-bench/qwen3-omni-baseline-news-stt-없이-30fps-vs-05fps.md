---
id: qwen3-omni-baseline-news-stt-없이-30fps-vs-05fps
title: "qwen3-omni-baseline-news-stt-없이-30fps-vs-05fps"
sidebar_position: 2
slug: "2"
last_update:
  date: 2026-05-27
---

> **news 카테고리 100 클립** 을 STT(Speech-to-Text) 컨텍스트 없이 Qwen3-Omni 로 분석한 baseline.
**30fps (원본) vs 0.5fps (저프레임 변환본)** 두 가지로 측정 — 영상 fps 가 분석 성능에 미치는 영향 비교.

---

#### 1. 실행 환경

| 항목 | 값 |
| --- | --- |
| 모델 | Qwen3-Omni-30B-A3B-Instruct |
| 서빙 | vLLM (OpenAI 호환 엔드포인트, 단일 GPU) |
| 클라이언트 | FastAPI 서버 (`POST /analyze/by-clip-path` ) |
| 동시성 | 4 (서버 측 `asyncio.Semaphore` ) |
| STT 컨텍스트 | **없음** — prompt 의 대사 섹션 자체 제거 (baseline 측정용) |
| 측정 일자 | 2026-05-22 |

#### 2. 데이터

- 카테고리: `news` / 클립 수: **100개** × 2 fps variant
- 각 클립 **6초** → 영상 합계 600초 (10분)
- 클립 명명: `0001_0600-0606` `0100_1194-1200` (원본 영상의 절대초 인코딩)

#### 2.1 클립 사양 (variant 별)

| 항목 | 30fps (원본) | 0.5fps (저프레임) |
| --- | --- | --- |
| 해상도 | 1280×720 | 1280×720 |
| Frame rate | 30 fps | 0.5 fps (2초당 1프레임) |
| 클립당 프레임 수 | **180** | **3** |
| 코덱 | h264 | h264 |
| Duration | 6.037 초 | 6.037 초 |
| 클립당 사이즈 | 1.2 MB | 492 KB |
| Bitrate | 1.6 Mbps | 0.67 Mbps |

#### 3. 처리 결과

| variant | ok | fail | fail 비율 |
| --- | --- | --- | --- |
| 30fps | 97 | 3 | 3.0% |
| 0.5fps | **99** | **1** | 1.0% |

Fail 케이스는 모두 HTTP 500 Internal Server Error (vLLM 측 일시 에러). 재시도 시 보통 해결.

#### 4. 시간 통계

#### 4.1 30fps (원본)

| 측정 항목 | n | 합계 (s) | 평균 (ms) | p50 (ms) | p95 (ms) | min / max (ms) |
| --- | --- | --- | --- | --- | --- | --- |
| Pipeline wall (배치 전체) | 100 | 191.13 | 1,911.3 | — | — | — |
| **Qwen 추론** | 97 | 690.20 | **7,115.5** | 7,171.0 | 7,985.4 | 5,268 / 9,058 |
| Client elapsed (HTTPX) | 100 | 761.73 | 7,617.3 | 7,188.5 | 8,811.2 | 5,279 / 24,139 |
| 네트워크 + 서버 오버헤드 | 97 | 50.09 | 516.4 | 12.0 | 1,603.2 | -2,140 / 17,312 |

#### 4.2 0.5fps (저프레임)

| 측정 항목 | n | 합계 (s) | 평균 (ms) | p50 (ms) | p95 (ms) | min / max (ms) |
| --- | --- | --- | --- | --- | --- | --- |
| Pipeline wall (배치 전체) | 100 | **78.10** | 781.0 | — | — | — |
| **Qwen 추론** | 99 | 294.01 | **2,969.8** | 2,910.0 | 3,470.1 | 2,429 / 3,767 |
| Client elapsed (HTTPX) | 100 | 309.57 | 3,095.7 | 2,917.0 | 3,551.1 | 2,431 / 15,023 |
| 네트워크 + 서버 오버헤드 | 99 | 12.86 | 129.8 | 2.0 | 451.9 | -693 / 12,142 |

#### 5. 토큰 사용량

| variant | prompt 합계 | prompt avg/클립 | completion 합계 | completion avg/클립 |
| --- | --- | --- | --- | --- |
| 30fps | 1,143,727 | **11,791** | 14,843 | 153 |
| 0.5fps | 169,389 | **1,711** | 13,454 | 136 |

Prompt 토큰의 대부분이 mp4 base64 인코딩 (영상 프레임 + 오디오). 0.5fps 는 영상 프레임이 1/60 로 줄어 prompt 토큰이 **6.89× 압축** 됨.

#### 6. 실시간 대비 처리 속도

| variant | 영상 합계 | wall-time | 실시간 대비 |
| --- | --- | --- | --- |
| 30fps | 600 초 | 191 초 | **3.14×** |
| 0.5fps | 600 초 | 78 초 | **7.69×** |

#### 7. 30fps vs 0.5fps 한눈 비교

| 측정 | 30fps | 0.5fps | 차이 |
| --- | --- | --- | --- |
| Pipeline wall | 191.13s | 78.10s | **2.45× 빠름** |
| Qwen 추론 평균 | 7,115ms | 2,970ms | **2.40× 빠름** |
| Qwen p95 | 7,985ms | 3,470ms | 2.30× 빠름 |
| Prompt 토큰 avg | 11,791 | 1,711 | **6.89× 감소** |
| Completion 토큰 avg | 153 | 136 | -11% |
| 실시간 대비 | 3.14× | 7.69× | 2.45× 향상 |
| ok/fail | 97/3 | 99/1 | 안정성 ↑ |

#### 8. 분석 품질 정성 비교

같은 클립 (0050 — 산업 통계 그래픽 장면) 의 두 fps 분석 결과:

**30fps** :

> 산업 현장 배경에 철강·알루미늄 원재료와 자동차·비행기 등 부품 파생상품을 보여주는 그래픽이 표시된 방송 장면이다. 오른쪽 하단에는 수화 통역사가 수화를 하고 있다.

**0.5fps** :

> 산업 현장 배경에 철강·알루미늄 원재료와 자동차·비행기 등 부품 파생상품을 시각화한 그래픽이 표시된다. 오른쪽 하단에는 손을 흔드는 남성이 보인다.

→ 핵심 그래픽·자막 내용은 두 fps 모두 정확히 묘사. **차이는 우측 하단 동적 요소** — 30fps 는 "수화 통역사가 수화를 하고 있다" 로 정확, 0.5fps 는 "손을 흔드는 남성" 으로 **연속 동작의 의미를 오인** .

#### 8.1 관찰 정리

| 측면 | 30fps | 0.5fps |
| --- | --- | --- |
| 그래픽 / 자막 / 정적 시각 요소 | 정확 | 정확 (3프레임으로도 충분) |
| 인물 의상 / 배경 디테일 | 정확 | 일부 누락 |
| 장면 전환 인식 | 정확 | 누락 빈도 ↑ |
| 연속 동작 (수화 등) | 정확 묘사 | 단순화 또는 오인 (예: 수화 → 손짓) |
| 환각 (없는 요소 생성) | 낮음 | 약간 ↑ |
| `actions` 다양성 | 평균 더 다양 | 현저히 적음 |

#### 9. 결론

| 결론 | 내용 |
| --- | --- |
| **속도** | 0.5fps 가 **2.40× 빠르고 prompt 토큰 6.89× 절감** — 비용·throughput 측면 명백한 우위 |
| **품질** | 자막·로고·인물 위치 같은 정적 요소는 동등. 단 **장면 전환·연속 동작 인식 능력 떨어짐** , 일부 환각 |
| **활용 권장** | 자막·OCR·고정 장면 위주 (예: 자막 인식, 정적 thumbnail 생성) 에는 0.5fps 충분. 동작·장면 전환·세밀한 컷 분석엔 30fps 권장 |

#### 10. 다음 단계

- 나머지 6 카테고리 동일 조건 측정 (특히 동작 많은 `baseball` , `lol` — 0.5fps 격차 더 클 것으로 예상)
- Fail 케이스 재시도 + 원인 분석
- STT 컨텍스트 추가 후 동일 100 클립 재측정 → baseline 대비 품질 개선 정량 비교
- Gemini 동일 입력 평행 측정 → 모델 간 비교

#### 11. 재현 명령

```bash
# FastAPI 서버 기동
./script/start.sh

# 30fps 측정 (baseline)
PYTHONPATH=src uv run script/run_batch.py news news --no-script --model qwen_no_script

# 0.5fps 측정
PYTHONPATH=src uv run script/run_batch.py news news_0.5fps --no-script --model qwen_no_script_0.5fps

# 사람 보기용 markdown
PYTHONPATH=src uv run script/render_summary.py qwen_no_script news news
PYTHONPATH=src uv run script/render_summary.py qwen_no_script_0.5fps news news_0.5fps
```

산출물:

- `predictions/{model}/news/{source}/{clip_id}.json` — 요청별 envelope
- `predictions/{model}/news/{source}/_meta.json` — 시간·토큰 통계 raw
- `predictions/{model}/news/{source}/summary.md` — 사람 보기용 요약

