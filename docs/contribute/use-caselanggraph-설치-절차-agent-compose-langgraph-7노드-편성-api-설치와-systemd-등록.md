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

[`agent-compose`](https://github.com/SceneMakerAI/agent-compose) 를 새 서버에 올리는 순서다. 리포에 README 가 아직 없어서([#1](https://github.com/SceneMakerAI/agent-compose/issues/1) ) 여기에 먼저 적어 둔다.

agent-compose 는 자연어 질의를 받아 영상의 클립 구간 목록을 돌려주는 API 이고, 안쪽은 LangGraph `StateGraph` 다.

#### 준비물

- Python 3.12 (`>=3.12,<3.13` ), `uv`
- MariaDB, Milvus — [`sm_db`](https://github.com/SceneMakerAI/sm_db) 의 `docker-compose.yml` 로 띄울 수 있다
- OpenAI 호환 chat LLM 서버, 임베딩 서버

#### 설치

```bash
git clone https://github.com/SceneMakerAI/agent-compose.git
cd agent-compose
uv sync --frozen
cp .env.example .env
PYTHONPATH=src .venv/bin/python src/run.py
```

`.env` 에서 꼭 채워야 하는 건 네 개다. 나머지는 기본값으로 뜬다.

| 변수 |  |
| --- | --- |
| `APP_PORT` | 리슨 포트 |
| `LLM_BASE_URL` | chat 서버, `http://{host}:{port}/v1` |
| `EMBED_BASE_URL` | 임베딩 서버, `http://{host}:{port}/v1` |
| `MILVUS_URI` | Milvus 주소 |

호스트와 포트를 CLI 인자로 받지 않고 `.env` 에서만 읽는다.

떴는지는 `/healthz` (프로세스 생존)와 `/readyz` (DB·Milvus·임베딩 서버까지)로 본다. 편성은 `POST /api/v1/compose` 로 접수하고 `GET /api/v1/compose?v_id=&search_id=` 로 결과를 조회한다. 동시 편성은 기본 1건이고 넘치면 거절한다.

한 가지 미리 말해 두면, 설치만 해서는 편성 결과가 나오지 않는다. 구간과 증거 색인이 DB 와 Milvus 에 들어 있어야 하는데 그걸 만드는 `agent-vision` 이 아직 공개 전이다. 빈 환경에서는 `/readyz` 까지 확인할 수 있다.

#### systemd

`deploy/agent-compose.service` 를 그대로 쓴다.

```text
[Service]
Environment=PYTHONPATH=src
ExecStart=<설치경로>/.venv/bin/python src/run.py
Restart=on-failure
RestartSec=3
TimeoutStopSec=30
```

갱신은 `deploy/update.sh` 가 한다. 원격 `main` 과 다를 때만 `git reset --hard` → `uv sync --frozen` → 재기동. `.env` 는 추적 대상이 아니라 남는다.

#### 알아 두면 좋은 것

`PYTHONPATH=src` 를 빼먹으면 모듈을 못 찾는다. `pyproject.toml` 에 `[build-system]` 을 일부러 안 두고 `package = false` 로 해서, `src/` 가 그대로 import 루트다.

임베딩 서버와 모델은 색인할 때 쓴 것과 같아야 한다. 색인은 `agent-vision` 이 하고 검색은 여기서 하는데, 모델이 다르면 검색 결과가 의미가 없다.

`/readyz` 는 LLM 을 보지 않는다. GPU 서버를 밤에 자동으로 내리는데, 그때마다 서비스 전체가 not-ready 로 뒤집혀서 뺐다. LLM 은 부팅 로그의 접속 테스트로만 확인한다.

uvicorn 종료 대기는 10초로 묶었다(`timeout_graceful_shutdown=10` ). 편성이 백그라운드로 돌기 때문에, 재기동 때 이전 프로세스의 작업이 살아남으면 새 프로세스와 DB 를 두고 부딪힌다.

그래프는 지금 요청마다 새로 만든다. 구성이 굳으면 시작할 때 한 번만 컴파일하게 바꿀 생각이다.

