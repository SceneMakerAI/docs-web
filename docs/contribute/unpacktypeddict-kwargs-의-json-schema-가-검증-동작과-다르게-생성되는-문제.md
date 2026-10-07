---
id: unpacktypeddict-kwargs-의-json-schema-가-검증-동작과-다르게-생성되는-문제
title: "Unpack[TypedDict] kwargs 의 JSON Schema 가 검증 동작과 다르게 생성되는 문제"
sidebar_position: 40
slug: "40"
description: "pydantic: 함수의 **kwargs: Unpack[TypedDict] 에 대해 생성되는 JSON Schema 가 실제 검증과 양방향으로 어긋나는 문제 보고 (수정안 준비됨)"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-07
---

## pydantic: `**kwargs: Unpack[TypedDict]` 함수의 JSON Schema 가 검증 동작과 다르게 생성되는 문제 수정

링크: https://github.com/pydantic/pydantic/issues/13938

### 배경

pydantic 2.10 부터 `@validate_call` 과 `TypeAdapter(함수)` 는 가변 키워드 인자를 `**kwargs: Unpack[SomeTypedDict]` 로 선언할 수 있다 (pydantic#10416). 이때 TypedDict 의 각 항목은 개별 키워드 인자로 검증된다. 우리는 함수 시그니처에서 뽑은 JSON Schema 를 LLM tool 정의와 OpenAPI 문서에 쓰기 때문에, 스키마가 실제 검증 동작과 다르면 모델이 잘못된 인자를 만들어 낸다.

`main` (1e6cc758a) 에서 아래 함수의 스키마를 뽑으면 TypedDict 전체가 `additionalProperties` 아래에 들어간다. 이것은 `**kwargs: Options` (추가 키워드 하나하나가 Options 객체) 의 스키마다.

```python
class Options(TypedDict):
    timeout: int
    label: NotRequired[str]

def run(name: str = 'job', **kwargs: Unpack[Options]): ...

TypeAdapter(run).json_schema()
# 'additionalProperties': {'$ref': '#/$defs/Options'}, 'properties': {'name': ...}
```

결과적으로 스키마와 검증기가 양쪽으로 어긋난다.

- `name='x', timeout=5` : 검증 통과, 스키마로는 invalid
- `name='x'` : 검증 실패 (missing), 스키마로는 valid
- `anything=dict(timeout=5)` : 검증 실패 (missing), 스키마로는 valid

### 원인

`pydantic/json_schema.py` 의 `GenerateJsonSchema.arguments_schema()` 가 core schema 의 `var_kwargs_mode` 를 보지 않고 `var_kwargs_schema` 를 그대로 `kw_arguments_schema()` 에 넘긴다. 그래서 `'unpacked-typed-dict'` 모드가 `'uniform'` 모드와 똑같이 처리된다. #10416 은 검증 쪽만 추가했고 `json_schema.py` 는 건드리지 않았다. 나중에 추가된 `arguments_v3_schema()` 는 두 모드를 구분하지만 `@validate_call` 과 `TypeAdapter` 가 쓰는 경로가 아니다.

### 변경 내용

- `arguments_schema()` 에서 `var_kwargs_mode` 가 `'unpacked-typed-dict'` 이면 TypedDict 의 JSON Schema 를 구해 `properties` 와 `required` 를 인자 객체에 합친다.
- `additionalProperties` 는 TypedDict 를 따른다: `closed=True` 면 `False` , `extra_items` 가 있으면 그 스키마, 둘 다 없으면 키를 넣지 않는다 (런타임에서 추가 키워드를 무시하는 것과 일치).
- 서브클래스가 오버라이드할 수 있는 `kw_arguments_schema()` 의 시그니처는 바꾸지 않았다.
- `tests/test_validate_call.py` 에 테스트 2개 추가 (필수/선택 항목 병합, `closed` 와 `extra_items` ).
- 변경량: 2개 파일, +68 / -1.

### 검증

- 수정 전 `main` 에서 재현 스크립트와 새 테스트가 실패하는 것을 확인했고, 수정 후 통과한다.
- `tests/test_validate_call.py` , `tests/test_json_schema.py` , `tests/test_experimental_arguments_schema.py` , `tests/test_type_adapter.py` : 962 passed.
- 전체 Python 테스트: 수정 전 63 failed / 6151 passed, 수정 후 63 failed / 6153 passed. 실패 63건은 수정 전후 목록이 같고, 이 머신에 Rust 가 없어 체크아웃보다 오래된 `pydantic-core==2.49.0` 릴리스 휠로 돌렸기 때문에 생긴다.
- `ruff check` , `ruff format --check` (uv.lock 의 0.15.10) 통과. pyright 는 같은 이유로 수정 전후 동일하게 66건이 나와 CI 와 같은 조건으로는 확인하지 못했다.
- 저장소 규정상 사소하지 않은 변경은 이슈를 먼저 열어야 하므로 `issue.md` 에 버그 리포트 초안을 함께 두었다.

2026-10-06 에 다른 사용자 pranavpk404 가 최신 main 에서 재현했다고 확인하고 수정 PR [#13939](https://github.com/pydantic/pydantic/pull/13939) 를 올렸다. 다만 pydantic 은 이슈에 배정된 사람만 PR 을 열 수 있어서 봇이 그 PR 을 자동으로 닫았고, 그는 메인테이너에게 배정을 요청한 상태다.

