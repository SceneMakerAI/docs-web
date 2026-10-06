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

월별 계획 7월 항목 "개발 Architecture 공유 (LangGraph)"에 해당하는 글입니다. 질의 기반 하이라이트 편성 API 인 [`agent-compose`](https://github.com/SceneMakerAI/agent-compose) 의 LangGraph 구조와, 그렇게 나눈 이유를 공유합니다.

### 하는 일

야구 중계 영상과 자연어 질의를 받아 클립 구간 목록(시작·끝 초)을 돌려줍니다. 문서 RAG 와 다른 점은 답이 문단이 아니라 타임코드 구간이라는 것입니다.

### 그래프

```text
load_inventory ─► parse_query ─► retrieve_evidence
  ─► select_clips ─► select_end_point ─► merge_overlap ─► trim_budget ─► END
```

| 노드 | LLM | 하는 일 |
| --- | --- | --- |
| `load_inventory` | 없음 | 그 영상의 구간 목록을 DB 에서 한 번 읽어 불변 스냅샷으로 둔다. 구간이 없으면 바로 `END` |
| `parse_query` | 사용 | 질의를 필터(이닝·팀·라벨)와 검색어로 해석한다 |
| `retrieve_evidence` | 임베딩 | 검색어를 임베딩해 Milvus 에서 증거를 찾는다 |
| `select_clips` | 사용 | 규칙으로 후보를 좁힌 뒤 LLM 이 구간을 고른다 |
| `select_end_point` | 사용 | 고른 구간의 시작·끝 좌표를 확정한다 |
| `merge_overlap` | 없음 | 한 플레이가 두 구간으로 쪼개져 겹친 클립을 합친다 |
| `trim_budget` | 없음 | 목표 분량(`budget_sec` )에 맞춰 덜어낸다 |

### 설계에서 정한 것

**1. LLM 은 제안하고 코드가 집행합니다.**

`parse_query` 에서 LLM 은 그 경기에 실제로 존재하는 어휘 중에서만 필터를 고르고, 파서는 어휘 밖 값을 버립니다. `select_clips` 에서도 후보에 실존하는 구간 번호만 통과시킵니다.

**2. LLM 출력은 JSON 이 아니라 `키: 값` 줄 형식입니다.**

Qwen 에서는 JSON 보다 줄 형식 파싱이 안정적이었습니다(실측).

**3. 증거 종류별로 따로 검색합니다.**

증거는 해설(stt)·화면 캡션(shot)·하단 자막(etc) 세 종류입니다. 한 번에 섞어 검색하면 개수가 많은 shot·etc 가 상위를 독식해 해설이 밀려납니다.

**4. 추상적인 질의는 벡터 검색을 생략합니다.**

"하이라이트"처럼 구체적 행위가 없는 질의로 검색하면 매칭이 무너집니다. 이때는 필터만으로 편성합니다. 질의 원문으로 대신 검색하지 않습니다.

**5. 사용자가 명시한 조건은 완화하지 않습니다.**

후보가 0건이면 내용 축(라벨·전광판)만 완화합니다. 이닝·팀은 하드 제약이라 그대로 두고, 그래도 0건이면 빈 편성을 돌려줍니다.

**6. 분량 계산은 LLM 에게 시키지 않습니다.**

분량 규칙을 프롬프트에 넣으면 thinking 이 폭주했습니다(실측). 분량 맞춤은 `trim_budget` 이 순수 계산으로 합니다. 선곡 중요도의 꼬리부터 버리고, 모자라도 채우지 않습니다.

**7. 상태에는 직렬화할 수 없는 것을 넣지 않습니다.**

DB·LLM 클라이언트는 그래프를 만들 때 클로저로 주입합니다. 구간 목록은 frozen dataclass 라 노드가 수정할 수 없고, 중간 산출은 별도 키에 새 객체로 담습니다. 상태 갱신은 reducer 없이 전부 교체입니다.

### 도메인 분리

노드는 `src/domains/baseball/` 아래에 있고, `src/pipeline/dispatch.py` 가 영상의 카테고리로 도메인 플로우를 고릅니다. 지금 등록된 도메인은 야구 하나입니다.

### 증적

- 소스: https://github.com/SceneMakerAI/agent-compose
  - 그래프 배선: `src/domains/baseball/graph/build.py`

  - 상태 스키마: `src/domains/baseball/graph/state.py`

  - 노드: `src/domains/baseball/graph/*.py`

- 설치 절차: 이 저장소의 "[Use Case][LangGraph] 설치 절차" 글
- LangGraph: https://github.com/langchain-ai/langgraph

