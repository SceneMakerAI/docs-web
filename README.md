# SceneMakerAI · docs-web

> 오픈소스 AI 기반 방송 콘텐츠 재가공 프로젝트 **SceneMakerAI**의 기술 블로그 및 문서 사이트

[![Built with Docusaurus](https://img.shields.io/badge/Built%20with-Docusaurus%203-3ECC5F?logo=docusaurus&logoColor=white)](https://docusaurus.io/)
[![License](https://img.shields.io/badge/License-TBD-lightgrey.svg)]()
[![Node](https://img.shields.io/badge/Node-%E2%89%A520-339933?logo=node.js&logoColor=white)]()

---

## 📖 소개

본 저장소는 **솔박스(Solbox Inc.)** 가 수행하는 *2026년 오픈소스 AI·SW 개발·활용 지원사업*
국책과제의 **공개 기술 블로그 및 문서 사이트**입니다.

본 과제(**SceneMakerAI**)는 오픈소스 기반 모델 위에 4 가지 방송 도메인 AI
서비스를 제공합니다.

| 서비스 | 목적 |
| ------ | ---- |
| **모아보기** | 방송 전체에서 핵심 구간 자동 선별 |
| **리믹스** | 자동 하이라이트 탐지를 통한 숏폼 생성 |
| **광고** | 맥락 기반 광고 매칭 |
| **Batch** | 대규모 배치 분석 파이프라인 |

본 사이트는 과제 산출물 중 다음 두 가지를 공개합니다.

- **기술 블로그** — 격주 정기 게시 (목표 **20건 이상**)
- **문서** — 아키텍처, 운영 가이드, 오픈소스 기여 인덱스 (목표 **30건 이상의 업스트림 기여** 링크)

---

## 🧱 기술 스택

| 구분 | 도구 | 비고 |
| ---- | ---- | ---- |
| 정적 사이트 생성기 | **Docusaurus 3** (TS) | 문서/블로그/i18n/MDX 일급 지원 |
| 프론트엔드 런타임 | React 19 | — |
| 언어 | **한국어(기본)** + **English** (i18n) | 국내 + 글로벌 커뮤니티 동시 어필 |
| 호스팅 (예정) | GitHub Pages | 무료, GitHub 워크플로우와 자연스럽게 연동 |
| CI/CD (예정) | GitHub Actions | `main` push 시 자동 빌드·배포 |
| 검색 (예정) | Algolia DocSearch (오픈소스 플랜) | 오픈소스 문서에 무료 |

---

## 🗂 디렉토리 구조

```
docs-web/
├── blog/                              # 📝 기술 블로그 글 (한국어 원본)
│   ├── 2019-05-28-first-blog-post.mdx       # (Docusaurus 샘플 — 추후 제거)
│   ├── authors.yml
│   └── tags.yml
│
├── docs/                              # 📘 문서 (한국어 원본)
│   ├── intro.mdx                            # 문서 첫 페이지
│   ├── guide/                               # 사용/운영 가이드
│   │   └── overview.md
│   ├── architecture/                        # 시스템 아키텍처
│   │   ├── _category_.json
│   │   └── overview.md
│   ├── contribute/                          # 오픈소스 기여 인덱스
│   │   ├── _category_.json
│   │   └── overview.md
│   └── tutorial-basics/, tutorial-extras/   # (Docusaurus 샘플 — 추후 제거)
│
├── src/
│   ├── pages/                         # 🧩 자유 React/MDX 페이지
│   │   ├── index.tsx                       # 사이트 랜딩 페이지 (/)
│   │   ├── about.mdx                       # /about — 프로젝트 소개
│   │   └── markdown-page.mdx               # (샘플)
│   ├── components/                    # 커스텀 React 컴포넌트 (차트 등)
│   └── css/custom.css                 # 전역 스타일
│
├── static/                            # 🖼  정적 자원 (그대로 서빙)
│   └── img/
│
├── i18n/                              # 🌐 번역
│   └── en/                            #   English 로케일
│       ├── code.json                        # UI 문구 (82개)
│       ├── docusaurus-theme-classic/        # 네비/푸터 번역
│       │   ├── navbar.json
│       │   └── footer.json
│       ├── docusaurus-plugin-content-docs/
│       │   ├── current.json                 # 사이드바 카테고리 라벨
│       │   └── current/                     # 영어 .md 문서 (docs/ 미러)
│       ├── docusaurus-plugin-content-blog/  # 영어 블로그 글
│       │   └── options.json
│       └── docusaurus-plugin-content-pages/ # 영어 자유 페이지
│
├── docusaurus.config.ts               # ⚙️  사이트 전체 설정
├── sidebars.ts                        # 📑 사이드바 정의 (3개 사이드바)
├── package.json
├── tsconfig.json
└── README.md                          # 👈 현재 파일
```

### 내비게이션 맵

```
좌측 메뉴                              우측 메뉴
├─ 블로그          → /blog              ├─ 🌐 언어 드롭다운
├─ 문서            → docsSidebar         └─ GitHub
├─ 아키텍처        → architectureSidebar
├─ 오픈소스 기여   → contributeSidebar
└─ 프로젝트 소개   → /about
```

---

## 🚀 빠른 시작

### 사전 요구사항

- **Node.js ≥ 20** (현재 v22 사용)
- **npm ≥ 10**

### 설치

```bash
git clone https://github.com/SceneMakerAI/docs-web.git
cd docs-web
npm install
```

### 로컬 개발

```bash
# 한국어 dev 서버 (기본 로케일)
npm start
# → http://localhost:3000

# 영어 dev 서버 (별도 포트)
npm run start:en
# → http://localhost:3002/en/
```

> ⚠️  Docusaurus dev 서버는 **한 번에 한 로케일만** 띄울 수 있습니다 (HMR 제약).
> 두 로케일을 동시에 보려면 두 터미널에서 각각 실행하거나,
> 아래 [빌드 & 미리보기](#-빌드--미리보기)로 한 서버에서 모두 확인하세요.

### 빌드 & 미리보기

```bash
# 양쪽 로케일을 ./build/ 에 빌드
npm run build

# 빌드 결과를 로컬에서 서빙 (한 서버에서 양쪽 모두 접근 가능)
npm run serve
# → http://localhost:3000          (한국어)
# → http://localhost:3000/en/      (English)
```

### 자주 쓰는 명령어

| 명령어 | 설명 |
| ------ | ---- |
| `npm start` | 한국어 dev 서버 시작 |
| `npm run start:en` | 영어 dev 서버 시작 (포트 3002) |
| `npm run build` | 프로덕션 빌드 (모든 로케일) |
| `npm run serve` | `build/` 결과를 로컬에서 서빙 |
| `npm run typecheck` | TypeScript 타입 체크 (빌드 X) |
| `npm run write-translations:en` | 영어 번역 JSON 파일 재생성 |
| `npm run clear` | Docusaurus 캐시 정리 |

---

## 🌐 i18n 워크플로우

### 동작 원리

1. **한국어가 원본**입니다. 원본 `.md` / `.mdx` 파일은 `docs/`, `blog/`, `src/pages/` 에 위치합니다.
2. **영어 번역**은 `i18n/en/docusaurus-plugin-content-*/` 아래에 같은 구조로 미러링합니다.
3. **영어 번역이 없는 콘텐츠는 한국어 원본으로 자동 fallback**됩니다. 따라서 번역은 점진적으로 추가해도 됩니다.

### 영어 번역 추가하기

```bash
# 1) 한국어 원본을 추가/수정한 뒤 영어 JSON 골격을 다시 생성
npm run write-translations:en

# 2) 새로 추가된 문자열을 영어로 번역:
#    i18n/en/code.json
#    i18n/en/docusaurus-theme-classic/{navbar,footer}.json
#    i18n/en/docusaurus-plugin-content-docs/current.json

# 3) 문서 전체를 번역할 때는 경로를 그대로 미러:
#    docs/architecture/overview.md
#      → i18n/en/docusaurus-plugin-content-docs/current/architecture/overview.md
```

### URL 레이아웃

| 로케일 | URL 프리픽스 |
| ------ | ------------ |
| 한국어 (기본) | `/` |
| English | `/en/` |

---

## ✍️ 콘텐츠 추가

### 새 블로그 글

```bash
# blog/ 에 날짜 패턴으로 새 MDX 파일 생성
touch blog/2026-06-15-qwen-vlm-broadcast.mdx
```

```mdx
---
slug: qwen-vlm-broadcast
title: Qwen3.5 VLM 방송 도메인 적용기
authors: [minsung]
tags: [qwen, vlm, broadcast]
date: 2026-06-15
---

본문은 truncate 마커 위까지 목록에 노출됩니다.

<!-- truncate -->

여기서부터는 상세 페이지에서만 보입니다.
```

### 새 문서 페이지

1. 적절한 폴더(`docs/guide/`, `docs/architecture/`, `docs/contribute/`)에 `.md` 또는 `.mdx` 파일 생성
2. 프론트매터 작성
   ```yaml
   ---
   id: my-page
   title: 페이지 제목
   sidebar_position: 2
   ---
   ```
3. 사이드바에 자동으로 노출됩니다.

---

## 🛠 배포 (예정)

### 타겟

`main` 브랜치 push 시 **GitHub Actions** 가 자동으로 **GitHub Pages** 에 배포.

### URL 전략

- 초기: `https://scenemakerai.github.io/docs-web/`
- 최종(예정): `https://tech.solbox.com` 등 커스텀 도메인

### 활성화 단계 (구현 예정)

1. `.github/workflows/deploy.yml` 추가 (GitHub Actions 워크플로우)
2. 저장소 Settings → **Pages** 에서 source 를 "GitHub Actions" 로 설정
3. `docusaurus.config.ts` 의 `url` / `baseUrl` 을 실제 배포 URL 에 맞춤
4. (선택) 커스텀 도메인용 `CNAME` 추가

---

## 🎯 과제 목표 (마일스톤 기반)

| 지표 | 목표치 |
| ---- | ------ |
| 오픈소스 생태계 기여 | **누적 30건 이상** (PR, Issue, 데이터셋) |
| 기술 블로그 게시 | **누적 20건 이상** (월 2건 이상 정기 게시) |
| 추론 처리 성능 | 1 시간 방송 → **20분 이하** |
| 장면 분류 F1 | ≥ 0.70 (40–60분) / ≥ 0.65 (60–120분) |

---

## 🤝 기여

현재는 단일 메인테이너 운영입니다. 초기 구조가 안정화된 뒤 PR/Issue/Discussion 을 환영합니다.

문의: **minsung7336 [at] solbox.com**

---

## 📄 라이선스

확정 예정입니다. 사이트 콘텐츠는 **CC BY 4.0**, 코드 샘플 및 레퍼런스 구현은 **Apache 2.0** 으로 계획되어 있습니다.

---

## 🔗 관련 링크

- 사업: 2026년 오픈소스 AI·SW 개발·활용 지원사업
- 주관 조직: [Solbox Inc.](https://solbox.com)
- 기반 모델: [Qwen3.5 (Hugging Face)](https://huggingface.co/Qwen)
- 워크플로우: [LangGraph](https://langchain-ai.github.io/langgraph/)
- 사이트 프레임워크: [Docusaurus](https://docusaurus.io/)
