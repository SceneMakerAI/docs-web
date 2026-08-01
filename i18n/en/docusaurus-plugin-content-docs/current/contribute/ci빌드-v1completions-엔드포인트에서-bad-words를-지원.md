---
title: "[CI/Build] Support for `bad_words` at the `/v1/completions` endpoint"
sidebar_position: 4
slug: "4"
tags: [PR, Merged]
keywords: [PR, Merged]
last_update:
  date: 2026-07-09
---


[https://github.com/vllm-project/vllm/pull/46793](https://github.com/vllm-project/vllm/pull/46793)

### **Purpose**

The chat autocomplete endpoint ( `/v1/chat/completions` ) exposes the `bad_words` field and passes it to `SamplingParams`, but the existing autocomplete endpoint ( ) does not do so. This is a functional disparity. Users of the autocomplete endpoint cannot hide specific words.`SamplingParamsbad_words`

This PR adds the `bad_words` field to reflect the existing chat implementation (the sampling parameter block and the field) and connects it via `CompletionRequest`.`to_sampling_params()chat_completion/protocol.pybad_words=self.bad_wordsto_sampling_params`

**This is not a duplicate.** `bad_words`  I searched for open PRs regarding (title/body), `bad_words CompletionRequest`, and `completion bad_words parity`, but the existing `bad_words` PRs concern tokenizer conversion/caching bugs, and there are no PRs that add the field to the autocomplete endpoint.

### **Test Plan**

```text
python -m pytest tests/entrypoints/openai/completion/test_completion.py \
  -k "bad_words" -v
# lint
ruff check vllm/entrypoints/openai/completion/protocol.py \
  tests/entrypoints/openai/completion/test_completion.py
ruff format --check vllm/entrypoints/openai/completion/protocol.py \
  tests/entrypoints/openai/completion/test_completion.py
```

I added two CPU-specific unit tests.

- `test_completion_request_bad_words_to_sampling_paramsbad_wordsSamplingParams`
  —

  is passed to

  .

- `test_completion_request_bad_words_default_empty`
  — It is set to an empty list by default (same as in chat).

### **Test Results**

```
2 passed
ruff: All checks passed! / 2 files already formatted
```

