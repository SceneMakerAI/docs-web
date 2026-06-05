
# CLAUDE.md — docs-web 작업 가이드

콘텐츠 사이트. 작업 대부분은 Markdown 추가·수정.

---

## 프로젝트 개요

**SceneMakerAI** — 오픈소스 AI(멀티모달 LLM)로 방송 콘텐츠를 재가공하는 솔박스 사내 프로젝트.

- 운영 URL: `https://doc.scenemaker.solbox.com`
- 스택: **Docusaurus 3.10.1** (React 19, TypeScript 6), 한국어
- 파이프라인: Notion DB → 서버 crontab(30분, `server-sync.sh`) → GH Pages (`deploy.yml`)
- 참고: https://docusaurus.io/ko/docs

---

## 디렉토리 핵심 (비자명한 것만)

| 경로 | 역할 |
|------|------|
| `docs/` | KR 원본. **Notion 자동 동기화가 덮어씀** — 수동 수정은 다음 sync에 사라짐 |
| `scripts/notion_to_md.py` | Notion → docs/ · blog/ 변환 핵심 스크립트 |
| `scripts/server-sync.sh` | crontab 진입점 (pull→sync→commit→push) |

## URL/Slug 시스템

Notion 동기화 파일은 섹션 내 순서 기반 숫자 slug:

```
docs/install/qwen-3x-설치.md  (slug: "1")  →  /docs/install/1
docs/poc/vision-bench/_category_.json  (generated-index, slug: "/poc/vision-bench")  →  /docs/poc/vision-bench
docs/poc/vision-bench/child.md  (slug: "1")  →  /docs/poc/vision-bench/1
```

- **slug는 섹션 내 상대경로.** `"install/1"` 같은 절대경로 사용 금지
- `_category_.json`에 `"slug": "/"` 사용 금지 — Duplicate routes 발생
- `_category_.json` 서브디렉토리 버전은 `notion_to_md.py`가 자동 관리 — 직접 수정하면 다음 sync에 덮어씌워짐

---

## 자동화 구조

### 서버 crontab (콘텐츠 동기화 주체)

```
*/30 * * * * /root/docs-web/scripts/server-sync.sh >> /var/log/notion-sync.log 2>&1
```

`server-sync.sh` 실행 흐름: `git pull` → Notion 8개 DB 동기화 → `git commit [skip-notion]` → `push` → `deploy.yml` 트리거

로그 확인: `tail -f /var/log/notion-sync.log`

### GitHub Actions 워크플로우

| 파일 | 트리거 | 역할 |
|------|--------|------|
| `deploy.yml` | main push | npm build → GH Pages 배포 |
| `sync-develop.yml` | 매일 KST 03:00 | main 콘텐츠를 develop으로 머지 (`.notion-sync.json` 충돌 자동 해소) |
| `merge-develop.yml` | 매일 KST 11:00 | develop 코드 변경을 main으로 머지 (콘텐츠 디렉토리 제외, 빌드 게이트 포함) |
| `md-to-notion.yml` | `docs/**/*.md` push | 수동 편집된 md → Notion DB 역업로드 |
| `pr-build.yml` | main·develop PR | 프로덕션 빌드 검증 (깨진 링크·MDX 오류 차단) |

### 커밋 메시지 태그 규칙

| 태그 | 효과 |
|------|------|
| `[skip-notion]` | `md-to-notion.yml` 스킵 — 서버 crontab 커밋에 자동 부여 |
| 커미터가 `server-cron` | `md-to-notion.yml` 스킵 |

**`md-to-notion.yml`이 트리거되지 말아야 할 상황:** Notion에서 내려받은 내용을 다시 올리면 무한 루프. 서버 crontab은 `[skip-notion]`으로 이를 방지한다. Claude가 수동으로 커밋할 때도 Notion 동기화 내용(`.notion-sync.json`, `docs/` Notion 원본)을 커밋하면 `[skip-notion]` 필수.

---

## 브랜치 전략

> ⚠️ **핵심 규칙: `main`·`develop`에 코드를 직접 커밋하지 않는다.**
> 모든 코드 변경은 반드시 별도 브랜치에서 작업 후 merge한다.
> (예외: 서버 crontab의 Notion 자동 동기화는 `main`에 직접 커밋 — `[skip-notion]` 태그 포함)

| 작업 유형 | 브랜치 |
|----------|--------|
| 콘텐츠 변경 (Markdown, Notion 자동 동기화) | `main` 직접 커밋 *(자동화 전용)* |
| **UI 변경** (CSS·컴포넌트·디자인·레이아웃) | `design` 브랜치 → main merge |
| **기능 추가·버그픽스·설정 변경** | `feat/<이름>` 브랜치 → main merge 후 삭제 |

**수동 작업 시 절대 금지:**
- `git commit` 을 `main` 또는 `develop` 에서 직접 실행 ❌
- 작업 시작 전 항상 `git checkout feat/<이름>` 또는 `git checkout design` 먼저

**design 브랜치:** 장기 유지 (삭제 금지). 작업 전 반드시 `git rebase origin/main` 실행.
**feat 브랜치:** 작업 완료 후 main에 merge → 로컬·원격 브랜치 삭제.
Notion 자동 동기화가 main에 직접 커밋하므로 브랜치 작업 시작 전 rebase 생략 시 conflict 발생.

---

## 자주 쓰는 명령어

| 명령어 | 용도 |
|--------|------|
| `npm start` | main 브랜치 dev 서버 (port 3000) |
| `npm run start:develop` | develop 브랜치 dev 서버 (port 3001) |
| `npm run start:design` | design 브랜치 dev 서버 (port 3002) |
| `npm run build` | 프로덕션 빌드 (한국어) — **PR 전 통과 필수** |
| `npm run clear` | Docusaurus 캐시 정리 |
| `npm run typecheck` | TypeScript 검사 (빌드와 무관, IDE 보조) |

---

## 빌드 게이트

`onBrokenLinks: 'throw'` — CI에서 아래 시 빌드 실패:
- **깨진 내부 링크** — PR 전 `npm run build` 로컬 통과 필수
- **MDX 컴파일 오류** — frontmatter·JSX 문법 오류

---

## 사이드바 ID 매핑

| 사이드바 ID | `docs/` 경로 |
|------------|-------------|
| `aboutSidebar` | `about/` |
| `architectureSidebar` | `architecture/` |
| `installSidebar` | `install/` |
| `pocSidebar` | `poc/` |
| `docsSidebar` | `guide/` |
| `contributeSidebar` | `contribute/` |
| `releaseNotesSidebar` | `release-notes/` |

블로그는 `sidebars.ts` 미포함 — navbar에 `{to: '/blog'}` 방식.

---

## 콘텐츠 추가 체크리스트

**새 Notion 섹션 추가:**
1. GitHub `secrets.NOTION_XXX` 등록
2. `scripts/server-sync.sh`에 DB 동기화 블록 추가
3. `docs/new-section/_category_.json` 생성
4. `sidebars.ts` + `docusaurus.config.ts` navbar 추가
5. KR 플레이스홀더 `.md` 즉시 생성 (navbar 등록 직후 빌드 통과 필요)

**수동 새 문서 추가:**
1. `docs/section/filename.md` 생성 (`slug`, `sidebar_position`, `title` 포함)
2. `npm run build` 통과 확인 후 main push

**수동 Notion 동기화 (단일 섹션):**
```bash
NOTION_TOKEN=... NOTION_DATABASE_ID=... SAVE_DIR=docs/guide python3 scripts/notion_to_md.py
```

---

## 하지 말 것

- `docusaurus.config.ts`의 `url`/`baseUrl`/`organizationName`/`projectName` 변경 금지
- `onBrokenLinks: 'throw'` → `'warn'`으로 낮추지 말 것
- `.docusaurus/`, `build/`, `node_modules/` 커밋 금지
- 부모 `index.md`에 `id:` 필드 추가 금지 — `_category_.json` link.id와 충돌
- `.docusaurus/` 캐시를 무시하고 빌드 통과로 간주하지 말 것 — `npm run clear` 후 재빌드
