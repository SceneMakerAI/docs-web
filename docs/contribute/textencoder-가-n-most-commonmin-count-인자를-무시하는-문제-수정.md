---
id: textencoder-가-n-most-commonmin-count-인자를-무시하는-문제-수정
title: "TextEncoder 가 n_most_common·min_count 인자를 무시하는 문제 수정"
sidebar_position: 42
slug: "42"
description: "speechbrain: TextEncoder.limited_labelset_from_iterable 가 인자 대신 고정값을 넘겨 라벨 집합이 제한되지 않던 문제 수정"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## speechbrain: TextEncoder.limited_labelset_from_iterable 가 n_most_common / min_count 를 무시하는 문제 수정

링크: https://github.com/speechbrain/speechbrain/pull/3095

### 배경

`speechbrain.dataio.encoder.CategoricalEncoder.limited_labelset_from_iterable` 는 라벨 빈도를 세어 상위 N개(`n_most_common` ) 또는 최소 등장 횟수(`min_count` ) 이상인 라벨만 라벨셋에 넣는 메서드다. 텍스트용 서브클래스 `TextEncoder` (및 이를 상속한 `CTCTextEncoder` )는 `sequence_input` 기본값만 `True` 로 바꾸기 위해 이 메서드를 오버라이드한다.

### 원인

`speechbrain/dataio/encoder.py` 916-922행의 오버라이드가 전달받은 인자를 부모에 넘기지 않고 상수를 하드코딩해서 넘긴다.

```python
return super().limited_labelset_from_iterable(
    iterable, sequence_input=True, n_most_common=None, min_count=1
)
```

그래서 `TextEncoder` 에서는 `n_most_common` , `min_count` , `sequence_input` 을 어떤 값으로 주든 조용히 무시되고, 모든 라벨이 라벨셋에 들어간다. 예외도 경고도 없어서 어휘 크기를 제한했다고 생각한 채로 학습이 진행된다. 바로 위의 형제 오버라이드 `update_from_iterable` , `update_from_didataset` 은 인자를 그대로 전달하고 있어 단순 실수로 보인다 (2020-12 최초 작성 이후 그대로).

### 변경 내용

- `speechbrain/dataio/encoder.py` : 오버라이드가 `sequence_input` , `n_most_common` , `min_count` 를 그대로 부모에 전달하도록 수정 (1행 → 4행). `sequence_input` 기본값 `True` 는 유지.
- `tests/unittests/test_categorical_encoder.py` : `test_text_encoder_limited_labelset` 추가 (`n_most_common=2` , `min_count=3` , `sequence_input=False` 세 경우).

### 재현 방법

```python
from speechbrain.dataio.encoder import TextEncoder

sentences = [["a", "b", "c"], ["a", "b"], ["a"]]
text = TextEncoder()
text.limited_labelset_from_iterable(sentences, n_most_common=2)
print(text.lab2ind)  # develop: a, b, c 모두 포함 / 수정 후: a, b 만
```

### 검증

- 새 테스트는 `develop` (89ead74d) 에서 실패, 수정 후 통과.
- `pytest tests/unittests/test_categorical_encoder.py` 7 passed, `pytest --doctest-modules speechbrain/dataio/encoder.py` 5 passed.
- `pytest tests/unittests` 전체: 750 passed, 5 skipped, 7 failed. 7건은 수정 전 `develop` 에서도 동일하게 실패하는 환경 요인(torch 버전, transformers 미설치).
- `ruff check` , `ruff format --check` (0.12.4) 통과. codespell, yamllint 는 로컬에서 실행하지 않음.
- 중복 확인: 이슈/PR 검색에서 동일 보고 없음, 오픈 PR 중 `encoder.py` 를 건드리는 것 없음.

