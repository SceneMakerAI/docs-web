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

한국어 방송에 faster-whisper large-v3 와 Qwen3-ASR 을 같은 조건으로 돌려 본 결과다. 코드와 결과 파일은 [`poc-stt-bench`](https://github.com/SceneMakerAI/poc-stt-bench) 에 있다.

- Whisper: `Systran/faster-whisper-large-v3`
- Qwen: `Qwen3-ASR-1.7B` + `Qwen3-ForcedAligner-0.6B`
- 데이터: 뉴스·다큐·드라마·사극·예능·스포츠 한 편씩, 합쳐서 약 6시간 20분
- 장비: RTX 4090 24GB

|  | Whisper | Qwen |
| --- | --- | --- |
| 평균 점수 (-3 \~ 3) | 2.71 | 2.63 |
| 자막 사용 가능률 (0점 이상) | 97.8% | 97.0% |
| 환각 비율 (-3점) | 1.4% | 1.8% |
| 평균 RTF | 0.042 | 0.032 |
| VRAM | 약 3.5 GB | 약 7 GB |

전반적으로 Whisper 가 조금 더 정확했고 다큐에서 차이가 벌어졌다(환각 1.6% 대 6.0%). Qwen 은 더 빠르고, 야구 중계처럼 말이 빠른 콘텐츠에서 근소하게 앞섰다. VRAM 은 Whisper 가 절반이다.

#### 채점은 사람이 하지 않았다

정답 자막이 없어서 Gemini 에게 오디오와 세그먼트 텍스트를 같이 주고 -3 \~ 3 점을 매기게 했다. 그래서 위 점수는 절대 정확도로 읽으면 안 되고, 두 시스템을 같은 잣대로 비교한 값 정도로 봐야 한다.

#### 파이프라인

```text
raw wav
 → denoise (DeepFilterNet v3, atten_lim_db=-30)
 → VAD (Silero, raw)
 → LID (Whisper detect_language, raw)
 → ASR (Whisper / Qwen, denoised)
 → 후처리
 → 채점
```

VAD 와 LID 는 원본으로, ASR 만 denoise 한 오디오로 돌린다. denoise 한 걸로 언어를 감지하면 정확도가 떨어진다(95.2% → 93.4%). 이 비교는 [#35](https://github.com/SceneMakerAI/docs-web/discussions/35) 에 있다.

#### Whisper 환각 줄이기

효과가 컸던 순서대로다.

1. VAD 로 침묵·BGM 구간을 아예 ASR 에 안 보낸다. 이게 제일 크다.
2. `avg_logprob < -1.0` 인 세그먼트는 버린다.
3. 언어 감지 확률이 0.5 미만인데 한국어가 아니라고 나오면 한국어로 강제한다.
4. 3초 미만 비한국어 발화는 한국어와 감지 언어로 둘 다 전사해서 `avg_logprob` 이 높은 쪽을 쓴다. 둘 다 -0.6 미만이면 버린다.
5. 한국어로 판정됐는데 한글 비율이 30% 미만이면 버린다. 한국어 모드에서 가나·한자가 튀어나오는 경우다.

#### 돌려 보려면

```bash
uv venv .venv --python 3.11 && .venv/bin/uv sync
uv venv .venv-qwen --python 3.12
.venv-qwen/bin/uv pip install -r pyproject-qwen.toml

.venv/bin/python main.py
.venv-qwen/bin/python main_qwen.py
.venv/bin/python evaluate.py all
.venv/bin/python report.py
```

Qwen 쪽은 의존성이 부딪혀서 venv 를 따로 뒀다.

콘텐츠별 수치는 [`output/report.csv`](https://github.com/SceneMakerAI/poc-stt-bench/blob/HEAD/output/report.csv) , 튜닝 과정은 [블로그](https://doc.scenemaker.solbox.com/blog/4) 에 있다.

