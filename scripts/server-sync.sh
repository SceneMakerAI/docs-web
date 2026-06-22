#!/bin/bash
# Notion → docs/ 동기화 → git push
# 서버 crontab에서 3시간마다 실행 (0 */3 * * *)

set -e

cd /root/docs-web

# 환경 변수 로드
set -a
. .env
set +a

# 잠금: 동시 실행 방지 (sync-develop.sh 와 충돌 방지)
LOCKFILE="/tmp/docs-web-sync.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { echo "[$(date)] 이미 다른 sync가 실행 중, 스킵"; exit 0; }

# 시작 브랜치 저장 — 스크립트 종료 시 복귀 (dev 서버 파일 보호)
ORIG_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "")
trap 'if [ -n "$ORIG_BRANCH" ] && [ "$ORIG_BRANCH" != "main" ]; then git checkout "$ORIG_BRANCH" --quiet 2>/dev/null || true; fi' EXIT

# 진행 중인 rebase 중단 (이전 실행 충돌로 잠긴 경우 해제)
git rebase --abort 2>/dev/null || true

# 항상 main에서 실행 보장 (실패 시 즉시 종료)
if ! git checkout main --quiet 2>/dev/null; then
  echo "[$(date)] ERROR: main 브랜치 checkout 실패, 스킵"
  exit 1
fi

# 최신 코드 pull (실패 시 rebase 중단 후 종료 — 다음 실행에서 재시도 가능)
if ! git pull --rebase origin main --quiet; then
  git rebase --abort 2>/dev/null || true
  echo "[$(date)] ERROR: git pull --rebase 실패, 스킵"
  exit 1
fi

# Notion DB 병렬 동기화
pids=()

[ -n "$NOTION_ABOUT" ] && \
  NOTION_DATABASE_ID="$NOTION_ABOUT" SAVE_DIR=docs/about FETCH_MODE=ALL \
  python3 scripts/notion_to_md.py & pids+=($!)

[ -n "$NOTION_ARCHITECTURE" ] && \
  NOTION_DATABASE_ID="$NOTION_ARCHITECTURE" SAVE_DIR=docs/architecture FETCH_MODE=ALL \
  python3 scripts/notion_to_md.py & pids+=($!)

[ -n "$NOTION_BLOG" ] && \
  NOTION_DATABASE_ID="$NOTION_BLOG" SAVE_DIR=blog FETCH_MODE=ALL \
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

git add docs/ blog/ static/img/
if ! git diff --staged --quiet; then
  git -c user.name="server-cron" -c user.email="sbin@solbox.com" \
    commit -m "chore: Notion 동기화 $(date +'%Y-%m-%d %H:%M')"
  git push origin main
  echo "[$(date)] 동기화 완료 — 변경사항 push됨"
else
  echo "[$(date)] 동기화 완료 — 변경사항 없음"
fi

# EN 번역 — 변경된 파일만 (hash cache로 미변경 스킵, DeepL quota 절약)
if [ -n "$DEEPL_API_KEY" ]; then
  python3 scripts/translate_to_en.py || echo "[$(date)] WARN: 번역 중 오류 발생 (배포는 계속)"
  git add i18n/en/ .notion-translate-hashes.json
  if ! git diff --staged --quiet; then
    git -c user.name="server-cron" -c user.email="sbin@solbox.com" \
      commit -m "chore: EN 번역 자동 동기화 $(date +'%Y-%m-%d %H:%M')"
    git push origin main
    echo "[$(date)] EN 번역 완료 — 변경사항 push됨"
  else
    echo "[$(date)] EN 번역 완료 — 변경사항 없음"
  fi
fi
