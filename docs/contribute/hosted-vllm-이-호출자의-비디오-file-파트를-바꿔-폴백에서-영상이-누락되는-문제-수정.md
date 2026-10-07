---
id: hosted-vllm-이-호출자의-비디오-file-파트를-바꿔-폴백에서-영상이-누락되는-문제-수정
title: "hosted_vllm 이 호출자의 비디오 file 파트를 바꿔 폴백에서 영상이 누락되는 문제 수정"
sidebar_position: 44
slug: "44"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-07
---

## litellm: hosted_vllm 이 호출자의 비디오 file 파트를 video_url 로 제자리에서 바꿔 쓰는 문제

링크: https://github.com/BerriAI/litellm/pull/44977

### 배경

SceneMakerAI 는 vLLM 이 서빙하는 OpenAI 호환 엔드포인트를 LiteLLM 의 `hosted_vllm/` 프로바이더로 호출하고, 메시지에 영상 파트를 넣는다. LiteLLM 에서 프로바이더 중립적인 영상 표현은 `type: "file"` 파트이고, `hosted_vllm` 은 요청을 보낼 때 이것을 vLLM 전용인 `type: "video_url"` 파트로 변환한다.

문제는 이 변환이 요청용 사본이 아니라 호출자가 넘긴 `content` 리스트 자체에 덮어써진다는 점이다. `litellm.completion` 은 메시지 dict 는 호출마다 얕게 복사하지만 그 안의 `content` 리스트는 호출자의 객체를 그대로 공유한다.

그 결과:

- `litellm.completion(model="hosted_vllm/...", messages=messages)` 가 끝나면 호출자의 `messages` 안 `file` 파트가 `video_url` 로 바뀌어 있다.
- Router 폴백에서 실제 피해가 난다. vLLM 이 500 을 내서 Gemini 로 폴백하면, Gemini 변환은 `video_url` 파트를 읽지 않으므로 영상이 조용히 빠진 채 텍스트만 전달된다. 응답은 200 이고 경고도 없다.

### 원인

`litellm/llms/hosted_vllm/chat/transformation.py` 의 `HostedVLLMChatConfig._transform_messages` user 분기 (main `5455152` 기준 224\~234행):

```python
for idx, content_item in replaced_content_items:
    message_content[idx] = self._convert_file_to_video_url(content_item)
```

`message_content` 는 `message.get("content")` 로 얻은 호출자의 리스트라서, 인덱스 대입이 호출자 데이터를 바꾼다.

### 변경 내용

- user 메시지의 `content` 를 새 리스트로 만들어 메시지 dict 에 대입한다. 비디오 `file` 파트만 `video_url` 로 바뀌고 나머지 파트는 같은 객체를 그대로 쓴다.
- 파트 하나를 변환하는 작은 메서드 `_video_file_as_video_url` 를 추가하고, 기존의 2단계 루프(인덱스 수집 후 덮어쓰기)를 한 줄로 줄였다.
- vLLM 으로 나가는 요청 본문은 이전과 같다.
- 회귀 테스트 1개 추가: `litellm.completion` 을 respx 로 막은 vLLM 주소에 호출한 뒤, 전송된 본문에는 `video_url` 이 있고 호출자의 `file` 파트 객체는 그대로인지 확인한다.

변경 규모: 2개 파일, +39 / -9.

### 재현 방법

API 키 없이 로컬 HTTP 서버 두 개(500 을 내는 vLLM 대역, 받은 본문을 기록하는 Gemini 대역)와 실제 `litellm.Router` 로 재현했다. 스크립트는 `_drafts/litellm/repro_fallback.py` .

수정 전 (main `5455152` ):

```text
vLLM received parts:   [{"type": "text", ...}, {"type": "video_url", "video_url": {"url": "https://example.com/video.mp4"}}]
Gemini received parts: [{"text": "Describe this video"}]
caller's messages now: [{"type": "text", ...}, {"type": "video_url", ...}]
```

수정 후:

```text
Gemini received parts: [{"text": "Describe this video"}, {"file_data": {"mime_type": "video/mp4", "file_uri": "https://example.com/video.mp4"}}]
caller's messages now: [{"type": "text", ...}, {"type": "file", "file": {"file_id": "https://example.com/video.mp4", "format": "video/mp4"}}]
```

`router.acompletion` 과 `file_data` data URI 조합에서도 같은 차이를 확인했다 (수정 전 텍스트만, 수정 후 `inline_data` ).

### 검증

- 새 테스트는 수정 전 실패, 수정 후 통과. `tests/unit/llms/hosted_vllm` 전체 91개 통과.
- hosted_vllm 을 언급하는 비 proxy 단위 테스트와 `tests/unit/llms/openai/chat` : 수정 후 1755 통과 / 45 실패, 수정 전 1754 통과 / 45 실패. 실패 45개는 양쪽이 동일하다 (이 가상환경에는 proxy extras 가 없고, 원인은 따로 조사하지 않았다).
- `ruff format --check` , `ruff check` , `ruff check --config ruff-tests.toml` , `scripts/ruff_strict_gate.py` , `scripts/type_discipline_gate.py` , `scripts/test_quality_gate.py` 통과. basedpyright 는 해당 파일 오류 수가 수정 전후 52개로 같다.
- 실행하지 못한 것: 전체 `make lint` / `make test-unit` , Rust 브리지 빌드, 실제 vLLM 서버와 실제 Gemini API 를 쓴 검증, proxy 를 띄운 curl 검증.

### 제출 전 확인할 것

- CLA: PR 을 열면 CLA assistant 봇이 댓글을 단다. 계정 소유자가 직접 `https://cla-assistant.io/BerriAI/litellm` 에서 GitHub 로그인 후 서명해야 한다.
- PR 템플릿의 "Proof of Fix" 는 mock 없는 실제 호출을 요구한다. 가능하면 실제 vLLM 서버와 Gemini 키로 Before / After 를 다시 찍어 본문을 교체한다.
- 베이스 브랜치는 `main` , 제목은 Conventional Commits, 브랜치 이름은 `bugfix/...` .

