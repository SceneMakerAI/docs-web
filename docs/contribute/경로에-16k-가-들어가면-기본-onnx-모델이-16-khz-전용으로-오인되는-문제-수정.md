---
id: 경로에-16k-가-들어가면-기본-onnx-모델이-16-khz-전용으로-오인되는-문제-수정
title: "경로에 16k 가 들어가면 기본 ONNX 모델이 16 kHz 전용으로 오인되는 문제 수정"
sidebar_position: 35
slug: "35"
description: "silero-vad: OnnxWrapper 가 전체 경로에서 16k 를 찾아, 상위 디렉터리 이름에 16k 가 있으면 기본 모델이 8 kHz 입력을 거부하던 문제 수정"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## silero-vad: 경로에 16k 가 들어가면 일반 ONNX 모델이 16 kHz 전용으로 오인되는 문제

링크: https://github.com/snakers4/silero-vad/pull/814

### 배경

`OnnxWrapper` 는 16 kHz 전용 모델(`silero_vad_16k_op15.onnx` )을 구분하기 위해 `'16k' in path` 로 검사한다. 그런데 `path` 는 파일명이 아니라 전체 경로다. `load_silero_vad(onnx=True)` 는 설치된 패키지 내부 경로를 넘기므로, 가상환경이나 프로젝트 디렉터리 이름에 `16k` 가 들어 있으면(예: `asr_16k_project/.venv/...` ) 8 kHz 와 16 kHz 를 모두 지원하는 기본 모델 `silero_vad.onnx` 까지 16 kHz 전용으로 처리된다.

### 원인

`src/silero_vad/utils_vad.py` 의 `OnnxWrapper.__init__` (master 기준 79행) 에서 부분 문자열 검사를 전체 경로에 대해 수행한다. 일치하면 `sample_rates` 가 `[16000]` 으로 고정되고 경고가 출력되며, 이후 8 kHz 입력은 `_validate_input` 에서 `ValueError: Supported sampling rates: [16000] (or multiply of 16000)` 로 거부된다.

### 재현 방법

기본 모델 파일을 `asr_16k_project` 라는 디렉터리에 복사해서 `OnnxWrapper` 로 로드한 뒤 8 kHz 오디오로 `get_speech_timestamps` 를 호출한다.

```text
original location : [8000, 16000] []
asr_16k_project/  : [16000] ['This model support only 16000 sampling rate!']
ValueError: Supported sampling rates: [16000] (or multiply of 16000)
```

### 변경 내용

- 검사 대상을 `os.path.basename(path)` 로 한정 (`import os` 추가 포함 2줄 추가, 1줄 삭제)
- `tests/test_onnx_wrapper.py` 신규: 상위 디렉터리에 `16k` 가 있어도 8 kHz 가 동작하는지, op15 모델은 여전히 16 kHz 전용으로 인식되는지 확인

### 검증

- 수정 전: 신규 테스트 1건 실패(위 경고), 수정 후: 2건 통과
- `pytest tests` 전체: 47 passed, 10 skipped (torchcodec 미설치로 인한 skip)
- Windows 경로는 로컬에서 실행하지 못함

