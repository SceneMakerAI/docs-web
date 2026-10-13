---
title: "Add an \"Allow\" header to StaticFiles 405 responses"
sidebar_position: 26
slug: "26"
description: "Starlette: Fixed an issue where the 405 response from StaticFiles was missing the \"Allow\" header required by RFC 9110"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-07
---

[https://github.com/Kludex/starlette/pull/3635](https://github.com/Kludex/starlette/pull/3635)

Preliminary Discussion: [https://github.com/Kludex/starlette/discussions/3634](https://github.com/Kludex/starlette/discussions/3634)

#### Purpose

`StaticFiles` responds to requests that are not `GET` or `HEAD` with an `405 Method Not Allowed` response but does not include the `Allow` header. Starlette’s `Route` and `HTTPEndpoint`, on the other hand, do include it.

```text
> POST /r             - 405 allow='HEAD, GET'
> POST /static/a.txt  - 405 allow=None
```

Section 15.5.6 of RFC 9110 requires that the `Allow` header be included in 405 responses. Issue #1436 from 2022 added this header to ``Route`` and ``HTTPEndpoint``, but ``StaticFiles``—which throws an exception on its own—was omitted.

SceneMaker’s API services run on FastAPI (Starlette 1.x), and the gateway passes the backend response through unchanged. If the header specifying the allowed methods is missing, it’s difficult for the client to determine the cause; I discovered this while investigating “mismatched behavior” similar to what was found in the previous merge PR (#3376).

#### Changes

- `starlette/staticfiles.py` — Added `headers={"Allow": "GET, HEAD"}` to the 405 exception (+1 / -1)
- `tests/test_staticfiles.py` — Added one line of header validation to the existing `test_staticfiles_post` (+1)

#### Procedure

Starlette requires contributions to begin in the discussion thread, and the PR template states that PRs submitted without prior discussion may be closed. Therefore, I first opened a “Potential Issue” discussion (#3634) and referenced it in the PR. Since the discussion and the PR address the same issue, this counts as a single contribution.

#### Testing

```text
$ pytest tests/test_staticfiles.py -k post    # Before modification: Failed with KeyError: 'allow'
$ pytest tests/test_staticfiles.py -k post    # After modification: 2 passed
$ ruff format --check starlette tests         # 71 files already formatted
$ ruff check starlette tests                  # All checks passed!
```

I was unable to verify 100% test coverage locally. This is because two permission tests failed even before the fix—since this server runs as the root account—so I left it to CI.

#### Duplicate Check

Starlette specifies in `AI_POLICY.md` that it blocks users who submit duplicate PRs. I re-searched open and closed issues, PRs, and discussions immediately prior to submission using `StaticFiles` + `Allow` / 405 and found no identical changes. #3585 only changes the value of `Allow` in `HTTPEndpoint` and does not modify `staticfiles.py`. I also checked the diffs for the four open PRs (#3589, #3586, #3248, #2955) that modify `staticfiles.py`, and none of them change the handling of 405.

#### Result

Submitted to the `main` branch on October 6, 2026. Awaiting review. The scope of the changes is 2 files, +2 / -1.

2026-10-07 Update: The maintainer (Kludex) closed this PR without explanation and submitted the same changes in their own PR #3640, which was merged into `main` on 2026-10-06. The bug report was accepted and incorporated into the upstream, but our PR was not merged. The preliminary discussion #3634 remains open.

