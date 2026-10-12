---
id: run-batch-가-toolreasoning-파서-플러그인을-import-하지-않는-문제-수정
title: "run-batch 가 tool/reasoning 파서 플러그인을 import 하지 않는 문제 수정"
sidebar_position: 51
slug: "51"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-12
---

## vLLM: run-batch 에서 파서 플러그인 로드 누락

링크: https://github.com/vllm-project/vllm/pull/61145

### 배경

`vllm serve` 는 `--tool-parser-plugin` , `--reasoning-parser-plugin` 으로 지정한 파일을 서버 기동 초기에 import 해서 커스텀 파서를 레지스트리에 등록한다. `vllm run-batch` 도 같은 옵션을 CLI 에서 받지만 실제로는 어디에서도 import 하지 않는다.

### 원인

`vllm/entrypoints/launchers/run_batch.py` 의 `main()` 은 `validate_run_batch_args` 와 `build_async_engine_client` 만 호출한다. 엔진 설정 생성 중 `ReasoningConfig.initialize_token_ids` (`vllm/config/reasoning.py:84` ) 가 파서 이름을 조회하는데, 플러그인이 아직 로드되지 않아 KeyError 가 난다. tool parser 쪽은 chat 핸들러 생성 시점에 TypeError 로 실패한다. 헤드리스 모드의 같은 문제는 #53124 에서 이미 수정됐고 run-batch 만 남아 있었다.

### 변경 내용

`run_batch.main()` 시작 부분에서 API 서버와 같은 순서로 두 플러그인을 import 하도록 7줄 추가. 테스트는 임시 플러그인 파일 두 개를 만들어 엔진 클라이언트 생성 시점에 두 파서가 등록돼 있는지 확인한다.

### 검증

- 수정 전: 재현 스크립트와 새 테스트 모두 KeyError 로 실패
- 수정 후: 새 테스트 포함 16개 통과, ruff check / format 통과
- 모델 가중치가 필요한 run-batch 통합 테스트 11개는 CPU 전용 환경이라 실행하지 못함

