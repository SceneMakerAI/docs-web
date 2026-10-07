---
id: state-에서-없는-속성을-del-하면-attributeerror-대신-keyerror-발생
title: "State 에서 없는 속성을 del 하면 AttributeError 대신 KeyError 발생"
sidebar_position: 43
slug: "43"
description: "starlette: State.__delattr__ 이 없는 속성에 대해 KeyError 를 그대로 올려 getattr 과 예외 종류가 다른 문제 제기 (Potential Issue discussion)"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-07
---

## starlette: State 에서 없는 속성을 del 하면 AttributeError 대신 KeyError 가 나는 문제

링크: https://github.com/Kludex/starlette/discussions/3644

### 배경

`request.state` 와 `app.state` 로 쓰는 `State` 객체는 속성 접근을 내부 dict 로 넘긴다. 없는 속성을 읽으면 `__getattr__` 이 dict 의 `KeyError` 를 `AttributeError` 로 바꿔 주는데, 없는 속성을 지울 때 쓰는 `__delattr__` 은 바꾸지 않아서 `KeyError` 가 그대로 올라온다.

### 재현 방법

```python
from starlette.datastructures import State

state = State()
state.missing        # AttributeError: 'State' object has no attribute 'missing'
del state.missing    # KeyError: 'missing'
```

정리 코드에서 `except AttributeError` 나 `contextlib.suppress(AttributeError)` 로 감싸 둔 `del request.state.x` 가 예외를 잡지 못한다.

### 원인

`starlette/datastructures.py` 의 `State.__delattr__` 이 `del self._state[key]` 만 수행한다. `__getattr__` 과 같은 `try` /`except KeyError` 변환이 없다.

### 검증

현재 main 에서 위 코드를 직접 실행해 예외 종류를 확인했다. Discussion, 이슈, PR 을 검색했고 같은 보고는 없었다. 이 리포는 PR 전에 Discussion 을 먼저 요구하고 메인테이너가 직접 고치는 경우가 많아, 수정 PR 은 열지 않고 "Potential Issue" 로만 올렸다.

