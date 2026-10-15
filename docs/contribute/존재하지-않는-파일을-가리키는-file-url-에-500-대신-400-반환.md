---
id: 존재하지-않는-파일을-가리키는-file-url-에-500-대신-400-반환
title: "존재하지 않는 파일을 가리키는 file:// URL 에 500 대신 400 반환"
sidebar_position: 56
slug: "56"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-15
---

## vLLM: 존재하지 않는 파일을 가리키는 file:// URL 에 500 대신 400 반환

링크: https://github.com/vllm-project/vllm/pull/61751

### 배경

`--allowed-local-media-path` 를 켠 서버에 허용 디렉터리 안의 없는 파일(또는 디렉터리)을 가리키는 `file://` URL 을 `image_url` / `video_url` 로 보내면 500 InternalServerError 가 난다. 경로는 요청이 준 값이므로 클라이언트 오류여야 하고, 원격 URL 의 404 는 이미 클라이언트 오류(#47165)로 처리되고 있다.

### 원인

`vllm/multimodal/media/connector.py` 의 `_load_file_url` 은 경로가 허용 디렉터리 하위인지 만 확인하고 `media_io.load_file` 을 호출한다. 여기서 나는 `FileNotFoundError` / `IsADirectoryError` 는 `ValueError` 가 아니어서 500 으로 매핑된다.

### 변경 내용

- 하위 경로 검사 뒤에 `filepath.is_file()` 검사를 추가하고 아니면 `ValueError` 발생 (동기·비동기 경로 공통).
- `tests/multimodal/media/test_connector.py` 에 없는 파일·디렉터리 케이스 테스트 추가.

### 검증

- main `03091e28b` (2026-10-12) 에서 새 테스트 2개 실패, 수정 후 통과. `tests/multimodal/media/test_connector.py` 전체 84개 통과 (CPU).
- `ruff check` , `ruff format --check` 통과. mypy·pre-commit 과 실제 서버 실행은 하지 못함 (HTTP 상태는 `create_error_response` 로 확인).

