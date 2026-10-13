---
title: "[Use Case][LangGraph] Installation Procedure — Installing agent-compose (LangGraph 7-node configuration API) and registering it with systemd"
sidebar_position: 11
slug: "11"
description: "Installing agent-compose (LangGraph 7-node configuration API) and registering it with systemd"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

GitHub Discussion: [https://github.com/SceneMakerAI/docs-web/discussions/32](https://github.com/SceneMakerAI/docs-web/discussions/32)

Here are the steps for deploying [`agent-compose`](https://github.com/SceneMakerAI/agent-compose) to the new server. Since there is no README in the repo yet ([#1](https://github.com/SceneMakerAI/agent-compose/issues/1)), I’m writing it here first.

agent-compose is an API that takes natural language queries and returns a list of video clip segments; it’s built on LangGraph `StateGraph`.

#### Requirements

- Python 3.12 (`>=3.12,<3.13`), `uv`
- MariaDB, Milvus — You can run it using the `docker-compose.yml` from [`sm_db`](https://github.com/SceneMakerAI/sm_db)
- An OpenAI-compatible chat LLM server and embedding server

#### Installation

```bash
git clone https://github.com/SceneMakerAI/agent-compose.git
cd agent-compose
uv sync --frozen
cp .env.example .env
PYTHONPATH=src .venv/bin/python src/run.py
```

There are four required fields in `.env`. The rest use default values.

| Variable |  |
| --- | --- |
| `APP_PORT` | Listen port |
| `LLM_BASE_URL` | Chat server, `http://{host}:{port}/v1` |
| `EMBED_BASE_URL` | Embedding server, `http://{host}:{port}/v1` |
| `MILVUS_URI` | Milvus address |

The host and port are not accepted as CLI arguments but are read only from `.env`.

You can check whether they are running via `/healthz` (process status) and `/readyz` (including the DB, Milvus, and embedding server). Configurations are submitted via `POST /api/v1/compose` and results are queried via `GET /api/v1/compose?v_id=&search_id=`. The default limit for concurrent configurations is one; any excess is rejected.

One thing to note in advance: simply installing the system will not produce scheduling results. The intervals and evidence indexes must be present in the DB and Milvus, but the `agent-vision` responsible for creating them has not yet been released. In an empty environment, you can verify up to `/readyz`.

#### systemd

Use `deploy/agent-compose.service` as is.

```text
[Service]
Environment=PYTHONPATH=src
ExecStart=<installation path>/.venv/bin/python src/run.py
Restart=on-failure
RestartSec=3
TimeoutStopSec=30
```

Updates are handled by `deploy/update.sh`. Only when it differs from the remote `main` does the process proceed from `git reset --hard` → `uv sync --frozen` → reboot. `.env` is not tracked and remains as-is.

#### Things to Keep in Mind

If you omit `PYTHONPATH=src`, the module cannot be found. By intentionally omitting `[build-system]` in `pyproject.toml` and using `package = false` instead, `src/` becomes the direct import root.

The embedding server and model must be the same as those used during indexing. Indexing is handled by `agent-vision` and search is performed here; if the models differ, the search results are meaningless.

`/readyz` does not monitor the LLM. The GPU server is automatically shut down at night, and each time this happens, the entire service would flip to “not-ready,” so this feature was removed. The LLM is verified only through the connection test in the boot log.

The uvicorn shutdown timeout was set to 10 seconds(`timeout_graceful_shutdown=10`). Since the orchestration runs in the background, if the previous process’s work persists during a restart, it conflicts with the new process and the database.

The graph is currently recreated for each request. Once the configuration is finalized, I plan to change it so that it is compiled only once at startup.

