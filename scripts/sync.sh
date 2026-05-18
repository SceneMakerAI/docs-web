#!/usr/bin/env bash
# blog/ 변경분을 커밋·푸시해 GitHub Actions 배포를 트리거한다.
# 사용: ./scripts/sync.sh [커밋 메시지 (선택)]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

DATE="$(date +%Y-%m-%d)"
MSG="${1:-"chore(blog): 동기화 ${DATE}"}"

git add blog/ static/img/

if git diff --cached --quiet; then
  echo "변경 사항 없음 — 푸시 생략"
  exit 0
fi

git commit -m "$MSG"
git push origin main

echo "배포 트리거 완료 → https://doc.scenemaker.solbox.com/blog/"
