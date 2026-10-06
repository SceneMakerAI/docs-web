---
id: ssl-verify-identity-만-켜면-sslcontext-생성에서-valueerror-발생
title: "ssl_verify_identity 만 켜면 SSLContext 생성에서 ValueError 발생"
sidebar_position: 25
slug: "25"
description: "PyMySQL: ssl_verify_cert 없이 ssl_verify_identity=True 만 주면 CERT_NONE 과 check_hostname 이 충돌해 접속 전에 ValueError 가 나는 문제 보고"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-06
---

## PyMySQL: ssl_verify_identity=True 단독 사용 시 ValueError 발생

링크: https://github.com/PyMySQL/PyMySQL/issues/1281

### 배경

SceneMakerAI 의 FastAPI 리버스 프록시와 관리 스크립트는 PyMySQL 로 MariaDB 10.11 / 11.x 에 접속한다. TLS 옵션을 점검하던 중, 문서에 "서버 identity 를 검증한다"고만 적혀 있는 `ssl_verify_identity=True` 를 `ssl_ca` 와 함께 주면 접속을 시도하기도 전에 `Connection.__init__` 에서 `ValueError` 가 나는 것을 확인했다. `ssl_verify_cert=True` 를 같이 줘야만 동작한다.

- 대상: PyMySQL/PyMySQL `main` 31126a3 (v1.2.3 이후), v1.0.0 부터 동일한 코드
- 형태: Issue (수정 방향에 메인테이너 판단이 필요). 한 줄 수정과 테스트는 로컬 브랜치 `fix-ssl-verify-identity-implies-verify-cert` 에 커밋하지 않은 상태로 남겨 둠

### 원인

`pymysql/connections.py` 280-286 행이 `ssl_*` 인자를 내부 dict 로 바꿀 때 `ssl_verify_cert` 가 기본값 `None` 이면 `verify_mode` 를 `False` 로 넣는다. 반면 `check_hostname` 은 `bool(ssl_verify_identity)` 라서 `True` 가 된다.

`_create_ssl_ctx` 는 이 dict 로 395 행에서 `ctx.check_hostname = True` , 400 행에서 `ctx.verify_mode = ssl.CERT_NONE` 을 차례로 설정하는데, 파이썬 `ssl.SSLContext` 는 이 조합을 허용하지 않아 다음 예외를 던진다.

```text
ValueError: Cannot set verify_mode to CERT_NONE when check_hostname is enabled.
```

기존 테스트(`pymysql/tests/test_connection.py` 751-752, 774-775 행)는 같은 인자 조합을 다루지만 `mock.Mock` 컨텍스트를 써서, 실제로는 만들 수 없는 상태(`check_hostname` 참 + `CERT_NONE` )를 오히려 정답으로 단언하고 있었다. 그래서 2020년 #903 에서 옵션이 추가된 뒤로 드러나지 않았다.

### 재현 방법

서버 없이 재현된다. `defer_connect=True` 면 소켓을 열지 않고 SSLContext 만 만든다.

```python
import pymysql

conn = pymysql.connect(
    host="db.example.com",
    ssl_ca="/etc/pki/tls/certs/ca-bundle.crt",
    ssl_verify_identity=True,
    defer_connect=True,
)
```

- 기대: `CERT_REQUIRED` + `check_hostname=True` 인 컨텍스트 생성. MySQL 클라이언트의 `--ssl-mode=VERIFY_IDENTITY` 가 `VERIFY_CA` 를 포함하는 것과 같은 의미
- 실제: 위 `ValueError`

### 제안한 수정

`ssl_verify_cert` 가 `None` 일 때 `verify_mode` 기본값을 `False` 대신 `bool(ssl_verify_identity)` 로 둔다 (1행). 테스트는 실제 `ssl.SSLContext` 를 쓰는 케이스 1개 추가, 기존 mock 단언 2곳을 `CERT_REQUIRED` 로 수정.

### 검증

- 수정 전 HEAD 를 `git archive` 로 따로 풀어 재현 스크립트 실행: `ValueError` 발생 확인
- 새 테스트를 먼저 추가해 같은 `ValueError` 로 실패하는 것을 확인한 뒤 수정, 이후 통과
- `test_connection.py` 는 import 시점에 DB 에 접속하므로 서버 없이는 pytest 수집이 안 된다. SSL 옵션 테스트 4개만 import 구간에서 `pymysql.connect` 를 stub 하는 하니스로 실행: 4개 통과
- 서버가 필요 없는 테스트 파일 5개 26개 통과, `converters.py` doctest 4개 통과, `ruff format --diff` / `ruff check --diff` 변경 없음
- 실행하지 못한 것: 실서버가 필요한 전체 테스트 스위트, 실제 TLS 핸드셰이크

