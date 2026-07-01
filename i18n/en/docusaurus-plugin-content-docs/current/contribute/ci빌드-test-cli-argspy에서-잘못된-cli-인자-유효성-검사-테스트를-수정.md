---
title: "[CI/Build] Fixed a test for invalid CLI argument validation in test_cli_args.py"
sidebar_position: 3
slug: "3"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-06-26
---

[https://github.com/vllm-project/vllm/pull/46779](https://github.com/vllm-project/vllm/pull/46779)

### **Purpose**

In two tests, `tests/entrypoints/openai/test_cli_args.py` presented incorrect contract information, leading to a false sense of certainty.

It claimed that when combined1 with `test_enable_auto_choice_fails_with_enable_reasoning-enable-auto-tool-choice`, `-reasoning-parser` should fail. However, this combination is **documented as supported** (e.g., ) and **does not** fail correctly. The test passed because was omitted, which triggered the irrelevant check “Automatic tool selection requires a tool-call parser,” obscuring the fact that an inference conflict validation does not exist (and should not exist). I rewrote the code to ensure that documented combinations pass when the tool call parser is enabled.`docs/features/tool_calling.md-tool-call-parser hunyuan_a13b --reasoning-parser hunyuan_a13bvalidate_parsed_serve_args-tool-call-parser`
2. `test_enable_auto_choice_passes_without_tool_call_parser` was misnamed. The function’s docstring and body explicitly state that the validation *fails*. `test_enable_auto_choice_fails_without_tool_call_parser` I renamed it to match the actual behavior.

This is a test-only change; runtime behavior remains unchanged.

**This is not a duplicate.** I searched for public PRs regarding `test_cli_args`, `validate_parsed_serve_args`, and `test_enable_auto_choice`, but none of them touched this test.

### **Test Plan**

```text
python -m pytest tests/entrypoints/openai/test_cli_args.py -v
# lint
ruff check tests/entrypoints/openai/test_cli_args.py
ruff format --check tests/entrypoints/openai/test_cli_args.py
```

### **Test Results**

```text
28 passed in 5.48s
ruff: All checks passed! / 1 file already formatted
```

