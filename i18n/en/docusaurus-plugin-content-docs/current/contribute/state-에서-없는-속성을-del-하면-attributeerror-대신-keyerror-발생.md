---
title: "If you use `del` on a non-existent attribute in `State`, a `KeyError` is raised instead of an `AttributeError`."
sidebar_position: 43
slug: "43"
description: "starlette: Raises a KeyError directly for attributes that do not have `State.__delattr__`, raising concerns that this is a different type of exception than `getattr` (Potential Issue discussion)"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-07
---

## starlette: Issue where deleting an attribute that doesn't exist in `State` raises a `KeyError` instead of an `AttributeError`

Link: https://github.com/Kludex/starlette/discussions/3644

### Background

The `State` object, which is used with `request.state` and `app.state`, delegates attribute access to an internal dictionary. When a non-existent attribute is read, `__getattr__` replaces the `KeyError` in the dict with `AttributeError`; however, when deleting a non-existent attribute using `__delattr__`, it does not make this replacement, so `KeyError` is passed up as-is.

### How to Reproduce

```python
from starlette.datastructures import State

state = State()
state.missing        # AttributeError: 'State' object has no attribute 'missing'
del state.missing    # KeyError: 'missing'
```

In the cleanup code, an `except AttributeError` or `contextlib.suppress(AttributeError)` wrapped around an `del request.state.x` fails to catch exceptions.

### Cause

The `State.__delattr__` in `starlette/datastructures.py` only executes `del self._state[key]`. There is no `try`/`except KeyError` conversion, such as with `__getattr__`.

### Verification

I verified the exception type by running the above code directly in `main`. I searched the Discussion, Issues, and PRs and found no similar reports. Since this repository often requires a Discussion before a PR and the maintainer frequently fixes issues directly, I did not open a fix PR but reported it only as a “Potential Issue.”

