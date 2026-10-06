---
id: audiocrop-pad-모드가-범위-밖-구간에서-틀린-길이실제-오디오-반환
title: "Audio.crop pad 모드가 범위 밖 구간에서 틀린 길이·실제 오디오 반환"
sidebar_position: 20
slug: "20"
description: "pyannote-audio: Audio.crop 의 pad 모드가 파일 범위를 완전히 벗어난 구간에서 틀린 결과를 내는 문제 보고"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-06
---

[https://github.com/pyannote/pyannote-audio/issues/2073](https://github.com/pyannote/pyannote-audio/issues/2073)

#### 문제

`Audio.crop(..., mode="pad")` 는 파일 범위를 벗어난 구간을 0 으로 채워 준다고 문서에 적혀 있습니다. 구간이 파일과 일부 겹칠 때는 맞게 동작하지만, 구간이 파일 범위를 **완전히** 벗어나면 결과가 틀립니다. 메모리에 올린 waveform 과 디스크 파일에서 증상도 서로 다릅니다.

10초짜리 waveform(16kHz, 값은 전부 1)에서 1초 구간을 자르면 매번 16000 샘플이 나와야 합니다.

| 구간 | 실제 결과 | 기대 |

| --- | --- | --- |

| 9.5\~10.5초 | 16000 샘플, 0 아닌 값 8000개 | 정상 |

| -0.5\~0.5초 | 16000 샘플, 0 아닌 값 8000개 | 정상 |

| 12\~13초 | 48000 샘플, 전부 0 | 16000 샘플의 0 |

| -3\~-2초 | 176000 샘플, 0 아닌 값 128000개 | 16000 샘플의 0 |

디스크 파일(30초)에서는 같은 종류의 구간이 `ValueError: Invalid start seconds` 로 실패합니다. 특히 -3\~-2초 구간은 존재하지 않는 영역인데 실제 오디오를 조용히 돌려준다는 점이 가장 위험합니다.

#### 원인

두 분기 모두 구간의 한쪽 끝만 범위 안으로 당깁니다(`src/pyannote/audio/core/io.py` ).

- 메모리 분기: 시작이 음수일 때만 0 으로, 끝이 넘칠 때만 마지막 샘플로 맞춥니다. 구간이 끝 뒤에 있으면 채울 길이가 구간 길이가 아니라 "파일 끝부터의 거리" 가 되고, 구간이 시작 앞에 있으면 음수인 끝 위치가 그대로 음수 인덱스로 쓰여 실제 오디오가 반환됩니다.
- 파일 분기: 당긴 뒤 시작이 끝보다 커져서 디코더가 거부합니다.

#### 재현

사전학습 모델 없이 `develop` 브랜치(78a6e44b)에서 재현했습니다.

```python
import torch
from pyannote.core import Segment
from pyannote.audio import Audio

audio = Audio()
file = {"waveform": torch.ones(1, 160000), "sample_rate": 16000}  # 10초

for segment in [Segment(9.5, 10.5), Segment(12, 13), Segment(-0.5, 0.5), Segment(-3, -2)]:
    waveform, _ = audio.crop(file, segment, mode="pad")
    print(segment, waveform.shape[1], int((waveform != 0).sum()))
```

#### 왜 PR 이 아니라 Issue 인가

기대 동작이 두 가지로 갈릴 수 있습니다. 구간 길이만큼 0 을 돌려줄 수도 있고, 명확한 오류를 낼 수도 있습니다. 어느 쪽이 맞는지는 메인테이너가 정할 일이라 Issue 로 먼저 물었고, 방향이 정해지면 PR 을 올리겠다고 적었습니다.

#### 중복 확인

- #2068(이미 머지): 구간이 waveform 끝과 정확히 맞닿는 경계 문제로, 이번 건과 다릅니다.
- #1417(닫힘): `mode="raise"` 에서 구간이 파일을 살짝 넘는 경우로, 이번 건과 다릅니다.
- `crop pad negative segment` , `crop pad wrong number of samples` , `crop Invalid start seconds` , `Audio.crop mode pad` 로 열린·닫힌 이슈와 PR 을 검색했고 같은 문제는 없었습니다.

#### 결과

2026-10-06 등록했습니다. 메인테이너 답변 대기 중입니다.

