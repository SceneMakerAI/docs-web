---
id: 추론-진행률-hook-이-전체보다-큰-완료-수를-보고하는-문제-수정
title: "추론 진행률 hook 이 전체보다 큰 완료 수를 보고하는 문제 수정"
sidebar_position: 21
slug: "21"
description: "pyannote-audio: 마지막 배치가 작을 때 진행률 hook 에 전체보다 큰 완료 수가 전달되는 문제 수정"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

[https://github.com/pyannote/pyannote-audio/pull/2074](https://github.com/pyannote/pyannote-audio/pull/2074)

#### 목적

슬라이딩 추론(`Inference` )은 배치를 하나 처리할 때마다 진행률 hook 을 `completed=c + self.batch_size` 로 호출합니다. 마지막 배치가 `batch_size` 보다 작아도 `batch_size` 를 그대로 더하기 때문에, 청크 수가 `batch_size` 의 배수가 아니면 hook 은 "전체보다 많이 끝났다" 는 값을 받습니다. 뒤이어 마지막 청크가 올바른 값을 다시 보고하면 진행률이 거꾸로 가기도 합니다.

`develop` 브랜치에서 hook 이 받은 `(completed, total)` 값입니다 (`duration=1.0` , `step=0.5` ).

| 오디오 길이 | `batch_size` | 호출 값 |

| --- | --- | --- |

| 3.0초 | 32 | `(0, 5), (32, 5)` |

| 3.05초 | 32 | `(0, 6), (32, 6), (6, 6)` |

| 3.05초 | 4 | `(0, 6), (4, 6), (8, 6), (6, 6)` |

| 10.0초 | 4 | `(0, 19), (4, 19), …, (16, 19), (20, 19)` |

기본값 `batch_size=32` 에서는 32청크보다 짧은 파일이면 첫 배치부터 걸립니다. 화자 구분 파이프라인의 `segmentation` 단계 진행률이 이 hook 이라, 비율을 계산하거나 `completed >= total` 로 완료를 판정하는 hook 은 잘못된 값을 받습니다.

#### 변경 사항

- `src/pyannote/audio/core/inference.py` — `completed` 를 `min(c + self.batch_size, num_chunks)` 로 제한 (실제로 처리한 청크 수)
- `tests/test_inference_hook.py` — 작은 더미 모델로 4가지 경우를 검증하는 테스트 신규 추가. 진행률이 전체를 넘지 않고, 뒤로 가지 않고, 0 에서 시작해 전체에서 끝나는지 확인
- `CHANGELOG.md` — `next` 항목에 한 줄

#### 테스트

```text
$ pytest tests/test_inference_hook.py     # 수정 전: 4 failed
$ pytest tests/test_inference_hook.py     # 수정 후: 4 passed
```

사전학습 모델 없이 도는 테스트입니다. 로컬 환경은 Python 3.12, torch 2.8.0(CPU) 입니다. 모델이 필요한 나머지 테스트는 로컬에서 돌리지 못했습니다.

#### 중복 확인

진행률 hook, `completed` , `total` 로 열린·닫힌 이슈와 PR 을 검색했고 같은 문제는 없었습니다. `inference.py` 를 건드리는 열린 PR(#2048, #1992)은 이 줄을 바꾸지 않습니다.

#### 결과

2026-10-06 `develop` 브랜치 대상으로 제출했습니다. 리뷰 대기 중입니다.

