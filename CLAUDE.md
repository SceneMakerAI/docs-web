# CLAUDE.md — docs-web 작업 가이드 (허브)

SceneMakerAI 기술 문서 사이트의 작업 가이드이자 **문서 인덱스**다. 작업 대부분은 콘텐츠(Markdown)·EN 번역이지만, 사이트 코드(`src/`·`scripts/`·설정)의 유지보수·기능개선도 포함한다. **콘텐츠는 Notion에서 `main`으로 자동 동기화**되고, **코드 작업은 [브랜치 전략](#-브랜치-전략-요약)(main/develop)**을 따른다.

---

## 📚 문서 맵

| 무엇을 찾나 | 문서 |
|------------|------|
| 외부 첫인상 · 빠른 시작 · 포인터 | [README.md](./README.md) |
| 기여 룰 · **브랜치 전략(상세·다이어그램)** · 릴리즈 룰 | [CONTRIBUTING.md](./CONTRIBUTING.md) |
| 디렉토리 구조 · slug 시스템 · 빌드 게이트 · 사이드바 · 콘텐츠 추가 | [dev-docs/codebase.md](./dev-docs/codebase.md) |
| i18n 메커니즘 (symlink · DeepL · EN 파일 규칙) | [dev-docs/i18n.md](./dev-docs/i18n.md) |
| Notion 동기화 (서버 crontab · DB 매핑 · 내부 로직) | [dev-docs/notion-sync.md](./dev-docs/notion-sync.md) |
| 디자인 토큰 (Revolut 스타일) | [.aidocs/design.md](./.aidocs/design.md) |

> 이 파일(CLAUDE.md)은 **허브**다 — 프로젝트 컨텍스트 + 핵심 함정 + 자주 쓰는 것만 담고, 상세는 위 문서로 위임한다.

---

## 환경

프로젝트가 무엇을 하는지(4대 서비스·KPI 등)는 [README](./README.md) 참조. 여기엔 작업에 필요한 사실만 둔다.

- 운영 URL: `https://doc.scenemaker.solbox.com`
- GitHub: `https://github.com/SceneMakerAI/docs-web`
- 기술 스택: **Docusaurus 3.10.1** (React 19, TypeScript 6)
- 기본 언어: 한국어(KR), 번역: 영어(EN)
- 콘텐츠 원본: **Notion DB** → 서버 crontab(2분 주기)이 `main`으로 자동 동기화 (GitHub Actions `notion-sync.yml`은 수동 백업)

---

## ⚠️ 핵심 함정 (작업 전 반드시)

작업 중 가장 자주 부딪히는 메커니즘. 상세는 각 dev-docs 참조.

- **symlink 방향** — `i18n/.../current → docs_en` (반대로 만들면 빌드 라우팅 깨짐). → [i18n.md](./dev-docs/i18n.md)
- **한글 파일명은 정상** — `notion_to_docs_generic.py` slugify가 한글 제목을 보존하고, URL은 `slug: "숫자"`로 따로 잡힌다. 수동 파일만 kebab-case. → [codebase.md](./dev-docs/codebase.md)
- **`onBrokenLinks: 'throw'`** — 깨진 내부 링크 = 빌드 실패. PR 전 `npm run build` 필수.
- **서버 crontab 2분 push** — main에 콘텐츠가 2분마다 자동 commit/push된다. main 관련 작업 직전 `git pull --rebase origin main`. → [notion-sync.md](./dev-docs/notion-sync.md)
- **`_category_.json`** — 서브디렉토리는 sync가 자동 생성(수동 수정은 다음 sync에 덮어씌워짐). 부모 `index.md`에 `id:` 추가 금지(파일 경로 기반 ID와 충돌).
- **수동 `git mv`로 KR 파일명 변경 시** — 대응 EN 파일도 함께 옮길 것. (Notion sync를 통한 rename은 old 삭제를 `git diff -D`가 잡아 EN까지 자동 처리되지만, 사람이 직접 `git mv`하면 자동 감지 밖이라 stale EN이 남는다.)

---

## 🌿 브랜치 전략 (요약)

콘텐츠(Notion 자동 동기화)와 코드 작업을 **main/develop 2개 브랜치**로 분리한다.

- **main** — 배포 + 서버 crontab 콘텐츠 자동 commit/push. **사람이 직접 작업하지 않는다.**
- **develop** — 상시 통합 브랜치. 모든 기능개선·버그픽스가 모인다. 배포되지 않으므로 검증은 로컬 `npm run build && npm run serve`.
- `feature/*` → PR → **develop** → PR → **main** → 배포
- `hotfix/*`는 develop을 거치지 않고 **main에 직접 PR** 후 develop으로 백머지(미완성 기능 동반 배포 방지).
- 모든 PR은 `pr-build.yml`(빌드)을 통과해야 머지(브랜치 보호 규칙으로 강제).

> **다이어그램·머지 전략·역방향 흡수 등 상세는 [CONTRIBUTING.md §7](./CONTRIBUTING.md#7-코드사이트-기여-github-develop-플로우)**.

---

## 자주 쓰는 명령어

| 명령어 | 용도 |
|--------|------|
| `npm start` | KR dev 서버 (port 3000) |
| `npm run start:en` | EN dev 서버 (port 3002) |
| `npm run build` | 프로덕션 빌드 (KR + EN 동시) |
| `npm run serve` | build/ 결과 로컬 서빙 |
| `npm run clear` | Docusaurus 캐시 정리 |
| `npm run typecheck` | TypeScript 타입 체크 |
| `npm run write-translations:en` | EN 번역 JSON 골격 재생성 |

---

## 🚫 하지 말 것

- `docusaurus.config.ts`의 `url` / `baseUrl` / `organizationName` / `projectName` 임의 변경 금지 (GH Pages 배포와 RSS 절대 URL에 직접 영향)
- `onBrokenLinks: 'throw'`를 `'warn'`으로 낮추지 말 것
- EN 번역 만든다고 KR 원본(`docs/`)을 영어로 덮어쓰지 말 것
- `i18n/en/.../current` 를 real directory로 바꾸지 말 것 (symlink여야 함 — [i18n.md](./dev-docs/i18n.md))
- `.docusaurus/`, `build/`, `node_modules/` 커밋 금지
- `_category_.json` 서브디렉토리 수동 편집 금지(sync가 덮어씀), 부모 `index.md`에 `id:` 금지 — [codebase.md](./dev-docs/codebase.md) · 위 핵심 함정 참조
