---
title: "[Use Case][Milvus] Custom Chunking Methods and How to Use Vector Databases — Time-Interval Evidence Indexing"
sidebar_position: 6
slug: "6"
description: "Time Interval Evidence Index"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

GitHub Discussion: [https://github.com/milvus-io/milvus/discussions/53969](https://github.com/milvus-io/milvus/discussions/53969)

The proposal mentioned “Qdrant,” but we’re actually using Milvus. I’ll explain how we cut and inserted the video. The schema is at [`sm_db`](https://github.com/SceneMakerAI/sm_db), and the search code is at [`agent-compose`](https://github.com/SceneMakerAI/agent-compose).

#### Chunk-Based Approach

While documents can be split by length, videos cannot. Therefore, I treated each piece of evidence with a time interval as a single chunk.

| `kind` |  |
| --- | --- |
| `stt` | Commentary |
| `shot` | Screen Caption |
| `etc` | Bottom Caption OCR |

Each piece of evidence has `start_sec` and `end_sec` and is grouped under the corresponding game segment (`scene_stream_seq`). The coordinates of the evidence found in a search become the exact positions where the video is split.

#### Collection

[`milvus/sm_sport_baseball.json`](https://github.com/SceneMakerAI/sm_db/blob/HEAD/milvus/sm_sport_baseball.json), Milvus 2.6.18.

- 18 fields; dynamic fields are disabled
- `vector` is 2560-dimensional; `Qwen3-Embedding-4B`, AUTOINDEX / COSINE
- Only `text` is used for embedding. It is the original evidence text, cropped at 1024 bytes
- The rest are all for filtering: `v_id`, `stream_id`, `kind`, `inning`, `home_team`, `away_team`, `labels`, `board_tags`, `score`, `score_delta` …

The fields used for filtering are copies of the segment values from each evidence record. Although this creates redundancy, it’s convenient for completing both vector search and conditional filtering in a single query.

The original data is from MariaDB, and Milvus is a search-optimized copy extracted from it. Search results are aligned with the original intervals using `(v_id, stream_id, scene_stream_seq)`. Although the cumulative interval number (`scene_seq`) is included, it is not used for matching because the values become outdated when the preceding chunk is reprocessed.

#### When searching

- Always narrow the search to `v_id`. Search only within a single game.
- Search separately by `kind`. If mixed, there are too many `shot` and `etc`, which slows down the commentary.
- The query embedding must be on the same server and use the same model as the index.
- For abstract queries like “highlights,” skip vector search and use only the filter.

#### Launching an Empty Environment

```bash
git clone https://github.com/SceneMakerAI/sm_db.git && cd sm_db
cp .env.example .env
docker compose up -d --wait
pip install -r requirements.txt
python3 milvus/create.py
```

There are a few points to note.

If `t_code` (status code table) is empty, the first INSERT will fail. This is because `status_code` in another table references this table via a foreign key. If `mariadb/code.sql` exists, it will be loaded along with the volume, but this file is currently missing from the repository ([sm_db#1](https://github.com/SceneMakerAI/sm_db/issues/1)).

The table is created only during the first startup when the volume is empty. To recreate it, use `docker compose down -v`.

This configuration runs Milvus in a single container (with built-in etcd + local storage). While etcd and MinIO are kept separate in production, the schema remains the same.

