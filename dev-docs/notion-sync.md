# Notion 동기화

> [CLAUDE.md](../CLAUDE.md) 허브에서 분리한 상세 문서. 서버 crontab 운영 방식 · DB 매핑 · 동기화 내부 로직.

## 실제 운영 방식 — 서버 crontab

GitHub Actions가 아닌 **서버에서 직접 crontab으로 2분마다** 실행한다.

```
*/2 * * * * /root/docs-web/scripts/server-sync.sh >> /var/log/notion-sync.log 2>&1
```

**`scripts/server-sync.sh` 흐름:**

1. `git pull --rebase origin main` — 원격 최신 코드 반영
2. 8개 Notion DB 병렬 동기화 (`notion_to_docs_generic.py`, `FETCH_MODE=ALL`)
3. `translate_to_en.py` — 변경된 KR 파일 DeepL 번역 → `docs_en/` 저장
4. 변경사항 있으면 `git commit + push` → `deploy.yml` 트리거 → GH Pages 배포

환경변수는 `/root/docs-web/.env` 파일에서 로드한다 (레포에 포함되지 않음).

로그 확인:
```bash
tail -f /var/log/notion-sync.log
```

> **GitHub Actions `notion-sync.yml`** 은 수동 실행용 백업 (`workflow_dispatch`). 평소에는 서버 crontab이 실제 운영을 담당한다.

---

## DB ↔ 디렉토리 매핑

| `.env` 변수 | 저장 경로 |
|------------|-----------|
| `NOTION_ABOUT` | `docs/about/` |
| `NOTION_ARCHITECTURE` | `docs/architecture/` |
| `NOTION_BLOG` | `docs/blog/` |
| `NOTION_CONTRIBUTE` | `docs/contribute/` |
| `NOTION_DOCS` | `docs/guide/` |
| `NOTION_INSTALL` | `docs/install/` |
| `NOTION_POC` | `docs/poc/` |
| `NOTION_RELEASE` | `docs/release-notes/` |
| `NOTION_TOKEN` | API 인증 토큰 |
| `DEEPL_API_KEY` | DeepL 번역 API 키 |

## 동기화 내부 로직 (`notion_to_docs_generic.py`)

Notion "하위 항목" relation을 읽어 자동으로 계층 구조를 결정한다.

- 하위 항목 없는 페이지 → `docs/{section}/{slug}.md` (평면)
- 하위 항목 있는 부모 → `docs/{section}/{slug}/index.md` + `_category_.json` 자동 생성
- 자식 페이지 → `docs/{section}/{parent-slug}/{child-slug}.md`

| 환경변수 | 기본값 | 설명 |
|---------|--------|------|
| `NOTION_PROPERTY_SUBITEM` | `하위 항목` | Sub-items relation 속성명 |
| `NOTION_PROPERTY_PARENT` | `상위 항목` | Parent item relation 속성명 |

## 수동 동기화 (단일 섹션)

```bash
NOTION_TOKEN=... NOTION_DATABASE_ID=... SAVE_DIR=docs/guide python3 scripts/notion_to_docs_generic.py
```
