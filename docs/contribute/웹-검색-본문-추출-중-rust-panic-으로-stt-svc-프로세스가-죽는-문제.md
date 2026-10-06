---
id: 웹-검색-본문-추출-중-rust-panic-으로-stt-svc-프로세스가-죽는-문제
title: "웹 검색 본문 추출 중 Rust panic 으로 stt_svc 프로세스가 죽는 문제"
sidebar_position: 36
slug: "36"
description: "agent-stt: ddgs.extract() 내부의 Rust html2text panic 이 프로세스를 죽이는 문제와 조치 기록"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-06
---

[https://github.com/SceneMakerAI/agent-stt/issues/3](https://github.com/SceneMakerAI/agent-stt/issues/3)

#### 문제

자막 공정의 웹 검색 단계(등장인물·선수 명단 수집)에서 위키 페이지 본문을 가져오다가 `stt_svc` 프로세스가 통째로 죽었습니다(2026-09-21). 파이썬 예외가 아니라 프로세스 `SIGABRT` 라서 `try/except` 로 잡히지 않았고, 같은 프로세스에서 처리 중이던 다른 요청도 함께 끊겼습니다.

#### 원인

본문 추출에 `ddgs` 의 `DDGS().extract()` 를 쓰고 있었습니다.

- `extract()` 는 요청한 형식과 무관하게 `text_markdown` 등 모든 형식을 미리 계산합니다.
- 그 변환은 `primp` 안의 Rust `html2text` 가 수행합니다.
- Rust 쪽에서 panic 이 나면 파이썬 예외로 올라오지 않고 프로세스가 중단됩니다.

"한 질의의 실패가 전체 검색을 흔들면 안 된다" 는 설계를 `except Exception` 으로 지키고 있었지만, 이 종류의 실패는 그 방어선을 통과합니다. 환경은 `ddgs 9.14.4` , `primp 1.3.1` 입니다.

#### 조치

- 커밋 41cc248 — `DDGS().extract()` 를 쓰지 않도록 바꿨습니다. `ddgs` 의 HTTP 클라이언트로 HTML 원문만 받고, 텍스트 변환은 `lxml` 기반의 자체 함수가 합니다. 블록 요소마다 줄을 바꾸고 표 칸은 ` | ` 로 이어, 명단 표의 한 행이 한 줄로 남게 했습니다.
- 같은 커밋에서 스포츠·드라마 프로파일의 검색을 잠시 껐다가, 커밋 418b75d 에서 다시 켰습니다.

#### 남은 일

- 죽었던 URL 을 기록해 두지 않았습니다. 재현용 HTML 을 확보하면 `primp` (또는 `ddgs` ) 업스트림에 panic 을 보고합니다.
- 새 변환 함수의 회귀 테스트가 없습니다.
- 네이티브 확장이 프로세스를 죽일 수 있는 다른 호출 지점을 점검해야 합니다.

#### 교훈

네이티브 확장(Rust·C)의 panic 은 `try/except` 로 격리되지 않습니다. 신뢰할 수 없는 외부 입력을 그런 코드에 넘길 때는 순수 파이썬 경로를 쓰거나 별도 프로세스로 격리해야 합니다.

#### 결과

2026-10-06 등록했습니다. 수정은 이미 반영돼 있고, 남은 일 때문에 이슈는 열어 두었습니다. `agent-stt` 는 비공개 저장소라 이슈 링크는 권한이 있는 사람만 열 수 있습니다.

