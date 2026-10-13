---
title: "Fixed an issue where video was missing in the fallback because `hosted_vllm` modified the caller's video file part"
sidebar_position: 44
slug: "44"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-07
---

## litellm: Issue where `hosted_vllm` in-place replaces the caller's video file part with `video_url`

Link: https://github.com/BerriAI/litellm/pull/44977

### Background

SceneMakerAI calls an OpenAI-compatible endpoint served by vLLM using LiteLLM’s `hosted_vllm/` provider and includes a video part in the message. In LiteLLM, the provider-neutral video representation is the `type: "file"` part, and `hosted_vllm` converts this to the vLLM-specific `type: "video_url"` part when sending the request.

The problem is that this conversion overwrites the `content` list passed by the caller itself, rather than creating a copy for the request. `litellm.completion` performs a shallow copy of the message dict for each call, but the `content` list inside it shares the caller’s object as-is.

As a result:

- Once `litellm.completion(model="hosted_vllm/...", messages=messages)` is complete, the `file` part inside the caller’s `messages` has been changed to `video_url`.
- Actual damage occurs during the Router fallback. If vLLM returns a 500 and falls back to Gemini, the Gemini transformation does not read the `video_url` part, so the video is silently omitted and only the text is transmitted. The response is 200, and there are no warnings.

### Cause

The `HostedVLLMChatConfig._transform_messages` user branch of `litellm/llms/hosted_vllm/chat/transformation.py` (lines 224–234 in the main `5455152`):

```python
for idx, content_item in replaced_content_items:
    message_content[idx] = self._convert_file_to_video_url(content_item)
```

Since `message_content` is a list of callers obtained from `message.get("content")`, index assignment modifies the caller data.

### Changes

- Create a new list for the `content` in the user message and assign it to the message dict. Only the video `file` part is replaced with `video_url`; the remaining parts continue to use the same object.
- Added a small method `_video_file_as_video_url` to convert a single part, reducing the existing two-step loop (collecting indices followed by overwriting) to a single line.
- The request body sent to vLLM remains the same as before.
- Added one regression test: Call the vLLM address with `litellm.completion` blocked by respx, then verify that the transmitted body contains `video_url` and that the caller’s `file` part object remains unchanged.

Scope of changes: 2 files, +39 / -9.

### Reproduction Method

Reproduced without an API key using two local HTTP servers (one for the vLLM, which returns a 500 error, and one for Gemini, which logs the received body) and the actual `litellm.Router`. The script is `_drafts/litellm/repro_fallback.py`.

Before modification (main `5455152` ):

```text
vLLM received parts:   [{"type": "text", ...}, {"type": "video_url", "video_url": {"url": "https://example.com/video.mp4"}}]
Gemini received parts: [{"text": "Describe this video"}]
caller's messages now: [{"type": "text", ...}, {"type": "video_url", ...}]
```

After modification:

```text
Gemini received parts: [{"text": "Describe this video"}, {"file_data": {"mime_type": "video/mp4", "file_uri": "https://example.com/video.mp4"}}]
caller's messages now: [{"type": "text", ...}, {"type": "file", "file": {"file_id": "https://example.com/video.mp4", "format": "video/mp4"}}]
```

The same discrepancy was observed with combinations of `router.acompletion` and `file_data` data URIs (text only before modification; `inline_data` after modification).

### Verification

- The new test failed before the fix and passed after the fix. All 91 `tests/unit/llms/hosted_vllm` tests passed.
- Non-proxy unit tests mentioning `hosted_vllm` and ``tests/unit/llms/openai/chat``: 1,755 passed / 45 failed after the fix; 1,754 passed / 45 failed before the fix. The 45 failures were identical in both cases (this virtual environment lacks proxy extras, and the cause was not investigated separately).
- `ruff format --check`, `ruff check`, `ruff check --config ruff-tests.toml`, `scripts/ruff_strict_gate.py`, `scripts/type_discipline_gate.py`, and `scripts/test_quality_gate.py` passed. The number of errors in `basedpyright` remained the same at 52 before and after the fix.
- Items not tested: All `make lint` / `make test-unit`, Rust bridge build, verification using the actual vLLM server and the actual Gemini API, and curl verification with a proxy.

### Things to check before submitting

- CLA: When you open a PR, the CLA assistant bot will leave a comment. The account owner must log in to GitHub via `https://cla-assistant.io/BerriAI/litellm` and sign it personally.
- The "Proof of Fix" section in the PR template requires actual calls without mocks. If possible, replace the body with Before/After screenshots taken using the actual vLLM server and Gemini keys.
- The base branch is `main`, the title is “Conventional Commits,” and the branch name is `bugfix/...`.

