---
id: httpsredirectmiddleware-가-ipv6-호스트의-대괄호를-떼어-잘못된-location-을-만드는-문제-수정
title: "HTTPSRedirectMiddleware 가 IPv6 호스트의 대괄호를 떼어 잘못된 Location 을 만드는 문제 수정"
sidebar_position: 37
slug: "37"
description: "starlette: Host 가 [::1]:80 처럼 IPv6 + 기본 포트일 때 리다이렉트 URL 에서 대괄호가 빠지던 문제 수정 (Discussion #3637)"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## starlette: HTTPSRedirectMiddleware 가 IPv6 호스트의 기본 포트를 뗄 때 대괄호까지 떼는 문제

링크: https://github.com/Kludex/starlette/pull/3638

### 배경

`HTTPSRedirectMiddleware` 는 `http` /`ws` 요청을 `https` /`wss` 로 307 리다이렉트한다. 이때 `Host` 헤더의 포트가 80 또는 443 이면 리다이렉트 URL 에서 포트를 뺀다. 호스트가 IPv6 리터럴이면 이 과정에서 대괄호가 함께 사라져 `Location` 헤더가 올바른 URL 이 아니게 된다.

```text
Host: [::1]:80            -> Location: https://::1/path?a=1
Host: [2001:db8::1]:443   -> Location: https://2001:db8::1/path?a=1
```

`urllib.parse.urlsplit` 은 이 값의 포트를 읽을 때 `ValueError` 를 내고, httpx 는 `Invalid URL in location header` 로 리다이렉트를 따라가지 않는다. 포트가 없거나(`[::1]` ) 다른 포트(`[::1]:8000` )일 때는 정상이다.

### 원인

`starlette/middleware/httpsredirect.py` 17행.

```python
netloc = url.hostname if url.port in (80, 443) else url.netloc
url = url.replace(scheme=redirect_scheme, netloc=netloc)
```

`url.hostname` 은 표준 라이브러리 `SplitResult.hostname` 과 같이 IPv6 주소를 대괄호 없이 돌려준다. 그 값을 `netloc=` 으로 넘기면 `URL.replace` 는 그대로 사용한다. 최근 머지된 #3617 은 `URL.replace(hostname=...)` 경로에만 대괄호를 붙이므로 이 호출에는 적용되지 않는다.

### 변경 내용

기본 포트일 때 netloc 을 hostname 으로 바꾸는 대신 `url.replace(port=None)` 으로 포트만 제거한다. 이 경로는 기존 netloc 에서 호스트 부분을 대괄호째 유지한다.

```python
url = url.replace(scheme=redirect_scheme)
if url.port in (80, 443):
    url = url.replace(port=None)
```

- 기본 포트가 아닌 경우의 결과는 이전과 완전히 같다.
- 부수적인 차이 하나: 기본 포트 경로에서 `url.hostname` 때문에 호스트가 소문자로 바뀌던 동작이 없어진다 (`Example.org:80` 은 이제 `https://Example.org/` . 다른 포트에서는 원래도 대소문자를 유지했다).
- 테스트 `test_https_redirect_middleware_ipv6_default_port` 를 추가했다 (포트 80, 443 매개변수화).
- 문서 변경은 없다. 문서에 리다이렉트 URL 구성 방식 설명이 없다.

### 검증

- 수정 전 main (`ff5b4df` ) 에서 새 테스트 4건(포트 2개 x asyncio/trio) 실패, 수정 후 `tests/middleware/test_https_redirect.py` 10건 통과.
- `scripts/check` (ruff format, mypy, ruff check) 통과.
- 전체 테스트: 1347 통과, 2 실패. 실패 2건은 root 로 실행할 때만 실패하는 `tests/test_staticfiles.py` 권한 테스트로 이 변경과 무관하다.
- 변경한 두 파일의 커버리지 100%.
- 중복 확인: PR·이슈·Discussion 을 `HTTPSRedirectMiddleware` , `httpsredirect` , `IPv6` , `hostname brackets` 등으로 검색했고 같은 보고나 수정은 없었다. 열린 PR 중 `httpsredirect.py` 를 건드리는 것도 없다.

