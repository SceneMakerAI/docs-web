# SceneMakerAI · docs-web 기여 가이드

이 문서는 **"무엇을 어디에 어떻게 올리는가"의 결정 룰과 수용 기준**을 정의합니다.
설치·실행·번역 추가 절차 등 *how-to*는 [README.md](./README.md)를 참조하세요.

원칙은 단 한 줄입니다.

> **"링크가 안 깨지고 빌드가 통과하면, 메인테이너 셀프 리뷰 후 머지한다."**

`docusaurus.config.ts`에 `onBrokenLinks: 'throw'`가 걸려 있어 깨진 내부 링크는 빌드 자체를 실패시킵니다. 이것이 사실상 자동 강제되는 유일한 룰이며, 아래의 모든 규칙은 이를 떠받치기 위한 결정 기준입니다.

---

## 1. 콘텐츠 라우팅 — 이 글은 어디에 가는가?

작성하려는 글이 다음 중 어디에 해당하는지 먼저 정합니다. 헷갈리면 위에서부터 매칭되는 첫 번째 항목을 따릅니다.

| 글의 성격 | 위치 | 예시 |
| --- | --- | --- |
| **시점이 있는 회고/실험/공지** (날짜에 의미가 있다) | `blog/` | "Qwen3.5 VLM 방송 도메인 적용기", "1Q 리뷰" |
| **변하지 않는 사용/운영 방법** | `docs/guide/` | "SceneMakerAI 시작하기", "장애 대응 매뉴얼" |
| **시스템 설계·데이터 흐름·기술 의사결정** | `docs/architecture/` | "vLLM 클러스터 토폴로지", "LangGraph 워크플로우" |
| **외부 OSS 기여 인덱스·관련 저장소 링크** | `docs/contribute/` | Qwen에 올린 PR 링크, 데이터셋 공개 |
| **릴리즈 노트** (4대 서비스 버전 단위 변경) | `docs/release-notes/` | `v0.1.0.md`, `v0.2.0-aurora.md` |
| **사이트 자체 페이지** (정보 구조의 일부, 사이드바 밖) | `src/pages/` | `/about`, `/` 랜딩 |

판단이 안 서면 **`blog/`** 가 기본값입니다. 가치 있는 글이 docs에 안 가는 것보다, blog에 올라가서 발견되는 편이 낫습니다. 시간이 지나 "이건 docs로 옮기는 게 맞다"고 판단되면 그때 이관합니다.

---

## 2. 문서(`docs/`) 룰

### 파일 위치 · 명명
- `docs/{guide,architecture,contribute}/` 중 하나의 하위에 `.md` 또는 `.mdx`로 둡니다.
- 파일명은 **kebab-case** (`vllm-cluster.md`), 한글 파일명 금지.
- 한 폴더가 5개를 넘으면 하위 카테고리(`docs/architecture/inference/...`)로 분리하고 `_category_.json`을 추가합니다.

### 필수 frontmatter
```yaml
---
id: <파일명과 동일한 슬러그>
title: <한국어 문서 제목>
sidebar_position: <폴더 내 정렬, 1부터>
slug: /<섹션>/<id>           # 예: /architecture/vllm-cluster
description: <한 줄 SEO 설명>
---
```

### 새 카테고리 추가
- 폴더 생성 시 `_category_.json`을 함께 둡니다 (`docs/architecture/_category_.json` 참고).
- `link.type`은 `generated-index`를 기본으로 합니다. 별도 인덱스 페이지가 필요하면 `doc`으로 바꾸고 해당 문서를 작성합니다.

### 수용 기준
- [ ] frontmatter 5개 항목(`id`, `title`, `sidebar_position`, `slug`, `description`) 모두 채워짐
- [ ] 본문에 H1(`#`)을 별도로 쓰지 않음 (frontmatter `title`이 H1을 생성)
- [ ] 내부 링크는 `/docs/<섹션>/<id>` 절대 경로 또는 같은 폴더 내 상대 경로
- [ ] `npm run build`가 통과 (= 깨진 링크 없음)

---

## 3. 블로그(`blog/`) 룰

### 게시 주기 (KPI 직결)
- 과제 목표: **블로그 누적 20+건**, **월 2건 이상**. 최소 격주 게시를 권장합니다.
- 회고/실험 결과/오픈소스 기여 노트는 가능한 한 blog로 먼저 공개합니다.

### 파일 명명
```
blog/YYYY-MM-DD-kebab-case-slug.mdx
```
예: `blog/2026-06-15-qwen-vlm-broadcast.mdx`

날짜는 게시 예정일을 기준으로 합니다. 같은 날 여러 글을 올릴 일은 거의 없지만, 발생 시 슬러그로 구분합니다.

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
- 리드 끝에 **반드시** `<!-- truncate -->` 마커를 넣습니다 (블로그 목록에서 노출되는 분량의 컷).
- 마커가 없으면 빌드 시 경고(`onUntruncatedBlogPosts: 'warn'`)가 떨어집니다.

### 저자(`blog/authors.yml`)
- 글을 올리기 전, 본인 키가 `authors.yml`에 없으면 추가합니다.
- 신규 저자 항목 최소 필드: `name`, `title`, `url`, `image_url`, `page: true`, `socials.github`.
- 인라인 저자(`authors: [{name: ..., title: ...}]`)는 사용하지 않습니다 (`onInlineAuthors: 'warn'` 정책).

### 태그
- 태그는 `tags.yml`에서 관리되는 항목만 사용합니다. 새 태그가 필요하면 `blog/tags.yml`에 정의를 추가한 뒤 사용합니다.
- 인라인 태그(`tags: ['처음쓰는태그']`)는 사용하지 않습니다 (`onInlineTags: 'warn'` 정책).
- 태그는 **주제**(qwen, vllm, langgraph, dataset) 또는 **활동 유형**(retro, experiment, contribution) 중 하나로 작명. 너무 일반적인 태그(`ai`, `ml`)는 지양.

### 수용 기준
- [ ] 파일명·`slug`·`date` 세 곳의 날짜·슬러그가 일치
- [ ] `<!-- truncate -->` 마커 존재
- [ ] `authors`가 `authors.yml`에 등록된 키
- [ ] `tags`가 `tags.yml`에 정의됨
- [ ] `npm run build`가 경고 없이 통과

---

## 4. i18n 룰

기본 정책은 README의 i18n 섹션에 정리되어 있습니다 — 룰 측면에서의 결정 사항만 정리합니다.

- **한국어가 원본**입니다. 한국어를 먼저 쓰고, 영어는 뒤따라옵니다.
- **영어 번역은 선택적**입니다. 번역이 없는 콘텐츠는 자동으로 한국어 원본으로 fallback됩니다.
- 영어 번역 우선순위:
  1. `docusaurus.config.ts`의 네비/푸터 라벨 (사이트 전역 노출)
  2. `intro.mdx`, `about.mdx`, 각 섹션 `overview.md` (entry point)
  3. KPI에 직결되는 핵심 블로그 글 (오픈소스 커뮤니티에 외부 인용될 가능성이 있는 글)
  4. 나머지
- 영어 번역을 추가했다면 PR 설명에 *"i18n: ko 추가/수정에 대응하는 en 번역 포함"* 또는 *"i18n: en 번역 보류(추후 일괄)"* 중 하나를 명시합니다. 빠뜨림과 의도적 미작성을 구분하기 위함입니다.

명령어·디렉토리 구조는 [README — i18n 워크플로우](./README.md#-i18n-워크플로우) 참조.

---

## 5. 외부 오픈소스 기여 로깅 룰 (KPI 직결)

과제 목표는 **누적 30건 이상의 외부 OSS 기여**입니다. 모든 외부 기여는 사이트에 반드시 흔적을 남깁니다.

- **외부 PR / Issue / Discussion / 데이터셋 공개**가 머지/공개되는 즉시, `docs/contribute/overview.md`(또는 카테고리 인덱스)에 **한 줄 항목**을 추가합니다.
- 한 줄 형식 예:
  ```markdown
  - [vLLM] `flash-attn` MoE 라우팅 버그 수정 PR — [vllm-project/vllm#12345](https://github.com/vllm-project/vllm/pull/12345) (2026-06-12, merged)
  ```
- 항목에는 다음을 포함합니다: **업스트림 프로젝트명**, **요약**, **링크**, **날짜**, **상태**(open / merged / closed / released).
- 기여에 별도 회고가 필요하면 blog 글을 함께 작성하고, 인덱스 항목에서 블로그를 링크합니다.

이 룰은 강제됩니다 — 외부 기여 PR을 머지했는데 `docs/contribute/`에 항목이 없다면, **이 사이트의 KPI 카운트에 포함되지 않은 것으로 간주**합니다.

---

## 6. 브랜치 · 커밋 · PR 룰

### 브랜치
- `main` 외 모든 작업은 별도 브랜치에서 진행합니다.
- 명명: **`type/short-kebab-desc`**
  - `feat/blog-qwen-vlm`, `docs/architecture-vllm-cluster`, `chore/template-cleanup`, `fix/broken-intro-link`
- type은 커밋 컨벤션과 동일한 prefix를 씁니다.

### 커밋 메시지 (Conventional Commits, 한국어)
현재 리포의 관행을 룰화합니다.

```
<type>(<scope>): <한국어 변경 요약>
```

- `type`: `feat`, `fix`, `docs`, `chore`, `refactor`, `ci`, `style`, `perf` 중 하나
- `scope`: 영향 범위 (`blog`, `docs`, `intro`, `i18n`, `ci`, `infra` 등). 없으면 생략 가능.
- 본문은 한국어, 명령형(`~한다` / `~추가`).
- 예시 (기존 커밋 패턴):
  - `docs(intro): Docusaurus 튜토리얼 본문을 SceneMakerAI 임시 소개로 교체`
  - `chore(blog): Docusaurus 기본 템플릿 잔재 제거 및 임시 저자 교체`
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
- 단일 PR 크기 가이드: 문서 1편 또는 같은 맥락의 변경만. 콘텐츠와 인프라 변경은 분리합니다.

---

## 7. 리뷰 · 머지 · 검증

### 단일 메인테이너 정책 (현 단계)
- 현재 단일 메인테이너 운영입니다. 외부 리뷰어가 없으므로 **셀프 리뷰 체크리스트 + CI 통과**가 머지 조건입니다.
- 외부 기여자가 합류하는 시점에 본 섹션을 재정의합니다.

### 셀프 리뷰 체크리스트 (머지 전 본인이 확인)
- [ ] `npm run typecheck` 통과 (코드 변경이 포함된 경우)
- [ ] `npm run build` 통과 — 깨진 내부 링크 없음, `onUntruncatedBlogPosts` / `onInlineAuthors` / `onInlineTags` 경고 없음
- [ ] 라우팅 룰(§1)에 맞는 위치에 콘텐츠가 있는가
- [ ] frontmatter 필수 항목이 모두 있는가 (§2 또는 §3)
- [ ] 외부 OSS 기여 PR이라면 `docs/contribute/`에 항목을 추가했는가 (§5)
- [ ] 신규 저자/태그라면 `authors.yml` / `tags.yml`에 등록했는가
- [ ] PR 본문의 4개 섹션이 채워졌는가

### CI
- `.github/workflows/`의 GitHub Actions가 `main` push 시 자동 빌드·배포합니다.
- **빌드가 실패하면 사이트는 갱신되지 않습니다.** 이전 배포가 그대로 유지되므로 운영 중단은 아니지만, 의도한 변경은 반영되지 않습니다. CI 빨간불 = 즉시 처리.

---

## 8. 릴리즈 노트 룰

릴리즈 노트는 **SceneMakerAI 프로젝트(4대 서비스: 모아보기·리믹스·광고·Batch)** 의 버전 단위 공식 발표 기록입니다. docs-web 사이트 자체의 변경은 대상이 아니며 — [GitHub Release](https://github.com/SceneMakerAI/docs-web/releases) 또는 `git log`로 갈음합니다.

### 버전 명명
- **SemVer**(`vMAJOR.MINOR.PATCH`)를 따릅니다.
  - MAJOR: 호환성 깨지는 변경 / MINOR: 호환되는 기능 추가 / PATCH: 호환되는 버그 수정.
- 4대 서비스는 **통합 버전**으로 운영합니다 (서비스별 분리 운영이 필요해지는 시점에 본 룰 재정의).
- 코드명을 붙이려면 hyphen suffix: `v0.1.0-aurora.md`.

### 파일 위치 · 명명
- `docs/release-notes/<버전>.md` — 예: `docs/release-notes/v0.1.0.md`
- 파일명 = frontmatter `id` = slug 마지막 세그먼트. 셋 모두 일치시킵니다.

### 정렬 (사이드바)
Docusaurus 사이드바는 알파벳 정렬이라 `v0.10.0` < `v0.9.0` 문제가 발생합니다. **반드시 `sidebar_position`을 명시**하여 최신 릴리즈가 위에 오게 합니다.
- `overview.md` = `sidebar_position: 0` (고정)
- 가장 최신 릴리즈 = `sidebar_position: 1`
- 새 릴리즈를 추가할 때 기존 릴리즈들의 `sidebar_position`을 모두 +1 갱신

### 필수 frontmatter
```yaml
---
id: v0.1.0
title: v0.1.0 — <한 줄 요약 또는 코드명>
sidebar_position: 1
slug: /release-notes/v0.1.0
description: <한 줄 SEO 설명>
date: YYYY-MM-DD
---
```

### 본문 구조 (Keep a Changelog 적용)
다음 섹션을 **순서대로** 사용하며, 해당 항목이 없으면 섹션 자체를 생략합니다.

```markdown
## 요약 (1~3줄)

## 호환성
- 마이그레이션 필요 여부 · 영향 받는 API/설정 · 다운그레이드 안전성
- 변경 없으면 "변경 없음" 한 줄로 명시

## 서비스별 변경
### 모아보기
- ...
### 리믹스
- ...
### 광고
- ...
### Batch
- ...

## 의존성 변경
- Qwen ... / vLLM ... / LangGraph ... / faster-whisper ... 등

## 알려진 이슈

## 기여자
- @<github-handle>, ...
```

### 머지 · 게시 시점
- 릴리즈 노트 PR은 **해당 버전의 릴리즈 태그가 찍히는 시점에 함께 머지**합니다 (별도 PR이어도 같은 날).
- 사후 보강은 PATCH 릴리즈(`v0.1.1`)로 분리하거나, 본문 끝에 `## 갱신 이력` 섹션을 추가합니다 — 이미 발표된 본문을 무성의하게 덮어쓰지 않습니다.

### 수용 기준
- [ ] 최신 릴리즈의 `sidebar_position: 1` 보장 (기존 릴리즈 모두 +1 갱신)
- [ ] `slug`가 `/release-notes/<버전>` 형식
- [ ] 본문에 "호환성" 섹션 존재 (해당 없음이면 "변경 없음" 명시)
- [ ] 릴리즈에 포함된 외부 OSS 기여가 `docs/contribute/` 인덱스에 누락되지 않음 (§5)
- [ ] `npm run build` 통과

---

## 9. 자주 헷갈리는 1줄 룰

- **디자인 토큰의 단일 출처**는 `.aidocs/design.md` 입니다. 본격 적용·세부 룰은 별도 PR에서 확정합니다 — 지금은 컬러/타이포 변경 시 이 파일을 먼저 갱신한다는 것만 기억하면 됩니다.
- **배포**: `main` push = 자동 배포. 다른 트리거는 없습니다.
- **정적 자산**(`static/img/`): 출처가 외부인 이미지는 파일과 같은 폴더의 `CREDITS.md`에 출처·라이선스를 1줄 명기. 출처가 불명확한 자산은 커밋하지 않습니다.
- **`.docusaurus/`, `build/`, `node_modules/`** 는 커밋하지 않습니다 (`.gitignore` 적용 중).
- **`docusaurus.config.ts`의 `url` / `baseUrl` / `organizationName` / `projectName`** 변경은 배포 도메인에 직접 영향. 변경 PR은 본인 외에 한 명 더 확인하거나, 변경 후 즉시 프로덕션 확인.

---

## 10. 이 가이드 자체의 변경

이 문서가 현실과 충돌하기 시작하면 그것이 첫 번째 우선순위 PR입니다. 룰이 일을 막으면 룰을 고칩니다.

문의: **minsung7336@solbox.com**
