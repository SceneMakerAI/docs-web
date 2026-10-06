---
id: 파일-객체를-dict-로-넘길-때-keyerror-uri-수정
title: "파일 객체를 dict 로 넘길 때 KeyError 'uri' 수정"
sidebar_position: 14
slug: "14"
description: "pyannote-audio: 파일 객체를 담은 dict 입력에서 uri 기본값이 빠져 파이프라인이 KeyError 로 실패하는 문제 수정"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

[https://github.com/pyannote/pyannote-audio/pull/2072](https://github.com/pyannote/pyannote-audio/pull/2072)

#### 목적

`Audio.validate_file` 은 입력 형태 네 가지를 받는다고 문서에 적혀 있고, 그중 하나가 "`audio` 키에 파일 객체를 담은 Mapping" 입니다. `channel` 을 함께 넘기려면 이 형태를 써야 합니다. 그런데 이 경우에만 기본 `uri` 가 채워지지 않았습니다. Mapping 분기가 파일 객체(`IOBase` )를 만나면 `setdefault("uri", ...)` 에 도달하기 전에 바로 반환하기 때문입니다.

파이프라인은 결과를 만들 때 `file["uri"]` 를 읽습니다(`speaker_diarization.py` , `voice_activity_detection.py` , `speech_separation.py` , `multilabel.py` ). 그래서 `pipeline({"audio": f, "channel": 0})` 는 추론을 다 돌린 뒤에 `KeyError: 'uri'` 로 실패합니다.

SceneMaker 의 `worker-prep_stt` 는 pyannote 4.0.7 로 화자 구분을 하고, 파일 디코딩을 거치지 않는 입력 경로를 씁니다. 같은 입력 검증 함수를 지나는 경로라 코드를 읽다가 발견했습니다.

#### 변경 사항

- `src/pyannote/audio/core/io.py` — 파일 객체를 담은 Mapping 에도 기본 `uri` 를 `"stream"` 으로 채움. 파일 객체를 그대로 넘길 때 이미 쓰던 값과 같고, 호출자가 준 `uri` 는 건드리지 않음 (+2)
- `tests/io_test.py` — 기본값이 채워지는지, 호출자가 준 `uri` 가 유지되는지 검증하는 테스트 2건 (+15)
- `CHANGELOG.md` — `next` 항목에 한 줄 (+1)

#### 재현

사전학습 모델 없이 `develop` 브랜치에서 재현했습니다.

```python
from pyannote.audio import Pipeline
from pyannote.core import Annotation

class Echo(Pipeline):
    def default_parameters(self):
        return {}

    def apply(self, file):
        return Annotation(uri=file["uri"])

pipeline = Echo()
pipeline.instantiate({})
with open("tests/data/dev00.wav", "rb") as f:
    pipeline(f)                             # 정상, uri == "stream"
    pipeline({"audio": f, "channel": 0})    # KeyError: 'uri'
```

#### 테스트

```text
$ pytest tests/io_test.py        # 수정 전: 새 테스트 1건 실패 (KeyError: 'uri')
$ pytest tests/io_test.py        # 수정 후: 11 passed
```

로컬 환경은 Python 3.12, torch 2.8.0(CPU), torchcodec 0.7.0 입니다. 모델이 필요한 나머지 테스트는 로컬에서 돌리지 않았고 CI 에 맡겼습니다.

#### 중복 확인

제출 전에 열린·닫힌 이슈와 PR 을 `uri` + `IOBase` / file-like / `KeyError` 로 검색했고, 같은 문제를 다룬 것은 없었습니다. 열린 PR 중 `core/io.py` 를 건드리는 것은 2023년의 무관한 PR(#1336) 하나뿐입니다.

#### 결과

2026-10-06 `develop` 브랜치 대상으로 제출했습니다. 리뷰 대기 중입니다. 변경 규모는 3개 파일, +18 입니다.

