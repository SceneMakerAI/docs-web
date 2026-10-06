---
id: max-speech-duration-s-강제-분할-시-이어지는-음성이-누락되는-문제-수정
title: "max_speech_duration_s 강제 분할 시 이어지는 음성이 누락되는 문제 수정"
sidebar_position: 33
slug: "33"
description: "silero-vad: max_speech_duration_s 로 강제 분할될 때 자른 지점의 윈도우와 neg_threshold 로 유지되던 음성이 버려지는 문제 수정"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## silero-vad: max_speech_duration_s 강제 분할 시 이어지는 음성이 누락되는 문제 수정

링크: https://github.com/snakers4/silero-vad/pull/813

### 배경

SceneMakerAI 는 16 kHz 모노 방송 음성(1\~2시간)을 STT 앞단에서 `get_speech_timestamps` 로 자르고, STT 입력 길이를 맞추기 위해 `max_speech_duration_s` 를 사용한다. 이 옵션은 "긴 구간을 나눈다"고 문서화되어 있는데, 실제로는 나누는 지점에서 음성이 사라지는 경우가 있었다.

- 강제 분할(자를 만한 무음이 없어 현재 윈도우에서 자르는 경우)마다 윈도우 1개(16 kHz 기준 512 샘플, 32 ms)가 어느 구간에도 들어가지 않는다. 기본값 `speech_pad_ms=30` 에서는 양쪽 패딩이 우연히 구멍을 메워 보이지 않지만 `speech_pad_ms` 가 16 ms 미만이면 그대로 드러난다.
- 확률이 `neg_threshold` (기본 0.35) 와 `threshold` (0.5) 사이에 머무는 구간은 상태 기계상 "발화 지속"인데, 강제 분할 뒤에는 `threshold` 를 다시 넘는 윈도우가 나올 때까지 통째로 버려진다. 기본 파라미터에서도 발생한다. 예: 9.6초짜리 한 구간이 `max_speech_duration_s=5` 를 주면 앞 4.96초만 남고 뒤 4.6초가 사라진다.

### 원인

`src/silero_vad/utils_vad.py` 의 `get_speech_timestamps_from_probs` , 최대 길이 도달 시 fallback 분기(527\~534행). `current_speech['end'] = cur_sample` 로 자른 뒤 `triggered = False` 로 바꾸고 `continue` 한다. 그래서 자른 지점의 윈도우는 새 구간에 포함되지 않고, 새 구간은 이후 확률이 `threshold` 이상인 윈도우가 나와야만 시작된다. 2022년 `max_speech_duration_s` 가 처음 들어올 때(PR 271)부터 있던 동작이다.

### 변경 내용

fallback 분기에서 자르는 지점이 무음 구간 안이 아니면(`temp_end` 가 비어 있고 현재 확률이 `neg_threshold` 이상) `triggered` 를 유지하고 다음 구간을 `cur_sample` 에서 바로 시작한다. 무음 구간 안에서 잘린 경우는 기존과 동일하게 음성이 돌아올 때 새 구간을 시작한다. 기록된 무음 지점에서 자르는 분기(`possible_ends` , `prev_end` )는 건드리지 않았다. 변경은 4줄 추가, 1줄 삭제.

```python
if temp_end or speech_prob < neg_threshold:
    triggered = False  # cut inside a pause: wait for speech to return
else:
    current_speech['start'] = cur_sample  # speech goes on: keep it in the next chunk
```

테스트 `tests/test_max_speech_split.py` 추가. 모델 없이 확률 목록을 직접 넣어 상태 기계만 검증한다 (5개 케이스, 그중 4개가 수정 전 실패).

### 검증

- 수정 전 HEAD(1e261b0) 에서 재현: 연속 발화 700 윈도우를 2초 제한으로 자르면 분할 11곳마다 512 샘플 누락(352768 / 358400). 히스테리시스 구간 예제는 뒤 4.6초 누락.
- 수정 후: 358400 / 358400, 히스테리시스 예제는 두 구간으로 정상 분할. 모든 구간이 여전히 `max_speech_duration_s` 이하.
- 실제 음성 `tests/data/test.wav` (60초, JIT 모델, 패딩 0, 3초 제한): 제한 없이 구간에 포함되던 윈도우 중 누락이 15개에서 8개로 감소. 남은 8개는 의도적으로 분할 지점으로 쓰인 무음 2곳(각 4 윈도우)이다.
- `pytest tests` : 50 passed, 10 skipped (skip 은 torchcodec 미설치 테스트). torch 2.8.0 / torchaudio 2.8.0 / onnxruntime 1.30.0, Python 3.12.
- 무작위 확률 시퀀스 4만 건으로 정렬, 비중첩, 범위, 최대 길이 불변식을 확인했고 수정으로 새로 깨지는 것은 없었다.

