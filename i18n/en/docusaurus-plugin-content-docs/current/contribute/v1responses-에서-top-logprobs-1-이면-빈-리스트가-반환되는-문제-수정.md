---
title: "Fixed an issue where setting `top_logprobs=-1` in `/v1/responses` returned an empty list"
sidebar_position: 52
slug: "52"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-12
---

## vLLM: Issue where `top_logprobs` returns an empty result when `top_logprobs=-1` is requested in the Responses API

Link: https://github.com/vllm-project/vllm/pull/61141

### Background

`top_logprobs=-1` means “return all candidates,” and `/v1/chat/completions` actually returns all candidates. If the same value is sent to `/v1/responses` along with `include=["message.output_text.logprobs"]`, the request goes through and the engine calculates the logprob for the entire vocabulary, but the token-by-token `top_logprobs` in the response returns an empty list.

### Cause

The `_topk_logprobs` in `vllm/entrypoints/openai/responses/serving.py` limits the count to `if i >= top_logprobs: break`. If the value is -1, it exits immediately at the first item (i=0). The chat-side `_get_top_logprobs` handles `top_logprobs == -1` separately.

### Changes

- Modified one line of code in `_topk_logprobs` to prevent truncation when the value is -1.
- Added tests to `tests/entrypoints/openai/responses/test_serving_responses.py` to verify the three cases: -1, 2, and 0.

### Verification

- The -1 case in the new test failed in `main`; after the fix, the entire file had 67 passes and 1 xfailed.
- Passed ruff check and ruff format --check.
- Could not run on an actual server due to lack of a GPU. Verified by directly calling the serialization function.
- The closest existing work is #55717 (open, approved), which fixes a similar issue in the completions section and does not touch the Responses path.

