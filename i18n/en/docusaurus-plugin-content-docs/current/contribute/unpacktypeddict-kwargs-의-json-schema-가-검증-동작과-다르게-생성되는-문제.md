---
title: "Issue where the JSON Schema for [TypedDict] kwargs in `Unpack` is generated differently from how validation works"
sidebar_position: 40
slug: "40"
description: "pydantic: Reported an issue where the JSON Schema generated for the function's **kwargs: Unpack[TypedDict] is inconsistent with the actual validation in both directions (fix prepared)"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-07
---

## pydantic: Fixed an issue where the JSON Schema for `**kwargs: Unpack[TypedDict]` functions was generated differently than expected during validation

Link: https://github.com/pydantic/pydantic/issues/13938

### Background

Starting with pydantic 2.10, `@validate_call` and `TypeAdapter(함수)` can be declared with variable keyword arguments as `**kwargs: Unpack[SomeTypedDict]` (pydantic#10416). In this case, each entry in the TypedDict is validated as an individual keyword argument. Since we use JSON Schema extracted from function signatures for LLM tool definitions and OpenAPI documentation, if the schema differs from the actual validation behavior, the model generates incorrect arguments.

If we extract the schema for the function below from `main` (1e6cc758a), the entire `TypedDict` is included under `additionalProperties`. This is the schema for `**kwargs: Options` (where each additional keyword is an `Options` object).

```python
class Options(TypedDict):
    timeout: int
    label: NotRequired[str]

def run(name: str = 'job', **kwargs: Unpack[Options]): ...

TypeAdapter(run).json_schema()
# 'additionalProperties': {'$ref': '#/$defs/Options'}, 'properties': {'name': ...}
```

As a result, the schema and the validator are out of sync in both directions.

- `name='x', timeout=5`: Validation passes, but is invalid according to the schema
- `name='x'`: Validation fails (missing), but is valid according to the schema
- `anything=dict(timeout=5)`: Validation fails (missing), but is valid according to the schema

### Cause

In `pydantic/json_schema.py`, `GenerateJsonSchema.arguments_schema()` passes `var_kwargs_schema` directly to `kw_arguments_schema()` without checking the core schema’s `var_kwargs_mode`. As a result, the `'unpacked-typed-dict'` mode is handled exactly the same as the `'uniform'` mode. #10416 only added validation logic and did not modify `json_schema.py`. The later-added `arguments_v3_schema()` distinguishes between the two modes, but it is not the path used by `@validate_call` and `TypeAdapter`.

### Changes

- In `arguments_schema()`, if `var_kwargs_mode` is `'unpacked-typed-dict'`, retrieve the JSON Schema from TypedDict and merge `properties` and `required` into the argument object.
- `additionalProperties` follows TypedDict: if `closed=True` is present, use the schema specified by `False` and `extra_items`; if neither is present, do not include the key (consistent with ignoring additional keywords at runtime).
- The signature of `kw_arguments_schema()`, which subclasses can override, has not been changed.
- Added two tests to `tests/test_validate_call.py` (merging required/optional items, `closed` and `extra_items`).
- Changes: 2 files, +68 / -1.

### Verification

- Before the fix, the reproduction script and new tests failed for `main`; after the fix, they pass.
- `tests/test_validate_call.py`, `tests/test_json_schema.py`, `tests/test_experimental_arguments_schema.py`, `tests/test_type_adapter.py`: 962 passed.
- All Python tests: Before the fix, 63 failed / 6,151 passed; after the fix, 63 failed / 6,153 passed. The list of 63 failures is identical before and after the fix; this is because Rust is not installed on this machine, so the tests ran using a `pydantic-core==2.49.0` release wheel that is older than the checked-out version.
- `ruff check` and `ruff format --check` (uv.lock 0.15.10) passed. For pyright, 66 failures were reported both before and after the fix for the same reason, so I was unable to verify under the same conditions as CI.
- Since repository guidelines require opening an issue first for non-trivial changes, I included a draft bug report with `issue.md`.

On October 6, 2026, another user, pranavpk404, confirmed that the issue could be reproduced in the latest main branch and submitted a fix PR [#13939](https://github.com/pydantic/pydantic/pull/13939). However, since pydantic only allows the person assigned to an issue to open a PR, the bot automatically closed that PR, and he has requested assignment to a maintainer.

