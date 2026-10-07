---
id: bug-use-audio-in-video-에서-멀티모달-프로세서-캐시가-오디오를-누락-qwen3-omni
title: "[Bug] use_audio_in_video 에서 멀티모달 프로세서 캐시가 오디오를 누락 (Qwen3-Omni)"
sidebar_position: 12
slug: "12"
description: "Qwen3-Omni use_audio_in_video 요청에서 프로세서 캐시 충돌로 StopIteration / HTTP 400"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-07
---

[https://github.com/vllm-project/vllm/issues/44538](https://github.com/vllm-project/vllm/issues/44538)

작성: MinsungIM · 2026-06-04 등록

#### 환경

```text
vLLM 0.21.0 · transformers 5.8.1 · torch 2.11.0+cu130 (CUDA 13.0)
Python 3.12.13 · Amazon Linux 2023
GPU: NVIDIA RTX PRO 6000 Blackwell Server Edition (96 GB)
Model: Qwen/Qwen3-Omni-30B-A3B-Instruct
```

#### 증상

Qwen3-Omni 를 OpenAI 호환 API 로 서빙하면서 `use_audio_in_video=True` 로 비디오만 보내는 요청(오디오는 비디오에서 자동 추출)이 **HTTP 400** 으로 실패한다. 이전 요청이 **다른 비디오** 로 같은 오디오 트랙을 이미 캐시해 둔 경우에만 일어난다.

서버 로그의 실제 예외는 transformers 의 `StopIteration` 이다.

```text
transformers/models/qwen3_omni_moe/processing_qwen3_omni_moe.py
  replace_multimodal_special_tokens:
      audio_token_indices = np.arange(next(audio_lengths))   # StopIteration
```

HF 프로세서가 `audio=None` 을 받는다. 오디오 디코딩 자체는 정상이라, 오디오가 **멀티모달 프로세서 캐시** 에서 빠지는 것이다.

#### 발생 조건

해상도·프레임레이트·길이가 같고 **오디오 트랙이 바이트 단위로 동일** (MD5 확인)하지만 비디오 프레임만 다른 두 요청. 첫 요청이 처리된 오디오를 첫 비디오에 묶어 캐시하고, 두 번째 요청이 그 캐시를 다른 비디오와 짝지으면서 오디오가 사라진다.

#### 최소 재현

```bash
ffmpeg -y -f lavfi -i color=c=black:s=1920x1080:r=30:d=6 \
  -f lavfi -i sine=frequency=440:duration=6 -c:v libx264 -c:a aac -shortest A.mp4
ffmpeg -y -f lavfi -i testsrc=s=1920x1080:r=30:d=6 \
  -f lavfi -i sine=frequency=440:duration=6 -c:v libx264 -c:a aac -shortest B.mp4
```

새로 띄운 서버(기본값 `mm-processor-cache-gb=4` ) 기준:

| 단계 | 요청 | 결과 |
| --- | --- | --- |
| 1 | `A.mp4` , `use_audio_in_video=True` | 200 OK |
| 2 | `B.mp4` (다른 비디오, 같은 오디오) | 400 (StopIteration) |
| 대조 | `B.mp4` 에 다른 오디오(880 Hz) | 200 OK |

`--mm-processor-cache-gb 0` 으로 캐시를 끄면 2단계도 통과한다.

#### 제안한 수정 방향

1. `use_audio_in_video` 오디오 캐시 키가 짝이 되는 비디오를 반영하도록 한다 (또는 서로 다른 비디오 사이에서는 공유하지 않는다).
2. 오디오가 없을 때 `replace_multimodal_special_tokens` 가 `StopIteration` 대신 명확한 오류를 내도록 한다.

#### 진행 상황

2026-06-04 에 등록했다. 메인테이너 응답 없이 90일이 지나 stale 로 표시됐고, 2026-10-06 에 자동으로 닫혔다(not planned). 같은 캐시 계열의 관련 이슈는 #33865, #43941, #42995.

이슈를 올린 당일 외부 개발자 abinggo 가 이 문제를 고치는 PR [#44543](https://github.com/vllm-project/vllm/pull/44543) (Couple audio+video in mm processor cache, "fixes #44538")을 올렸고, vLLM 메인테이너 Isotr0py 가 리뷰했다. 이 PR 은 2026-10-07 기준 열려 있고 머지되지 않았다.

