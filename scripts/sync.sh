#!/usr/bin/env bash
# Notion → blog/ 동기화 후 커밋·푸시해 사이트에 즉시 반영한다.
#
# 필수 환경변수:
#   NOTION_TOKEN          Notion Integration 토큰
#   NOTION_DATABASE_ID    동기화할 Notion DB ID
#
# 선택 환경변수:
#   FETCH_MODE            DAILY(기본) | ALL
#   BLOG_DEFAULT_AUTHOR   기본 저자 키 (기본: minsung)
#
# 사용 예:
#   NOTION_TOKEN=... NOTION_DATABASE_ID=... ./scripts/sync.sh
#   FETCH_MODE=ALL ./scripts/sync.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# .env 자동 로드 (blog/.env → .env 순서로 탐색)
for env_file in "blog/.env" ".env"; do
  if [[ -f "$env_file" ]]; then
    set -a
    source "$env_file"
    set +a
    break
  fi
done

if [[ -z "${NOTION_TOKEN:-}" || -z "${NOTION_DATABASE_ID:-}" ]]; then
  echo "오류: NOTION_TOKEN, NOTION_DATABASE_ID 환경변수가 필요합니다."
  echo "  .env 또는 blog/.env 에 두 값을 추가하거나, 환경변수로 직접 넘기세요."
  exit 1
fi

export FETCH_MODE="${FETCH_MODE:-DAILY}"
DATE="$(date +%Y-%m-%d)"

echo "=== Notion 동기화 시작 (FETCH_MODE=${FETCH_MODE}) ==="
python scripts/notion_to_blog.py

echo "=== git 커밋·푸시 ==="
git add blog/ static/img/blog/ 2>/dev/null || git add blog/

if git diff --cached --quiet; then
  echo "변경 사항 없음 — 푸시 생략"
  exit 0
fi

git commit -m "chore(blog): Notion 동기화 ${DATE}"
git push origin main

echo "=== 배포 트리거 완료 → https://doc.scenemaker.solbox.com/blog/ ==="
