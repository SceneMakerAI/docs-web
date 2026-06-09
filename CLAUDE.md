
# CLAUDE.md — docs-web 작업 가이드

콘텐츠 사이트. 작업 대부분은 Markdown 추가·수정과 notion_to_md.py 스크립트 유지보수.

---

## 프로젝트 개요

**SceneMakerAI** — 오픈소스 AI(멀티모달 LLM)로 방송 콘텐츠를 재가공하는 솔박스 사내 프로젝트.

- 운영 URL: `https://doc.scenemaker.solbox.com`
- 스택: **Docusaurus 3.x** (React 19, TypeScript), 한국어 단일 로케일
- 파이프라인: Notion DB → 서버 crontab(30분, `server-sync.sh`) → GH Pages (`deploy.yml`)
- 참고: https://docusaurus.io/ko/docs

---

## 디렉토리 구조

```
docs-web/
├── docs/               # KR 원본 — Notion sync가 덮어씀 (수동 수정 금지)
│   ├── about/          # 프로젝트 소개 (NOTION_ABOUT)
│   ├── architecture/   # 아키텍처 (NOTION_ARCHITECTURE)
│   ├── contribute/     # 오픈소스 기여 (NOTION_CONTRIBUTE)
│   ├── guide/          # 문서 (NOTION_DOCS)
│   ├── install/        # 설치 (NOTION_INSTALL)
│   ├── poc/            # PoC (NOTION_POC) — 서브디렉토리 구조
│   └── release-notes/  # 릴리즈 노트 (NOTION_RELEASE)
├── blog/               # 블로그 (NOTION_BLOG) — Notion sync 대상
├── src/css/custom.css  # 전역 CSS — design 브랜치에서 수정
├── sidebars.ts         # 사이드바 ID↔dirName 매핑
├── docusaurus.config.ts
├── scripts/
│   ├── notion_to_md.py       # Notion → docs/·blog/ 변환 핵심 스크립트
│   ├── md_to_notion.py       # docs/ → Notion 역업로드 (md-to-notion.yml 용)
│   ├── server-sync.sh        # 서버 crontab 진입점 (pull→sync→commit→push)
│   ├── sync-local.sh         # 로컬에서 전체 섹션 수동 동기화
│   ├── sync-develop.sh       # main 콘텐츠를 develop으로 즉시 흡수 (로컬 수동 헬퍼)
│   ├── sync.sh               # blog·contribute 즉시 동기화 후 push
│   └── tests/                # notion_to_md.py·md_to_notion.py 단위 테스트
└── .github/workflows/
    ├── deploy.yml
    ├── md-to-notion.yml
    ├── merge-develop.yml
    ├── pr-build.yml
    └── sync-develop.yml
```

---

## 환경변수 (.env)

서버와 로컬 모두 프로젝트 루트 `.env` 에서 로드. GitHub Actions는 Secrets로 동일 값 등록.

| 변수 | 역할 |
|------|------|
| `NOTION_TOKEN` | Notion Integration 비밀 토큰 |
| `NOTION_ABOUT` | "프로젝트 소개" DB ID → `docs/about/` |
| `NOTION_ARCHITECTURE` | "아키텍처" DB ID → `docs/architecture/` |
| `NOTION_POC` | "PoC" DB ID → `docs/poc/` |
| `NOTION_DOCS` | "문서(가이드)" DB ID → `docs/guide/` |
| `NOTION_BLOG` | "블로그" DB ID → `blog/` |
| `NOTION_CONTRIBUTE` | "오픈소스 기여" DB ID → `docs/contribute/` |
| `NOTION_RELEASE` | "릴리즈 노트" DB ID → `docs/release-notes/` |
| `NOTION_INSTALL` | "설치" DB ID → `docs/install/` |

`server-sync.sh`는 `[ -n "$NOTION_XXX" ]` 조건으로 변수가 없으면 해당 DB sync를 건너뜀.

---

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
- **한 섹션 내 두 파일이 동일 slug를 가지면 사이드바 이중 하이라이트 버그 발생** — placeholder.md와 Notion sync 파일 slug 충돌 주의

---

## 자동화 구조

### 서버 crontab (콘텐츠 동기화 주체)

```
*/30 * * * * /root/docs-web/scripts/server-sync.sh >> /var/log/notion-sync.log 2>&1
```

`server-sync.sh` 실행 흐름: `git checkout main` → `git pull --rebase` → Notion 8개 DB 병렬 동기화 → `git commit` (커미터: `server-cron`) → `push` → `deploy.yml` 트리거

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
| `[skip-notion]` | `md-to-notion.yml` 스킵 |
| 커미터가 `server-cron` | `md-to-notion.yml` 스킵 |

**`[skip-notion]` 필수 상황:** Notion에서 내려받은 내용을 다시 올리면 무한 루프가 된다.
- 서버 crontab 커밋 → 자동 부여됨
- Claude가 수동 커밋할 때 `.notion-sync.json`·`docs/` Notion 원본 포함 시 → 반드시 추가
- `design → main` 등 머지 커밋이 `docs/` 파일 포함 시 → 머지 커밋 메시지에도 추가

---

## 브랜치 전략

> ⚠️ **핵심 규칙: `main`·`develop`에 코드를 직접 커밋하지 않는다.**
> feat 브랜치는 항상 작업 대상 브랜치(보통 `design`)에서 따고, 해당 브랜치로 머지한다.

### 브랜치 흐름

```
main (콘텐츠 자동화 전용)
 └─ design (장기 유지, UI·CSS·설정)
     └─ feat/<이름> (단위 작업, 완료 후 design으로 머지 → 삭제)
```

| 작업 유형 | 시작 브랜치 | 머지 대상 | dev 서버 포트 | 담당 |
|----------|------------|----------|--------------|------|
| 콘텐츠 (Notion 자동 동기화) | — | `main` 직접 커밋 *(자동화 전용)* | 3000 | 서버 crontab |
| **모든 코드 변경** | `design` | `feat/<이름>` → `design` → `develop` | 3002 | **Claude** |
| **main 반영** | — | `design` 또는 `develop` → `main` | 3000 | **사용자** |

**작업 흐름 (Claude 담당 부분):**

```bash
# 1. design 최신화
git checkout design && git merge origin/main --ff-only

# 2. feat 브랜치 생성 (design 기점)
git checkout -b feat/<이름>

# 3. 작업 후 커밋 ([skip-notion] 포함)
git commit -m "feat(...): ... [skip-notion]"

# 4. design으로 머지 후 feat 삭제
git checkout design && git merge feat/<이름> && git branch -d feat/<이름>
git push origin design

# 5. develop으로도 머지
git checkout develop && git merge design && git push origin develop

# → 이후 main 머지는 사용자가 직접 수행
```

**절대 금지:**
- `main` 또는 `develop`에 직접 커밋 ❌
- `feat` 브랜치를 `main`에 직접 머지 ❌ (design 경유 필수)
- Claude가 `main`에 머지·push ❌ (사용자 전용)

**design 브랜치:** 장기 유지 (삭제 금지). 작업 전 반드시 `git merge origin/main --ff-only` 실행.
**feat 브랜치:** design으로 머지 완료 후 로컬 삭제. 원격 push 불필요.

### crontab 충돌 처리

crontab이 30분마다 main에 push하므로 `non-fast-forward` 에러 시:

```bash
git pull --rebase origin main
# 충돌 시: .notion-sync.json 등 Notion 파일은 --theirs 선택
git add <충돌파일> && git rebase --continue
git push origin main
```

### design 브랜치 최신화

```bash
git checkout design
git merge origin/main --ff-only
git push origin design
```

---

## 자주 쓰는 명령어

| 명령어 | 용도 |
|--------|------|
| `npm start` | main 브랜치 dev 서버 (port 3000) |
| `npm run start:develop` | develop 브랜치 dev 서버 (port 3001) |
| `npm run start:design` | design 브랜치 dev 서버 (port 3002) |
| `npm run build` | 프로덕션 빌드 — **PR 전 통과 필수** |
| `npm run clear` | Docusaurus 캐시 정리 |
| `npm run typecheck` | TypeScript 검사 (빌드와 무관, IDE 보조) |

**dev 서버 404 / 브랜치 전환 후 캐시 꼬임:** `npm run clear` 후 재시작.

---

## 빌드 게이트

`onBrokenLinks: 'throw'` — CI에서 아래 시 빌드 실패:
- **깨진 내부 링크** — PR 전 `npm run build` 로컬 통과 필수
- **MDX 컴파일 오류** — frontmatter·JSX 문법 오류
- **사이드바 비어있음** — Notion DB에 콘텐츠가 없는 섹션은 `placeholder.md` 필수 (현재: `about/`, `release-notes/`)

---

## 사이드바 ID ↔ Notion DB 매핑

| 사이드바 ID | `docs/` 경로 | 환경변수 | Notion 콘텐츠 유무 |
|------------|-------------|----------|-------------------|
| `aboutSidebar` | `about/` | `NOTION_ABOUT` | ❌ placeholder.md 필요 |
| `architectureSidebar` | `architecture/` | `NOTION_ARCHITECTURE` | ✅ |
| `installSidebar` | `install/` | `NOTION_INSTALL` | ✅ |
| `pocSidebar` | `poc/` | `NOTION_POC` | ✅ |
| `docsSidebar` | `guide/` | `NOTION_DOCS` | ✅ |
| `contributeSidebar` | `contribute/` | `NOTION_CONTRIBUTE` | ✅ |
| `releaseNotesSidebar` | `release-notes/` | `NOTION_RELEASE` | ❌ placeholder.md 필요 |

블로그는 `sidebars.ts` 미포함 — navbar에 `{to: '/blog'}` 방식.

---

## notion_to_md.py 핵심 동작

### 번호 매기기 목록 (OL) 순서 번호

스크립트가 `numbered_list_item` 블록에 실제 순서 번호(1, 2, 3…)를 출력한다.
HTML `<ol start="N">`이 자동 생성되어 코드블록으로 분리된 OL도 연속 번호가 유지된다.

**카운터 리셋 기준 (`_OL_RESET_TYPES`):**

| 블록 타입 | 동작 |
|----------|------|
| `heading_1~4` | **리셋** (섹션 경계) |
| `table`, `toggle`, `column_list` | **리셋** |
| `code`, `paragraph`, `image`, `divider`, `quote`, `callout` | **유지** (split-OL 연속 번호) |
| `bulleted_list_item`, `to_do` | **유지** |

### HTML 엔티티 처리

Notion API가 `&amp;gt;` 형태로 이중 인코딩할 때 `extract_text_from_rich_text`에서 안정될 때까지 반복 unescape.

### 꺾쇠 이스케이프 (`escape_mdx_angle_brackets`)

`<한글>` 패턴을 `&lt;한글&gt;`으로 변환해 MDX JSX 파싱 오류 방지. 코드 블록·인라인 코드 안은 건드리지 않는다.

### child_page · link_to_page 블록

Notion 인라인 서브페이지(`child_page`)와 페이지 링크(`link_to_page`)를 `- [제목](https://www.notion.so/PAGE_ID)` 형태로 렌더링.

---

## 콘텐츠 추가 체크리스트

**새 Notion 섹션 추가:**
1. GitHub `secrets.NOTION_XXX` 등록 + `.env`에 추가
2. `scripts/server-sync.sh`에 DB 동기화 블록 추가
3. `docs/new-section/_category_.json` 생성
4. `sidebars.ts` + `docusaurus.config.ts` navbar 추가
5. Notion DB에 콘텐츠가 없으면 `placeholder.md` 즉시 생성 (빌드 실패 방지)

**수동 Notion 동기화 (단일 섹션):**
```bash
export $(grep -v '^#' .env | xargs)
NOTION_DATABASE_ID="$NOTION_POC" SAVE_DIR=docs/poc FETCH_MODE=ALL python3 scripts/notion_to_md.py
```

**특정 페이지 강제 재sync (캐시 무효화):**
```bash
python3 -c "
import json
with open('docs/poc/.notion-sync.json') as f:
    data = json.load(f)
for pid, info in data.items():
    if 'vision-bench' in str(info.get('file', '')):  # 조건 수정
        info['last_edited'] = ''
        info['content_hash'] = ''
with open('docs/poc/.notion-sync.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
"
# 이후 수동 sync 실행
```

---

## 하지 말 것

- `docusaurus.config.ts`의 `url`/`baseUrl`/`organizationName`/`projectName` 변경 금지
- `onBrokenLinks: 'throw'` → `'warn'`으로 낮추지 말 것
- `.docusaurus/`, `build/`, `node_modules/` 커밋 금지
- 부모 `index.md`에 `id:` 필드 추가 금지 — `_category_.json` link.id와 충돌
- `.docusaurus/` 캐시를 무시하고 빌드 통과로 간주하지 말 것 — `npm run clear` 후 재빌드
- `docs/` 파일 수동 편집 금지 — 다음 Notion sync에 덮어씌워짐. 영구 수정은 Notion 원본을 고치거나 `notion_to_md.py`를 수정할 것
- `scripts/tests/` 테스트 없이 `notion_to_md.py` 수정 금지 — `python3 -m pytest scripts/tests/` 통과 필수
- 한 섹션 내 두 파일에 동일 slug 부여 금지 — 사이드바 이중 하이라이트 버그 발생
