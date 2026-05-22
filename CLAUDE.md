# CLAUDE.md — docs-web 작업 가이드

이 저장소는 SceneMakerAI의 **Docusaurus 3** 기술 블로그·문서 사이트다. 코드 개발 저장소가 아니라 콘텐츠 사이트이므로, 작업의 대부분은 MDX/Markdown 추가·수정과 i18n 미러링이다. 아래는 이 저장소에서 실제로 발생하는 마찰점만 정리한 것이다. 그 외 일반적인 사항은 `README.md`를 참조한다.

---

## 1. 자주 쓰는 명령어

| 명령어 | 용도 |
| ------ | ---- |
| `npm start` | 한국어 dev 서버 (3000) |
| `npm run start:en` | 영어 dev 서버 (3002) |
| `npm run build` | 프로덕션 빌드 (양쪽 로케일 동시) |
| `npm run serve` | `build/` 결과를 로컬 서빙 (양쪽 로케일 한 서버에서 확인) |
| `npm run typecheck` | TypeScript 타입 체크 (빌드 없이) |
| `npm run write-translations:en` | EN 번역 JSON 골격 재생성 |
| `npm run clear` | Docusaurus 캐시 정리 |

---

## 2. URL 구조 — 숫자 slug

모든 docs 페이지 URL은 `sidebar_position` 기반 **숫자 slug**를 사용한다.

```
/docs/architecture/1
/docs/poc/2
/docs/install/3
```

### 규칙

- 프론트매터에 `slug: "N"` (N = sidebar_position 값)을 반드시 포함한다.
- `slug`는 파일 디렉토리 기준 상대 경로이므로 숫자만 쓰면 된다 — 섹션명 prefix 불필요.
- Notion 동기화 스크립트(`scripts/notion_to_docs_generic.py`)가 신규 페이지 생성 시 `slug: "{order}"`를 자동 삽입한다. 수동 생성 파일은 직접 추가해야 한다.

### 프론트매터 예시

```yaml
---
id: my-page
title: "페이지 제목"
sidebar_position: 2
slug: "2"
---
```

### EN 미러의 slug

EN 미러 파일도 KR 원본과 **동일한 slug 값**을 사용한다. KR `/docs/poc/2` 에 대응하는 EN 페이지는 `/en/docs/poc/2` 가 되어야 한다.

---

## 3. 콘텐츠 추가 워크플로우

### 새 문서 페이지 (`docs/`)

현재 섹션: `about`, `architecture`, `blog`, `contribute`, `guide`, `install`, `poc`, `release-notes`

1. 해당 섹션 폴더에 `.md` 또는 `.mdx` 파일 생성
2. 프론트매터에 `id`, `title`, `sidebar_position`, `slug` 필수 포함
3. Notion 동기화 대상 섹션은 스크립트가 자동 생성하므로 수동 생성 불필요
4. 새 섹션 추가 시 `sidebars.ts`에 sidebar 항목과 `docusaurus.config.ts` navbar 항목을 함께 추가

### Notion 동기화 대상 섹션

`notion-sync.yml`의 GitHub Secrets로 매핑됨:

| Secret | 저장 경로 |
|--------|-----------|
| `NOTION_BLOG` | `docs/blog` |
| `NOTION_CONTRIBUTE` | `docs/contribute` |
| `NOTION_ABOUT` | `docs/about` |
| `NOTION_ARCHITECTURE` | `docs/architecture` |
| `NOTION_POC` | `docs/poc` |
| `NOTION_DOCS` | `docs/guide` |
| `NOTION_RELEASE` | `docs/release-notes` |
| `NOTION_INSTALL` | `docs/install` |

Notion Sync는 KST 오전 9시~오후 7시 매 정각 실행되며, 변경이 있으면 `main`에 자동 커밋 후 배포가 트리거된다.

---

## 4. i18n 미러 규율

- **한국어가 원본**이다. `docs/`, `src/pages/`에 KR로 먼저 쓴다.
- **EN 미러가 없으면 KR로 fallback** 되므로 번역은 점진적으로 추가해도 사이트가 깨지지 않는다.
- EN 미러 파일은 KR과 **동일한 파일명·경로**로 아래 위치에 생성한다:

```
docs/architecture/아키텍처-설계.md
  → i18n/en/docusaurus-plugin-content-docs/current/architecture/아키텍처-설계.md

src/pages/about.mdx
  → i18n/en/docusaurus-plugin-content-pages/about.mdx
```

- EN 미러 프론트매터에도 `slug: "N"`을 KR과 동일하게 포함할 것.
- 네비/푸터/UI 문구는 JSON으로 따로 번역한다:
  - `i18n/en/code.json` — 컴포넌트 UI 문자열
  - `i18n/en/docusaurus-theme-classic/navbar.json`, `footer.json` — 네비/푸터 라벨
  - `i18n/en/docusaurus-plugin-content-docs/current.json` — 사이드바 카테고리 라벨
- KR 원본 라벨/UI 문구를 추가·변경한 뒤에는 `npm run write-translations:en`을 돌려 JSON 골격을 갱신한다.

---

## 5. 빌드 게이트

`.github/workflows/deploy.yml`이 `main` push 시 `npm run build`만 돌려 GH Pages에 배포한다. **CI는 빌드만 돌리고 typecheck은 따로 안 돈다.**

### CI에서 실제로 막히는 것

- **깨진 내부 링크** — `docusaurus.config.ts`에 `onBrokenLinks: 'throw'`로 잡혀 있어 빌드 실패한다. PR 머지 전 로컬에서 `npm run build`로 한 번 통과시킬 것.
- **MDX 컴파일 에러** — 프론트매터·JSX 문법 오류는 즉시 빌드 실패.

### 로컬 가드 (CI는 막지 않지만 권장)

- **TypeScript 타입 체크** — `tsconfig.json`이 `strict: true`이지만 `docusaurus start/build`는 이를 사용하지 않는다. IDE 보조용이며 `npm run typecheck`로 수동 실행.

### 경고만 뜨고 통과되는 것

- 블로그의 인라인 태그/저자/truncate 누락은 `warn`이라 배포 자체를 막진 않지만 누적되면 검색·필터링이 망가지므로 발생 시 그 PR 안에서 정리한다.

---

## 6. 도메인·배포 메모

- 운영 URL: `https://doc.scenemaker.solbox.com` (`baseUrl: '/'`, 서브패스 없음)
- DNS·CNAME은 이미 적용됨. `docusaurus.config.ts`의 `url`을 임의로 바꾸지 말 것 — RSS/sitemap의 절대 URL이 따라 움직인다.

---

## 7. `.aidocs/design.md` 메모

추후 사이트 리디자인을 위한 디자인 토큰 참조 문서(Revolut 스타일 — 검은 캔버스, Aeonik Pro, cobalt violet). 현재 컴포넌트엔 아직 적용되어 있지 않고, 적용 시점에 `src/css/custom.css`와 컴포넌트 swizzle로 반영할 예정이다. 그때까지는 **읽기 전용 참조 문서**로 다룬다.

---

## 8. 하지 말 것

- `docusaurus.config.ts`의 `url` / `baseUrl` / `organizationName` / `projectName`을 함부로 바꾸지 말 것 (GH Pages 배포와 RSS 절대 URL에 직접 영향).
- `onBrokenLinks: 'throw'`를 `'warn'`으로 낮추지 말 것. 깨진 링크가 배포로 새는 것보다 빌드를 막는 게 낫다.
- 영어 미러를 만든답시고 KR 원본을 영어로 덮어쓰지 말 것. 원본은 KR 유지, 번역은 `i18n/en/` 아래.
- `.docusaurus/`, `build/`, `node_modules/`는 빌드 산출물·캐시다. 커밋 대상이 아니다(이미 `.gitignore`로 빠져 있다).
- 수동 생성 docs 파일에 `slug` 프론트매터를 빠뜨리지 말 것 — URL이 한글 인코딩 경로로 노출된다.
