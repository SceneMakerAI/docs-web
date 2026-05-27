#!/usr/bin/env bash
# 로컬 Notion 전체 동기화 스크립트
# 사용법: bash scripts/sync-local.sh [ALL|DAILY]
# .env 파일에서 환경변수를 읽어 모든 섹션을 병렬 동기화

set -e
FETCH_MODE=${1:-ALL}

# .env 로드
if [ -f .env ]; then
  set -a
  source .env
  set +a
else
  echo "ERROR: .env 파일이 없습니다"
  exit 1
fi

echo ">> Notion 동기화 시작 (FETCH_MODE=$FETCH_MODE)"
pids=()

# Blog
BLOG_DB="${NOTION_BLOG:-$NOTION_DATABASE_ID}"
if [ -n "$BLOG_DB" ]; then
  NOTION_DATABASE_ID="$BLOG_DB" SAVE_DIR=docs/blog FETCH_MODE="$FETCH_MODE" \
    python scripts/notion_to_md.py &
  pids+=($!)
fi

# Contribute
CONTRIBUTE_DB="${NOTION_CONTRIBUTE:-$NOTION_CONTRIBUTE_DATABASE_ID}"
if [ -n "$CONTRIBUTE_DB" ]; then
  NOTION_DATABASE_ID="$CONTRIBUTE_DB" SAVE_DIR=docs/contribute FETCH_MODE=ALL \
    python scripts/notion_to_md.py &
  pids+=($!)
fi

# Generic docs sections
if [ -n "$NOTION_ABOUT" ]; then
  NOTION_DATABASE_ID="$NOTION_ABOUT" SAVE_DIR=docs/about FETCH_MODE=ALL \
    python scripts/notion_to_md.py &
  pids+=($!)
fi

if [ -n "$NOTION_ARCHITECTURE" ]; then
  NOTION_DATABASE_ID="$NOTION_ARCHITECTURE" SAVE_DIR=docs/architecture FETCH_MODE=ALL \
    python scripts/notion_to_md.py &
  pids+=($!)
fi

if [ -n "$NOTION_POC" ]; then
  NOTION_DATABASE_ID="$NOTION_POC" SAVE_DIR=docs/poc FETCH_MODE=ALL \
    python scripts/notion_to_md.py &
  pids+=($!)
fi

if [ -n "$NOTION_DOCS" ]; then
  NOTION_DATABASE_ID="$NOTION_DOCS" SAVE_DIR=docs/guide FETCH_MODE=ALL \
    python scripts/notion_to_md.py &
  pids+=($!)
fi

if [ -n "$NOTION_RELEASE" ]; then
  NOTION_DATABASE_ID="$NOTION_RELEASE" SAVE_DIR=docs/release-notes FETCH_MODE=ALL \
    python scripts/notion_to_md.py &
  pids+=($!)
fi

if [ -n "$NOTION_INSTALL" ]; then
  NOTION_DATABASE_ID="$NOTION_INSTALL" SAVE_DIR=docs/install FETCH_MODE=ALL \
    python scripts/notion_to_md.py &
  pids+=($!)
fi

if [ ${#pids[@]} -eq 0 ]; then
  echo "동기화할 DB가 없습니다. .env 파일에 NOTION_* 변수를 설정하세요."
  exit 0
fi

failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || { echo "ERROR: pid $pid failed"; failed=1; }
done

echo ">> 동기화 완료"
exit $failed
