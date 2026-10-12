---
id: 음성-인식번역-요청이-서버-기본-presencefrequency-penalty-를-무시하는-문제-수정
title: "음성 인식·번역 요청이 서버 기본 presence/frequency penalty 를 무시하는 문제 수정"
sidebar_position: 53
slug: "53"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-12
---

## vLLM: 음성 인식·번역 요청이 서버 기본 presence/frequency penalty를 무시하는 문제

링크: https://github.com/vllm-project/vllm/pull/61133

### 배경

vLLM은 `generation_config.json` 이나 `--override-generation-config` 에 있는 샘플링 기본값을 요청이 값을 생략했을 때 적용한다. chat completions와 completions는 #50769에서, batch chat은 #60307에서 `presence_penalty` , `frequency_penalty` 도 이 규칙을 따르게 고쳐졌다. `/v1/audio/transcriptions` 와 `/v1/audio/translations` 는 아직 서버 기본값을 무시한다.

### 원인

`vllm/entrypoints/speech_to_text/transcription/protocol.py` 와 `translation/protocol.py` 에서 두 필드의 기본값이 `0.0` 이고 `to_sampling_params` 가 `self.frequency_penalty` , `self.presence_penalty` 를 그대로 `SamplingParams` 에 넘긴다. 바로 옆의 `repetition_penalty` 는 `default_sampling_params` 에서 기본값을 찾는다.

### 변경 내용

- 두 요청 모델에서 `presence_penalty` , `frequency_penalty` 기본값을 `None` 으로 변경.
- `_DEFAULT_SAMPLING_PARAMS` 에 두 값(0.0)을 추가하고 `to_sampling_params` 에서 요청 값, 서버 기본값, 0.0 순으로 결정.
- `tests/entrypoints/openai/test_penalty_default_resolution.py` 에 두 요청 클래스를 대상으로 한 테스트 추가.

### 검증

- main에서 서버 기본값 케이스가 두 클래스 모두 실패(`assert 0.0 == 1.5` ), 수정 후 18 passed.
- CPU 전용 환경의 teardown 오류는 main에서도 동일하며 실패는 0건.
- ruff 통과.
- GPU와 모델 가중치가 없어 Whisper 서버 테스트와 실제 `vllm serve` 실행은 하지 못했다.

