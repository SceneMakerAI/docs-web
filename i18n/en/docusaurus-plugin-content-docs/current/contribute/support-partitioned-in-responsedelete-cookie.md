---
title: "Support split across Response.delete_cookie"
sidebar_position: 5
slug: "5"
tags: [PR, Merged]
keywords: [PR, Merged]
last_update:
  date: 2026-10-06
---



[https://github.com/Kludex/starlette/pull/3376](https://github.com/Kludex/starlette/pull/3376)

### **Purpose**

`Response.set_cookie` accepts the `partitioned` flag, but its counterpart, `Response.delete_cookie`, does not. To delete partitioned cookies (CHIPS), the `Set-Cookie` header for expiration must also include the `Partitioned` attribute. Since browsers store `Partitioned` as part of the cookie’s identifier, a deletion header missing this attribute will not match the existing cookie, causing the cookie to remain.

This PR adds the `partitioned: bool = False` argument to `delete_cookie` and passes it directly to `set_cookie` along with other attributes, aligning the argument structures of the two methods. In versions prior to Python 3.14, the version check that triggers `ValueError` is already included within `set_cookie`, so no separate handling was added.

### **Changes**

- `starlette/responses.py` — Added the `partitioned` argument to `delete_cookie` and passed it to `set_cookie` (+2)
- `tests/test_responses.py` — Added `test_delete_cookie_partitioned`. Verifies whether `Partitioned` appears in the header for Python 3.14 and later, and whether `ValueError` occurs for earlier versions (+18)
- `docs/responses.md` — Updated the signature for `delete_cookie`. The existing documentation was outdated and lacked `secure`, `httponly`, and `samesite`; added an example of deleting partition cookies along with the mandatory `Secure` warning (+18 / -1)

```python
response = Response()
response.delete_cookie("session", secure=True, samesite="none", partitioned=True)
```

### **Testing**

```text
$ pytest tests/test_responses.py -k cookie
18 passed

$ ruff format --check starlette tests   # already formatted
$ ruff check starlette tests            # All checks passed
$ mypy starlette                        # no issues
```

Since the local interpreter is Python 3.13, I ran only the paths for versions prior to 3.14 locally, and verified the paths for 3.14 and later using the CI matrix.

### **Review Responses**

- Documentation issue — Following a comment that the `delete_cookie` documentation lacked an explanation of `partitioned`, I added it in a subsequent commit.
- Proposal to automatically enable `secure` when `partitioned=True` is used — I did not implement this. We follow the convention of passing attributes as-is; for example, `set_cookie` does not enforce `secure`, and Starlette does not enforce `secure` even for `samesite="none"`. Since enforcing it only for `delete_cookie` would cause the two methods to behave differently, it was decided to leave the code as is and add a warning in the documentation stating that `Secure` is required.

### **Result**

Submitted on July 13, 2026; merged into `main` by the maintainer (Kludex) on September 5, 2026. The scope of changes was 3 files, +38 / -1.

