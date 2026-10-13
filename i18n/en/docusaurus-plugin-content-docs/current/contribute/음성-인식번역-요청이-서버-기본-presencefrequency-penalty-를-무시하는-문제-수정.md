---
title: "Fixed an issue where voice recognition and translation requests bypassed the server's default presence/frequency penalty"
sidebar_position: 53
slug: "53"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-12
---

## vLLM: The Issue Where Speech Recognition and Translation Requests Bypass the Server’s Default Presence/Frequency Penalty

Link: https://github.com/vllm-project/vllm/pull/61133

### Background

vLLM applies the sampling defaults in `generation_config.json` or `--override-generation-config` when a request omits a value. Chat completions and completions were fixed in #50769, and batch chat was fixed in #60307 to follow this rule for `presence_penalty` and `frequency_penalty`. `/v1/audio/transcriptions` and `/v1/audio/translations` still ignore the server defaults.

### Cause

In `vllm/entrypoints/speech_to_text/transcription/protocol.py` and `translation/protocol.py`, the default value for both fields is `0.0`, and `to_sampling_params` passes `self.frequency_penalty` and `self.presence_penalty` directly to `SamplingParams`. The adjacent `repetition_penalty` retrieves its default value from `default_sampling_params`.

### Changes

- Changed the default values for `presence_penalty` and `frequency_penalty` in both request models to `None`.
- Added two values (0.0) to `_DEFAULT_SAMPLING_PARAMS` and set `to_sampling_params` to determine the value in the order of request value, server default, and 0.0.
- Added a test targeting the two request classes to `tests/entrypoints/openai/test_penalty_default_resolution.py`.

### Verification

- In `main`, the server default case failed for both classes (`assert 0.0 == 1.5`); after the fix, 18 passed.
- The teardown error in the CPU-only environment was identical in `main`, with zero failures.
- Passed Ruff.
- Could not run the Whisper server test or the actual `vllm serve` execution due to the lack of a GPU and model weights.

