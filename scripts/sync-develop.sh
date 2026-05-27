#!/usr/bin/env bash
# main 의 최신 콘텐츠(서버 crontab 이 쌓은 docs/·docs_en/·static/img/)를
# develop 으로 즉시 흡수하는 로컬 수동 헬퍼.
#
# 정기 자동 흡수는 .github/workflows/sync-develop.yml 이 매일(KST 03:00) 수행한다.
# 이 스크립트는 develop 에서 작업하기 직전 "지금 당장" 최신화하고 싶을 때 쓴다.
# 충돌이 나면 머지가 중단된다(set -e) — 수동 해결 후 다시 실행하면 된다.
set -euo pipefail

cd "$(dirname "$0")/.."

echo ">> main → develop 흡수 시작"
git fetch origin

git checkout develop
git merge --ff-only origin/develop   # 로컬 develop 을 origin 최신으로 (로컬이 앞서 있으면 중단)
git merge origin/main --no-edit      # main 콘텐츠 흡수 (충돌 시 중단)
git push origin develop

echo ">> 완료: develop 이 main 의 최신 콘텐츠를 포함합니다"
