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

## 서비스 개요 — 무엇을 만드나

> ⚠️ 아래는 **SceneMaker 제품(파이프라인)** 설명이다. 이 저장소(`docs-web`)는 그 제품을 소개하는 **문서 사이트**일 뿐이고, 파이프라인 코드는 형제 디렉토리(`agent/`, `worker/`, `ui/`)에 있다.

**한 줄:** 방송 영상 1편을 넣으면 오픈소스 멀티모달 AI가 분석·색인해서, **자연어 질의로 원하는 장면(클립)을 찾아주는** 서비스. 최종 산출물은 숏폼·하이라이트·예고편·광고매칭용 **클립 구간 목록**(다음 단계 ffmpeg 조립의 입력).

- **검색 원자 = 6초 세그먼트.** 모든 요약 계층에 타임코드를 보존한다 — 최종 목적이 클립 컷팅이라 요약↔원본 매핑이 끊기면 안 됨.
- **뼈대 = RAG.** 색인(agent-scenario)이 영상을 접어 Milvus에 넣고, 검색(agent-search)이 질의로 클립을 꺼낸다. 영상 RAG라 "답이 문단이 아니라 타임코드 구간"인 게 문서 RAG와 다른 점.
- **데이터 4계층:** 세그먼트(6초, `t_segment`) → 씬(`t_chapter` L2) → 서브/막(`t_chapter` L1) → 전체 줄거리(`t_video.summary`).

**5공정 (영상 → 클립):**

```
업로드(ui) → 자막(agent-stt+worker) → 화면분석(agent-vision)
          → 색인(agent-scenario) → 검색(agent-search) → ffmpeg 조립(다음 단계)
```


| 공정     | 담당                                   | 하는 일                                                               | 산출물                  |
| ------ | ------------------------------------ | ------------------------------------------------------------------ | -------------------- |
| 업로드    | `ui-workspace` (Next.js)             | S3 업로드 + 분석결과 조회 콘솔                                                | `t_video`            |
| ① 자막   | `agent-stt` (+`worker-prep_stt` STT) | 음성 → 대사·화자, vLLM 자막교정                                              | `t_dialogue`         |
| ② 화면분석 | `agent-vision`                       | 6초 세그먼트 화면·OCR·소리·동작 분석                                            | `t_segment`          |
| ③ 색인   | `agent-scenario`                     | 씬→막→전체 map-reduce 요약 + 인물 신원 해소 + 임베딩                              | `t_chapter` · Milvus |
| ④ 검색   | `agent-search`                       | LangGraph 6단계(scope→plan→retrieve→expand→select→assemble)로 질의 → 클립 | 클립 구간 목록             |


- 색인·검색 상세는 형제 문서: `agent/agent-scenario/CLAUDE.md`, `agent/agent-search/README.md`.
- 공정 진행 상태는 `t_video.status_code` 로 전이(1001 업로드 → 1006 자막 → 1010 화면 → 1016 화자보정 → 1021 색인).



### 4대 서비스 (agent-search `service` 값)


| service       | UI 이름  | route              | 세부 유형(preset)                       |
| ------------- | ------ | ------------------ | ----------------------------------- |
| `compilation` | 모아보기   | structural (여러 클립) | 회차_요약 / 정주행_가이드 / 인물_하이라이트 / 감성_몽타주 |
| `shortform`   | 숏폼·리믹스 | pinpoint (한 장면)    | 명장면_클립 / 명대사_카드 / (예고편·티저)          |
| `trailer`     | 예고편    | structural + 정렬 특수 | 예고편                                 |
| `ad_slot`     | 광고 최적화 | (LLM 해석)           | (광고 매칭)                             |


- **Batch 자동화** = 위 서비스를 대량·반복·자동으로 굴리는 **오케스트레이션**(제안서 4번째 서비스). 개별 콘텐츠가 아니라 파이프라인 전체를 자동 구동.
- 코드상 하드분기는 `trailer` 정렬(`assemble.py`) 하나뿐. 나머지는 `service` 문자열이 scope/plan LLM 프롬프트에 들어가 `route`(pinpoint/structural)를 가른다 — 전용 파일 없음.



### 구현 현황 (2026-07-20 기준 — 코드 검증)

```
[업로드]✅ → [자막]🔄 → [화면분석]⚠️ → [색인]✅ → [검색]✅ → [영상생성]❌ → [배포]📋
```

- **색인(agent-scenario)·검색(agent-search) = 완성·실측됨.** RAG 코어 견고. compilation·shortform 실행 검증(야구·겨울연가 덤프). trailer·ad_slot은 미착수(뼈대/이름만).
- **자막(**`worker-prep_stt`**) = faster-whisper → Qwen3-ASR 이관 중** (2026-07 전면 재작성, HTTP 서비스화). `worker-prep-stt2`는 그 실험판(은퇴 예정).
- `agent-vision` **= 서비스 코드 리포 밖.** `t_segment`(검색 원자) 공급 주체인데, 리포엔 오프라인 실험판 `agent/agent-test`(Qwen3-VL, CLI, DB 안 씀)만 있음.
- **영상 생성(⑤ ffmpeg 컷팅·concat·9:16) = 미구현.** agent-search는 클립 **좌표**(`v_id, start~end`)까지만 냄. 제안서 STEP 04 "Serving"이 통째로 빔.
- **자동 연쇄·Batch = 미구현.** 지금은 공정을 수동 HTTP로 연결(코드상 자동 트리거는 `agent-stt→agent-vision` 1곳뿐). `status_code`는 정의돼 있으나 구동 오케스트레이터 없음.
- **agent-search 소비 UI 없음** — `ui-workspace`는 업로드·분석조회 콘솔이고 검색 API(`/api/v1/search`)를 호출하지 않음.



### 설계(제안서) vs 실제 코드 — 바뀐 것 (블로그 쓸 때 주의)


| 항목       | 제안서 발표자료                   | 실제 코드                                |
| -------- | -------------------------- | ------------------------------------ |
| 벡터 DB    | Qdrant                     | **Milvus** (1개 컬렉션 + `ref_type` 4계층) |
| STT      | Fast-Whisper               | **Qwen3-ASR** (이관 중)                 |
| 장면 전환 탐지 | FFmpeg + **PySceneDetect** | scenedetect 미사용, **LLM 씬 분리**        |




### 핵심 주의 (파이프라인 작업 시)

- **RAG ≠ 학습.** 영상 데이터는 검색용 **색인(임베딩)** 이지 모델 fine-tune 아님. "학습에 쓴다"는 오해.
- **장면/감정 태깅은** `agent-scenario/lib/pipeline/scene/scene.py` 가 함(`emotion`·`highlight`·`events`·`is_ad`). 이게 **국책과제 F1 KPI(VLM+RAG 장면/감정 분류)** 대상. 단 **F1 측정 인프라(정답 GT·채점기)는 없음** — KPI 입증 수단 부재.
- **출력 규격 미강제** — `max_clip_sec`/`min_clip_sec`이 select 프롬프트에만 있고 코드 강제 없어, 규격 초과 클립(예: 102초)이 통과할 수 있음.



### 국책과제 (참고 — 발표자료는 gitignore된 confidential PDF)

「오픈소스 멀티모달 AI 기반 방송 콘텐츠 지능형 재가공 서비스」(과기정통부·NIPA 2026 오픈소스 AI·SW 지원사업, 실증 파트너 SBS). 정량 KPI(ETRI 공인 시험): ① 1시간 방송 처리 ≤ 20분, ② 장면/감정 분류 F1 ≥ 0.70(4060분)·0.65(60120분), ③ 오픈소스 기여 30건+, ④ 기술 블로그 20건+. Apache 2.0 공개.

---



## 서비스 인프라 (참고 — 문서 사이트와 무관)

이 `docs-web` 은 문서 사이트일 뿐이고, 실제 SceneMaker 파이프라인(agent-stt / agent-vision / agent-scenario / agent-search, worker)은 **별도 AWS 서버들에 분산 배포**된다. 추후 참고용 요약(2026-07-20 확인).

- **리전:** `ap-northeast-2` (서울). aws CLI 설치돼 있으나 활성 자격증명이 **임시 STS 토큰이라 만료**되기 쉬움 → 라이브 인스턴스 조회는 갱신 후 `aws ec2 describe-instances` 로.
- **개발 박스:** `RTX4090x2` (Intel i9-14900K, 125GB RAM, RTX 4090 ×2, 로컬 192.168.0.208). 코드 개발 + docs-web dev 서버 전용. 운영 서비스는 안 돈다. (이 CPU/보드는 만성 하드웨어 불안정 이력 있음.)
- **운영 토폴로지 — 원격 5개 호스트.** 컴포넌트끼리는 HTTP + 공유 RDB/Milvus + `status_code` 로 느슨히 연결. **구체 IP·자격증명은 각 컴포넌트** `.env` **에만** 두고 이 공개 파일엔 적지 않는다(역할·포트만).


| 원격 호스트(역할)                    | 포트    | 쓰는 컴포넌트                             |
| ----------------------------- | ----- | ----------------------------------- |
| DB (MariaDB `sm_db`)          | 13306 | 전 컴포넌트 공유 상태·데이터                    |
| DB (Milvus `sm_db`/`sm_1024`) | 19530 | agent-scenario 색인 / agent-search 검색 |
| 텍스트추론 (vLLM `qwen`)           | 8000  | agent-scenario·agent-search 판단·요약   |
| 텍스트추론 (임베딩 `qwen-embed`)      | 8001  | agent-scenario·agent-search 벡터      |
| STT/VL GPU (STT worker)       | 8000  | agent-stt                           |
| STT/VL GPU (Qwen3-VL)         | 8002  | agent-test / vision                 |
| 자막교정 (vLLM `qwen`)            | 8000  | agent-stt 자막교정 · agent-test refine  |
| vision (agent-vision)         | 8001  | agent-stt 가 트리거, `t_segment` 기록 주체  |


- **로컬 서비스 포트:** agent-stt `19010` · agent-scenario `19011` · agent-search `19012` · worker-prep_stt `19600`.
- **미완:** 공정 자동 연쇄(ui→stt→vision→scenario→search)는 미구현(수동 HTTP). agent-search 를 쓰는 UI 없음. agent-vision 서비스 코드는 리포 밖(리포 안엔 오프라인 실험판 agent-test).

> ⚠️ 이 파일은 **공개 repo(GH Pages 배포)** 에 있다. 운영 IP·자격증명을 하드코딩하지 말 것 — 위 표처럼 역할·포트만 적고 구체 엔드포인트는 `.env` 로.

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


| 파일                      | 트리거                  | 역할                                                    |
| ----------------------- | -------------------- | ----------------------------------------------------- |
| `deploy.yml`            | main push            | npm build → GH Pages 배포                               |
| `monthly-translate.yml` | 매월 1일 KST 11:00 / 수동 | KR docs·blog → DeepL → `i18n/en/` 번역, main에 커밋        |
| `sync-develop.yml`      | 매일 KST 03:00         | main 콘텐츠를 develop으로 머지 (`.notion-sync.json` 충돌 자동 해소) |
| `merge-develop.yml`     | 매일 KST 11:00         | develop 코드 변경을 main으로 머지 (콘텐츠 디렉토리 제외, 빌드 게이트 포함)     |
| `md-to-notion.yml`      | `docs/**/*.md` push  | 수동 편집된 md → Notion DB 역업로드                            |
| `pr-build.yml`          | main·develop PR      | 프로덕션 빌드 검증 (깨진 링크·MDX 오류 차단)                          |




### 커밋 메시지 태그 규칙


| 태그                 | 효과                    |
| ------------------ | --------------------- |
| `[skip-notion]`    | `md-to-notion.yml` 스킵 |
| 커미터가 `server-cron` | `md-to-notion.yml` 스킵 |


`[skip-notion]` **필수 상황:** Notion에서 내려받은 내용을 다시 올리면 무한 루프가 된다.

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

> ⚠️ **핵심 규칙:** `main`**·**`develop`**에 코드를 직접 커밋하지 않는다.**
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


| 명령어                     | 용도                                    |
| ----------------------- | ------------------------------------- |
| `npm start`             | main 브랜치 dev 서버 (port 3000, KO+EN)    |
| `npm run start:develop` | develop 브랜치 dev 서버 (port 3001, KO+EN) |
| `npm run build`         | 프로덕션 빌드 — **PR 전 통과 필수**              |
| `npm run clear`         | Docusaurus 캐시 정리                      |
| `npm run typecheck`     | TypeScript 검사 (빌드와 무관, IDE 보조)        |


**dev 서버 404 / 브랜치 전환 후 캐시 꼬임:** `npm run clear` 후 재시작.

**EN 로케일 접근:** `--locale` 플래그 없이 실행하면 KO (`/`) + EN (`/en/`) 모두 서빙된다. `http://localhost:3001/en/docs/...` 로 바로 접근 가능.

---



## EN 번역 파이프라인



### 개요

`scripts/translate_to_en.py`가 `docs/`·`blog/` 의 KR Markdown을 DeepL Free API로 번역해 `i18n/en/` 에 저장한다. `monthly-translate.yml`**이 매월 1일 자동 실행**한다 (서버 crontab은 번역 미포함).

### 동작 방식

- **해시 캐시** (`.notion-translate-hashes.json`): SHA-256으로 변경된 파일만 번역. 미변경 파일 스킵.
- **제목 영어화**: docs·blog 모두 frontmatter `title:`·`description:` 을 DeepL로 번역해 EN 로케일 제목이 영어로 표시된다. 접두 정렬번호(`07_` 등)는 유지. **블로그 글 제목은 반드시 영어여야 한다** — EN 제목에 한글이 남으면 `translate_to_en.py`의 title 번역 로직을 점검할 것.
- **에러 격리**: 파일 하나 실패해도 나머지 계속 진행 (try-except per file).
- `<hr/>` **버그 방지**: DeepL이 `<hr/>` 앞뒤 줄바꿈을 제거하는 문제를 `\n\n---\n\n`으로 복원.
- **heading 공백 복원**: DeepL이 `###3.` 처럼 공백을 제거하는 경우 정규식으로 복원.
- **blockquote 마커 복원**: DeepL이 `>`  마커를 문장 중간으로 이동시키는 경우 복원.
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


| 사이드바 ID               | `docs/` 경로       | 환경변수                  | Notion 콘텐츠 유무                   |
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

**카운터 리셋 기준 (**`_OL_RESET_TYPES`**):**


| 블록 타입                                                       | 동작                      |
| ----------------------------------------------------------- | ----------------------- |
| `heading_1~4`                                               | **리셋** (섹션 경계)          |
| `table`, `toggle`, `column_list`                            | **리셋**                  |
| `code`, `paragraph`, `image`, `divider`, `quote`, `callout` | **유지** (split-OL 연속 번호) |
| `bulleted_list_item`, `to_do`                               | **유지**                  |




### HTML 엔티티 처리

Notion API가 `>` 형태로 이중 인코딩할 때 `extract_text_from_rich_text`에서 안정될 때까지 반복 unescape.

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

