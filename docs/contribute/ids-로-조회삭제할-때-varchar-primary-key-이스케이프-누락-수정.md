---
id: ids-로-조회삭제할-때-varchar-primary-key-이스케이프-누락-수정
title: "ids 로 조회·삭제할 때 VARCHAR primary key 이스케이프 누락 수정"
sidebar_position: 22
slug: "22"
description: "pymilvus: MilvusClient get/query/delete(ids=) 가 따옴표·역슬래시가 든 VARCHAR 키를 이스케이프하지 않아 오류가 나거나 다른 행이 삭제되는 문제 수정"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## pymilvus: VARCHAR primary key 이스케이프 누락 수정 (MilvusClient get/query/delete by ids)

링크: https://github.com/milvus-io/pymilvus/pull/3823

### 배경

SceneMakerAI 는 `MilvusClient` / `AsyncMilvusClient` 로 문자열 primary key 컬렉션을 다룬다. `get(ids=...)` , `query(ids=...)` , `delete(ids=...)` 는 내부에서 id 목록을 필터 표현식 문자열로 바꿔 서버에 보내는데, 문자열 PK 에 작은따옴표나 역슬래시, 줄바꿈이 들어 있으면 호출이 실패하거나 엉뚱한 행이 대상이 된다.

### 원인

`pymilvus/milvus_client/base.py` 의 `BaseMilvusClient._pack_pks_expr` 가 VARCHAR PK 값을 이스케이프 없이 작은따옴표로 감싸기만 한다 (수정 전 134행).

```python
ids = ["'" + str(entry) + "'" for entry in pks]
```

그 결과 master (9b1d5ad) + Milvus Lite 3.0 에서 다음과 같이 동작한다.

- `O'Brien` : `unterminated string literal` 오류
- `back\slash` : `unknown escape sequence \s` 오류
- 줄바꿈 포함 키 : `unterminated string literal (newline)` 오류
- `a', 'plain` : 표현식이 `id in ['a', 'plain']` 이 되어 `delete` 가 요청한 행은 남기고 무관한 `plain` 행을 삭제

### 변경 내용

- `_escape_str_pk` 헬퍼를 추가하고 `_pack_pks_expr` 에서 사용. 역슬래시, 작은따옴표, `\n` , `\r` 네 가지만 이스케이프한다. Milvus 표현식 문법(`Plan.g4` 의 `SingleSChar` )이 작은따옴표 문자열 안에서 금지하는 문자가 정확히 이 네 가지다.
- 해당 문자가 없는 키는 기존과 동일한 표현식이 만들어진다.
- 헬퍼가 공통 베이스 클래스에 있어 sync / async 클라이언트 모두에 적용된다.
- 단위 테스트(핸들러에 전달되는 표현식 검증)와 Milvus Lite 통합 테스트(get / query / delete 왕복)를 추가.

### 검증

- 실패 테스트를 먼저 작성해 수정 전 실패(단위 4건, Lite 1건)를 확인한 뒤 수정.
- `pytest tests/unit` : 5261 passed, 3 skipped
- `pytest tests/integration/lite` : 5 passed
- `black --check` , `ruff check` 통과
- 독립 실행형 Milvus 서버에서는 실행하지 못했다. Milvus Lite 3.0 실행 결과와 Milvus 본체 문법 파일 확인으로 대체.

### 참고

- iterator 쪽 PK 표현식(`pymilvus/client/iterator/` )은 별도 이슈 #1960 범위라 건드리지 않았다.
- 이 저장소는 DCO 서명(`git commit -s` )이 필요하다.

