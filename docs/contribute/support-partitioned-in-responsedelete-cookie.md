---
id: support-partitioned-in-responsedelete-cookie
title: "Support partitioned in Response.delete_cookie"
sidebar_position: 5
slug: "5"
tags: [PR, Merged]
keywords: [PR, Merged]
last_update:
  date: 2026-10-06
---



[https://github.com/Kludex/starlette/pull/3376](https://github.com/Kludex/starlette/pull/3376)

### **목적**

`Response.set_cookie` 는 `partitioned` 플래그를 받지만, 짝이 되는 `Response.delete_cookie` 는 받지 않았습니다. 파티션된 쿠키(CHIPS)를 지우려면 만료용 `Set-Cookie` 헤더에도 `Partitioned` 속성이 실려야 합니다. 브라우저는 `Partitioned` 를 쿠키 식별 정보의 일부로 저장하므로, 이 속성이 빠진 삭제 헤더는 기존 쿠키와 매칭되지 않아 쿠키가 그대로 남습니다.

이 PR은 `delete_cookie` 에 `partitioned: bool = False` 인자를 추가하고 다른 속성과 함께 `set_cookie` 로 그대로 전달해, 두 메서드의 인자 구성을 맞춥니다. Python 3.14 미만에서 `ValueError` 를 내는 버전 검사는 이미 `set_cookie` 안에 있어 별도 처리를 추가하지 않았습니다.

### **변경 사항**

- `starlette/responses.py` — `delete_cookie` 에 `partitioned` 인자 추가, `set_cookie` 로 전달 (+2)
- `tests/test_responses.py` — `test_delete_cookie_partitioned` 추가. Python 3.14 이상에서는 헤더에 `Partitioned` 가 실리는지, 그 미만에서는 `ValueError` 가 발생하는지 검증 (+18)
- `docs/responses.md` — `delete_cookie` 시그니처 갱신. 기존 문서는 `secure` ·`httponly` ·`samesite` 도 빠진 낡은 상태였고, 파티션 쿠키 삭제 예제와 `Secure` 필수 경고를 함께 추가 (+18 / -1)

```python
response = Response()
response.delete_cookie("session", secure=True, samesite="none", partitioned=True)
```

### **테스트**

```text
$ pytest tests/test_responses.py -k cookie
18 passed

$ ruff format --check starlette tests   # already formatted
$ ruff check starlette tests            # All checks passed
$ mypy starlette                        # no issues
```

로컬 인터프리터는 Python 3.13이라 3.14 미만 경로만 로컬에서 실행했고, 3.14 이상 경로는 CI 매트릭스로 검증했습니다.

### **리뷰 대응**

- 문서 지적 — `delete_cookie` 문서에 `partitioned` 설명이 없다는 지적을 받아 후속 커밋으로 보강했습니다.
- `partitioned=True` 일 때 `secure` 를 자동으로 켜자는 제안 — 반영하지 않았습니다. `set_cookie` 도 `secure` 를 강제하지 않고, Starlette 는 `samesite="none"` 에도 `secure` 를 강제하지 않는 등 속성을 그대로 전달하는 관례를 따릅니다. `delete_cookie` 에서만 강제하면 두 메서드의 동작이 갈라지므로, 코드는 그대로 두고 문서에 `Secure` 필수 경고를 넣는 것으로 정리됐습니다.

### **결과**

2026-07-13 제출, 2026-09-05 메인테이너(Kludex)가 `main` 에 머지했습니다. 변경 규모는 3개 파일, +38 / -1 입니다.

