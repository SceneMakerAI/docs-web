#!/bin/bash
# EN 번역 daily cron — 하루 한 번 실행
# 마지막 번역 이후 변경된 docs/ 파일만 DeepL로 번역하여 docs_en/ 에 저장

set -e

cd /root/docs-web

set -a
source .env
set +a

git pull --rebase origin main --quiet

python3 scripts/translate_to_en.py

git config user.name "server-cron"
git config user.email "sbin@solbox.com"
git add docs_en/
if ! git diff --staged --quiet; then
  git commit -m "chore: EN 번역 업데이트 $(date +'%Y-%m-%d')"
  git push origin main
  echo "[$(date)] EN 번역 완료 — push됨"
else
  echo "[$(date)] EN 번역 완료 — 변경사항 없음"
fi
