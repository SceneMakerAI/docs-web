---
id: 대소문자-무시-모드에서-중첩-dataclass-의-대문자-필드-누락-수정
title: "대소문자 무시 모드에서 중첩 dataclass 의 대문자 필드 누락 수정"
sidebar_position: 15
slug: "15"
description: "pydantic-settings: case_sensitive=False 에서 중첩 pydantic dataclass 의 대문자 필드가 env·dotenv 로 채워지지 않는 문제 수정"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## pydantic-settings: 중첩 pydantic dataclass 필드의 대소문자 무시 매칭 누락 수정

링크: https://github.com/pydantic/pydantic-settings/pull/1010

### 배경

SceneMakerAI 는 `BaseSettings` + `.env` + `env_nested_delimiter` 조합으로 설정을 읽는다. pydantic-settings 는 기본값이 `case_sensitive=False` 라서 환경변수 이름을 전부 소문자로 바꿔 매칭한 뒤, 중첩 모델에 넘기기 전에 실제 필드 이름(대소문자 포함)으로 키를 되돌린다.

이 "키 되돌리기" 단계가 중첩 타입이 `BaseModel` 일 때만 동작하고, pydantic dataclass 일 때는 빠져 있었다. 그래서 필드 이름에 대문자가 들어간 중첩 dataclass 는 환경변수나 dotenv 로 채울 수 없다.

- 필수 필드인 경우: `Field required` ValidationError (입력값이 `apikey` 로 들어가 `ApiKey` 를 못 찾음)
- Optional 이거나 더 깊은 단계의 dataclass 인 경우: 에러 없이 값이 조용히 버려지고 `None` 으로 남음

같은 구조를 `BaseModel` 로 선언하면 정상 동작한다.

### 원인

`pydantic_settings/sources/base.py` 의 `PydanticBaseEnvSettingsSource._replace_field_names_case_insensitively` :

- 진입 조건이 `hasattr(annotation, 'model_fields')` 라서 pydantic dataclass 는 키를 그대로 통과시킨다.
- 재귀 조건이 `_lenient_issubclass(..., BaseModel)` 라서 모델 안에 들어 있는 dataclass 도 방문하지 않는다.

반면 값을 수집하는 쪽인 `EnvSettingsSource.next_field` (`sources/providers/env.py` ) 는 이미 `is_model_class(...) or is_pydantic_dataclass(...)` 조건과 `_get_model_fields` 로 dataclass 를 지원한다. 즉 값 수집은 되는데 키 복원만 빠진 비대칭이다. Optional 중첩 모델에 대한 같은 종류의 누락은 #903 / #905 에서 메인테이너가 직접 고친 전례가 있다.

### 변경 내용

- `_is_model_or_dataclass` 헬퍼 추가 (`is_model_class or is_pydantic_dataclass` ).
- `_replace_field_names_case_insensitively` 의 진입 조건과 재귀 조건을 이 헬퍼로 교체하고, 필드 조회를 기존 `_get_model_fields` 로 변경.
- 사용처가 없어진 import (`BaseModel` , `_lenient_issubclass` ) 제거.
- 테스트 2건 추가: `test_case_insensitive_nested_dataclass` , `test_case_insensitive_deeply_nested_dataclass` .
- `BaseModel` 경로의 동작은 그대로.

범위에서 뺀 것: stdlib `dataclasses.dataclass` , `dict[str, Model]` 의 값, Optional 이 아닌 모델 유니온. 같은 증상이 재현되지만 대상 타입 선택 방식에 메인테이너 결정이 필요해서 PR 본문에 미포함 사항으로만 적었다.

### 검증

- upstream `main` HEAD `5927b44` 에서 재현 스크립트 실행: BaseModel 은 성공, dataclass 는 env/dotenv 모두 ValidationError, 깊은 중첩은 `Inner=None` .
- 새 테스트 2건이 수정 전 실패, 수정 후 통과.
- 전체 테스트 891 passed / 5 skipped, `ruff check` , `ruff format --check` , `mypy pydantic_settings` 통과, `base.py` 커버리지 100% 유지.
- 로컬은 Linux / Python 3.12 / pydantic 2.13.5 한 조합만 실행. CI 매트릭스(3.10\~3.14, macOS, Windows)와 PyYAML 제거 후 재실행 단계는 돌리지 않았다.

