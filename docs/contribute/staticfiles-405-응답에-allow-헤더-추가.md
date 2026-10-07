---
id: staticfiles-405-응답에-allow-헤더-추가
title: "StaticFiles 405 응답에 Allow 헤더 추가"
sidebar_position: 26
slug: "26"
description: "Starlette: StaticFiles 의 405 응답에 RFC 9110 이 요구하는 Allow 헤더가 빠진 문제 수정"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-07
---

[https://github.com/Kludex/starlette/pull/3635](https://github.com/Kludex/starlette/pull/3635)

사전 논의: [https://github.com/Kludex/starlette/discussions/3634](https://github.com/Kludex/starlette/discussions/3634)

#### 목적

`StaticFiles` 는 `GET` ·`HEAD` 가 아닌 요청에 `405 Method Not Allowed` 로 답하지만 `Allow` 헤더를 붙이지 않습니다. 같은 Starlette 의 `Route` 와 `HTTPEndpoint` 는 붙입니다.

```text
POST /r             -> 405 allow='HEAD, GET'
POST /static/a.txt  -> 405 allow=None
```

RFC 9110 15.5.6 절은 405 응답에 `Allow` 헤더를 반드시 넣도록 요구합니다. 2022년 #1436 이 `Route` 와 `HTTPEndpoint` 에 이 헤더를 추가했는데, 자체적으로 예외를 던지는 `StaticFiles` 만 빠져 있었습니다.

SceneMaker 의 API 서비스들은 FastAPI(Starlette 1.x) 위에서 돌고, 게이트웨이가 뒷단 응답을 그대로 전달합니다. 허용 메서드를 알려 주는 헤더가 빠지면 클라이언트가 원인을 알기 어려워, 기존 머지 PR(#3376) 때와 같은 "짝이 안 맞는 동작" 을 찾다가 발견했습니다.

#### 변경 사항

- `starlette/staticfiles.py` — 405 예외에 `headers={"Allow": "GET, HEAD"}` 추가 (+1 / -1)
- `tests/test_staticfiles.py` — 기존 `test_staticfiles_post` 에 헤더 검증 한 줄 추가 (+1)

#### 절차

Starlette 는 기여를 디스커션에서 시작하도록 요구하고, 사전 논의 없는 PR 은 닫을 수 있다고 PR 양식에 적어 둡니다. 그래서 "Potential Issue" 디스커션(#3634)을 먼저 열고 PR 에서 참조했습니다. 디스커션과 PR 은 같은 문제 하나를 다루므로 기여 건수는 1건으로 셉니다.

#### 테스트

```text
$ pytest tests/test_staticfiles.py -k post    # 수정 전: KeyError: 'allow' 로 실패
$ pytest tests/test_staticfiles.py -k post    # 수정 후: 2 passed
$ ruff format --check starlette tests         # 71 files already formatted
$ ruff check starlette tests                  # All checks passed!
```

전체 테스트의 100% 커버리지는 로컬에서 확인하지 못했습니다. 이 서버가 root 계정이라 권한 테스트 2건이 수정 전에도 실패하기 때문이고, CI 에 맡겼습니다.

#### 중복 확인

Starlette 는 중복 PR 제출자를 차단한다고 `AI_POLICY.md` 에 명시합니다. 제출 직전에 열린·닫힌 이슈, PR, 디스커션을 `StaticFiles` + `Allow` / 405 로 다시 검색했고 같은 변경은 없었습니다. #3585 는 `HTTPEndpoint` 의 `Allow` 값만 바꾸고 `staticfiles.py` 를 건드리지 않습니다. `staticfiles.py` 를 건드리는 열린 PR 4건(#3589, #3586, #3248, #2955)의 diff 도 확인했고 405 처리는 바꾸지 않습니다.

#### 결과

2026-10-06 `main` 브랜치 대상으로 제출했습니다. 리뷰 대기 중입니다. 변경 규모는 2개 파일, +2 / -1 입니다.

2026-10-07 갱신: 메인테이너(Kludex)가 이 PR 을 설명 없이 닫고, 같은 수정을 자신의 PR #3640 으로 올려 2026-10-06 에 main 에 머지했습니다. 버그 보고는 받아들여져 업스트림에 반영됐지만, 우리 PR 은 머지되지 않았습니다. 사전 논의 디스커션 #3634 는 열려 있습니다.

