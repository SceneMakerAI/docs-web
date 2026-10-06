---
id: dotenv-run-이-fifo-형태의-env-를-거부하는-문제-수정
title: "dotenv run 이 FIFO 형태의 .env 를 거부하는 문제 수정"
sidebar_position: 27
slug: "27"
description: "python-dotenv: dotenv run 이 named pipe 형태의 .env 를 does not exist 로 거부하던 문제를 라이브러리·list/get 과 같게 수정"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## python-dotenv: `dotenv run` 이 FIFO 형태의 .env 를 거부하는 문제 수정

링크: https://github.com/theskumar/python-dotenv/pull/723

### 배경

python-dotenv 는 1.2.2 부터 FIFO(named pipe) 로 된 `.env` 읽기를 공식 지원한다 (PR #586, README 의 File format 절에도 명시). 1Password 의 로컬 `.env` 마운트나 `dotenv -f <(sops -d secrets.env) ...` 같은 process substitution 처럼, 평문 시크릿을 디스크에 남기지 않으려는 용도다.

그런데 CLI 의 `dotenv run` 만 이 경로를 받아들이지 않는다. 같은 경로에 대해 라이브러리(`load_dotenv` , `dotenv_values` )와 `dotenv list` , `dotenv get` 은 정상 동작한다.

### 원인

`src/dotenv/cli.py` 의 `run` 커맨드(196행)가 `DotEnv` 에 넘기기 전에 `os.path.isfile(file)` 로 경로를 검사한다. FIFO 는 regular file 이 아니므로 "does not exist" 에러로 종료(exit 2)한다. 라이브러리 쪽 `DotEnv._get_stream` 과 `find_dotenv` 는 #586 에서 `_is_file_or_fifo` 로 바뀌었지만 CLI 의 이 가드는 누락됐다.

### 재현 방법

```shell
$ dotenv -f <(echo A=1) list
A=1
$ dotenv -f <(echo A=1) run printenv A
Error: Invalid value: Invalid value for '-f' "/dev/fd/63" does not exist.
```

`mkfifo .env` 로 만든 named pipe 를 기본 경로로 쓸 때도 동일하다.

### 변경 내용

- `src/dotenv/cli.py` : `run` 의 가드를 `os.path.isfile` 에서 `_is_file_or_fifo` 로 교체 (import 1줄, 조건 1줄).
- `tests/test_fifo_dotenv.py` : `test_cli_run_from_fifo` 추가. FIFO `.env` 에 대해 `dotenv run printenv MY_PASSWORD` 가 값을 출력하는지 확인.
- `CHANGELOG.md` : Unreleased / Fixed 에 항목 추가. PR 번호는 `#NNN` 자리표시자라 PR 생성 후 실제 번호로 바꿔야 한다.

없는 경로와 디렉터리는 기존과 같은 메시지로 계속 거부된다.

### 검증

- 수정 전: 새 테스트 실패 (exit 2, "does not exist").
- 수정 후: `pytest` 285 passed, 4 skipped. `ruff check src tests` , `ruff format --check src tests` , `mypy --python-version=3.10~3.14 src tests` 모두 통과.
- Python 3.11 / Linux 에서만 실행. tox 전체 매트릭스(3.10\~3.14, 3.14t, PyPy, Windows)와 `check-manifest` 는 돌리지 않았다.

