---
id: ssdictcursor-가-dict-대신-tuple-을-반환하는-문제-수정
title: "SSDictCursor 가 dict 대신 tuple 을 반환하는 문제 수정"
sidebar_position: 17
slug: "17"
description: "asyncmy: Cython cdef 메서드라 오버라이드가 안 먹어 SSDictCursor 가 tuple 을 돌려주던 문제를 cpdef 로 바꿔 수정"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## asyncmy: SSDictCursor 가 dict 대신 tuple 을 반환하는 버그 수정

링크: https://github.com/long2ice/asyncmy/pull/164

- 대상: long2ice/asyncmy (기본 브랜치 `dev` , HEAD `0000bd0` )
- 유형: PR (버그 수정 + 회귀 테스트)
- 제목: `fix: return dicts from SSDictCursor instead of tuples`

### 배경

SceneMakerAI 는 FastAPI 서비스에서 asyncmy 를 MySQL/MariaDB 드라이버로 쓰고, 결과는 주로 `DictCursor` 로 받는다. 대량 조회용 unbuffered 커서의 dict 버전인 `SSDictCursor` 는 클래스 docstring 에 "An unbuffered cursor, which returns results as a dictionary" 라고 돼 있지만, 실제로는 `fetchone` / `fetchmany` / `fetchall` / `async for` 모두 tuple 을 반환한다. 저장소 테스트에 `SSCursor` / `SSDictCursor` 를 쓰는 케이스가 하나도 없어서 드러나지 않았다.

### 원인

`asyncmy/cursors.pyx` 의 `SSCursor.read_next()` 는 `self._conv_row(...)` 로 행을 변환한다. 그런데 `_conv_row` 가 `Cursor` , `SSCursor` (둘 다 `cdef class` ) 에 `cdef` 메서드로 선언돼 있다. Cython 은 `cdef class` 내부의 `cdef` 메서드 호출을 C vtable 로 직접 디스패치하고, 순수 Python 서브클래스는 vtable 슬롯을 덮어쓸 수 없다. 그래서 `class SSDictCursor(DictCursorMixin, SSCursor)` 에서 MRO 상 앞에 있는 `DictCursorMixin._conv_row` 는 호출되지 않고, 입력을 그대로 돌려주는 `SSCursor._conv_row` 만 실행된다.

`DictCursor` 가 정상인 이유는 buffered 경로에서는 Python 메서드인 `DictCursorMixin._do_get_result` 안에서 변환이 끝나기 때문이다. unbuffered 커서는 그 시점에 `_rows` 가 `None` 이라 `read_next()` 가 유일한 변환 지점이다.

`git log -S"cdef _conv_row"` 기준으로 2022-04 커밋 `8836fc5` 에서 `def` 가 `cdef` 로 바뀌면서 생긴 회귀다.

### 변경 내용

- `asyncmy/cursors.pyx` : `Cursor._conv_row` , `SSCursor._conv_row` 를 `cdef` 에서 `cpdef` 로 변경 (2줄). `cpdef` 는 서브클래스 인스턴스일 때 Python 오버라이드를 찾아 호출하므로 `DictCursorMixin._conv_row` 와 사용자 정의 `dict_type` 이 다시 적용된다.
- `tests/test_cursor.py` : `test_ss_dict_cursor` 추가 (`fetchone` / `fetchmany` / `fetchall` / `async for` ).
- `CHANGELOG.md` : 0.2.16 항목에 한 줄 추가.

### 재현 방법

```python
async with conn.cursor(cursor=SSDictCursor) as cur:
    await cur.execute("SELECT 1 AS a, 'x' AS b UNION ALL SELECT 2, 'y'")
    print(await cur.fetchone())   # 수정 전: (1, 'x')   수정 후: {'a': 1, 'b': 'x'}
```

### 검증

- 임시 `mariadbd` 10.11.15 (전용 datadir, 포트 33917) 에서 실행. 기존 컨테이너/볼륨은 건드리지 않았고 작업 후 정리했다.
- 수정 전: 새 테스트가 AssertionError 로 실패 (tuple 이 반환되어 dict 와 불일치).
- 수정 후: 전체 `pytest` 87 passed, 4 skipped. `ruff format --check` , `ruff check` , `mypy` 통과.
- `stubtest` 는 Python 3.11 환경에서 `contexts.TypeVar` 관련 기존 오류 9건이 수정 전후 동일하게 나온다 (CI 는 3.14 사용). 이번 변경으로 새로 생긴 오류는 없다.
- MySQL 서버와 다른 Python 버전 매트릭스는 로컬에서 돌리지 못했다.

