---
title: "[Frontend] min_p Support in the Responses API"
sidebar_position: 13
slug: "13"
description: "Added the `min_p` sampling parameter to the Responses API (`/v1/responses`)"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

[https://github.com/vllm-project/vllm/pull/48084](https://github.com/vllm-project/vllm/pull/48084)

#### Purpose

The Responses API (`/v1/responses`) accepts `top_k` as a request field and passes it to `SamplingParams`, but the corresponding `min_p` is missing. `SamplingParams` and `SamplingParams.from_optional` support `min_p`, and the Completions and Chat endpoints already expose it.

This PR adds the `min_p` field to `ResponsesRequest` and sets a default value in `to_sampling_params` in the same way as `top_k`, passing it to `SamplingParams.from_optional`. It follows the existing `top_k` handling exactly. Now, `/v1/responses` can also use min-p sampling, just like other generation endpoints.

**This is not a duplicate.** I searched for public PRs and issues using terms such as `responses min_p`, `ResponsesRequest min_p`, and `responses/protocol.py min_p`. `responses/protocol.py` contains no mention of `min_p`, and there is no public PR to add a sampling parameter to the Responses API. PR #45839 adds a sampling parameter only to a separate Translation API, so it does not overlap.

#### Files Affected

- `vllm/entrypoints/openai/responses/protocol.py`
- `tests/entrypoints/openai/responses/test_sampling_params.py`
- `docs/serving/online_serving/openai_compatible_server.md`

#### Test Plan

```bash
.venv/bin/python -m pytest \
  tests/entrypoints/openai/responses/test_sampling_params.py -v
pre-commit run --files \
  vllm/entrypoints/openai/responses/protocol.py \
  tests/entrypoints/openai/responses/test_sampling_params.py \
  docs/serving/online_serving/openai_compatible_server.md
```

I added a validation for `min_p` to `test_basic_sampling_params` and added a new test, `test_min_p_default`, to verify the default value (`0.0`).

#### Test Results

```text
8 passed in 1.07s
```

`ruff check`, `ruff format`, and `mypy` all passed pre-commit.

