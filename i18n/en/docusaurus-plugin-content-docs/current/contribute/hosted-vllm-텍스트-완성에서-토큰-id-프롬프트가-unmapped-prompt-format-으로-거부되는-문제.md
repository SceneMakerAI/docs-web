---
title: "Issue where token ID prompts are rejected as \"Unmapped prompt format\" in hosted_vllm text completion"
sidebar_position: 49
slug: "49"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-08
---

## litellm: Issue with token ID prompts being rejected in hosted_vllm text completion (Issue)

Link: https://github.com/BerriAI/litellm/issues/45253

### Background

The vLLM’s `/v1/completions` accepts not only strings but also token ID arrays (lists of integers or lists of lists of integers) via `prompt`. When called with the `openai/` prefix, litellm passes the token IDs as-is; however, when called with `hosted_vllm/`—the vLLM-specific provider—it throws an exception before even sending the request. I discovered this while reading the text completion path code in the vLLM backend (this was not an issue encountered during production).

### Cause

The `text_completion()` in `litellm/main.py` limits the providers to be passed when the prompt is a list of integers to only five: openai, azure, azure_text, text-completion-codestral, and text-completion-openai (lines 7660–7677). This list was added in PR #18011 (fixing issue #17118) in December 2025; at the time, the reporter used the `openai/` prefix, so only that path was opened.

In contrast, when `completion()` is set to `openai_text_completion_compatible_providers` (such as hosted_vllm, together_ai, fireworks_ai, or llamafile), it is passed directly to the OpenAI text completion handler as `text_completion=True` (lines 5904–5911). In other words, the latter path can pass the token ID without any issues, but the former check is blocking it.

### Reproduction Steps

```python
import litellm

for model in ("openai/Qwen/Qwen3-8B", "hosted_vllm/Qwen/Qwen3-8B"):
    try:
        r = litellm.text_completion(
            model=model,
            prompt=[151644, 872, 198, 14990, 151645],
            api_base="http://127.0.0.1:18000/v1",
            api_key="EMPTY",
            max_tokens=4,
        )
        print(model, "->", r.choices[0].text)
    except Exception as e:
        print(model, "->", type(e).__name__, e)
```

```text
  stub got /v1/completions {"model": "Qwen/Qwen3-8B", "prompt": [151644, 872, 198, 14990, 151645], "max_tokens": 4}
> openai/Qwen/Qwen3-8B - Hello!
> hosted_vllm/Qwen/Qwen3-8B - Exception Unmapped prompt format. Your prompt is neither a list of strings nor a string. prompt=[151644, 872, 198, 14990, 151645]. File an issue - https://github.com/BerriAI/litellm/issues
```

### Verification

- Reproduced on the local stub server in main `5825840` (1.106.0). No actual LLM calls were made.
- The same exception occurs in `atext_completion` and `Router.atext_completion`, wrapped in `APIConnectionError`.
- If you enter a token ID directly in ``litellm.completion(..., text_completion=True)``, the stub receives ``"prompt": [1, 2, 3]``. This means the issue lies solely with the front-end validation.
- `together_ai`, `fireworks_ai`, and `llamafile` also fail in the same way.
- I have not tested this with the actual proxy (port 4000) or the actual vLLM server.

### Differences from Previous Issues

- #17118 (closed): This is the same error, but it involved the `openai/` prefix, and only those providers were fixed in #18011.
- Our PR #44977 addresses the video file part of `hosted_vllm/chat/transformation.py`, so there is no code overlap.
- The scope of the fix (whether to add only hosted_vllm or use the entire list of compatible providers) requires the maintainer’s judgment, so I’m raising this as an issue.

