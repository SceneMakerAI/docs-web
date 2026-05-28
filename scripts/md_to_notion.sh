#!/usr/bin/env bash
# docs/ 미커밋 변경 감지 → 자동 commit + push → md_to_notion.py 실행
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOCKFILE="/tmp/md-to-notion.lock"

exec 9>"$LOCKFILE"
if ! flock -n 9; then
  echo "[md_to_notion] 다른 git 작업 중 — 스킵"
  exit 0
fi

cd "$REPO_DIR"

git add docs/ docs_en/ static/img/

if git diff --staged --quiet; then
  echo "[md_to_notion] 변경 없음 — 스킵"
  exit 0
fi

git commit -m "docs: 수동 편집 자동 커밋 $(date +'%Y-%m-%d %H:%M')"
git push origin feature/sbin
echo "[md_to_notion] push 완료"
