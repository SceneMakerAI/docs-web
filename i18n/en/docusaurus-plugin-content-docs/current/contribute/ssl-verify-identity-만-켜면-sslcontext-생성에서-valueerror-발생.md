---
title: "A ValueError occurs during SSLContext creation if only `ssl_verify_identity` is enabled"
sidebar_position: 25
slug: "25"
description: "PyMySQL: I've seen reports of an issue where, if you set only `ssl_verify_identity=True` without `ssl_verify_cert`, `CERT_NONE` and `check_hostname` conflict, causing a `ValueError` before the connection is established."
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-06
---

## PyMySQL: ValueError occurs when using `ssl_verify_identity=True` on its own

Link: https://github.com/PyMySQL/PyMySQL/issues/1281

### Background

SceneMakerAI’s FastAPI reverse proxy and management scripts use PyMySQL to connect to MariaDB 10.11 / 11.x. While reviewing TLS options, I discovered that if `ssl_verify_identity=True`—which the documentation merely states “verifies the server’s identity”—is set alongside `ssl_ca`, a `Connection.__init__` error occurs in `ValueError` before the connection attempt even begins. It only works when `ssl_verify_cert=True` is also set.

- Affected: PyMySQL/PyMySQL `main` 31126a3 (v1.2.3 and later); identical code since v1.0.0
- Type: Issue (requires maintainer’s judgment on how to fix). A single-line fix and tests have been left in the local branch `fix-ssl-verify-identity-implies-verify-cert` without being committed

### Cause

In lines `pymysql/connections.py` 280–286, when converting the `ssl_*` argument to an internal dict, if `ssl_verify_cert` is the default value `None`, it sets `verify_mode` to `False`. On the other hand, since `check_hostname` is `bool(ssl_verify_identity)`, it becomes `True`.

`_create_ssl_ctx` uses this dict to set `ctx.check_hostname = True` on line 395 and `ctx.verify_mode = ssl.CERT_NONE` on line 400, respectively; however, Python `ssl.SSLContext` does not allow this combination and raises the following exception:

```text
ValueError: Cannot set verify_mode to CERT_NONE when check_hostname is enabled.
```

The existing tests (`pymysql/tests/test_connection.py` lines 751–752, lines 774–775) handle the same combination of arguments but use the `mock.Mock` context; as a result, they were actually asserting as correct an impossible state (`check_hostname` true + `CERT_NONE`). Therefore, this issue did not surface after the option was added in #903 in 2020.

### Reproduction Steps

This can be reproduced without a server. In the `defer_connect=True` context, only an SSLContext is created without opening a socket.

```python
import pymysql

conn = pymysql.connect(
    host="db.example.com",
    ssl_ca="/etc/pki/tls/certs/ca-bundle.crt",
    ssl_verify_identity=True,
    defer_connect=True,
)
```

- Expected: Create a context where `CERT_REQUIRED` + `check_hostname=True`. This is equivalent to the MySQL client’s `--ssl-mode=VERIFY_IDENTITY` containing `VERIFY_CA`.
- Actual: The `ValueError` mentioned above

### Proposed Fix

When `ssl_verify_cert` is `None`, set the default value of `verify_mode` to `bool(ssl_verify_identity)` instead of `False` (line 1). Tests: Added 1 case that uses the actual `ssl.SSLContext`; modified 2 existing mock assertions to use `CERT_REQUIRED`.

### Verification

- Before the fix, unpack HEAD separately as `git archive` and run the reproduction script: confirmed that `ValueError` occurs
- First added the new test to verify that it fails with the same `ValueError`, then made the fix, after which it passed
- Since `test_connection.py` connects to the database at import time, pytest collection is not possible without a server. Ran only the four SSL option tests using a harness that stubs `pymysql.connect` in the import section: all four passed
- 5 test files that do not require a server passed 26 tests; 4 `converters.py` doctests passed; no changes to `ruff format --diff` / `ruff check --diff`
- Tests that could not be run: the entire test suite requiring a production server, and the actual TLS handshake

