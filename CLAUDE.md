# CLAUDE.md — docs-web 작업 가이드

콘텐츠 사이트. 작업 대부분은 Markdown 추가·수정과 notion_to_md.py 스크립트 유지보수.

---

## 프로젝트 개요

**SceneMakerAI** — 오픈소스 AI(멀티모달 LLM)로 방송 콘텐츠를 재가공하는 솔박스 사내 프로젝트.

- 운영 URL: `https://doc.scenemaker.solbox.com`
- 스택: **Docusaurus 3.x** (React 19, TypeScript), **한국어(기본)·영어 이중 로케일**
- 파이프라인: Notion DB → 서버 crontab(1시간, `server-sync.sh`) → GH Pages (`deploy.yml`)
- 번역 파이프라인: `docs/`·`blog/` KR → DeepL → `i18n/en/` EN (매월 1일, `monthly-translate.yml`)
- 참고: [https://docusaurus.io/ko/docs](https://docusaurus.io/ko/docs)

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
├── i18n/en/            # EN 번역 파일 — translate_to_en.py가 자동 생성 (수동 편집 금지)
│   ├── docusaurus-theme-classic/
│   │   ├── navbar.json         # 네비바 항목 EN 번역
│   │   └── footer.json         # 푸터 항목 EN 번역
│   ├── docusaurus-plugin-content-docs/
│   │   ├── current.json        # 사이드바 카테고리 라벨 EN 번역
│   │   └── current/            # docs/ 미러 — 번역된 .md 파일들
│   └── docusaurus-plugin-content-blog/
│       └── (번역된 블로그 .md 파일들)
├── .notion-translate-hashes.json  # EN 번역 해시 캐시 — 삭제 금지 (CI 재번역 방지)
├── src/css/custom.css  # 전역 CSS — design 브랜치에서 수정
├── sidebars.ts         # 사이드바 ID↔dirName 매핑
├── docusaurus.config.ts
├── scripts/
│   ├── notion_to_md.py       # Notion → docs/·blog/ 변환 핵심 스크립트
│   ├── translate_to_en.py    # docs/·blog/ KR → DeepL → i18n/en/ EN 번역 스크립트
│   ├── md_to_notion.py       # docs/ → Notion 역업로드 (md-to-notion.yml 용)
│   ├── server-sync.sh        # 서버 crontab 진입점 (pull→sync→commit→push)
│   ├── sync-local.sh         # 로컬에서 전체 섹션 수동 동기화
│   ├── sync-develop.sh       # main 콘텐츠를 develop으로 즉시 흡수 (로컬 수동 헬퍼)
│   ├── sync.sh               # blog·contribute 즉시 동기화 후 push
│   └── tests/                # notion_to_md.py·md_to_notion.py 단위 테스트
└── .github/workflows/
    ├── deploy.yml
    ├── monthly-translate.yml  # 매월 1일 EN 번역 자동 실행
    ├── md-to-notion.yml
    ├── merge-develop.yml
    ├── pr-build.yml
    └── sync-develop.yml
```

---

## 환경변수 (.env)

서버와 로컬 모두 프로젝트 루트 `.env` 에서 로드. GitHub Actions는 Secrets로 동일 값 등록.

| 변수                    | 역할                                                                       |
| --------------------- | ------------------------------------------------------------------------ |
| `NOTION_TOKEN`        | Notion Integration 비밀 토큰                                                 |
| `NOTION_ABOUT`        | "프로젝트 소개" DB ID → `docs/about/`                                          |
| `NOTION_ARCHITECTURE` | "아키텍처" DB ID → `docs/architecture/`                                      |
| `NOTION_POC`          | "PoC" DB ID → `docs/poc/`                                                |
| `NOTION_DOCS`         | "문서(가이드)" DB ID → `docs/guide/`                                          |
| `NOTION_BLOG`         | "블로그" DB ID → `blog/`                                                    |
| `NOTION_CONTRIBUTE`   | "오픈소스 기여" DB ID → `docs/contribute/`                                     |
| `NOTION_RELEASE`      | "릴리즈 노트" DB ID → `docs/release-notes/`                                   |
| `NOTION_INSTALL`      | "설치" DB ID → `docs/install/`                                             |
| `DEEPL_API_KEY`       | DeepL Free API 키 — `translate_to_en.py` 및 `monthly-translate.yml` Secret |

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
0 */1 * * * /root/docs-web/scripts/server-sync.sh >> /var/log/notion-sync.log 2>&1
```

`server-sync.sh` 실행 흐름:
1. ORIG_BRANCH 저장 + `trap EXIT` 등록 (종료 시 원래 브랜치 복귀 — dev 서버 파일 보호)
2. `git checkout main` → `git pull --rebase`
3. Notion 8개 DB 병렬 동기화
4. `git commit` → `git push origin main` → `deploy.yml` 트리거
5. 스크립트 종료 → trap이 자동으로 원래 브랜치(develop 등)로 복귀

로그 확인: `tail -f /var/log/notion-sync.log`

> ⚠️ **staged files 주의:** git index에 스테이징된 파일(커밋 안 한 `git add`)이 있으면 `git pull --rebase`가 실패해 crontab이 멈춘다. Claude가 작업 후에는 반드시 커밋까지 완료하고 떠나야 한다. 확인: `git diff --staged --quiet || echo "STAGED"` — 출력이 있으면 커밋 또는 `git restore --staged .` 후 종료.

### GitHub Actions 워크플로우

| 파일                      | 트리거                  | 역할                                                                  |
| ----------------------- | -------------------- | ------------------------------------------------------------------- |
| `deploy.yml`            | main push            | npm build → GH Pages 배포                                             |
| `monthly-translate.yml` | 매월 1일 KST 11:00 / 수동 | KR docs·blog → DeepL → `i18n/en/` 번역, main에 커밋                     |
| `sync-develop.yml`      | 매일 KST 03:00         | main 콘텐츠를 develop으로 머지 (`.notion-sync.json` 충돌 자동 해소)               |
| `merge-develop.yml`     | 매일 KST 11:00         | develop 코드 변경을 main으로 머지 (콘텐츠 디렉토리 제외, 빌드 게이트 포함)                   |
| `md-to-notion.yml`      | `docs/**/*.md` push  | 수동 편집된 md → Notion DB 역업로드                                          |
| `pr-build.yml`          | main·develop PR      | 프로덕션 빌드 검증 (깨진 링크·MDX 오류 차단)                                        |

### 커밋 메시지 태그 규칙

| 태그                 | 효과                    |
| ------------------ | --------------------- |
| `[skip-notion]`    | `md-to-notion.yml` 스킵 |
| 커미터가 `server-cron` | `md-to-notion.yml` 스킵 |

**`[skip-notion]` 필수 상황:** Notion에서 내려받은 내용을 다시 올리면 무한 루프가 된다.

- 서버 crontab 커밋 → 자동 부여됨
- Claude가 수동 커밋할 때 `.notion-sync.json`·`docs/` Notion 원본 포함 시 → 반드시 추가
- `design → main` 등 머지 커밋이 `docs/` 파일 포함 시 → 머지 커밋 메시지에도 추가

### 외부 검색 최적화 (SEO) — 2026-06-22 적용

| 항목                    | 내용                                      | 파일                                   |
| --------------------- | --------------------------------------- | ------------------------------------ |
| Google Search Console | 소유권 인증 완료, `sitemap.xml` 제출됨            | `static/google8226dc54aa85a9f0.html` |
| JSON-LD 구조화 데이터       | `@graph`: Organization + WebSite 타입     | `docusaurus.config.ts` → `headTags`  |
| GitHub 링크             | navbar·footer 모두 `SceneMakerAI` org로 변경 | `docusaurus.config.ts`               |

JSON-LD 스키마 참고: [schema.org/WebSite](https://schema.org/WebSite) · [schema.org/Organization](https://schema.org/Organization)  
Google Rich Results Test: [https://search.google.com/test/rich-results](https://search.google.com/test/rich-results)

---

## 브랜치 전략

> ⚠️ **핵심 규칙: `main`·`develop`에 코드를 직접 커밋하지 않는다.**
> feat 브랜치는 `develop`에서 따고, 완료 후 `develop`으로 머지한다. design 브랜치는 경유하지 않는다.

### 브랜치 흐름

```
main (콘텐츠 자동화 전용)
 └─ develop (코드 통합)
     └─ feat/<이름> (단위 작업, 완료 후 develop으로 머지 → 삭제)
 └─ design (장기 유지, UI·CSS·설정 전용)
```

| 작업 유형               | 시작 브랜치    | 머지 대상                   | dev 서버 포트 | 담당         |
| ------------------- | --------- | ----------------------- | --------- | ---------- |
| 콘텐츠 (Notion 자동 동기화) | —         | `main` 직접 커밋 *(자동화 전용)* | 3000      | 서버 crontab |
| **모든 코드 변경**        | `develop` | `feat/<이름>` → `develop` | 3001      | **Claude** |
| **main 반영**         | —         | `develop` → `main`      | 3000      | **사용자**    |

**작업 흐름 (Claude 담당 부분):**

```bash
# 1. develop 최신화
git checkout develop && git pull origin develop

# 2. feat 브랜치 생성 (develop 기점)
git checkout -b feat/<이름>

# 3. 작업 후 커밋 ([skip-notion] 포함)
git commit -m "feat(...): ... [skip-notion]"

# 4. develop으로 머지 후 feat 삭제
git checkout develop && git merge feat/<이름> && git branch -d feat/<이름>
git push origin develop

# → 이후 main 머지는 사용자가 직접 수행
```

**절대 금지:**

- `main`에 직접 커밋 ❌
- `feat` 브랜치를 `main`에 직접 머지 ❌
- Claude가 `main`에 머지·push ❌ (사용자 전용, 명시적 요청 시 예외)

**design 브랜치:** 장기 유지 (삭제 금지). UI·CSS 전용. feat 작업의 기점·머지 대상이 아님.
**feat 브랜치:** develop으로 머지 완료 후 로컬 삭제. 원격 push 불필요.

### crontab 충돌 처리

crontab이 1시간마다 main에 push하므로 `non-fast-forward` 에러 시:

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

| 명령어                     | 용도                                                              |
| ----------------------- | --------------------------------------------------------------- |
| `npm start`             | main 브랜치 dev 서버 (port 3000, KO+EN)                              |
| `npm run start:develop` | develop 브랜치 dev 서버 (port 3001, KO+EN)                           |
| `npm run build`         | 프로덕션 빌드 — **PR 전 통과 필수**                                        |
| `npm run clear`         | Docusaurus 캐시 정리                                                |
| `npm run typecheck`     | TypeScript 검사 (빌드와 무관, IDE 보조)                                  |

**dev 서버 404 / 브랜치 전환 후 캐시 꼬임:** `npm run clear` 후 재시작.

**EN 로케일 접근:** `--locale` 플래그 없이 실행하면 KO (`/`) + EN (`/en/`) 모두 서빙된다. `http://localhost:3001/en/docs/...` 로 바로 접근 가능.

---

## EN 번역 파이프라인

### 개요

`scripts/translate_to_en.py`가 `docs/`·`blog/` 의 KR Markdown을 DeepL Free API로 번역해 `i18n/en/` 에 저장한다. **`monthly-translate.yml`이 매월 1일 자동 실행**한다 (서버 crontab은 번역 미포함).

### 동작 방식

- **해시 캐시** (`.notion-translate-hashes.json`): SHA-256으로 변경된 파일만 번역. 미변경 파일 스킵.
- **에러 격리**: 파일 하나 실패해도 나머지 계속 진행 (try-except per file).
- **`<hr/>` 버그 방지**: DeepL이 `<hr/>` 앞뒤 줄바꿈을 제거하는 문제를 `\n\n---\n\n`으로 복원.
- **heading 공백 복원**: DeepL이 `###3.` 처럼 공백을 제거하는 경우 정규식으로 복원.
- **blockquote 마커 복원**: DeepL이 `> ` 마커를 문장 중간으로 이동시키는 경우 복원.
- **빌드 안전**: EN 번역 파일 없어도 Docusaurus는 KO fallback — 번역 실패가 배포 실패로 이어지지 않음.

### 수동 번역 실행

```bash
export $(grep -v '^#' .env | xargs)
python3 scripts/translate_to_en.py
```

### 주의사항

- `DEEPL_API_KEY`는 `.env` (로컬) + GitHub Secrets `DEEPL_API_KEY` (CI) 모두 필요.
- DeepL Free API 한도: 500,000자/월. 전체 재번역 시 소진 주의.
- `monthly-translate.yml`은 `continue-on-error: true`로 번역 실패 시에도 워크플로우 green.

---

## 빌드 게이트

`onBrokenLinks: 'throw'` — CI에서 아래 시 빌드 실패:

- **깨진 내부 링크** — PR 전 `npm run build` 로컬 통과 필수
- **MDX 컴파일 오류** — frontmatter·JSX 문법 오류
- **사이드바 비어있음** — Notion DB에 콘텐츠가 없는 섹션은 `placeholder.md` 필수 (현재: `about/`, `architecture/`, `release-notes/`)

---

## navbar 자동 숨김 — `hasNotionContent`

`docusaurus.config.ts`에 빌드 타임 함수 `hasNotionContent(dirName)`가 있다. `docs/<dir>/` 안에 `placeholder.md` 외 `.md` 파일이 없으면 navbar 항목을 숨긴다.

- Notion 콘텐츠가 없는 섹션: navbar에서 자동 제거 (빌드 시 평가)
- Notion 콘텐츠 도착 → sync → `.md` 파일 생성 → 다음 빌드에서 자동 복원
- `placeholder.md`는 사이드바 비어있음 빌드 에러 방지용 (Notion 콘텐츠가 없는 섹션에 필수)

## 사이드바 ID ↔ Notion DB 매핑

| 사이드바 ID               | `docs/` 경로       | 환경변수                  | Notion 콘텐츠 유무                  |
| --------------------- | ---------------- | --------------------- | ------------------------------- |
| `aboutSidebar`        | `about/`         | `NOTION_ABOUT`        | ❌ placeholder.md 필요 (navbar 숨김) |
| `architectureSidebar` | `architecture/`  | `NOTION_ARCHITECTURE` | ❌ placeholder.md 필요 (navbar 숨김) |
| `installSidebar`      | `install/`       | `NOTION_INSTALL`      | ✅                               |
| `pocSidebar`          | `poc/`           | `NOTION_POC`          | ✅                               |
| `docsSidebar`         | `guide/`         | `NOTION_DOCS`         | ✅                               |
| `contributeSidebar`   | `contribute/`    | `NOTION_CONTRIBUTE`   | ✅                               |
| `releaseNotesSidebar` | `release-notes/` | `NOTION_RELEASE`      | ❌ placeholder.md 필요 (navbar 숨김) |

블로그는 `sidebars.ts` 미포함 — navbar에 `{to: '/blog'}` 방식.

---

## notion_to_md.py 핵심 동작

### 번호 매기기 목록 (OL) 순서 번호

스크립트가 `numbered_list_item` 블록에 실제 순서 번호(1, 2, 3…)를 출력한다.
HTML `<ol start="N">`이 자동 생성되어 코드블록으로 분리된 OL도 연속 번호가 유지된다.

**카운터 리셋 기준 (`_OL_RESET_TYPES`):**

| 블록 타입                                                       | 동작                      |
| ----------------------------------------------------------- | ----------------------- |
| `heading_1~4`                                               | **리셋** (섹션 경계)          |
| `table`, `toggle`, `column_list`                            | **리셋**                  |
| `code`, `paragraph`, `image`, `divider`, `quote`, `callout` | **유지** (split-OL 연속 번호) |
| `bulleted_list_item`, `to_do`                               | **유지**                  |

### HTML 엔티티 처리

Notion API가 `&gt;` 형태로 이중 인코딩할 때 `extract_text_from_rich_text`에서 안정될 때까지 반복 unescape.

### 꺾쇠 이스케이프 (`escape_mdx_angle_brackets`)

`<한글>` 패턴을 `\<한글>`으로 변환해 MDX JSX 파싱 오류 방지. 코드 블록·인라인 코드 안은 건드리지 않는다.

### child_page · link_to_page 블록

Notion 인라인 서브페이지(`child_page`)와 페이지 링크(`link_to_page`)를 `- [제목](https://www.notion.so/PAGE_ID)` 형태로 렌더링.

---

## 콘텐츠 추가 체크리스트

**새 Notion 섹션 추가:**

1. GitHub `secrets.NOTION_XXX` 등록 + `.env`에 추가
2. `scripts/server-sync.sh`에 DB 동기화 블록 추가
3. `docs/new-section/_category_.json` 생성
4. `sidebars.ts` + `docusaurus.config.ts` navbar 추가 (hasNotionContent 조건부 포함)
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
- `i18n/en/` 파일 수동 편집 금지 — `translate_to_en.py` 실행 시 덮어씌워짐. EN 번역 수정은 스크립트 로직 수정으로.
- `.notion-translate-hashes.json` 삭제·gitignore 금지 — 삭제 시 다음 CI 실행에서 전체 파일 재번역 (DeepL 한도 소진 위험)
