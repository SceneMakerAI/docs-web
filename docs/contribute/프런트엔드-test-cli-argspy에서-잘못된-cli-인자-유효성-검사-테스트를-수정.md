---
id: 프런트엔드-test-cli-argspy에서-잘못된-cli-인자-유효성-검사-테스트를-수정
title: "[프런트엔드] test_cli_args.py에서 잘못된 CLI 인자 유효성 검사 테스트를 수정"
sidebar_position: 3
slug: "3"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-06-26
---

[https://github.com/vllm-project/vllm/pull/46779](https://github.com/vllm-project/vllm/pull/46779)

### **목적**

두 가지 테스트에서 `tests/entrypoints/openai/test_cli_args.py` 잘못된 계약 내용이 제시되어 허위 확신을 심어주었습니다.

1. `test_enable_auto_choice_fails_with_enable_reasoning-enable-auto-tool-choice` 와 결합하면 `-reasoning-parser` 실패해야 한다고 주장했습니다. 그러나 이 조합은 (예: ) 에 **지원되는 것으로 문서화되어**  있으며, 올바르게 거부하지 **않습니다**  . 테스트가 통과한 것은 가 생략되었기 때문이며, 실제로는 관련 없는 "자동 도구 선택에는 도구 호출 파서가 필요합니다" 검사를 트리거하여 추론 충돌 유효성 검사가 존재하지 않는다는 사실(그리고 존재해서는 안 된다는 사실)을 가렸습니다. 도구 호출 파서가 설정된 경우 문서화된 조합이 통과하는지 확인하도록 다시 작성했습니다.`docs/features/tool_calling.md-tool-call-parser hunyuan_a13b --reasoning-parser hunyuan_a13bvalidate_parsed_serve_args-tool-call-parser`
2. `test_enable_auto_choice_passes_without_tool_call_parser` 이름이 잘못 지정되었습니다. 해당 함수의 문서 문자열과 본문에서는 유효성 검사가 *실패한다고*  명시하고 있습니다 . `test_enable_auto_choice_fails_without_tool_call_parser` 실제 동작과 일치하도록 이름을 변경했습니다.

이는 테스트 전용 변경 사항이며, 런타임 동작은 수정되지 않습니다.

**중복이 아닙니다.** `test_cli_args`  , `validate_parsed_serve_args` , 및 에 대한 공개 PR을 검색해 보았지만, `test_enable_auto_choice` 해당 테스트는 건드리지 않았습니다.

### **테스트 플랜**

```text
python -m pytest tests/entrypoints/openai/test_cli_args.py -v
# lint
ruff check tests/entrypoints/openai/test_cli_args.py
ruff format --check tests/entrypoints/openai/test_cli_args.py
```

### **시험 결과**

```text
28 passed in 5.48s
ruff: All checks passed! / 1 file already formatted
```

