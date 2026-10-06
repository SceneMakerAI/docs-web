---
id: frontend-responses-api-에서-min-p-를-지원
title: "[Frontend] Responses API 에서 min_p 를 지원"
sidebar_position: 13
slug: "13"
description: "Responses API(/v1/responses)에 min_p 샘플링 파라미터 추가"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

[https://github.com/vllm-project/vllm/pull/48084](https://github.com/vllm-project/vllm/pull/48084)

#### 목적

Responses API(`/v1/responses` )는 `top_k` 를 요청 필드로 받아 `SamplingParams` 로 넘기지만, 짝이 되는 `min_p` 는 빠져 있다. `SamplingParams` 와 `SamplingParams.from_optional` 은 `min_p` 를 지원하고, Completions·Chat 엔드포인트도 이미 노출하고 있다.

이 PR 은 `ResponsesRequest` 에 `min_p` 필드를 추가하고, `to_sampling_params` 에서 `top_k` 와 같은 방식으로 기본값을 정해 `SamplingParams.from_optional` 로 넘긴다. 기존 `top_k` 처리를 그대로 따랐다. 이제 `/v1/responses` 에서도 다른 생성 엔드포인트처럼 min-p 샘플링을 쓸 수 있다.

**중복이 아닙니다.** `responses min_p` , `ResponsesRequest min_p` , `responses/protocol.py min_p` 등으로 공개 PR·이슈를 검색했다. `responses/protocol.py` 에는 `min_p` 가 아예 없고, Responses API 에 샘플링 파라미터를 추가하는 공개 PR 도 없다. PR #45839 는 별도의 Translation API 에만 샘플링 파라미터를 추가하는 것이라 겹치지 않는다.

#### 변경 파일

- `vllm/entrypoints/openai/responses/protocol.py`
- `tests/entrypoints/openai/responses/test_sampling_params.py`
- `docs/serving/online_serving/openai_compatible_server.md`

#### 테스트 플랜

```bash
.venv/bin/python -m pytest \
  tests/entrypoints/openai/responses/test_sampling_params.py -v
pre-commit run --files \
  vllm/entrypoints/openai/responses/protocol.py \
  tests/entrypoints/openai/responses/test_sampling_params.py \
  docs/serving/online_serving/openai_compatible_server.md
```

`test_basic_sampling_params` 에 `min_p` 검증을 추가하고, 기본값(`0.0` )을 확인하는 `test_min_p_default` 를 새로 넣었다.

#### 시험 결과

```text
8 passed in 1.07s
```

`ruff check` , `ruff format` , `mypy` 모두 pre-commit 으로 통과.

