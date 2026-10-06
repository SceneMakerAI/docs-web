---
id: header-값의-콜론-뒤-공백-때문에-h11wsproto-응답이-전부-실패하는-문제
title: "--header 값의 콜론 뒤 공백 때문에 h11·wsproto 응답이 전부 실패하는 문제"
sidebar_position: 29
slug: "29"
description: "uvicorn: --header \"Name: Value\" 처럼 콜론 뒤에 공백을 넣으면 h11·wsproto 에서 모든 응답과 핸드셰이크가 실패하는 문제 보고 (Potential Issue discussion)"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

## uvicorn: `--header "Name: Value"` 사용 시 h11 / wsproto 에서 모든 응답이 실패하는 문제

링크: https://github.com/Kludex/uvicorn/discussions/3188

- 대상: Kludex/uvicorn (main, 724f82f, 0.54.0)
- 형태: Discussion ("Potential Issue" 카테고리) 초안. 이 저장소는 이슈를 바로 열 수 없고 Discussion 을 먼저 거쳐야 한다.
- 로컬 브랜치 `fix/cli-header-strip-whitespace` 에 수정 + 테스트가 커밋되지 않은 상태로 있음 (메인테이너가 버그로 인정하면 후속 PR 로 전환 가능)

### 배경

SceneMakerAI 는 FastAPI 앱을 `uvicorn app:app --workers K ...` 형태로 systemd 아래에서 운영하고, 보안 헤더 등을 `--header` 로 붙일 수 있다. `--header` 값을 curl 의 `-H` 나 실제 HTTP 헤더처럼 콜론 뒤에 공백을 넣어 `--header "X-Frame-Options: DENY"` 로 쓰면, HTTP 구현체에 따라 동작이 갈린다.

| 구현체 | 결과 |

|---|---|

| `--http h11` | 모든 요청이 `LocalProtocolError: Illegal header value b' DENY'` 로 실패, 응답 없이 연결 종료 (curl exit 52). access log 에는 `200 OK` 로 찍힘 |

| `--ws wsproto` | 모든 WebSocket 핸드셰이크 실패 |

| `--http httptools` , `--http zttp` | 정상 동작, 헤더는 `x-frame-options:  DENY` (공백 2개) 로 전송 |

| `--ws websockets` , `--ws websockets-sansio` | 정상 동작 |

서버는 정상 기동하고 첫 요청이 올 때까지 아무 경고도 없다. httptools 없이 `pip install uvicorn` 만 한 환경에서는 `--http auto` 가 h11 을 고르므로 서버 전체가 응답 불능이 된다.

### 원인

- `uvicorn/main.py:494` 에서 `header.split(":", 1)` 로만 나누고 공백을 제거하지 않는다. 값이 `" DENY"` 로 저장된다.
- `uvicorn/config.py:496` 에서 그대로 인코딩되어 `encoded_headers` 가 되고, `uvicorn/server.py:262` 에서 `server_state.default_headers` 로 들어간다.
- `uvicorn/protocols/http/h11_impl.py:467,484` 에서 기본 헤더를 `h11.Response(...)` 에 넘기는데, h11 은 필드 값 앞뒤 공백을 허용하지 않아 예외를 던진다. `wsproto_impl.py:391` 도 wsproto 내부의 h11 검증에 걸린다.
- httptools / zttp / websockets 구현체는 값을 검증 없이 그대로 써서 통과한다.

RFC 9110 5.5 절에 따르면 필드 값 앞뒤 공백은 값의 일부가 아니므로 CLI 경계에서 제거해도 의미가 달라지지 않는다.

### 재현 방법

```shell
$ cat app.py
async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"ok\n"})

$ uvicorn app:app --port 18731 --http h11 --header "X-Frame-Options: DENY" &
$ curl -si http://127.0.0.1:18731/
curl: (52) Empty reply from server
# 서버 로그: h11._util.LocalProtocolError: Illegal header value b' DENY'
```

### 제안한 변경 (로컬, 미커밋)

```python
# uvicorn/main.py
headers=[[part.strip() for part in header.split(":", 1)] for header in headers],
```

`tests/test_cli.py` 에 `test_cli_headers_strip_whitespace` 추가.

### 검증

- 수정 전 HEAD: h11 은 curl exit 52, wsproto 는 핸드셰이크 실패, 나머지는 공백 2개로 전송되는 것을 확인
- 새 테스트는 수정 전 실패 (`[['X-Frame-Options', ' DENY ']]` ), 수정 후 통과
- 수정 후: h11 / httptools / zttp 모두 `x-frame-options: DENY` 로 200 응답, websockets / websockets-sansio / wsproto 핸드셰이크 모두 성공
- 전체 테스트 1351 passed, 12 skipped. `ruff format --check` , `mypy` , `ruff check` 통과
- 커버리지 100% 게이트 (`scripts/coverage` ) 와 docs 빌드는 실행하지 않음

### 중복 확인

- 이슈 / PR / Discussion 에서 `Illegal header value` , `--header` whitespace / space / strip 등으로 검색했으나 동일 보고 없음
- 가장 가까운 것은 열려 있는 PR #2992 (콜론이 없는 `--header` 를 `BadParameter` 로 거부). 같은 줄을 고치지만 공백 제거는 하지 않으므로 동작상 겹치지 않는다. 본문에 해당 PR 을 언급해 둠

