
# CLAUDE.md — docs-web 작업 가이드

콘텐츠 사이트. 작업 대부분은 Markdown 추가·수정과 notion_to_md.py 스크립트 유지보수.

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
| `scripts/translate_to_en.py` | 변경된 KR → DeepL → `docs_en/` 자동 번역 |
| `scripts/server-sync.sh` | crontab 진입점 (pull→sync→commit→push) |
| `scripts/tests/` | notion_to_md.py · md_to_notion.py 단위 테스트 |

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

> ⚠️ **merge 커밋 주의:** `design → main` 등 브랜치 머지 커밋이 `docs/` 파일을 포함하면 merge 커밋 메시지에도 반드시 `[skip-notion]` 부여. 누락 시 `md-to-notion.yml`이 트리거되어 Notion 내용이 일시 삭제·덮어써질 수 있음.

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

**design 브랜치:** 장기 유지 (삭제 금지). 작업 전 반드시 `git merge origin/main --ff-only` 실행.
**feat 브랜치:** 작업 완료 후 main에 merge → 로컬·원격 브랜치 삭제.
Notion 자동 동기화가 main에 직접 커밋하므로 브랜치 작업 시작 전 rebase 생략 시 conflict 발생.

### ⚠️ feat → design 머지 금지 — cherry-pick 사용

feat 브랜치는 main을 기점으로 생성되므로, main의 모든 커밋이 포함된다.
`git merge feat/<이름>` 을 design에 실행하면 **feat 브랜치에 딸려 온 main 커밋까지 design으로 유입**된다.

**올바른 방법:** feat 브랜치의 변경만 design에 적용할 때는 `git cherry-pick <커밋해시>` 사용.

```bash
# 잘못된 방법 (main 커밋이 따라옴)
git checkout design
git merge feat/something  # ❌

# 올바른 방법 (해당 커밋만 적용)
git checkout design
git cherry-pick <feat-commit-hash>  # ✅
```

### crontab 충돌 처리

crontab은 30분마다 main에 직접 push한다. 내가 main에 push하려 할 때 `non-fast-forward` 에러가 나면:

```bash
git stash            # 미커밋 변경 임시 저장
git pull --rebase origin main   # crontab 커밋 위로 rebase
# 충돌 시: docs/poc/.notion-sync.json 등 Notion 파일은 --theirs 선택
git add <충돌파일>
git rebase --continue
git stash pop
git push origin main
```

### design 브랜치 최신화

main에 변경이 쌓이면 design도 함께 업데이트한다:

```bash
git checkout design
git merge main --ff-only   # 또는: git merge origin/main --ff-only
git push origin design
```

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

**dev 서버 404 / 브랜치 전환 후 캐시 꼬임:** `npm run clear` 후 재시작.

---

## 빌드 게이트

`onBrokenLinks: 'throw'` — CI에서 아래 시 빌드 실패:
- **깨진 내부 링크** — PR 전 `npm run build` 로컬 통과 필수
- **MDX 컴파일 오류** — frontmatter·JSX 문법 오류
- **사이드바 비어있음** — `aboutSidebar`처럼 docs/가 비면 빌드 실패 → placeholder.md 필요

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

## notion_to_md.py 핵심 동작

### 번호 매기기 목록 (OL) 순서 번호

스크립트가 `numbered_list_item` 블록에 실제 순서 번호(1, 2, 3…)를 출력한다.
HTML `<ol start="N">`이 자동 생성되어 코드블록으로 분리된 OL도 연속 번호가 유지된다.
CSS는 표준 `list-style: decimal`을 사용 — CSS 카운터 없음.

**카운터 리셋 기준 (`_OL_RESET_TYPES`):**

| 블록 타입 | 동작 |
|----------|------|
| `heading_1~4` | **리셋** (섹션 경계) |
| `table`, `toggle`, `column_list` | **리셋** |
| `code`, `paragraph`, `image`, `divider`, `quote`, `callout` | **유지** (split-OL 연속 번호) |
| `bulleted_list_item`, `to_do` | **유지** — 번호 목록 항목 사이 sub-bullet로 나타나므로 |

### HTML 엔티티 처리

Notion API가 일부 셀에서 `&amp;gt;` 형태로 이중 인코딩해 반환할 때
`extract_text_from_rich_text`에서 안정될 때까지 반복 unescape한다.

### 꺾쇠 이스케이프 (`escape_mdx_angle_brackets`)

`<한글>` 패턴을 `&lt;한글&gt;`으로 변환해 MDX JSX 파싱 오류 방지.
트리플 백틱 코드 블록과 인라인 코드 스팬(`` ` ``) 안은 건드리지 않는다.

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
export $(grep -v '^#' .env | xargs)
NOTION_DATABASE_ID="$NOTION_POC" SAVE_DIR=docs/poc FETCH_MODE=ALL python3 scripts/notion_to_md.py
```

**특정 페이지 강제 재sync (last_edited 캐시 무효화):**
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
