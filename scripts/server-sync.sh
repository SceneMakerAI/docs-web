#!/bin/bash
# Notion → docs/ 동기화 + DeepL EN 번역 → git push
# 서버 crontab에서 2분마다 실행

set -e

cd /root/docs-web

# 환경 변수 로드
set -a
source .env
set +a

# 최신 코드 pull
git pull --rebase origin main --quiet

# Notion DB 병렬 동기화
pids=()

[ -n "$NOTION_ABOUT" ] && \
  NOTION_DATABASE_ID="$NOTION_ABOUT" SAVE_DIR=docs/about FETCH_MODE=ALL \
  python3 scripts/notion_to_md.py & pids+=($!)

[ -n "$NOTION_ARCHITECTURE" ] && \
  NOTION_DATABASE_ID="$NOTION_ARCHITECTURE" SAVE_DIR=docs/architecture FETCH_MODE=ALL \
  python3 scripts/notion_to_md.py & pids+=($!)

[ -n "$NOTION_BLOG" ] && \
  NOTION_DATABASE_ID="$NOTION_BLOG" SAVE_DIR=docs/blog FETCH_MODE=ALL \
  python3 scripts/notion_to_md.py & pids+=($!)

[ -n "$NOTION_CONTRIBUTE" ] && \
  NOTION_DATABASE_ID="$NOTION_CONTRIBUTE" SAVE_DIR=docs/contribute FETCH_MODE=ALL \
  python3 scripts/notion_to_md.py & pids+=($!)

[ -n "$NOTION_DOCS" ] && \
  NOTION_DATABASE_ID="$NOTION_DOCS" SAVE_DIR=docs/guide FETCH_MODE=ALL \
  python3 scripts/notion_to_md.py & pids+=($!)

[ -n "$NOTION_INSTALL" ] && \
  NOTION_DATABASE_ID="$NOTION_INSTALL" SAVE_DIR=docs/install FETCH_MODE=ALL \
  python3 scripts/notion_to_md.py & pids+=($!)

[ -n "$NOTION_POC" ] && \
  NOTION_DATABASE_ID="$NOTION_POC" SAVE_DIR=docs/poc FETCH_MODE=ALL \
  python3 scripts/notion_to_md.py & pids+=($!)

[ -n "$NOTION_RELEASE" ] && \
  NOTION_DATABASE_ID="$NOTION_RELEASE" SAVE_DIR=docs/release-notes FETCH_MODE=ALL \
  python3 scripts/notion_to_md.py & pids+=($!)

# 모든 동기화 완료 대기
failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || { echo "ERROR: pid $pid failed"; failed=1; }
done
[ $failed -ne 0 ] && exit 1

# 변경된 KR 파일 즉시 EN 번역 (body 해시 캐시로 중복 호출 방지)
python3 scripts/translate_to_en.py

# 변경사항 커밋 & 푸시 (KR + EN 동시)
git config user.name "server-cron"
git config user.email "sbin@solbox.com"
git add docs/ docs_en/ static/img/
if ! git diff --staged --quiet; then
  git commit -m "chore: Notion 동기화 $(date +'%Y-%m-%d %H:%M')"
  git push origin main
  echo "[$(date)] 동기화 완료 — 변경사항 push됨"
else
  echo "[$(date)] 동기화 완료 — 변경사항 없음"
fi
