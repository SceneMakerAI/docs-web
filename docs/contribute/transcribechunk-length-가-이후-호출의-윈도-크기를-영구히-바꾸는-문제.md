---
id: transcribechunk-length-가-이후-호출의-윈도-크기를-영구히-바꾸는-문제
title: "transcribe(chunk_length) 가 이후 호출의 윈도 크기를 영구히 바꾸는 문제"
sidebar_position: 23
slug: "23"
description: "faster-whisper: chunk_length 를 준 호출이 같은 모델의 이후 호출 윈도 크기를 바꾸는 상태 누수 보고"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-06
---

[https://github.com/SYSTRAN/faster-whisper/issues/1661](https://github.com/SYSTRAN/faster-whisper/issues/1661)

#### 문제

`transcribe()` 를 한 번이라도 `chunk_length` 를 줘서 호출하면, 같은 `WhisperModel` 로 하는 이후 모든 호출의 윈도 크기가 바뀝니다. `chunk_length` 를 주지 않은 호출도 영향을 받습니다.

```python
print(seeks())                 # [0, 2200]
print(seeks(chunk_length=5))   # [0, 500, 1000, 1500, 2000, 2500]
print(seeks())                 # [0, 500, 1000, 1500, 2000, 2500]  <- [0, 2200] 이어야 함
```

세 번째 호출은 첫 번째와 인자가 같은데도 5초 윈도로 디코딩됩니다.

모델 하나를 띄워 놓고 여러 요청을 처리하는 서버라면, 한 요청이 `chunk_length` 를 쓴 뒤로는 프로세스를 재시작할 때까지 모든 요청의 결과가 조용히 달라집니다. SceneMaker 의 `worker-prep_stt` 도 faster-whisper 1.2.1 모델을 상주시켜 2차 전사에 쓰는 구조라 같은 조건에 해당합니다(현재 코드는 `chunk_length` 를 요청별로 바꾸지 않아 실제 피해는 없습니다).

#### 원인

`FeatureExtractor.__call__` 이 `chunk_length` 를 받으면 자기 속성(`n_samples` , `nb_max_frames` )을 덮어쓰고 되돌리지 않습니다(`faster_whisper/feature_extractor.py` 203\~205행). `self.chunk_length` 는 그대로 30 이라 내부 상태도 서로 어긋납니다. 이후 `generate_segments` 와 `detect_language` 가 이 값을 읽어 윈도를 나눕니다.

#### 재현

`master` (f6ef59b), faster-whisper 1.2.1, ctranslate2 4.8.2, Python 3.12, CPU, `tiny` 모델로 재현했습니다. 이슈 본문에 전체 스크립트를 넣었습니다.

#### 왜 PR 이 아니라 Issue 인가

작은 수정(호출마다 값을 다시 계산)은 테스트와 함께 준비돼 있습니다. 하지만 그것만으로는 상태가 호출별로 분리되지 않습니다. `transcribe()` 가 지연 생성기를 돌려주기 때문에, 서로 다른 `chunk_length` 로 두 전사를 번갈아 소비하면 여전히 간섭합니다. 완전히 고치려면 함수 시그니처를 바꿔야 해서, 어느 방향을 원하는지 먼저 물었습니다.

#### 중복 확인

`chunk_length` 와 `nb_max_frames` / `n_samples` / state / reuse 조합으로 열린·닫힌 이슈와 PR 을 검색했고 같은 보고는 없었습니다. #624, #1204 는 `chunk_length` 의 다른 동작에 관한 것이고, `feature_extractor.py` 를 건드리는 열린 PR 은 없습니다.

#### 결과

2026-10-06 등록했습니다. 메인테이너 답변 대기 중입니다.

