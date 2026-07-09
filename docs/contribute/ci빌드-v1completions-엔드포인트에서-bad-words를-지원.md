---
id: ci빌드-v1completions-엔드포인트에서-bad-words를-지원
title: "[CI/빌드]  /v1/completions 엔드포인트에서 bad_words를 지원"
sidebar_position: 4
slug: "4"
tags: [PR, Merged]
keywords: [PR, Merged]
last_update:
  date: 2026-07-09
---


[https://github.com/vllm-project/vllm/pull/46793](https://github.com/vllm-project/vllm/pull/46793)

### **목적**

채팅 자동 완성 엔드포인트( `/v1/chat/completions` ) 는 `bad_words` 필드를 노출하고 이를 로 전달 `SamplingParams` 하지만, 기존 자동 완성 엔드포인트( ) 는 `/v1/completions` 그렇지 않습니다 . 이는 기능 동등성 격차입니다. 자동 완성 엔드포인트 사용자는 특정 단어를 숨길 수 없습니다.`SamplingParamsbad_words`

이 PR은 기존 채팅 구현( 샘플링 매개변수 블록 및 의 필드 ) 을 반영하여 `bad_words` 필드를 추가하고 `CompletionRequest` 이를 통해 연결합니다 .`to_sampling_params()chat_completion/protocol.pybad_words=self.bad_wordsto_sampling_params`

**중복이 아닙니다.** `bad_words`  (제목/본문), `bad_words CompletionRequest` , 및 에 대한 열린 PR을 검색해 보았지만, `completion bad_words parity` 기존 `bad_words` PR은 토크나이저 변환/캐싱 버그에 관한 것이며, 필드를 완성 엔드포인트에 추가하는 PR은 없습니다.

### **테스트 플랜**

```text
python -m pytest tests/entrypoints/openai/completion/test_completion.py \
  -k "bad_words" -v
# lint
ruff check vllm/entrypoints/openai/completion/protocol.py \
  tests/entrypoints/openai/completion/test_completion.py
ruff format --check vllm/entrypoints/openai/completion/protocol.py \
  tests/entrypoints/openai/completion/test_completion.py
```

CPU 전용 유닛 테스트 두 개를 추가했습니다.

- `test_completion_request_bad_words_to_sampling_paramsbad_wordsSamplingParams`
  —

  는 다음으로 전달됩니다

  .

- `test_completion_request_bad_words_default_empty`
  — 기본적으로 빈 목록으로 설정됩니다(채팅과 동일).

### **시험 결과**

```
2 passed
ruff: All checks passed! / 2 files already formatted
```

