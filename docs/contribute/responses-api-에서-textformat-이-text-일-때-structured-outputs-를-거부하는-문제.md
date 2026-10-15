---
id: responses-api-에서-textformat-이-text-일-때-structured-outputs-를-거부하는-문제
title: "Responses API 에서 text.format 이 \"text\" 일 때 structured_outputs 를 거부하는 문제"
sidebar_position: 55
slug: "55"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-15
---

## vLLM: Responses API에서 text.format이 "text"일 때 structured_outputs를 거부하는 문제

링크: https://github.com/vllm-project/vllm/pull/61752

### 배경

`/v1/responses` 는 vLLM 확장 필드 `structured_outputs` (choice, regex, grammar 등)를 받는다. 여기에 `text.format` 의 type을 `"text"` 로 지정해 함께 보내면 "Cannot specify both structured_outputs and text.format" 400이 난다. type `"text"` 는 제약이 없는 기본 포맷이고, chat completions는 `response_format` 의 type이 `"text"` 일 때 `structured_outputs` 와의 조합을 문제없이 처리한다.

```json
{"input": "hi", "text": {"format": {"type": "text"}}, "structured_outputs": {"choice": ["yes", "no"]}}
```

### 원인

`vllm/entrypoints/openai/responses/protocol.py` 의 `ResponsesRequest.extract_structured_outputs` 가 `text.format` 의 존재 여부만 보고 충돌로 판단한다. chat/completions가 쓰는 `structured_outputs_from_response_format` 은 `response_format.type == "text"` 이면 `structured_outputs` 를 그대로 반환한다.

### 변경 내용

- `text.format.type == "text"` 인 경우를 포맷이 없는 경우와 같게 처리하도록 조건 추가.
- `json_schema` 나 `json_object` 와 `structured_outputs` 를 함께 주는 실제 충돌은 그대로 에러.
- `tests/entrypoints/openai/responses/test_sampling_params.py` 에 회귀 테스트 추가.

### 검증

- main(03091e28b, 2026-10-12 재확인)에서 새 테스트 실패(VLLMValidationError), 수정 후 통과. 기존 충돌 테스트도 통과.
- CPU 전용 환경의 teardown 오류는 main에서도 동일하며 실패는 0건.
- ruff 통과. 실제 서버 실행은 하지 못했다.
- 가까운 기존 작업: #33709(이 검사를 도입, 병합), #50544·#53006(오픈, 같은 함수에서 json_schema strict=false 만 다룸).

