---
title: "Fixed an issue where run-batch did not import the tool/reasoning parser plugin"
sidebar_position: 51
slug: "51"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-12
---

## vLLM: Parser plugin not loaded in run-batch

Link: https://github.com/vllm-project/vllm/pull/61145

### Background

`vllm serve` imports the files specified by `--tool-parser-plugin` and `--reasoning-parser-plugin` early during server startup to register custom parsers in the registry. `vllm run-batch` also accepts the same option via the CLI but does not actually import anything.

### Cause

`vllm/entrypoints/launchers/run_batch.py`’s `main()` calls only `validate_run_batch_args` and `build_async_engine_client`. While generating engine settings, `ReasoningConfig.initialize_token_ids` (`vllm/config/reasoning.py:84`) attempts to look up the parser name, but since the plugin has not yet been loaded, a KeyError occurs. On the tool parser side, it fails with a TypeError when creating the chat handler. The same issue in headless mode had already been fixed in #53124, leaving only run-batch remaining.

### Changes

Added 7 lines at the beginning of `run_batch.main()` to import the two plugins in the same order as the API server. The test creates two temporary plugin files to verify that both parsers are registered when the engine client is created.

### Verification

- Before the fix: Both the reproduction script and the new test failed with a KeyError
- After the fix: 16 tests passed, including the new test; passed ruff check and format
- The 11 run-batch integration tests requiring model weights could not be run because they require a CPU-only environment

