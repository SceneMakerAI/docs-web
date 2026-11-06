#!/bin/bash
# Notion → docs/ 동기화 → git push
# 서버 crontab에서 6시간마다 실행 (0 */6 * * *)

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

# 커밋 안 한 로컬 변경을 stash로 치운다 — checkout·pull 보다 먼저.
# 이게 없으면 파일 하나가 pull --rebase 를 영구히 막아 동기화가 통째로 멈춘다
# (2026-07-21 ~ 08-11, 42회 연속 실패한 실제 사례).
# 추적 파일만 대상이며 stash에 보존되므로 작업은 유실되지 않는다: git stash list / git stash pop
if ! git diff --quiet HEAD; then
  echo "[$(date)] WARN: 커밋되지 않은 로컬 변경 감지 — stash 처리 (git stash list 로 복구 가능)"
  git diff --name-only HEAD
  if ! git stash push -m "server-sync auto-stash $(date +'%Y-%m-%d %H:%M')" --quiet; then
    echo "[$(date)] ERROR: stash 실패, 스킵"
    exit 1
  fi
fi

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
# DB ID 가 비어 있는 섹션은 건너뛴다. 예전처럼 `[ -n "$X" ] && … &` 로 띄우면
# 빈 변수의 백그라운드 작업이 상태 1 로 끝나 아래 wait 가 실패로 받고, 동기화 전체가 멈췄다.
pids=()
sync_db() {
  local db_id="$1" save_dir="$2"
  if [ -z "$db_id" ]; then
    echo "[$(date)] $save_dir: DB ID 없음, 스킵"
    return 0
  fi
  NOTION_DATABASE_ID="$db_id" SAVE_DIR="$save_dir" FETCH_MODE=ALL \
    python3 scripts/notion_to_md.py &
  pids+=($!)
}

sync_db "${NOTION_ABOUT:-}"        docs/about
sync_db "${NOTION_ARCHITECTURE:-}" docs/architecture
sync_db "${NOTION_DOCS:-}"         docs/guide
sync_db "${NOTION_INSTALL:-}"      docs/install
sync_db "${NOTION_POC:-}"          docs/poc
# 옛 이름: NOTION_POSTS·NOTION_RELEASE (2026-11-06 「릴리즈 노트」→「게시글」→「개발 노트」 개명)
sync_db "${NOTION_NOTES:-${NOTION_POSTS:-${NOTION_RELEASE:-}}}" docs/notes
sync_db "${NOTION_TEST:-}"         docs/test
sync_db "${NOTION_ACHIEVEMENT:-}"  docs/achievement

# 모든 동기화 완료 대기
failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || { echo "ERROR: pid $pid failed"; failed=1; }
done
[ $failed -ne 0 ] && exit 1

git add docs/ static/img/
if ! git diff --staged --quiet; then
  git -c user.name="server-cron" -c user.email="sbin@solbox.com" \
    commit -m "chore: Notion 동기화 $(date +'%Y-%m-%d %H:%M')"
  git push origin main
  echo "[$(date)] 동기화 완료 — 변경사항 push됨"
else
  echo "[$(date)] 동기화 완료 — 변경사항 없음"
fi
