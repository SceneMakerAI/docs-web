---
title: "Fixed an issue where HTTPSRedirectMiddleware removed the square brackets from IPv6 hostnames, resulting in an incorrect Location header"
sidebar_position: 37
slug: "37"
description: "starlette: Fixed an issue where the square brackets were missing from the redirect URL when the host was an IPv6 address followed by the default port, such as [::1]:80 (Discussion #3637)"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## starlette: Issue where HTTPSRedirectMiddleware removes the brackets when stripping the default port from an IPv6 host

Link: https://github.com/Kludex/starlette/pull/3638

### Background

`HTTPSRedirectMiddleware` performs a 307 redirect of requests from `http` /`ws` to `https` /`wss`. If the port in the `Host` header is 80 or 443, the port is removed from the redirect URL. If the host is an IPv6 literal, the square brackets are also removed during this process, causing the `Location` header to contain an invalid URL.

```text
> Host: [::1]:80            - Location: https://::1/path?a=1
> Host: [2001:db8::1]:443   - Location: https://2001:db8::1/path?a=1
```

`urllib.parse.urlsplit` generates an `ValueError` error when reading the port from this value, and httpx does not follow the redirect to `Invalid URL in location header`. If there is no port (`[::1]`) or if it is a different port (`[::1]:8000`), the behavior is normal.

### Cause

`starlette/middleware/httpsredirect.py` Line 17.

```python
netloc = url.hostname if url.port in (80, 443) else url.netloc
url = url.replace(scheme=redirect_scheme, netloc=netloc)
```

`url.hostname` returns IPv6 addresses without square brackets, just like the standard library `SplitResult.hostname`. If that value is passed to `netloc=`, `URL.replace` uses it as-is. The recently merged #3617 only adds square brackets to the `URL.replace(hostname=...)` path, so it does not apply to this call.

### Changes

When the port is the default, instead of replacing `netloc` with the hostname, only the port is removed using ``url.replace(port=None)``. This path retains the host portion from the original `netloc`, including the square brackets.

```python
url = url.replace(scheme=redirect_scheme)
if url.port in (80, 443):
    url = url.replace(port=None)
```

- The result when it is not the default port is exactly the same as before.
- One minor difference: The behavior where the host was converted to lowercase due to `url.hostname` in the default port path is removed (`Example.org:80` is now `https://Example.org/`. For other ports, case sensitivity was preserved from the start).
- Added test `test_https_redirect_middleware_ipv6_default_port` (parameterization of ports 80 and 443).
- No documentation changes. The documentation does not explain how to configure redirect URLs.

### Verification

- Before the fix, 4 new tests (2 ports × asyncio/trio) failed in main (`ff5b4df`); after the fix, all 10 tests passed (`tests/middleware/test_https_redirect.py`).
- Passed `scripts/check` (ruff format, mypy, ruff check).
- Total tests: 1,347 passed, 2 failed. The two failures are `tests/test_staticfiles.py` permission tests that only fail when run as root and are unrelated to this change.
- 100% code coverage for the two modified files.
- Duplicate check: I searched PRs, issues, and discussions for `HTTPSRedirectMiddleware`, `httpsredirect`, `IPv6`, and `hostname brackets`, and found no duplicate reports or fixes. None of the open PRs touch `httpsredirect.py` either.

