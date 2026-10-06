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

GitHub Discussion: [https://github.com/milvus-io/milvus/discussions/53969](https://github.com/milvus-io/milvus/discussions/53969)

계획서에는 Qdrant 라고 적었는데 실제로는 Milvus 를 쓰고 있다. 영상을 어떻게 잘라 넣었는지 적는다. 스키마는 [`sm_db`](https://github.com/SceneMakerAI/sm_db) , 검색 코드는 [`agent-compose`](https://github.com/SceneMakerAI/agent-compose) 에 있다.

#### 청크 단위

문서는 길이로 자르면 되지만 영상은 그럴 수가 없다. 그래서 시간 구간이 붙은 증거 한 건을 청크로 삼았다.

| `kind` |  |
| --- | --- |
| `stt` | 해설 대사 |
| `shot` | 화면 캡션 |
| `etc` | 하단 자막 OCR |

증거마다 `start_sec` , `end_sec` 가 있고 자기가 속한 경기 구간(`scene_stream_seq` )에 묶인다. 검색에 걸린 증거의 좌표가 그대로 영상을 자를 위치가 된다.

#### 컬렉션

[`milvus/sm_sport_baseball.json`](https://github.com/SceneMakerAI/sm_db/blob/HEAD/milvus/sm_sport_baseball.json) , Milvus 2.6.18.

- 필드 18개, 동적 필드는 껐다
- `vector` 는 2560차원, `Qwen3-Embedding-4B` , AUTOINDEX / COSINE
- 임베딩하는 건 `text` 하나뿐이다. 증거 원문이고 1024바이트에서 자른다
- 나머지는 전부 필터용이다: `v_id` , `stream_id` , `kind` , `inning` , `home_team` , `away_team` , `labels` , `board_tags` , `score` , `score_delta` …

필터용 필드는 구간의 값을 증거마다 복사해 넣은 것이다. 중복이긴 한데, 벡터 검색과 조건 필터를 질의 한 번에 끝내려면 이게 편하다.

원본은 MariaDB 이고 Milvus 는 거기서 뽑아낸 검색용 사본이다. 검색 결과는 `(v_id, stream_id, scene_stream_seq)` 로 원본 구간에 맞춘다. 통산 구간 번호(`scene_seq` )도 넣어 두긴 했지만 앞 청크를 다시 처리하면 값이 낡아서 매칭에는 안 쓴다.

#### 검색할 때

- 항상 `v_id` 로 좁힌다. 한 경기 안에서만 찾는다.
- `kind` 별로 따로 검색한다. 섞으면 `shot` ·`etc` 가 많아서 해설이 밀린다.
- 질의 임베딩은 색인과 같은 서버, 같은 모델이어야 한다.
- "하이라이트" 같은 추상적인 질의는 벡터 검색을 건너뛰고 필터만 쓴다.

#### 빈 환경 띄우기

```bash
git clone https://github.com/SceneMakerAI/sm_db.git && cd sm_db
cp .env.example .env
docker compose up -d --wait
pip install -r requirements.txt
python3 milvus/create.py
```

주의할 점이 몇 개 있다.

`t_code` (상태 코드표)가 비어 있으면 첫 INSERT 가 실패한다. 다른 테이블의 `status_code` 가 이 표를 FK 로 물고 있어서다. `mariadb/code.sql` 이 있으면 같이 올라가는데 이 파일이 지금 리포에 없다([sm_db#1](https://github.com/SceneMakerAI/sm_db/issues/1) ).

테이블은 볼륨이 비어 있는 첫 기동 때만 만들어진다. 다시 만들려면 `docker compose down -v` .

이 구성은 Milvus 를 컨테이너 하나(내장 etcd + 로컬 저장소)로 띄운다. 운영은 etcd 와 MinIO 를 따로 두지만 스키마는 같다.

