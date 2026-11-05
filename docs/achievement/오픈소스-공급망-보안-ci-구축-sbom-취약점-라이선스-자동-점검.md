---
id: 오픈소스-공급망-보안-ci-구축-sbom-취약점-라이선스-자동-점검
title: "오픈소스 공급망 보안 CI 구축 (SBOM · 취약점 · 라이선스 자동 점검)"
sidebar_position: 5
slug: "5"
last_update:
  date: 2026-11-05
---

> 💡 **저장소 9개 적용(공개 2 · 비공개 7) · PR과 Release마다 SBOM 생성 · 취약점 · 라이선스 자동 점검 · Release 서명 검증 · 통합자산 508건 중 GPL · AGPL 0건**
SceneMakerAI의 모든 서비스 저장소에 소프트웨어 공급망 점검을 CI로 붙였습니다. 코드가 바뀔 때마다 어떤 오픈소스가 들어 있는지 목록(SBOM)을 만들고, 위험한 취약점이나 금지 라이선스가 있으면 배포용 Release를 자동으로 사용 금지 상태로 표시합니다.

---

### 1. 왜 만들었나

SceneMakerAI는 vLLM, FFmpeg, PyTorch, Whisper 계열 STT, Pillow 등 수백 개의 오픈소스 위에서 동작합니다. 이 결과물을 방송사 장비에 설치 · 납품하려면 다음 세 가지를 증명할 수 있어야 합니다.

| 질문 | 확인 수단 |
| --- | --- |
| 이 배포본에 어떤 오픈소스가 몇 버전으로 들어 있는가 | SBOM (SPDX · CycloneDX 형식) |
| 알려진 심각한 취약점이 들어 있지 않은가 | 취약점 게이트 |
| 재배포에 문제가 되는 라이선스는 없는가 | 라이선스 게이트 · 오픈소스 고지문 |

사람이 배포 때마다 이를 확인하면 빠뜨리기 쉽고 기록도 남지 않습니다. 그래서 점검을 저장소의 CI에 넣어, 모든 변경과 배포에서 자동으로 돌고 결과가 증거로 남게 했습니다.


#### 용어

**SBOM (Software Bill of Materials, 소프트웨어 자재명세서)**  
소프트웨어에 들어 있는 오픈소스 구성요소의 목록입니다. 식품 포장의 성분표처럼, 어떤 패키지가 어떤 버전으로 들어 있고 각각의 라이선스와 출처가 무엇인지를 기계가 읽을 수 있는 형식으로 기록합니다. 국제 표준 형식으로 SPDX와 CycloneDX가 있습니다.

SBOM이 있으면 새로운 취약점이 발표됐을 때 "우리 배포본 중 어디가 영향을 받는가"를 바로 확인할 수 있습니다. 2021년 Log4j 취약점 때 많은 기관이 자사 시스템에 해당 라이브러리가 있는지조차 파악하지 못해 대응이 늦어졌고, 이후 미국 등에서 공공 납품 소프트웨어에 SBOM 제출을 요구하기 시작했습니다.

| 용어 | 뜻 |
| --- | --- |
| CVE · GHSA | 공개된 취약점에 붙는 고유 번호입니다. CVE는 국제 공통 번호이고, GHSA는 GitHub 취약점 DB의 번호입니다. |
| 취약점 등급 | Critical · High · Medium · Low. Critical은 원격에서 쉽게 악용될 수 있는 수준입니다. |
| purl | 패키지를 가리키는 표준 식별자입니다 (예: `pkg:pypi/pillow@13.0.0` ). |
| 게이트 | 기준을 넘는 위험이 있으면 다음 단계로 넘어가지 못하게 막는 자동 점검입니다. |
| Release · Pre-release | Release는 배포용으로 확정한 버전입니다. Pre-release는 시험용 표시로, 배포에 쓰면 안 된다는 뜻입니다. |
| attestation (서명) | 이 파일을 누가 어떤 절차로 만들었는지 암호학적으로 증명하는 서명입니다. 파일이 조금이라도 바뀌면 검증에 실패합니다. |
| 오픈소스 고지문 (NOTICE) | 사용한 오픈소스와 라이선스 문구를 모은 문서입니다. 라이선스 대부분이 재배포할 때 함께 제공하도록 요구합니다. |


---

### 2. 점검 구조

점검은 세 시점에서 돕니다. PR에서는 미리 알리고, 배포 시점인 Release에서 실제로 판정합니다.

| 시점 | 하는 일 | 실패 시 |
| --- | --- | --- |
| **PR** | 거버넌스 문서 점검, 새로 추가 · 변경된 의존성의 Critical 취약점 · 금지 라이선스 점검, 병합 후 상태의 SBOM 미리보기, PR에 점검 결과 댓글 1개 갱신 | 공개 저장소는 금지 항목을 새로 넣는 PR을 차단, 그 외에는 경고 |
| **스냅샷** (main 변경 시 · 매월 1일) | main 기준 SBOM과 취약점 · 라이선스 보고서를 90일 보관 | 관찰용이라 실패시키지 않음. 월간 점검의 입력 자료 |
| **Release 게시** | SBOM · 오픈소스 고지문 생성 → 적합성 · 라이선스 식별률 · 악성 패키지 검사 → 취약점 게이트 → 라이선스 게이트 → 서명(attestation) → 결과물 6종 첨부 | Release를 **Pre-release로 바꾸고 본문 맨 앞에 "사용 금지" 경고** 를 붙임 |

#### 배포 가능 판정

장비 설치 · 납품에는 아래 조건을 모두 만족하는 Release만 사용합니다.

| 조건 | 확인 위치 |
| --- | --- |
| 정식 Release (Pre-release 아님) | Releases 화면 |
| 첨부 6종:    • 소스 묶음(.tar.gz)    • SBOM 2종(CycloneDX · SPDX)    • 고지문(NOTICE)   • 오픈소스 고지 패키지   • 체크섬(SHA256SUMS) | Release의 첨부 파일 |
| Release 점검 워크플로 성공 | Actions 실행 기록 |

실패한 Release는 지우지 않고 기록으로 남깁니다. 문제를 해결하거나 예외를 승인받은 뒤 새 버전으로 다시 게시합니다.

#### Release 서명 검증 (공개 저장소)

공개 저장소의 Release 파일에는 GitHub attestation 서명이 붙습니다. 납품 전이나 평가 때 아래 명령으로, 파일이 **우리 저장소의 공식 Release 워크플로가 만든 원본인지** 와 **SBOM이 그 파일의 것인지** 를 확인할 수 있습니다.

```bash
gh attestation verify <파일>.tar.gz --repo SceneMakerAI/<저장소>
gh attestation verify <파일>.tar.gz --repo SceneMakerAI/<저장소> --predicate-type https://spdx.dev/Document/v2.3
```

파일이 1바이트라도 바뀌면 검증에 실패합니다. 체크섬은 파일과 함께 바꿔치기될 수 있지만, 서명은 워크플로의 신원 없이는 만들 수 없습니다.

---

### 3. 판정 기준

#### 3-1. 취약점

| 등급 | 처리 | 조치 기한 |
| --- | --- | --- |
| Critical | Release 차단, PR 경고 · 댓글 | 10일 |
| High | 기록 후 월간 점검에서 조치 (운영 안정화 후 차단 대상으로 상향 예정) | 30일 |
| Medium 이하 | 보고서 · Dependabot으로 확인 | — |

#### 3-2. 라이선스

| 구분 | 라이선스 | 처리 |
| --- | --- | --- |
| 금지 | GPL-2.0, GPL-3.0, AGPL-3.0 | Release 차단 (공개 저장소는 PR에서 차단) |
| 허용 | MIT, Apache, BSD, LGPL, MPL 등 | 통과 |
| 확인 필요 | 금지 라이선스와 다른 라이선스 중 선택하는 이중 라이선스 | 경고 |
| 재배포 조건 확인 | 독점 라이선스 (예: NVIDIA 구성요소) | 경고 |

금지 목록은 설정 파일 하나에서 관리해 모든 저장소에 같은 기준이 적용됩니다.

#### 3-3. 예외 승인

업그레이드할 수 없는 취약점이나 라이선스는 예외로 승인받아 통과시킬 수 있습니다. 게이트는 아래 네 조건을 모두 갖춘 예외만 인정합니다.

| 항목 | 조건 |
| --- | --- |
| 식별자 | CVE · GHSA 번호 또는 패키지 식별자(purl) |
| 상태 | "유효" |
| 승인자 | 프로젝트 책임자 승인 기록 |
| 만료일 | 오늘 이후 날짜 |

예외가 만료되면 PR은 다시 경고하고 Release는 다시 차단됩니다. 예외를 영구 면제가 아니라 **기한이 있는 유예** 로 만들어 재검토를 강제하는 장치입니다.

---

### 4. 적용 결과

#### 4-1. 적용 현황 (2026-10-26 기준)

| 구분 | 저장소 | 상태 |
| --- | --- | --- |
| 공개 | [worker-render](https://github.com/SceneMakerAI/worker-render) , [api-external](https://github.com/SceneMakerAI/api-external) | 적용 완료 |
| 비공개 | 서비스 저장소 7개 (STT · 비전 · 편성 에이전트, 전처리 워커 등) | 적용 완료. PR 점검 · SBOM 자동 생성 모두 성공 |
| 남은 대상 | 비공개 저장소 1개 | 적용 예정 |

모든 저장소에 거버넌스 문서(GOVERNANCE.md · MAINTAINERS.md · SECURITY.md · CODE_OF_CONDUCT.md)와 CI 도입 결정 기록을 함께 넣었습니다.

#### 4-2. 검증 사례

| 검증 내용 | 결과 |
| --- | --- |
| 시범 저장소에서 차단 → 예외 승인 → 통과 흐름 | 게이트가 차단하고, 예외 등록 후 통과하는 전 과정 확인 |
| 시연용 저장소의 Release 게이트 | Critical 취약점 2건을 탐지해 Release를 자동으로 Pre-release로 전환하고 사용 금지 경고 표시 |
| worker-render Release 서명 | 첨부 6종과 서명 2건(빌드 출처 · SBOM) 생성, 2026-10-23 검증 명령으로 둘 다 통과 |
| 라이선스 | 통합자산목록 508건 기준 8개 저장소에 GPL · AGPL 0건 |

공급망 점검에서 Critical 취약점 해소를 위해 요구한 Pillow 13.0.0에는 SceneMakerAI가 기여해 머지된 수정 3건이 들어 있습니다([오픈소스 기여](https://doc.scenemaker.solbox.com/docs/achievement/3) 참고).

---

### 5. 공개 · 비공개 저장소의 차이

GitHub는 공개 저장소에만 무료로 제공하는 보안 기능이 많습니다. 같은 기준을 지키되, 비공개 저장소는 다른 수단으로 대신했습니다.

| 기능 | 공개 | 비공개 (GitHub Free) | 비공개 대체 수단 |
| --- | --- | --- | --- |
| PR 의존성 점검(dependency-review) | O | X (유료) | PR 점검 댓글로 상세 경고 |
| Release 서명(attestation) | O | X (유료) | 체크섬 · 실행 기록 |
| main 직접 push 차단(Ruleset) | O | X | 운영 원칙 + 월간 점검 |
| 비밀 키 노출 감시 · 차단 | O | X (유료) | .env 미커밋 원칙 |
| 라이선스 게이트 | dependency-review가 대신 | O | — |
| Dependabot 취약점 경고 | O | O | — |

---

### 6. 어려웠던 점

**Release 게이트는 Release 생성 자체를 막을 수 없었습니다.**  
GitHub의 Release 워크플로는 Release가 게시된 뒤에 실행되므로, 점검에 실패해도 Release는 이미 만들어진 상태입니다. 이를 해결하기 위해 게이트 실패 시 워크플로가 Release를 Pre-release로 바꾸고 본문에 사용 금지 경고를 붙이도록 했습니다. 또한 첨부 6종이 갖춰진 정식 Release만 배포에 쓴다는 판정 기준을 따로 정했습니다. 워크플로가 취소되어 경고가 붙지 않은 Release는 월간 점검에서 찾아 처리합니다.

**취약점 데이터베이스마다 결과가 달랐습니다.**  
SBOM 기반 점검 도구와 GitHub Dependabot은 서로 다른 취약점 DB를 사용해, 같은 의존성에 대해 한쪽에서만 탐지되는 경우가 있었습니다(예: certifi 관련 GHSA는 Dependabot에서만 탐지). SBOM 점검은 게이트와 공식 증거로, Dependabot은 상시 감시와 수정 PR 제안용 보조 수단으로 역할을 나누고, 월간 점검에서 두 결과를 대조하도록 했습니다.

**PR 점검은 새로 추가된 의존성만 봅니다.**  
dependency-review는 PR이 새로 넣거나 바꾼 의존성만 점검하므로, 이미 들어와 있던 취약점은 잡지 못합니다. 기존 취약점은 SBOM 미리보기 알림, 월간 스냅샷, Dependabot으로 따로 추적합니다.

**비공개 저장소는 무료 요금제에서 쓸 수 있는 보호 기능이 적었습니다.**  
main 브랜치 보호 규칙, 서명, 비밀 키 감시가 유료 기능이라, 비공개 저장소에서는 운영 원칙과 월간 점검으로 같은 수준을 유지하고 있습니다.

**SBOM이 담지 못하는 구성요소가 있습니다.**  
SBOM은 Python 패키지 수준의 의존성을 기준으로 만들어지므로, NVENC 빌드 FFmpeg나 GPU 드라이버처럼 시스템에 설치되는 구성요소와 AI 모델 가중치의 라이선스는 목록에 들어가지 않습니다. 납품 시점에 이미지 스캔을 하거나 고지 패키지에 별도로 기재하는 방식을 준비하고 있습니다.

**개발 속도와 통제 수준의 균형이 필요했습니다.**  
개발 단계에서 승인 인원 필수, 태그 보호, Release 실행 승인까지 걸면 작업이 크게 느려집니다. 그래서 시스템으로는 "main 직접 push 금지 + PR 필수 + 필수 점검 통과"만 강제하고, 리뷰 승인은 변경의 중요도(일상 · 중요 · 중대)에 따라 운영 원칙으로 지키기로 결정하고 결정 기록으로 남겼습니다. 운영이 안정되면 다시 검토합니다.

---

### 7. 남은 과제

| 과제 | 내용 |
| --- | --- |
| 적용 마무리 | 남은 비공개 저장소 1개 적용, worker-render 정식 Release로 서명 증거 교체 |
| 기준 상향 | 운영 안정화 후 High 취약점까지 Release 차단 |
| 배포물 전체 범위 | FFmpeg · GPU 드라이버 층 이미지 스캔, AI 모델 라이선스 확인 |
| 운영 기록 | Dependabot 설정 화면 · 월간 지표 · 분기 표본검사 기록 축적 |
| CI 유지보수 | GitHub Actions 버전 갱신 자동 제안, 러너 버전 고정 |

---

### 8. 참고

| 자료 | 내용 |
| --- | --- |
| [SPDX](https://spdx.dev/) | SBOM 표준 형식 (ISO/IEC 5962) |
| [CycloneDX](https://cyclonedx.org/) | SBOM 표준 형식 (OWASP) |
| [SLSA](https://slsa.dev/) | 빌드 출처(provenance) 보안 수준 프레임워크 |
| [dependency-review-action](https://github.com/actions/dependency-review-action) | PR 의존성 점검 |
| [attest-build-provenance](https://github.com/actions/attest-build-provenance) | Release 파일 서명 |
| [worker-render Releases](https://github.com/SceneMakerAI/worker-render/releases) | 첨부 6종 · 서명이 붙은 Release 예시 |

---

**관련 문서**

- [오픈소스 기여](https://doc.scenemaker.solbox.com/docs/achievement/3)

