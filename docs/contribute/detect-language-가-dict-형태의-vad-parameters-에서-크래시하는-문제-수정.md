---
id: detect-language-가-dict-형태의-vad-parameters-에서-크래시하는-문제-수정
title: "detect_language 가 dict 형태의 vad_parameters 에서 크래시하는 문제 수정"
sidebar_position: 24
slug: "24"
description: "faster-whisper: detect_language 가 문서에 적힌 dict 형태의 vad_parameters 를 받으면 AttributeError 로 실패하는 문제 수정"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

[https://github.com/SYSTRAN/faster-whisper/pull/1662](https://github.com/SYSTRAN/faster-whisper/pull/1662)

#### 목적

`WhisperModel.detect_language` 는 `vad_parameters` 를 "Silero VAD 파라미터 dict 또는 VadOptions" 로 받는다고 문서와 타입 힌트에 적혀 있습니다. `transcribe` 와 같은 약속입니다. 그런데 dict 를 `VadOptions` 로 바꿔 주는 처리는 `transcribe` 에만 있고 `detect_language` 에는 빠져 있어서, 문서대로 dict 를 넘기면 크래시가 납니다.

```python
model.detect_language(audio, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))
# AttributeError: 'dict' object has no attribute 'threshold'
```

`VadOptions` 객체나 `None` 을 넘기면 정상 동작하고, 문서에 적힌 dict 형태만 실패합니다.

#### 변경 사항

- `faster_whisper/transcribe.py` — `detect_language` 에서 dict 를 `VadOptions` 로 변환. `transcribe` 가 이미 쓰는 방식과 동일 (+2)
- `tests/test_transcribe.py` — `test_detect_language_vad_parameters_dict` 추가 (+12)

#### 테스트

```text
$ pytest tests/test_transcribe.py::test_detect_language_vad_parameters_dict   # 수정 전: AttributeError 로 실패
$ pytest tests/test_transcribe.py::test_detect_language_vad_parameters_dict   # 수정 후: 1 passed
$ black --check ...   # 변경 없음
$ flake8 ...          # 통과
```

`tiny` 모델, CPU, Python 3.12 에서 실행했습니다. 전체 테스트(20건)는 조사 단계에서 통과를 확인했습니다.

#### 중복 확인

`detect_language` + `vad_parameters` , 그리고 오류 메시지로 열린·닫힌 이슈와 PR 을 검색했고 같은 보고는 없었습니다. #1150(타입 힌트 정리)이 같은 블록의 주변 줄을 건드리지만 변환 처리는 넣지 않습니다.

#### 결과

2026-10-06 `master` 브랜치 대상으로 제출했습니다. 리뷰 대기 중입니다. 변경 규모는 2개 파일, +14 입니다.

