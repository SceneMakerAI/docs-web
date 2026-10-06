---
id: use-casewhisper-단위테스트-결과-한국어-방송-6종에서-faster-whisper-large-v3-vs-qwen3-asr
title: "[Use Case][Whisper] 단위테스트 결과 — 한국어 방송 6종에서 faster-whisper large-v3 vs Qwen3-ASR"
sidebar_position: 8
slug: "8"
description: "한국어 방송 6종에서 faster-whisper large-v3 vs Qwen3-ASR"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

GitHub Discussion: [https://github.com/SceneMakerAI/docs-web/discussions/34](https://github.com/SceneMakerAI/docs-web/discussions/34)

월별 계획 8월 항목 "Use Case Report 단위테스트 결과 (Whisper)"에 해당하는 글입니다. 한국어 방송 콘텐츠에서 두 오픈소스 ASR 을 비교한 [`poc-stt-bench`](https://github.com/SceneMakerAI/poc-stt-bench) 의 결과를 공유합니다.

### 비교 대상

- **Whisper** : `Systran/faster-whisper-large-v3` (faster-whisper / CTranslate2)
- **Qwen** : `Qwen3-ASR-1.7B` + `Qwen3-ForcedAligner-0.6B`

### 방법

```text
raw wav
[1] denoise      DeepFilterNet v3 (atten_lim_db=-30)
[2] VAD          Silero VAD (raw audio)
[3] LID          Whisper detect_language (raw audio)
[4] ASR          Whisper / Qwen (denoised audio)
[5] post-filter  Whisper: 후처리 게이트 / Qwen: 문자 기반 언어 정정
[6] evaluate     Gemini 가 오디오와 세그먼트 텍스트를 비교해 -3 ~ 3 점 채점
[7] report       시스템 × 콘텐츠 집계
```

- 데이터: 한국어 방송 6종(뉴스·다큐·드라마·사극·예능·스포츠), 합계 약 6시간 20분
- 장비: RTX 4090 24GB
- 정답 자막이 없어서 사람 대신 멀티모달 모델을 평가자로 썼습니다. 점수는 절대 정확도가 아니라 두 시스템의 상대 비교로 봐야 합니다.

### 결과

| 지표 | Whisper | Qwen |
| --- | --- | --- |
| 평균 점수 (-3 \~ 3) | 2.71 | 2.63 |
| 자막 사용 가능률 (0 점 이상) | 97.8% | 97.0% |
| 환각 비율 (-3 점) | 1.4% | 1.8% |
| 평균 RTF | 0.042 | 0.032 |
| VRAM | 약 3.5 GB | 약 7 GB |

- Whisper 가 전반적으로 더 정확했고, 다큐에서 차이가 컸습니다(환각 비율 1.6% 대 6.0%).
- Qwen 은 더 빨랐고(RTF 0.032 대 0.042), 야구 중계처럼 발화가 빠른 콘텐츠에서 근소하게 앞섰습니다.
- VRAM 은 Whisper 가 절반입니다.

### 환각을 줄인 방법 (Whisper)

효과가 컸던 순서입니다.

1. **VAD pre-filter** : 침묵·BGM 구간을 ASR 에 보내지 않는다
2. **MIN_LOGPROB** : `avg_logprob < -1.0` 인 세그먼트를 버린다
3. **LID_TRUST_PROB** : 언어 감지 확률이 0.5 미만이고 한국어가 아니면 한국어로 강제한다
4. **dual transcribe** : 3초 미만의 비한국어 발화는 한국어와 감지 언어로 둘 다 전사해 `avg_logprob` 이 높은 쪽을 쓴다. 둘 다 -0.6 미만이면 버린다
5. **한글 비율 게이트** : 한국어로 판정됐는데 한글 비율이 30% 미만이면 버린다. 한국어 모드에서 가나·한자 토큰이 나오는 경우를 걸러낸다

입력은 둘로 나눴습니다. VAD 와 LID 는 raw, ASR 만 denoised 입니다. denoise 한 오디오로 언어를 감지하면 정확도가 떨어졌기 때문입니다(95.2% 대 93.4%, 음성분석 단위테스트 글 참고).

### 재현

```bash
uv venv .venv --python 3.11 && .venv/bin/uv sync          # Whisper
uv venv .venv-qwen --python 3.12                           # Qwen (의존성 충돌 때문에 분리)
.venv-qwen/bin/uv pip install -r pyproject-qwen.toml

.venv/bin/python main.py            # Whisper STT
.venv-qwen/bin/python main_qwen.py  # Qwen STT
.venv/bin/python evaluate.py all    # 채점
.venv/bin/python report.py          # 리포트
```

### 증적

- 소스: https://github.com/SceneMakerAI/poc-stt-bench (MIT)
- 결과 원본: https://github.com/SceneMakerAI/poc-stt-bench/blob/HEAD/output/report.csv (전사 결과와 채점 CSV 는 `output/` 아래)
- 최적화 과정 상세: https://doc.scenemaker.solbox.com/blog/4
- 모델: https://huggingface.co/Systran/faster-whisper-large-v3

