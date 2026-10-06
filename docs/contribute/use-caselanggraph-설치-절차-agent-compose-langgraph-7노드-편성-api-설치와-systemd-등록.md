---
id: use-caselanggraph-설치-절차-agent-compose-langgraph-7노드-편성-api-설치와-systemd-등록
title: "[Use Case][LangGraph] 설치 절차 — agent-compose (LangGraph 7노드 편성 API) 설치와 systemd 등록"
sidebar_position: 11
slug: "11"
description: "agent-compose (LangGraph 7노드 편성 API) 설치와 systemd 등록"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

GitHub Discussion: [https://github.com/SceneMakerAI/docs-web/discussions/32](https://github.com/SceneMakerAI/docs-web/discussions/32)

월별 계획 6월 항목 "Use Case Report 설치 절차 (LangGraph)"에 해당하는 글입니다. SceneMaker 에서 LangGraph 를 쓰는 곳은 질의 기반 하이라이트 편성 API 인 [`agent-compose`](https://github.com/SceneMakerAI/agent-compose) 입니다. 이 리포를 기준으로 설치 절차와, 운영하면서 정한 설정을 공유합니다.

### 무엇을 하는 서비스인가

자연어 질의를 받아 영상의 클립 구간 목록을 돌려줍니다. LangGraph `StateGraph` 로 7개 노드를 잇습니다.

```text
load_inventory ─► parse_query ─► retrieve_evidence
  ─► select_clips ─► select_end_point ─► merge_overlap ─► trim_budget ─► END
```

`load_inventory` 뒤에는 조건 분기가 있어, 분석된 장면이 없으면 바로 `END` 로 갑니다.

### 환경

| 항목 | 값 |
| --- | --- |
| Python | 3.12 (`>=3.12,<3.13` ) |
| 패키지 관리 | `uv` (`uv.lock` 고정) |
| 주요 의존성 | `langgraph>=0.2` , `fastapi>=0.115` , `pymilvus>=2.5` , `asyncmy` , `httpx` |
| 외부 자원 | MariaDB, Milvus, OpenAI 호환 chat LLM 서버, 임베딩 서버 |

MariaDB 와 Milvus 는 [`sm_db`](https://github.com/SceneMakerAI/sm_db) 의 `docker-compose.yml` 로 띄울 수 있습니다.

### 설치 절차

```bash
git clone https://github.com/SceneMakerAI/agent-compose.git
cd agent-compose

uv sync --frozen              # uv.lock 그대로 재현
cp .env.example .env          # DB · LLM · 임베딩 · Milvus 접속 정보를 채운다

PYTHONPATH=src .venv/bin/python src/run.py
```

바인딩 호스트와 포트는 CLI 인자가 아니라 `.env` 의 `APP_HOST` , `APP_PORT` 에서 읽습니다.

`.env` 에서 반드시 채워야 하는 값은 네 개입니다. 나머지는 기본값이 있습니다.

| 변수 | 내용 |
| --- | --- |
| `APP_PORT` | API 리슨 포트 |
| `LLM_BASE_URL` | OpenAI 호환 chat 서버 (`http://{host}:{port}/v1` ) |
| `EMBED_BASE_URL` | 임베딩 서버 (`http://{host}:{port}/v1` ) |
| `MILVUS_URI` | Milvus 주소 |

상태 확인용 라우트는 두 개입니다.

- `/healthz` : 프로세스 생존만 확인
- `/readyz` : DB · Milvus · 임베딩 서버까지 확인. 하나라도 준비되지 않으면 503

편성 API 는 `POST /api/v1/compose` 로 접수하고 `GET /api/v1/compose?v_id=&search_id=` 로 결과를 조회합니다. 동시 편성 상한은 기본 1건이고(`COMPOSE_CONCURRENCY` ), 넘치는 요청은 거절합니다.

> 설치만으로는 편성 결과가 나오지 않습니다. 영상 분석 결과(구간·증거 색인)가 DB 와 Milvus 에 있어야 하는데, 이 데이터를 만드는 `agent-vision` 은 아직 공개 전입니다. 빈 환경에서는 `/readyz` 까지 확인할 수 있습니다.

### systemd 등록

`deploy/agent-compose.service` 를 그대로 씁니다.

```text
[Service]
Environment=PYTHONPATH=src
ExecStart=<설치경로>/.venv/bin/python src/run.py
Restart=on-failure
RestartSec=3
TimeoutStopSec=30
```

이후 갱신은 `deploy/update.sh` 가 맡습니다. 원격 `main` 과 다를 때만 `git reset --hard` → `uv sync --frozen` → 재기동하고, `.env` 는 추적 대상이 아니라 보존됩니다.

### 설치하면서 정한 것

**1. 패키지로 빌드하지 않습니다.** `pyproject.toml` 에 `[build-system]` 을 일부러 두지 않고 `[tool.uv] package = false` 로 했습니다. `src/` 가 import 루트라서 실행할 때 `PYTHONPATH=src` 가 반드시 필요합니다.

**2. 임베딩 서버와 모델은 색인 쪽과 같아야 합니다.** 증거 색인은 `agent-vision` 이 Milvus 에 씁니다. 질의 임베딩이 다른 모델이면 검색 결과가 무의미해지므로 `.env` 의 `EMBED_BASE_URL` , `EMBED_MODEL` 을 색인과 맞춥니다.

**3. `/readyz` 에서 LLM 은 뺐습니다.** GPU 서버가 야간에 자동 중지되면 서비스 전체가 not-ready 로 뒤집히는 오탐이 생겨서입니다. LLM 은 부팅 로그에서만 확인합니다.

**4. 종료 대기 시간에 상한을 뒀습니다.** uvicorn `timeout_graceful_shutdown=10` . 편성은 백그라운드로 도는데, 재기동 때 이전 프로세스의 작업이 살아남으면 새 프로세스와 DB 를 두고 경합합니다.

**5. 그래프는 지금 요청마다 빌드합니다.** 구성이 굳으면 앱 시작 시 한 번만 컴파일하도록 옮길 예정입니다.

### 증적

- 소스: https://github.com/SceneMakerAI/agent-compose
  - 그래프 배선: `src/domains/baseball/graph/build.py`

  - 배포: `deploy/agent-compose.service` , `deploy/update.sh`

- DB · Milvus 구성: https://github.com/SceneMakerAI/sm_db
- LangGraph: https://github.com/langchain-ai/langgraph

설치하다 막히는 부분이 있으면 댓글로 알려 주세요.

