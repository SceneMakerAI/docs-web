---
title: "Fixed an issue where uppercase fields in nested dataclasses were omitted in case-insensitive mode"
sidebar_position: 15
slug: "15"
description: "Fixed an issue where capitalized fields in nested pydantic dataclasses were not populated by env and dotenv when `pydantic-settings: case_sensitive=False` was set."
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## pydantic-settings: Fixed a case-insensitive matching issue with nested pydantic dataclass fields

Link: https://github.com/pydantic/pydantic-settings/pull/1010

### Background

SceneMakerAI reads settings using a combination of `BaseSettings` + `.env` + `env_nested_delimiter`. Since pydantic-settings uses `case_sensitive=False` as its default, it converts all environment variable names to lowercase for matching, then reverts the keys to their actual field names (including uppercase letters) before passing them to the nested model.

This “key restoration” step only works when the nested type is `BaseModel`; it was omitted for pydantic dataclasses. As a result, nested dataclasses with field names containing uppercase letters cannot be populated via environment variables or dotenv.

- If the field is required: `Field required` ValidationError (the input value is passed as `apikey`, so `ApiKey` cannot be found)
- If the field is optional or part of a deeper-level dataclass: The value is silently discarded without an error and remains as `None`

If the same structure is declared as `BaseModel`, it works as expected.

### Cause

`pydantic_settings/sources/base.py`’s `PydanticBaseEnvSettingsSource._replace_field_names_case_insensitively`:

- Since the entry condition is `hasattr(annotation, 'model_fields')`, the pydantic dataclass passes the key through as-is.
- Since the recursion condition is `_lenient_issubclass(..., BaseModel)`, dataclasses contained within the model are not visited.

On the other hand, the value-collection side—`EnvSettingsSource.next_field` (`sources/providers/env.py`)—already supports dataclasses via the `is_model_class(...) or is_pydantic_dataclass(...)` condition and `_get_model_fields`. In other words, this is an asymmetry where value collection works but key restoration is missing. There is a precedent for the maintainer directly fixing similar omissions in optional nested models in #903 / #905.

### Changes

- Added the `_is_model_or_dataclass` helper (`is_model_class or is_pydantic_dataclass`).
- Replaced the entry and recursion conditions of `_replace_field_names_case_insensitively` with this helper, and changed field lookups to the existing `_get_model_fields`.
- Removed imports that are no longer used (`BaseModel`, `_lenient_issubclass`).
- Added 2 tests: `test_case_insensitive_nested_dataclass`, `test_case_insensitive_deeply_nested_dataclass`.
- The behavior of the `BaseModel` path remains unchanged.

Items excluded from the scope: values of stdlib’s `dataclasses.dataclass` and `dict[str, Model]`, and model unions that are not Optional. Although the same symptoms can be reproduced, the choice of target types requires a decision by the maintainer, so these were only noted in the PR body as items not included in the scope.

### Verification

- Ran the reproduction script on upstream `main` HEAD `5927b44`: BaseModel succeeded; dataclass resulted in a ValidationError in both env and dotenv; deep nesting occurred in `Inner=None`.
- Two new tests failed before the fix and passed afterward.
- Total tests: 891 passed / 5 skipped; `ruff check`, `ruff format --check`, and `mypy pydantic_settings` passed; `base.py` maintained 100% coverage.
- On my local machine, I ran only one combination: Linux / Python 3.12 / pydantic 2.13.5. I did not run the CI matrix (3.10–3.14, macOS, Windows) or the re-run phase after removing PyYAML.

