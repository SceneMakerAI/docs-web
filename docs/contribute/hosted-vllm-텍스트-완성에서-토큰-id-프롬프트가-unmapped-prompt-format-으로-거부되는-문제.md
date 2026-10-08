---
id: hosted-vllm-텍스트-완성에서-토큰-id-프롬프트가-unmapped-prompt-format-으로-거부되는-문제
title: "hosted_vllm 텍스트 완성에서 토큰 ID 프롬프트가 Unmapped prompt format 으로 거부되는 문제"
sidebar_position: 49
slug: "49"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-08
---

## litellm: hosted_vllm 텍스트 완성에서 토큰 ID 프롬프트가 거부되는 문제 (Issue)

링크: https://github.com/BerriAI/litellm/issues/45253

### 배경

vLLM 의 `/v1/completions` 는 `prompt` 로 문자열뿐 아니라 토큰 ID 배열(정수 리스트, 정수 리스트의 리스트)도 받는다. litellm 은 `openai/` 접두사로 호출하면 토큰 ID 를 그대로 전달하지만, vLLM 전용 provider 인 `hosted_vllm/` 로 호출하면 요청을 보내기도 전에 예외를 던진다. vLLM 백엔드의 텍스트 완성 경로 코드를 읽다가 발견했다 (운영 중 겪은 장애는 아니다).

### 원인

`litellm/main.py` 의 `text_completion()` 은 프롬프트가 정수 리스트일 때 통과시킬 provider 를 openai, azure, azure_text, text-completion-codestral, text-completion-openai 다섯 개로만 한정한다 (7660-7677행). 이 목록은 2025-12 의 PR #18011 (이슈 #17118 수정) 에서 추가됐는데, 당시 제보자가 `openai/` 접두사를 썼기 때문에 그 경로만 열렸다.

반면 `completion()` 은 `openai_text_completion_compatible_providers` (hosted_vllm, together_ai, fireworks_ai, llamafile 등) 에 속한 provider 를 `text_completion=True` 일 때 OpenAI 텍스트 완성 핸들러로 그대로 보낸다 (5904-5911행). 즉 뒤쪽 경로는 토큰 ID 를 문제없이 전달할 수 있는데 앞쪽 검사만 막고 있다.

### 재현 방법

```python
import litellm

for model in ("openai/Qwen/Qwen3-8B", "hosted_vllm/Qwen/Qwen3-8B"):
    try:
        r = litellm.text_completion(
            model=model,
            prompt=[151644, 872, 198, 14990, 151645],
            api_base="http://127.0.0.1:18000/v1",
            api_key="EMPTY",
            max_tokens=4,
        )
        print(model, "->", r.choices[0].text)
    except Exception as e:
        print(model, "->", type(e).__name__, e)
```

```text
  stub got /v1/completions {"model": "Qwen/Qwen3-8B", "prompt": [151644, 872, 198, 14990, 151645], "max_tokens": 4}
openai/Qwen/Qwen3-8B ->  Hello!
hosted_vllm/Qwen/Qwen3-8B -> Exception Unmapped prompt format. Your prompt is neither a list of strings nor a string. prompt=[151644, 872, 198, 14990, 151645]. File an issue - https://github.com/BerriAI/litellm/issues
```

### 검증

- main `5825840` (1.106.0) 에서 로컬 스텁 서버로 재현했다. 실제 LLM 호출은 없다.
- `atext_completion` , `Router.atext_completion` 도 같은 예외가 `APIConnectionError` 로 감싸져 나온다.
- `litellm.completion(..., text_completion=True)` 에 토큰 ID 를 직접 넣으면 스텁이 `"prompt": [1, 2, 3]` 을 받는다. 앞단 검사만 문제라는 뜻이다.
- together_ai, fireworks_ai, llamafile 도 같은 방식으로 실패한다.
- 실제 프록시(4000 포트)와 실제 vLLM 서버로는 돌려 보지 않았다.

### 기존 건과의 차이

- #17118 (닫힘): 같은 오류지만 `openai/` 접두사 사례이고 #18011 로 그 provider 들만 고쳐졌다.
- 우리 PR #44977 은 `hosted_vllm/chat/transformation.py` 의 비디오 file 파트 건이라 겹치는 줄이 없다.
- 수정 범위(hosted_vllm 만 추가할지, 호환 provider 목록 전체를 쓸지)는 메인테이너 판단이 필요해 Issue 로 올린다.

