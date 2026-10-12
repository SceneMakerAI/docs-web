---
id: v1responses-에서-top-logprobs-1-이면-빈-리스트가-반환되는-문제-수정
title: "/v1/responses 에서 top_logprobs=-1 이면 빈 리스트가 반환되는 문제 수정"
sidebar_position: 52
slug: "52"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-12
---

## vLLM: Responses API에서 top_logprobs=-1 요청 시 top_logprobs가 비어 나오는 문제

링크: https://github.com/vllm-project/vllm/pull/61141

### 배경

`top_logprobs=-1` 은 "모든 후보를 반환"이라는 뜻이고 `/v1/chat/completions` 는 실제로 전체 후보를 돌려준다. 같은 값을 `/v1/responses` 에 `include=["message.output_text.logprobs"]` 와 함께 보내면 요청은 통과하고 엔진은 전체 vocab logprob을 계산하지만, 응답의 토큰별 `top_logprobs` 는 빈 리스트로 나온다.

### 원인

`vllm/entrypoints/openai/responses/serving.py` 의 `_topk_logprobs` 가 `if i >= top_logprobs: break` 로 개수를 자른다. 값이 -1이면 첫 항목(i=0)에서 바로 빠져나간다. chat 쪽 `_get_top_logprobs` 는 `top_logprobs == -1` 을 따로 처리한다.

### 변경 내용

- `_topk_logprobs` 에서 -1일 때는 자르지 않도록 조건 한 줄 수정.
- `tests/entrypoints/openai/responses/test_serving_responses.py` 에 -1, 2, 0 세 경우를 확인하는 테스트 추가.

### 검증

- main에서 새 테스트의 -1 케이스 실패, 수정 후 파일 전체 67 passed, 1 xfailed.
- ruff check, ruff format --check 통과.
- GPU가 없어 실제 서버 실행은 하지 못했다. 직렬화 함수를 직접 호출해 확인했다.
- 가장 가까운 기존 작업은 completions 쪽 같은 문제를 고치는 #55717(오픈, 승인됨)이며 Responses 경로는 건드리지 않는다.

