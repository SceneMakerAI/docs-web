# SceneMakerAI · docs-web 기여 가이드

이 문서는 **"무엇을 어디에 어떻게 올리는가"의 결정 룰과 수용 기준**을 정의합니다. 설치·실행 등 *how-to*는 [README.md](./README.md), 디렉토리·메커니즘 상세는 [CLAUDE.md](./CLAUDE.md)와 [dev-docs/](./dev-docs/)를 참조하세요.

원칙은 단 한 줄입니다.

> **"링크가 안 깨지고 빌드가 통과하면, 메인테이너 셀프 리뷰 후 머지한다."**

`docusaurus.config.ts`에 `onBrokenLinks: 'throw'`가 걸려 있어 깨진 내부 링크는 빌드 자체를 실패시킵니다. 이것이 사실상 자동 강제되는 유일한 룰이며, 아래 규칙은 이를 떠받치기 위한 결정 기준입니다.

---

## 1. 두 가지 기여 경로

기여는 **콘텐츠**냐 **코드**냐에 따라 경로가 완전히 다릅니다. 먼저 이걸 구분하세요.

| 기여 종류 | 어디서 작업 | 어떻게 반영되나 |
| --- | --- | --- |
| **콘텐츠** (문서·블로그·기여 로그·릴리즈 노트) | **Notion DB** | 서버 crontab이 2분마다 `docs/`로 동기화 → DeepL이 `docs_en/`로 번역 → `main` push → 자동 배포 |
| **코드·사이트** (`src/`·`scripts/`·`sidebars.ts`·`docusaurus.config.ts`·`static/`·디자인) | **GitHub** | `feature/*` → `develop` → `main` PR 플로우 (§7) |

- **콘텐츠는 GitHub의 `docs/`를 직접 편집하지 않습니다** — Notion에 쓰면 sync가 가져옵니다 (§2). 예외는 수동 구조 파일뿐 (§2.3).
- **코드는 Notion과 무관**하게 `develop` 브랜치에서 작업합니다 (§7).
- 콘텐츠와 코드 변경은 **PR(또는 작업 단위)을 분리**합니다.

---

## 2. 콘텐츠 기여 — Notion에 작성

모든 문서는 Notion DB가 원본입니다. `scripts/notion_to_docs_generic.py`가 페이지 제목을 파일명으로, 본문을 Markdown으로 변환하고 frontmatter를 자동 생성합니다.

### 2.1 어느 DB에 쓰는가

작성하려는 글의 성격에 따라 해당 Notion DB에 페이지를 만듭니다. 헷갈리면 위에서부터 매칭되는 첫 항목을 따릅니다.

| 글의 성격 | Notion DB → 동기화 경로 | 예시 |
| --- | --- | --- |
| **시점이 있는 회고/실험/공지** (날짜에 의미) | `NOTION_BLOG` → `docs/blog/` | "Qwen VLM 방송 도메인 적용기" |
| **변하지 않는 사용/운영 방법** | `NOTION_DOCS` → `docs/guide/` | "SceneMakerAI 시작하기", "장애 대응" |
| **시스템 설계·데이터 흐름·기술 의사결정** | `NOTION_ARCHITECTURE` → `docs/architecture/` | "vLLM 클러스터 토폴로지" |
| **설치 가이드** | `NOTION_INSTALL` → `docs/install/` | "Qwen 설치", "LLM 설치" |
| **PoC 기획·벤치마크** | `NOTION_POC` → `docs/poc/` | "Vision 벤치마크" |
| **프로젝트 소개** | `NOTION_ABOUT` → `docs/about/` | "SceneMakerAI 소개" |
| **외부 OSS 기여 인덱스** | `NOTION_CONTRIBUTE` → `docs/contribute/` | Qwen PR 링크 (§4) |
| **릴리즈 노트** | `NOTION_RELEASE` → `docs/release-notes/` | `v0.1.0` (§5) |

> DB ↔ 경로 매핑 상세는 [dev-docs/notion-sync.md](./dev-docs/notion-sync.md).

판단이 안 서면 **blog DB**가 기본값입니다. 가치 있는 글이 안 올라가는 것보다, blog에 올라가 발견되는 편이 낫습니다. 나중에 "docs로 옮기는 게 맞다" 싶으면 그때 Notion에서 이관합니다.

### 2.2 Notion 작성 → 자동 반영

sync가 처리하므로 아래는 **알아두면 되는 것**이지 손으로 할 일이 아닙니다.

- **파일명·slug 자동**: slugify가 한글 제목을 보존해 한글 파일명을 만들고(정상), URL은 `slug: "숫자"`로 따로 잡힙니다. → [CLAUDE.md 핵심 함정](./CLAUDE.md)
- **계층 구조 자동**: Notion "하위 항목" relation을 걸면 sync가 서브디렉토리 + `_category_.json`을 자동 생성합니다(부모 `index.md`는 `slug: "/"`).
- **frontmatter 자동 생성**:
  - 평면·자식 페이지 → `id`, `title`, `sidebar_position`, `slug` (4개)
  - 부모 `index.md` → `title`, `sidebar_position`, `slug` (`id`는 생략 — 파일경로 기반 ID와 충돌 방지)
  - `description`·`date`는 **자동 생성되지 않습니다**(필요하면 SEO상 권장이나 강제 아님).
- **정렬 자동**: 섹션 내 `sidebar_position`은 Notion 페이지 `created_time` 오름차순으로 배정됩니다.
- **이미지 자동**: 본문 이미지는 `static/img/<섹션>/<slug>/`로 내려받아집니다.

### 2.3 수동 문서 추가 (예외)

sync는 `.notion-sync.json`에 추적된 *자기가 만든 파일만* 삭제하므로(`remove_orphans`), 사람이 만든 파일은 보존됩니다. 다만 **콘텐츠의 기본은 Notion**이고, 수동 추가는 빌드용 구조 파일 등 예외로 최소화합니다.

- 파일명은 **kebab-case**(`vllm-cluster.md`), frontmatter 4개(`id`/`title`/`sidebar_position`/`slug`)를 직접 채웁니다.
- `slug`는 **섹션 내 상대 경로**입니다. `/<섹션>/...` 전체경로는 금지.
- 같은 섹션의 Notion 파일과 `sidebar_position`이 겹치지 않게 합니다.
- 본문에 H1(`#`)을 따로 쓰지 않습니다(frontmatter `title`이 H1 생성).
- 내부 링크는 같은 폴더 상대 경로 또는 `/docs/<섹션>/<slug>` 형식.
- `_category_.json`은 **섹션 루트만** 수동 관리 대상이며, 하위 서브디렉토리는 sync가 덮어씁니다 — 부모 `index.md`에 `id:`를 넣지 마세요.

---

## 3. i18n (자동 번역)

EN 번역본 실파일은 **`docs_en/`**에 있고, `i18n/en/docusaurus-plugin-content-docs/current`가 그곳을 가리키는 **symlink**입니다. `scripts/translate_to_en.py`가 변경된 KR 문서를 DeepL로 자동 번역합니다. 상세는 [dev-docs/i18n.md](./dev-docs/i18n.md).

- **한국어가 원본**입니다. 번역이 없는 콘텐츠는 자동으로 한국어로 fallback됩니다.
- 콘텐츠 번역은 sync 파이프라인이 처리하므로 **별도 작업이 필요 없습니다**.
- 네비·푸터·컴포넌트 UI 라벨은 `i18n/en/`의 JSON으로 번역합니다 — 이건 콘텐츠가 아니라 **코드 기여(§7)** 영역입니다.

---

## 4. 외부 오픈소스 기여 로깅 (KPI 직결)

과제 목표는 **누적 30건 이상의 외부 OSS 기여**입니다. 모든 외부 기여는 사이트에 흔적을 남깁니다.

- 외부 **PR / Issue / Discussion / 데이터셋 공개**가 머지·공개되는 즉시, **Notion contribute DB**(`NOTION_CONTRIBUTE` → `docs/contribute/`)에 **한 줄 항목**을 추가합니다.
- 한 줄 형식 예:
  ```markdown
  - [vLLM] `flash-attn` MoE 라우팅 버그 수정 PR — [vllm-project/vllm#12345](https://github.com/vllm-project/vllm/pull/12345) (2026-06-12, merged)
  ```
- 포함 항목: **업스트림 프로젝트명**, **요약**, **링크**, **날짜**, **상태**(open / merged / closed / released).
- 별도 회고가 필요하면 blog 글을 함께 쓰고, 인덱스 항목에서 블로그를 링크합니다.

이 룰은 강제됩니다 — 외부 기여를 했는데 contribute DB에 항목이 없다면 **이 사이트의 KPI 카운트에 포함되지 않은 것으로 간주**합니다.

---

## 5. 릴리즈 노트 (Notion release DB)

릴리즈 노트는 **SceneMakerAI 프로젝트(4대 서비스: 모아보기·리믹스·광고·Batch)** 의 버전 단위 공식 발표 기록입니다. docs-web 사이트 자체의 변경은 대상이 아니며 — [GitHub Release](https://github.com/SceneMakerAI/docs-web/releases) 또는 `git log`로 갈음합니다.

**Notion release DB**(`NOTION_RELEASE` → `docs/release-notes/`)에 버전별 페이지를 작성하면 sync가 반영합니다. 파일명·slug·정렬은 sync가 자동 처리하므로(§2.2), 아래는 **Notion 페이지에 담을 내용 규칙**입니다.

### 버전 명명
- **SemVer**(`vMAJOR.MINOR.PATCH`)를 따릅니다.
  - MAJOR: 호환성 깨지는 변경 / MINOR: 호환되는 기능 추가 / PATCH: 호환되는 버그 수정.
- 4대 서비스는 **통합 버전**으로 운영합니다(서비스별 분리가 필요해지는 시점에 재정의).
- 코드명을 붙이려면 페이지 제목에: `v0.1.0 — Aurora`.

### 본문 구조 (Keep a Changelog)
다음 섹션을 **순서대로** 쓰며, 해당 항목이 없으면 섹션 자체를 생략합니다.

```markdown
## 요약 (1~3줄)

## 호환성
- 마이그레이션 필요 여부 · 영향 받는 API/설정 · 다운그레이드 안전성
- 변경 없으면 "변경 없음" 한 줄로 명시

## 서비스별 변경
### 모아보기
### 리믹스
### 광고
### Batch

## 의존성 변경
- Qwen ... / vLLM ... / LangGraph ... / faster-whisper ... 등

## 알려진 이슈

## 기여자
- @<github-handle>, ...
```

### 수용 기준
- [ ] 페이지 제목이 SemVer(`vMAJOR.MINOR.PATCH`) 형식
- [ ] 본문에 "호환성" 섹션 존재 (해당 없으면 "변경 없음" 명시)
- [ ] 릴리즈에 포함된 외부 OSS 기여가 contribute DB에 누락되지 않음 (§4)

> **정렬 주의**: sync는 `created_time` 오름차순으로 `sidebar_position`을 배정합니다(오래된 릴리즈가 위). 최신 릴리즈를 위에 고정하려면 sync 정렬 정책 조정이 필요하므로, 표시 순서가 문제가 되는 시점에 별도로 다룹니다.

---

## 6. 블로그 작성 규칙 (참고용 · 현재 비활성)

> **현행**: 블로그는 별도 blog 플러그인이 아니라 **`docs/blog/` 섹션(docs 플러그인)**으로 운영됩니다(`docusaurus.config.ts`의 `blog: false`). 글은 Notion blog DB에서 자동 동기화되며 **일반 콘텐츠 규칙(§2)을 따릅니다.** 따라서 아래의 `authors.yml`·`tags.yml`·`<!-- truncate -->`·`onInlineAuthors/Tags` 게이트는 **현재 비활성**입니다(향후 blog 플러그인으로 전환할 경우의 참고용으로 남겨둡니다).

### 게시 주기 (KPI 직결)
- 과제 목표: **블로그 누적 20+건**, **월 2건 이상**. 최소 격주 게시를 권장합니다.
- 회고/실험 결과/오픈소스 기여 노트는 가능한 한 blog로 먼저 공개합니다.

### 파일 명명
```
blog/YYYY-MM-DD-kebab-case-slug.mdx
```
예: `blog/2026-06-15-qwen-vlm-broadcast.mdx`

날짜는 게시 예정일 기준입니다. 같은 날 여러 글은 슬러그로 구분합니다.

### 필수 frontmatter
```yaml
---
slug: <URL 슬러그, 파일명의 슬러그 부분과 동일>
title: <한국어 제목>
authors: [<authors.yml에 등록된 키>]
tags: [<aspect>, <aspect>, ...]
date: YYYY-MM-DD
description: <한 줄 요약, 미리보기·OG·RSS 공통 사용>
---
```

### 본문 구조
- 본문 상단에 미리보기에 노출할 1–3문단의 리드를 작성합니다.
- 리드 끝에 **반드시** `<!-- truncate -->` 마커를 넣습니다(블로그 목록에서 노출되는 분량의 컷).
- 마커가 없으면 빌드 시 경고(`onUntruncatedBlogPosts: 'warn'`)가 떨어집니다.

### 저자(`blog/authors.yml`)
- 글을 올리기 전, 본인 키가 `authors.yml`에 없으면 추가합니다.
- 신규 저자 최소 필드: `name`, `title`, `url`, `image_url`, `page: true`, `socials.github`.
- 인라인 저자(`authors: [{name: ..., title: ...}]`)는 사용하지 않습니다(`onInlineAuthors: 'warn'` 정책).

### 태그
- 태그는 `tags.yml`에서 관리되는 항목만 사용합니다. 새 태그가 필요하면 `blog/tags.yml`에 정의를 추가한 뒤 사용합니다.
- 인라인 태그(`tags: ['처음쓰는태그']`)는 사용하지 않습니다(`onInlineTags: 'warn'` 정책).
- 태그는 **주제**(qwen, vllm, langgraph, dataset) 또는 **활동 유형**(retro, experiment, contribution) 중 하나로 작명. 너무 일반적인 태그(`ai`, `ml`)는 지양.

### 수용 기준
- [ ] 파일명·`slug`·`date` 세 곳의 날짜·슬러그가 일치
- [ ] `<!-- truncate -->` 마커 존재
- [ ] `authors`가 `authors.yml`에 등록된 키
- [ ] `tags`가 `tags.yml`에 정의됨
- [ ] `npm run build`가 경고 없이 통과

---

## 7. 코드·사이트 기여 (GitHub develop 플로우)

콘텐츠가 아닌 모든 것 — `src/`·`scripts/`·`sidebars.ts`·`docusaurus.config.ts`·`static/`·`i18n/`의 JSON·디자인 — 은 GitHub에서 작업합니다.

### 브랜치 전략 (main / develop)
코드 작업과 콘텐츠 자동 동기화를 분리합니다.

- **main** — 배포 브랜치. `deploy.yml`이 push마다 배포하고, **서버 crontab이 2분마다 콘텐츠(`docs/`·`docs_en/`·`static/img/`)를 자동 commit/push**합니다. 사람이 직접 작업하지 않습니다.
- **develop** — 상시 통합 브랜치. 모든 기능개선·버그픽스가 모입니다. 배포되지 않으므로 검증은 로컬 `npm run build && npm run serve`.

```
[기능]   feature/* ──PR+CI(squash)──▶ develop ──PR+CI(merge)──▶ main ──▶ 배포
[핫픽스] hotfix/*  ──────PR+CI───────────────────────────────▶ main ──▶ 배포
                                                                  └─(백머지)─▶ develop
[흡수]   main ──(sync-develop.yml 매일)──▶ develop
```

- **명명**: `feature/<kebab>`, `hotfix/<kebab>`, `chore/<kebab>` (커밋 type prefix와 동일)
- **머지 전략**: `feature→develop` = Squash, `develop→main` = Merge commit, `hotfix→main` = Squash(작으면)
- **hotfix는 develop을 거치지 않습니다** — develop의 미완성 기능이 동반 배포되는 것을 막기 위해 main에 직접 PR하고, 머지 후 develop으로 백머지합니다.
- 모든 PR은 `pr-build.yml`(`npm run build`)을 통과해야 머지합니다. **GitHub Settings → Branches에서 main·develop에 "Require status checks(pr-build) 통과 필수" 보호 규칙을 켜야** 강제됩니다. main 머지 직전엔 `git pull --rebase origin main`(서버 자동 push 레이스 방지).
- main의 최신 콘텐츠를 develop에 즉시 흡수하려면 `scripts/sync-develop.sh`(수동) 또는 `sync-develop.yml`(매일 자동).

### 커밋 메시지 (Conventional Commits, 한국어)
현재 리포의 관행을 룰화합니다.

```
<type>(<scope>): <한국어 변경 요약>
```

- `type`: `feat`, `fix`, `docs`, `chore`, `refactor`, `ci`, `style`, `perf` 중 하나
- `scope`: 영향 범위 (`home`, `brand`, `blog`, `docs`, `i18n`, `ci`, `infra` 등). 없으면 생략 가능.
- 본문은 한국어, 명령형(`~한다` / `~추가`).
- 예시 (실제 커밋 패턴):
  - `feat(brand): 로고·파비콘·OG 이미지 적용`
  - `feat(home): 홈페이지 Hero·KPI·서비스 카드 리디자인`
  - `feat: 커스텀 도메인(doc.scenemaker.solbox.com) 설정`

### PR
- 제목은 커밋 메시지와 동일한 컨벤션을 따릅니다.
- 본문은 다음 4개 섹션을 최소 포함:
  ```markdown
  ## 변경 사항
  ## 동기·맥락
  ## 검증
  - [ ] `npm run build` 통과
  - [ ] 영향받는 페이지 로컬에서 확인
  ## 관련
  ```
- WIP 단계는 **Draft PR** 로 둡니다.
- 단일 PR 크기 가이드: 같은 맥락의 변경만. 콘텐츠와 인프라(코드) 변경은 분리합니다.

---

## 8. 리뷰 · 머지 · 검증

### 단일 메인테이너 정책 (현 단계)
- 현재 단일 메인테이너 운영입니다. 외부 리뷰어가 없으므로 **셀프 리뷰 체크리스트 + CI 통과**가 머지 조건입니다.
- 외부 기여자가 합류하는 시점에 본 섹션을 재정의합니다.

### 셀프 리뷰 체크리스트 (머지 전 본인이 확인)
- [ ] `npm run typecheck` 통과 (코드 변경이 포함된 경우)
- [ ] `npm run build` 통과 — 깨진 내부 링크 없음
- [ ] 변경이 올바른 경로에 있는가 (코드=GitHub / 콘텐츠=Notion, §1)
- [ ] 수동 추가 문서라면 frontmatter 필수 항목이 모두 있는가 (§2.3)
- [ ] 외부 OSS 기여라면 Notion contribute DB에 항목을 추가했는가 (§4)
- [ ] PR 본문의 4개 섹션이 채워졌는가
- [ ] README/CLAUDE 등 **루트 `.md`의 내부 링크**는 빌드가 잡지 않으니 직접 확인했는가

### CI
- **PR 게이트**: `pr-build.yml`이 main·develop 대상 PR에서 `npm run build`를 돌립니다. 통과해야 머지(브랜치 보호 규칙으로 강제).
- **배포**: `deploy.yml`이 `main` push 시 자동 빌드·배포합니다.
- **콘텐츠 흡수**: `sync-develop.yml`이 매일 main→develop을 머지합니다.
- **빌드가 실패하면 사이트는 갱신되지 않습니다.** 이전 배포가 유지되므로 운영 중단은 아니지만, 의도한 변경은 반영되지 않습니다. CI 빨간불 = 즉시 처리.

---

## 9. 자주 헷갈리는 1줄 룰

- **디자인 토큰의 단일 출처**는 `.aidocs/design.md`입니다(Revolut 스타일). 디자인 토큰과 홈페이지엔 적용됐고 전체 리디자인은 진행 중 — 컬러/타이포 변경 시 이 파일을 먼저 갱신합니다.
- **배포**: `main` push = 자동 배포. 다른 트리거는 없습니다.
- **정적 자산**(`static/img/`): 출처가 외부인 이미지는 같은 폴더의 `CREDITS.md`에 출처·라이선스를 1줄 명기. 출처가 불명확한 자산은 커밋하지 않습니다.
- **`.docusaurus/`, `build/`, `node_modules/`** 는 커밋하지 않습니다 (`.gitignore` 적용 중).
- **`docusaurus.config.ts`의 `url` / `baseUrl` / `organizationName` / `projectName`** 변경은 배포 도메인·RSS 절대 URL에 직접 영향. 변경 후 즉시 프로덕션을 확인합니다.

---

## 10. 이 가이드 자체의 변경

이 문서가 현실과 충돌하기 시작하면 그것이 첫 번째 우선순위 PR입니다. 룰이 일을 막으면 룰을 고칩니다.

문의: **minsung7336@solbox.com**
