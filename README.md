# SceneMakerAI · docs-web

> 오픈소스 AI 기반 방송 콘텐츠 재가공 프로젝트 **SceneMakerAI**의 기술 블로그 및 문서 사이트

[![Built with Docusaurus](https://img.shields.io/badge/Built%20with-Docusaurus%203-3ECC5F?logo=docusaurus&logoColor=white)](https://docusaurus.io/)
[![License](https://img.shields.io/badge/License-TBD-lightgrey.svg)]()
[![Node](https://img.shields.io/badge/Node-%E2%89%A520-339933?logo=node.js&logoColor=white)]()

운영 사이트: **https://doc.scenemaker.solbox.com**

---

## 📖 소개

본 저장소는 **솔박스(Solbox Inc.)**가 수행하는 *2026년 오픈소스 AI·SW 개발·활용 지원사업*(NIPA) 국책과제 **SceneMakerAI**의 **공개 기술 블로그 및 문서 사이트**입니다.

오픈소스 멀티모달 LLM 위에 4가지 방송 도메인 AI 서비스를 제공합니다.

| 서비스 | 목적 |
| --- | --- |
| **모아보기** | 방송 전체에서 핵심 구간 자동 선별 |
| **리믹스** | 자동 하이라이트 탐지로 숏폼 생성 |
| **광고** | 맥락 기반 광고 매칭 |
| **Batch** | 대규모 배치 분석 파이프라인 |

공개 산출물: **기술 블로그**(목표 20+건) · **문서**(아키텍처 / 운영 가이드 / 오픈소스 기여 인덱스, 업스트림 기여 30+건 목표).

---

## 🧱 기술 스택

| 구분 | 도구 |
| --- | --- |
| 정적 사이트 생성기 | **Docusaurus 3.10.1** (TypeScript) |
| 런타임 | React 19 |
| 언어 | **한국어(원본)** + English (i18n, DeepL 자동 번역) |
| 콘텐츠 소스 | **Notion DB** → 서버 crontab 자동 동기화 |
| 호스팅 | GitHub Pages (커스텀 도메인 `doc.scenemaker.solbox.com`) |
| CI/CD | GitHub Actions (`main` push 시 자동 빌드·배포) |
| 검색 | Algolia DocSearch (적용 예정) |

---

## 🗂 디렉토리 구조

```
docs-web/
├── docs/                  # KR 원본 문서 (Notion 자동 동기화)
│   ├── about/  architecture/  blog/  contribute/
│   └── guide/  install/  poc/  release-notes/
├── docs_en/               # EN 번역본 (실파일 위치, DeepL 자동 번역)
├── i18n/en/
│   ├── docusaurus-plugin-content-docs/current → ../../../docs_en   (symlink)
│   ├── docusaurus-theme-classic/{navbar,footer}.json
│   └── code.json
├── src/
│   ├── pages/index.tsx    # 홈페이지 (Hero · Features · KPI)
│   ├── components/        # HomepageFeatures, HomepageKPI
│   └── css/custom.css     # 디자인 토큰
├── static/                # 정적 자원 (img/, CNAME)
├── scripts/               # Notion 동기화 · DeepL 번역 파이프라인
│   ├── notion_to_docs_generic.py
│   ├── translate_to_en.py
│   └── server-sync.sh     # 서버 crontab 진입점 (실 운영)
├── .github/workflows/     # deploy · pr-build · sync-develop · notion-sync
├── docusaurus.config.ts
└── sidebars.ts            # 8개 사이드바
```

상세 구조·운영 노트는 [CLAUDE.md](./CLAUDE.md), 기여 룰은 [CONTRIBUTING.md](./CONTRIBUTING.md) 참조.

---

## 🚀 빠른 시작

요구: **Node.js ≥ 20**

```bash
npm install
npm start              # KR dev 서버 → http://localhost:3000
npm run start:en       # EN dev 서버 → http://localhost:3002/en/
npm run build          # 프로덕션 빌드 (양쪽 로케일)
npm run serve          # build/ 결과 로컬 서빙 (한 서버에서 양쪽 확인)
```

> Docusaurus dev 서버는 한 번에 한 로케일만 띄웁니다(HMR 제약). 양쪽을 한 서버에서 보려면 `npm run build && npm run serve`.

---

## 🌐 i18n

- **한국어가 원본**, 영어는 번역본입니다. 번역이 없으면 KR로 자동 fallback.
- EN 실파일은 **`docs_en/`**에 있고, `i18n/en/.../current`가 이를 가리키는 **symlink**입니다 (방향 주의 — [dev-docs/i18n.md](./dev-docs/i18n.md)).
- `scripts/translate_to_en.py`가 변경된 KR 문서를 DeepL로 자동 번역합니다.
- 네비/푸터/UI 라벨은 `i18n/en/`의 JSON으로 번역합니다.

---

## 📥 콘텐츠 동기화 (Notion)

콘텐츠 원본은 **Notion DB**이며, 서버 crontab이 2분 주기로 동기화합니다.

```
Notion DB ──(notion_to_docs_generic.py)──▶ docs/ ──(translate_to_en.py · DeepL)──▶ docs_en/ ──▶ main push ──▶ 배포
```

- 실 운영: `scripts/server-sync.sh` (서버 crontab 2분 주기)
- 수동 백업: `.github/workflows/notion-sync.yml` (`workflow_dispatch`)
- 상세: [dev-docs/notion-sync.md](./dev-docs/notion-sync.md)

---

## 🌿 브랜치 전략

- **main** — 배포 + Notion 자동 동기화 (사람이 직접 작업하지 않음)
- **develop** — 상시 통합 브랜치. `feature/*` → develop → main 순으로 PR하며, `pr-build` 빌드를 통과해야 머지합니다. develop은 로컬 빌드로 검증합니다.

**다이어그램·hotfix 경로·머지 전략 등 상세는 [CONTRIBUTING.md §7](./CONTRIBUTING.md#7-코드사이트-기여-github-develop-플로우)**.

---

## 🎯 과제 목표

| 지표 | 목표 |
| --- | --- |
| 오픈소스 기여 | 누적 **30건+** (PR · Issue · 데이터셋) |
| 기술 블로그 | 누적 **20건+** (월 2건+) |
| 추론 처리 성능 | 1시간 방송 → **20분 이하** |
| 장면 분류 F1 | **≥ 0.70** (40–60분) |

---

## 🤝 기여 · 라이선스

- 기여 룰: [CONTRIBUTING.md](./CONTRIBUTING.md)
- 라이선스: 콘텐츠 **CC BY 4.0** / 코드 **Apache 2.0** (확정 예정)
- 문의: **minsung7336@solbox.com**

## 🔗 링크

- 주관: [Solbox Inc.](https://solbox.com)
- 기반 모델: [Qwen (Hugging Face)](https://huggingface.co/Qwen)
- 프레임워크: [Docusaurus](https://docusaurus.io/)
