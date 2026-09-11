# CLAUDE.md — docs-web 작업 가이드

콘텐츠 사이트. 작업 대부분은 Markdown 추가·수정과 notion_to_md.py 스크립트 유지보수.

---

## 프로젝트 개요

**SceneMakerAI** — 오픈소스 AI(멀티모달 LLM)로 방송 콘텐츠를 재가공하는 솔박스 사내 프로젝트.

- 운영 URL: `https://doc.scenemaker.solbox.com`
- 스택: **Docusaurus 3.x** (React 19, TypeScript), **한국어(기본)·영어 이중 로케일**
- 파이프라인: Notion DB → 서버 crontab(6시간, `server-sync.sh`) → GH Pages (`deploy.yml`)
- 번역 파이프라인: `docs/`·`blog/` KR → DeepL → `i18n/en/` EN (매월 1일, `monthly-translate.yml`)
- 참고: [https://docusaurus.io/ko/docs](https://docusaurus.io/ko/docs)

---

## 서비스 개요 — 무엇을 만드나

> ⚠️ 아래는 **SceneMaker 제품(파이프라인)** 설명이다. 이 저장소(`docs-web`)는 그 제품을 소개하는 **문서 사이트**일 뿐이다.
> 파이프라인 코드는 **개발 박스 `192.168.0.208` 의 `/usr/service/source/scenemaker`** 에 있다 (`agent/`·`api/`·`worker/`·`ui/`·`poc/`·`train/`). 이 작업 머신에는 없다.
> GitHub org: [SceneMakerAI](https://github.com/SceneMakerAI) — 16개 리포, 다수 private.

**한 줄:** 방송 영상 1편을 넣으면 오픈소스 멀티모달 AI가 분석·색인해서, **자연어 질의로 하이라이트 영상을 합성해주는** 서비스. 최종 산출물은 S3에 올라간 **완성된 MP4**(+ 구간 목록 JSON).

- **뼈대 = RAG.** 색인(`agent-vision` ingest 단계)이 증거를 Milvus에 넣고, 편성(`agent-compose`)이 질의로 클립 구간을 꺼낸 뒤 렌더(`worker-render`)가 영상으로 만든다. "답이 문단이 아니라 타임코드 구간"인 게 문서 RAG와 다른 점.
- **도메인 특화 구조.** 범용 파이프라인이 아니라 `cate_id` 로 도메인 플로우를 고른다. 현재 등록된 건 **야구(`cate_id=5100`)뿐**이고, `agent-vision`·`agent-compose` 모두 `domains/<종목>/` 아래에 단계·노드를 둔다. 도메인 추가 = 모듈 작성 + `pipeline/dispatch.py` 표에 한 줄.
- **스트림 청크 단위 처리.** `stream_mode=Y` 면 영상을 조각(`stream_id`·`stream_seq`)으로 나눠 순차 처리한다. 재처리(`force`)는 "이 청크부터 끝까지" 산출을 지운다 — 뒤 청크가 앞 청크 값(타순 시드·통산 구간 번호)을 이어받기 때문.

**공정 (영상 → 완성 MP4):**

```
api-external(19000)
  → ① agent-stt(19010) ─ worker-prep_stt(19600) STT · worker-img_models(19700) 프레임추론
  → ② agent-vision(8001) 분석+색인
  → ③ agent-compose(8084) 편성
  → ④ worker-render(19700, 별 호스트) 합성 → S3 MP4
```

| 공정 | 담당 | 하는 일 | 산출물 |
| --- | --- | --- | --- |
| 게이트웨이 | `api/api-external` | 외부 요청을 뒷단에 그대로 전달(가공 없음). `POST /api/v1/stt_svc`→agent-stt `pre_svc`, `POST /api/v1/compose`→agent-compose | 로그 · 접수 응답 |
| ① 자막 | `agent/agent-stt` (+`worker-prep_stt`) | 등록 → S3 download → ffmpeg 오디오·1fps 프레임 추출 → 화자분리+전사 → 자막교정·용어교정·환각제거 → 줄거리 요약 | `t_dialogue` |
| ② 화면분석·색인 | `agent/agent-vision` (`agent-vision4`) | `prep`(장면분할) → `board`(전광판) → `vision`(프레임 판정) → `play`(플레이 판정) → `scene`(구간 묶기) → `ingest`(임베딩·Milvus 색인) | `t_vision` · `t_scoreboard_baseball` · `t_play_baseball` · `t_scene_baseball` · Milvus |
| ③ 편성 | `agent/agent-compose` | LangGraph 7노드로 질의 → 클립 구간 목록. 접수만 하고 결과는 `callback_url` 통보(1~3분 소요) | `t_compose` · `t_compose_clip` |
| ④ 합성 | `worker/worker-render` | 구간별 ffmpeg 컷(재인코딩) + 그룹 범퍼 삽입 → concat → S3 업로드 | `{v_id}/result/{v_id}_{c_id}.mp4` |
| 소비 UI | `ui/ui-sbs-viwer` (Next.js) | 분석 완료 영상 탐색 · 클립 편성 요청 · 결과 재생 | — |

- **`agent-compose` 편성 그래프 (LangGraph):** `load_inventory → parse_query → retrieve_evidence → select_clips → select_end_point → merge_overlap → trim_budget`
- **상태 코드는 컴포넌트별 대역으로 분리됐다.** `agent-stt` 2000번대(2001 접수 → 2010 추출 → 2030 대사추출 → 2050 교정 → 2080 요약 → 2000 완료, 오류 29xx) · `agent-vision` 3000번대(3010 prep → 3020 board → 3060 vision → 3030 play → 3040 scene → 3050 publish → 3000 완료, 3900 오류·3901 미지원 cate_id).
- **자동 연쇄는 환경변수 트리거로 한다** — `agent-stt` 의 `STT_TRIGGER`·`VISION_TRIGGER`, 그리고 각 단계의 `callback_url`.

### 구현 현황 (2026-09-11 기준 — 208 소스 직접 확인)

```
[게이트웨이]✅ → [자막]✅ → [화면분석·색인]✅ → [편성]✅ → [영상합성]✅ → [공개 UI]✅
```

| 컴포넌트 | 최근 커밋 | 상태 |
| --- | --- | --- |
| `api/api-external` | 2026-09-11 | ✅ 게이트웨이 동작 (systemd) |
| `agent/agent-vision` | 2026-09-11 | ✅ 콜백 통보 + 실행 락 전역 1건 |
| `agent/agent-compose` | 2026-09-11 | ✅ 편성 + 렌더 트리거 |
| `agent/agent-stt` | 2026-09-10 | ✅ 스트림 청크 지원 |
| `worker/worker-prep_stt` | 2026-09-10 | ✅ HTTP + S3 download |
| `worker/worker-img_models` | 2026-09-10 | ✅ 야구 전용(축구는 뼈대만) |
| `worker/worker-render` | 2026-08-20 | ✅ S3 in/out |
| `ui/ui-sbs-viwer` | 2026-08-24 | ✅ 공개 뷰어 |
| `ui/ui-workspace` | 2026-06-25 | ⚠️ 사실상 정지 — 신규 공정은 `ui-sbs-viwer` 로 이동 |
| `agent/agent-test` | (git 아님) | 오프라인 실험판 |

- **야구 외 도메인은 미등록.** `DOMAIN_FLOWS = {5100: baseball.run}` 한 줄뿐이고, 미등록 `cate_id` 는 조용히 넘기지 않고 `3901 UNSUPPORTED` 로 명시 마킹된다.
- **F1 측정 인프라(정답 GT·채점기)는 여전히 없음** — 국책과제 KPI 입증 수단 부재.

### 이전 문서(2026-07-20) 대비 바뀐 것 — 블로그·문서 쓸 때 주의

| 항목 | 옛 서술 | 2026-09-11 실제 |
| --- | --- | --- |
| 색인 담당 | `agent-scenario` | **리포 없음.** 색인은 `agent-vision` 의 `ingest` 단계가 흡수 |
| 검색 담당 | `agent-search` (`/api/v1/search`) | **`agent-compose`** (`/api/v1/compose`) 로 개명·재작성 |
| 편성 그래프 | 6단계 scope→plan→retrieve→expand→select→assemble | **7노드** load_inventory→parse_query→retrieve_evidence→select_clips→select_end_point→merge_overlap→trim_budget |
| 4대 서비스 | `service` 문자열(compilation/shortform/trailer/ad_slot)로 분기 | **폐기.** 자연어 `query` + `budget_sec` 만 받는다 |
| 데이터 계층 | `t_segment`(6초) → `t_chapter` L2/L1 → `t_video.summary` | **도메인 테이블로 교체** — `t_vision` · `t_scoreboard_baseball` · `t_play_baseball` · `t_scene_baseball` · `t_compose`/`t_compose_clip` |
| 영상 생성 | ❌ 미구현 (클립 좌표까지만) | **✅ `worker-render`** — cut(재인코딩) + 범퍼 + concat + S3 업로드 |
| `agent-vision` | 리포 밖, 오프라인 실험판만 | **✅ 리포 존재**(`agent-vision4`), 분석+색인 주체 |
| 소비 UI | 없음 | **✅ `ui-sbs-viwer`** (탐색·편성·재생) |
| STT | faster-whisper → Qwen3-ASR **이관 중** | **이관 완료.** 1차 전사 = pyannote diarize + **Qwen3-ASR**, 2차 리컨사일 = faster-whisper(`stt2_svc`) |
| 외부 진입 | 각 에이전트 직접 호출 | **`api-external` 게이트웨이 단일화** |
| 출력 규격 | 강제 없음(102초 클립 통과) | **`trim_budget` 노드**가 `budget_sec` 기준으로 덜어낸다 |

### 핵심 주의 (파이프라인 작업 시)

- **읽기 전용.** `192.168.0.208:/usr/service/source/scenemaker` 는 조회만 한다 — 수정·생성·삭제·git 조작 금지.
- **RAG ≠ 학습.** 영상 데이터는 검색용 **색인(임베딩)** 이지 모델 fine-tune 아님.
- **`worker-render` 는 `-c copy` 를 쓰지 않는다.** 원본 키프레임이 5초 간격인데 하이라이트 평균이 16초라 copy 로 자르면 컷이 최대 5초씩 어긋나고, mp4 edit list 를 concat demuxer 가 무시해 앞부분이 되살아난다(실측). 전 조각을 **원본 규격으로 재인코딩**한다.
- **렌더 워커는 1개다.** ffmpeg 하나가 NVDEC 컨텍스트로 400MB 넘는 VRAM 을 잡아, 24GB 카드에서 입력 86개를 동시에 열면 61번째에 OOM(실측).
- **`force` 재처리 범위는 "이 청크부터 끝까지"** — 앞 청크를 다시 계산하면 뒤 청크가 이어받은 값이 무효가 된다.


### 국책과제 (참고 — 발표자료는 gitignore된 confidential PDF)

「오픈소스 멀티모달 AI 기반 방송 콘텐츠 지능형 재가공 서비스」(과기정통부·NIPA 2026 오픈소스 AI·SW 지원사업, 실증 파트너 SBS). 정량 KPI(ETRI 공인 시험): ① 1시간 방송 처리 ≤ 20분, ② 장면/감정 분류 F1 ≥ 0.70(4060분)·0.65(60120분), ③ 오픈소스 기여 30건+, ④ 기술 블로그 20건+. Apache 2.0 공개.

---



## 서비스 인프라 (참고 — 문서 사이트와 무관)

이 `docs-web` 은 문서 사이트일 뿐이고, 실제 SceneMaker 파이프라인은 **별도 AWS 서버들에 분산 배포**된다. 참고용 요약(2026-09-11 확인).

- **리전:** `ap-northeast-2` (서울). aws CLI 설치돼 있으나 활성 자격증명이 **임시 STS 토큰이라 만료**되기 쉬움 → 라이브 인스턴스 조회는 갱신 후 `aws ec2 describe-instances` 로.
- **개발 박스:** `RTX4090x2` (Intel i9-14900K, 125GB RAM, RTX 4090 ×2, 로컬 192.168.0.208). **소스 원본 위치 = `/usr/service/source/scenemaker`** (읽기 전용으로만 다룰 것). 운영 서비스는 안 돈다. (이 CPU/보드는 만성 하드웨어 불안정 이력 있음.)
- **배포 단위 = systemd.** 각 리포의 `deploy/<name>.service` + `deploy/update.sh`. 서비스는 `uv` 가상환경(`.venv/bin/python`)으로 뜬다.
- **구체 IP·자격증명은 각 컴포넌트** `.env` **에만** 둔다 — 이 공개 파일엔 역할·포트만.

| 컴포넌트 | 포트 | 역할 |
| --- | --- | --- |
| `api-external` | 19000 | 외부 공개 게이트웨이 (유일한 외부 진입점) |
| `agent-stt` | 19010 | 자막 공정 오케스트레이터 |
| `agent-vision` | 8001 | 화면분석 + 벡터 색인 |
| `agent-compose` | 8084 | 질의 기반 편성 |
| `worker-prep_stt` | 19600 | STT GPU (Qwen3-ASR / faster-whisper 2차) |
| `worker-img_models` | 19700 | 야구 프레임 추론 GPU |
| `worker-render` | 19700 | ffmpeg 합성 GPU (별 호스트) |
| MariaDB `sm_db` | 13306 | 전 컴포넌트 공유 상태·데이터 |
| Milvus | 19530 | `agent-vision` 색인 / `agent-compose` 검색 |
| vLLM (자막교정) | 8601 | `agent-stt` 자막·용어 교정 |

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
│   ├── release-notes/  # 릴리즈 노트 (NOTION_RELEASE)
│   └── test/           # 테스트 (NOTION_TEST)
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
│   └── tests/                # notion_to_md.py·md_to_notion.py·translate_to_en.py 단위 테스트
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
| `NOTION_TEST`         | "테스트" DB ID → `docs/test/`                                              |
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
0 */6 * * * /root/docs-web/scripts/server-sync.sh >> /var/log/notion-sync.log 2>&1
```

`server-sync.sh` 실행 흐름:

1. ORIG_BRANCH 저장 + `trap EXIT` 등록 (종료 시 원래 브랜치 복귀 — dev 서버 파일 보호)
2. `git checkout main` → `git pull --rebase`
3. Notion 9개 DB 병렬 동기화 (하나라도 실패하면 `exit 1` — 커밋·push 전체 중단)
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

crontab이 6시간마다 main에 push하므로 `non-fast-forward` 에러 시:

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
| `npm start`             | main 브랜치 dev 서버 (port 3000, **KO만**)    |
| `npm run start:develop` | develop 브랜치 dev 서버 (port 3001, **KO만**) |
| `npm run build`         | 프로덕션 빌드 — **PR 전 통과 필수**              |
| `npm run clear`         | Docusaurus 캐시 정리                      |
| `npm run typecheck`     | TypeScript 검사 (빌드와 무관, IDE 보조)        |


**dev 서버 404 / 브랜치 전환 후 캐시 꼬임:** `npm run clear` 후 재시작.

**EN 로케일 접근:** `docusaurus start` 는 **기본 로케일(KO)만 서빙**한다. dev 서버에서 `/en/` 은 404다. EN 확인은 별도 포트로 띄운다.

```bash
npx docusaurus start --host 0.0.0.0 --port 3002 --locale en   # http://localhost:3002/en/
```

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
- **해시 캐시는 스크립트 버그 수정을 소급 적용하지 않는다.** 번역 로직을 고쳐도 KR 원문이 그대로면 기존 EN 산출물은 재번역되지 않아 깨진 상태로 남는다 (실제 사례: 2026-08-11 이미지 보호 패치 이전에 번역된 블로그 6건이 `![image](...` 형태로 깨진 채 2026-09-11까지 방치).

**특정 파일 강제 재번역:**

```bash
python3 -c "
import json
p='.notion-translate-hashes.json'
h=json.load(open(p))
h['blog/파일명.md']['body_hash']=''   # 대상만 무효화
json.dump(h, open(p,'w'), indent=2, ensure_ascii=False)
"
export $(grep -v '^#' .env | xargs) && python3 scripts/translate_to_en.py
```

검증 (EN 이미지 개수가 KR과 같아야 함):

```bash
grep -rlE '^!\[[^]]*\]\([^)]*$' i18n/en/   # 출력 없으면 정상
```

---



## 빌드 게이트

`onBrokenLinks: 'throw'` — CI에서 아래 시 빌드 실패:

- **깨진 내부 링크** — PR 전 `npm run build` 로컬 통과 필수
- **MDX 컴파일 오류** — frontmatter·JSX 문법 오류
- **사이드바 비어있음** — Notion DB에 콘텐츠가 없는 섹션은 `placeholder.md` 필수. `notion_to_md.py`가 sync 결과 0건이면 자동 생성하고, 실제 문서가 생기면 자동 제거한다 (현재 보유: `architecture/`, `release-notes/`)

---



## navbar 자동 숨김 — `hasNotionContent`

`docusaurus.config.ts`에 빌드 타임 함수 `hasNotionContent(dirName)`가 있다. `docs/<dir>/` 안에 `placeholder.md` 외 `.md` 파일이 없으면 navbar 항목을 숨긴다.

- Notion 콘텐츠가 없는 섹션: navbar에서 자동 제거 (빌드 시 평가)
- Notion 콘텐츠 도착 → sync → `.md` 파일 생성 → 다음 빌드에서 자동 복원
- `placeholder.md`는 사이드바 비어있음 빌드 에러 방지용 (Notion 콘텐츠가 없는 섹션에 필수)



## 사이드바 ID ↔ Notion DB 매핑


| 사이드바 ID               | `docs/` 경로       | 환경변수                  | Notion 콘텐츠 유무                   |
| --------------------- | ---------------- | --------------------- | ------------------------------- |
| `aboutSidebar`        | `about/`         | `NOTION_ABOUT`        | ✅                               |
| `architectureSidebar` | `architecture/`  | `NOTION_ARCHITECTURE` | ❌ placeholder.md 자동 생성 (navbar 숨김) |
| `installSidebar`      | `install/`       | `NOTION_INSTALL`      | ✅                               |
| `pocSidebar`          | `poc/`           | `NOTION_POC`          | ✅                               |
| `docsSidebar`         | `guide/`         | `NOTION_DOCS`         | ✅                               |
| `contributeSidebar`   | `contribute/`    | `NOTION_CONTRIBUTE`   | ✅                               |
| `releaseNotesSidebar` | `release-notes/` | `NOTION_RELEASE`      | ❌ placeholder.md 자동 생성 (navbar 숨김) |
| `testSidebar`         | `test/`          | `NOTION_TEST`         | ✅                               |


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
6. **EN 라벨 수동 추가** — `translate_to_en.py`는 본문만 번역하고 라벨 JSON은 건드리지 않는다
   - `i18n/en/docusaurus-theme-classic/navbar.json` → `"item.label.<KR라벨>"`
   - `i18n/en/docusaurus-plugin-content-docs/current.json` → `"sidebar.<sidebarId>.category.<KR라벨>"`
   - 빠뜨리면 EN 로케일 메뉴에 한글이 그대로 노출된다

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

