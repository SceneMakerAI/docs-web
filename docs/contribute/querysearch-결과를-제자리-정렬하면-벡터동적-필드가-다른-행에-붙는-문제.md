---
id: querysearch-결과를-제자리-정렬하면-벡터동적-필드가-다른-행에-붙는-문제
title: "query·search 결과를 제자리 정렬하면 벡터·동적 필드가 다른 행에 붙는 문제"
sidebar_position: 31
slug: "31"
description: "pymilvus: query·search 결과를 제자리에서 정렬·역순·pop 하면 지연 디코딩 필드가 다른 행에 붙는 문제 보고"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-06
---

[https://github.com/milvus-io/pymilvus/issues/3824](https://github.com/milvus-io/pymilvus/issues/3824)

#### 문제

`MilvusClient.query()` 와 `MilvusClient.search()` 가 돌려주는 리스트는 일부 필드(벡터, JSON, 동적 필드)를 읽는 순간에 디코딩합니다. 이 디코딩이 "리스트 안에서의 위치" 를 기준으로 하고, 인덱스 접근과 반복에서만 일어납니다. 그래서 아직 읽지 않은 결과를 제자리에서 정렬하거나 뒤집거나 꺼내면(`sort` , `reverse` , `reversed()` , `pop` ) 필드가 다른 행에 붙거나 `None` 으로 남습니다. 예외는 나지 않습니다.

```text
query, 그대로         : [(1, 'clip-1', [1.0, 1.0]), (2, 'clip-2', [2.0, 2.0]), (3, 'clip-3', [3.0, 3.0])]
query, .sort(id 역순) : [(3, 'clip-1', [1.0, 1.0]), (2, 'clip-2', [2.0, 2.0]), (1, 'clip-3', [3.0, 3.0])]
query, reversed()     : [{'id': 3, 'vector': None}, {'id': 2, 'vector': None}, {'id': 1, 'vector': None}]
query, .pop()         : {'id': 3, 'vector': None}
```

정렬 뒤 id 3 이 id 1 의 제목과 벡터를 달고 나옵니다. `sorted(rows, ...)` 는 먼저 반복하기 때문에 안전합니다.

SceneMaker 는 Milvus 에 구간 증거를 색인하고 `agent-compose` 가 검색 결과를 시간순으로 다룹니다. 결과를 시간 필드로 `.sort()` 하면서 벡터나 동적 필드를 같이 읽는 코드가 있다면 조용히 잘못된 값을 쓰게 되는 종류의 문제라 보고했습니다. 현재 SceneMaker 코드가 실제로 이 경로를 타는지는 확인하지 않았습니다.

#### 원인

- `HybridExtraList.__getitem__` / `__iter__` (`pymilvus/client/types.py` ) 가 리스트 인덱스로 지연 필드를 채웁니다.
- `HybridHits.materialize()` (`pymilvus/client/search_result.py` ) 도 위치 기준입니다.
- `sort` , `reverse` , `__reversed__` , `pop` , `insert` , `del` , `copy` 는 `list` 의 기본 구현이라 위 경로를 거치지 않습니다.

같은 계열의 버그(#2986 마지막 행, #3136 음수 인덱스, #2862/#2866 반복 누락)가 접근 경로별로 하나씩 고쳐져 온 이력이 있습니다.

#### 재현

pymilvus `master` (9b1d5ad, 3.1.0rc90)와 Milvus Lite 3.2.1(로컬 파일), Python 3.12 에서 재현했습니다. 독립 실행형 Milvus 서버로는 확인하지 못했지만, 디코딩은 전부 클라이언트 쪽에서 일어납니다. 이슈 본문에 전체 스크립트를 넣었습니다.

#### 왜 PR 이 아니라 Issue 인가

수정안(위치에 의존하는 리스트 연산 전에 남은 행을 먼저 디코딩)과 단위 테스트는 준비돼 있습니다. 다만 비용 문제가 있습니다. `append` 나 `sort` 한 번에 전체 행을 디코딩하게 되므로, 모든 연산을 막을지 순서를 바꾸는 연산만 막을지는 메인테이너가 정할 일입니다. 방향을 먼저 물었습니다.

#### 중복 확인

`HybridExtraList` , `sort query result` , `query result reversed` , `lazy sort vector wrong row` , `in-place sort results` 로 열린·닫힌 이슈와 PR 을 검색했고 같은 보고는 없었습니다. 같은 날 다른 세션이 올린 #3823(VARCHAR 기본 키 이스케이프)은 다른 함수의 다른 문제입니다.

#### 결과

2026-10-06 등록했습니다. 메인테이너 답변 대기 중입니다.

