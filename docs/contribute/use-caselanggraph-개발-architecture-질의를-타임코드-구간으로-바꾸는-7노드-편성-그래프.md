---
id: use-caselanggraph-개발-architecture-질의를-타임코드-구간으로-바꾸는-7노드-편성-그래프
title: "[Use Case][LangGraph] 개발 Architecture — 질의를 타임코드 구간으로 바꾸는 7노드 편성 그래프"
sidebar_position: 9
slug: "9"
description: "질의를 타임코드 구간으로 바꾸는 7노드 편성 그래프"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

GitHub Discussion: [https://github.com/SceneMakerAI/docs-web/discussions/33](https://github.com/SceneMakerAI/docs-web/discussions/33)

[`agent-compose`](https://github.com/SceneMakerAI/agent-compose) 의 편성 그래프가 왜 지금 모양인지 정리한다. 설치는 [#32](https://github.com/SceneMakerAI/docs-web/discussions/32) 에 따로 있다.

야구 중계 영상과 "홈런만 3분" 같은 질의를 받아 클립 구간(시작·끝 초) 목록을 돌려준다. 문서 RAG 와 뼈대는 같은데 답이 문단이 아니라 타임코드라는 점이 다르다.

```text
load_inventory ─► parse_query ─► retrieve_evidence
  ─► select_clips ─► select_end_point ─► merge_overlap ─► trim_budget ─► END
```

| 노드 | LLM |  |
| --- | --- | --- |
| `load_inventory` |  | 영상의 구간 목록을 DB 에서 한 번 읽는다. 없으면 바로 `END` |
| `parse_query` | O | 질의를 필터(이닝·팀·라벨)와 검색어로 푼다 |
| `retrieve_evidence` | 임베딩 | 검색어로 Milvus 에서 증거를 찾는다 |
| `select_clips` | O | 규칙으로 후보를 좁히고 LLM 이 고른다 |
| `select_end_point` | O | 고른 구간의 시작·끝 좌표를 정한다 |
| `merge_overlap` |  | 한 플레이가 둘로 쪼개져 겹친 클립을 합친다 |
| `trim_budget` |  | 목표 분량에 맞춰 덜어낸다 |

#### LLM 에게 맡기지 않은 것들

LLM 은 고르기만 하고 검산은 코드가 한다. `parse_query` 에서 LLM 은 그 경기에 실제로 있는 어휘 안에서만 필터를 고르고, 어휘 밖 값은 파서가 버린다. `select_clips` 도 후보에 실제로 있는 구간 번호만 통과시킨다.

분량 계산은 아예 LLM 에게서 뺐다. "3분에 맞춰라" 같은 규칙을 프롬프트에 넣었더니 thinking 이 끝없이 길어졌다. 지금은 LLM 이 중요도 순으로 고르기만 하고, `trim_budget` 이 꼬리부터 잘라 낸다. 모자라도 채우지 않는다. 채우려고 선곡에 없던 구간을 끌어오기 시작하면 질의를 규칙이 덮어쓰게 된다.

출력 형식도 JSON 을 버리고 `키: 값` 줄 형식으로 바꿨다. Qwen 에서는 이쪽이 파싱이 덜 깨졌다.

#### 검색

증거는 해설(stt), 화면 캡션(shot), 하단 자막(etc) 세 종류인데 종류별로 따로 검색한다. 한 번에 섞으면 개수가 많은 shot·etc 가 상위를 다 차지해서 해설이 밀려난다.

"하이라이트"처럼 구체적인 장면 묘사가 없는 질의는 벡터 검색을 건너뛴다. 그런 단어로 검색하면 매칭이 엉망이 된다. 이럴 때 질의 원문으로 대신 검색하는 것도 하지 않고, 필터만으로 편성한다.

#### 조건을 어디까지 풀어 주나

후보가 0건이면 내용 쪽 조건(라벨·전광판)만 푼다. 이닝과 팀은 사용자가 직접 말한 조건이라 건드리지 않는다. 그래도 0건이면 빈 편성을 돌려준다. 없는 걸 있는 것처럼 채우는 것보다 낫다고 봤다.

#### 상태

DB·LLM 클라이언트는 상태에 넣지 않고 그래프를 만들 때 클로저로 넣어 준다. 구간 목록은 frozen dataclass 라 노드가 고칠 수 없고, 중간 결과는 다른 키에 새 객체로 담는다. reducer 는 쓰지 않고 전부 교체다.

노드는 `src/domains/baseball/` 아래에 있고 `src/pipeline/dispatch.py` 가 영상 카테고리로 도메인을 고른다. 지금은 야구 하나만 등록돼 있다.

코드는 `src/domains/baseball/graph/` 에 있다. 배선은 `build.py` , 상태는 `state.py` .

