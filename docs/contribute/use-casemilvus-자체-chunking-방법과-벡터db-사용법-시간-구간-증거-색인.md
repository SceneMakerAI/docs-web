---
id: use-casemilvus-자체-chunking-방법과-벡터db-사용법-시간-구간-증거-색인
title: "[Use Case][Milvus] 자체 Chunking 방법과 벡터DB 사용법 — 시간 구간 증거 색인"
sidebar_position: 6
slug: "6"
description: "시간 구간 증거 색인"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

GitHub Discussion: [https://github.com/SceneMakerAI/docs-web/discussions/36](https://github.com/SceneMakerAI/docs-web/discussions/36)

월별 계획 9월 항목 "자체 Chunking 방법과 벡터DB 사용법 공유"에 해당하는 글입니다. 계획서에는 Qdrant 로 적었지만 실제 구현은 **Milvus** 로 했습니다. 그 구성을 [`sm_db`](https://github.com/SceneMakerAI/sm_db) 와 [`agent-compose`](https://github.com/SceneMakerAI/agent-compose) 기준으로 공유합니다.

### 무엇을 청크로 삼는가

문서 RAG 는 글을 일정 길이로 자릅니다. 영상은 그렇게 자를 수 없어서, **시간 구간을 가진 증거 한 건** 을 청크 단위로 삼았습니다. 증거는 세 종류입니다.

| `kind` | 내용 |
| --- | --- |
| `stt` | 해설 대사 |
| `shot` | 화면 캡션 |
| `etc` | 하단 자막 OCR |

각 증거는 `start_sec` , `end_sec` 를 갖고, 자신이 속한 경기 구간(`scene_stream_seq` )에 귀속됩니다. 검색 결과가 곧 영상을 자를 좌표가 됩니다.

### 컬렉션 정의

`milvus/sm_sport_baseball.json` (Milvus 2.6.18)

- 필드 18개, 동적 필드 사용 안 함
- `vector` : 2560 차원, `Qwen3-Embedding-4B` , AUTOINDEX / COSINE
- **임베딩하는 것은 `text` 필드 하나뿐입니다** (증거 원문, 1024 바이트에서 절단)
- 나머지는 필터용 메타데이터입니다: `v_id` , `stream_id` , `kind` , `inning` , `home_team` , `away_team` , `labels` , `board_tags` , `score` , `score_delta` 등

메타데이터는 귀속 구간의 값을 증거마다 복사해 둔 것입니다. 벡터 검색과 조건 필터를 한 번의 질의로 처리하기 위해서입니다.

### 관계형 DB 와의 관계

원본은 MariaDB 이고 Milvus 는 검색용 파생본입니다. 검색 히트는 `(v_id, stream_id, scene_stream_seq)` 로 원장의 구간에 매칭합니다.

통산 구간 번호(`scene_seq` )도 함께 저장하지만, 앞 청크를 재처리하면 값이 낡을 수 있어 정본 매칭에는 쓰지 않습니다.

### 검색할 때 정한 것

- **항상 `v_id` 로 범위를 좁힙니다.** 한 경기 안에서만 찾습니다.
- **`kind` 별로 따로 검색합니다.** 한 번에 섞으면 개수가 많은 `shot` ·`etc` 가 상위를 독식해 해설(`stt` )이 밀려납니다.
- **질의 임베딩은 색인과 같은 서버·같은 모델을 써야 합니다.** 색인은 `agent-vision` 이, 검색은 `agent-compose` 가 합니다.
- **추상적인 질의는 벡터 검색을 생략합니다.** "하이라이트" 같은 말로 검색하면 매칭이 무너져서, 이때는 메타데이터 필터만 씁니다.

### 빈 환경 만들기

```bash
git clone https://github.com/SceneMakerAI/sm_db.git && cd sm_db
cp .env.example .env            # MARIADB_ROOT_PASSWORD 채우기
docker compose up -d --wait     # MariaDB 12.3 + Milvus 2.6.18
pip install -r requirements.txt
python3 milvus/create.py        # Milvus DB 와 빈 컬렉션 생성
```

### 막혔던 지점

- 이 구성은 Milvus 를 한 컨테이너(내장 etcd + 로컬 저장소)로 띄웁니다. 운영은 etcd 와 MinIO 를 따로 둡니다. 스키마에는 차이가 없습니다.
- 상태 코드표(`t_code` )가 비어 있으면 첫 INSERT 가 실패합니다. 다른 테이블의 `status_code` 가 이 표를 FK 로 참조하기 때문입니다. `mariadb/code.sql` 이 있으면 함께 적재되지만, 이 파일은 현재 리포에 들어 있지 않아 직접 채워야 합니다.
- 테이블은 볼륨이 비어 있는 첫 기동 때만 만들어집니다. 다시 만들려면 `docker compose down -v` .

### 증적

- 스키마: https://github.com/SceneMakerAI/sm_db
  - `milvus/sm_sport_baseball.json` , `milvus/create.py` , `mariadb/schema.sql`

- 검색 코드: https://github.com/SceneMakerAI/agent-compose (`src/domains/baseball/graph/retrieve_evidence.py` )
- Milvus: https://github.com/milvus-io/milvus

