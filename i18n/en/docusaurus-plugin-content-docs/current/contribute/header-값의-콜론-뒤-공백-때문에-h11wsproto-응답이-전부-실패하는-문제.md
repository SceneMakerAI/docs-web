---
title: "--Issue where all h11 and wsproto responses fail due to a space after the colon in the header value"
sidebar_position: 29
slug: "29"
description: "uvicorn: Reported an issue where adding a space after the colon (e.g., --header \"Name: Value\") causes all responses and handshakes to fail in h11·wsproto (Potential Issue discussion)"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

## uvicorn: Issue where all responses fail in h11 / wsproto when using `--header "Name: Value"`

Link: https://github.com/Kludex/uvicorn/discussions/3188

- Target: Kludex/uvicorn (main, 724f82f, 0.54.0)
- Type: Discussion (draft in the "Potential Issue" category). This repository does not allow opening issues directly; a discussion must be held first.
- Fixes and tests are currently in the local branch `fix/cli-header-strip-whitespace` and have not been committed (can be converted to a follow-up PR if the maintainer acknowledges it as a bug)

### Background

SceneMakerAI runs a FastAPI app under systemd in the `uvicorn app:app --workers K ...` format and allows security headers and other settings to be added via `--header`. If you write the `--header` value as `--header "X-Frame-Options: DENY"`—with a space after the colon, as in curl’s `-H` or actual HTTP headers—the behavior varies depending on the HTTP implementation.

| Implementation | Result |

|---|---|

| `--http h11` | All requests fail as `LocalProtocolError: Illegal header value b' DENY'`; connection terminates without a response (curl exit 52). Logged as `200 OK` in the access log |

| `--ws wsproto` | All WebSocket handshakes fail |

| `--http httptools`, `--http zttp` | Works normally; headers are sent as `x-frame-options:  DENY` (with two spaces) |

| `--ws websockets`, `--ws websockets-sansio` | Works normally |

The server starts up normally, and there are no warnings until the first request arrives. In an environment using only `pip install uvicorn` without httptools, `--http auto` selects h11, causing the entire server to become unresponsive.

### Cause

- It splits only from `uvicorn/main.py:494` to `header.split(":", 1)` and does not remove spaces. The value is stored as `" DENY"`.
- It is encoded as-is in `uvicorn/config.py:496`, becoming `encoded_headers`, and then passes from `uvicorn/server.py:262` to `server_state.default_headers`.
- In `uvicorn/protocols/http/h11_impl.py:467,484`, the default header is passed to `h11.Response(...)`; however, since h11 does not allow leading or trailing whitespace in field values, it throws an exception. `wsproto_impl.py:391` also fails the internal h11 validation in wsproto.
- The httptools, zttp, and WebSockets implementations pass the test by writing the value as-is without validation.

According to Section 5.5 of RFC 9110, leading and trailing whitespace in a field value is not part of the value, so removing it at the CLI boundary does not change the meaning.

### Reproduction Steps

```shell
$ cat app.py
async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"ok\n"})

$ uvicorn app:app --port 18731 --http h11 --header "X-Frame-Options: DENY" &
$ curl -si http://127.0.0.1:18731/
curl: (52) Empty reply from server
# Server log: h11._util.LocalProtocolError: Illegal header value b' DENY'
```

### Proposed Change (Local, Uncommitted)

```python
# uvicorn/main.py
headers=[[part.strip() for part in header.split(":", 1)] for header in headers],
```

Add `test_cli_headers_strip_whitespace` to `tests/test_cli.py`.

### Validation

- Pre-fix HEAD: Verified that h11 returns a curl exit code of 52, wsproto fails the handshake, and the rest are sent with two spaces
- New tests failed before the fix (`[['X-Frame-Options', ' DENY ']]`) but passed after the fix
- After the fix: h11, httptools, and zttp all returned a 200 response as shown in `x-frame-options: DENY`; handshakes for websockets, websockets-sansio, and wsproto all succeeded
- Total tests: 1,351 passed, 12 skipped. `ruff format --check`, `mypy`, and `ruff check` passed
- Did not run the 100% coverage gate (`scripts/coverage`) or the docs build

### Duplicate Check

- Searched for `Illegal header value` and `--header` (including terms like “whitespace,” “space,” and “strip”) in Issues, PRs, and Discussions, but found no identical reports
- The closest match is open PR #2992 (rejected `--header` without a colon as `BadParameter`). Although it fixes the same line, it does not remove whitespace, so there is no functional overlap. I have mentioned this PR in the body of this report

