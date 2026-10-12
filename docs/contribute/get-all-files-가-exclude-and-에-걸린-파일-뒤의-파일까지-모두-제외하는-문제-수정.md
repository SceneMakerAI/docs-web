---
id: get-all-files-가-exclude-and-에-걸린-파일-뒤의-파일까지-모두-제외하는-문제-수정
title: "get_all_files 가 exclude_and 에 걸린 파일 뒤의 파일까지 모두 제외하는 문제 수정"
sidebar_position: 54
slug: "54"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-12
---

## speechbrain: get_all_files 가 exclude_and 에 걸린 파일 뒤의 파일까지 모두 빼 버리는 문제 수정

링크: https://github.com/speechbrain/speechbrain/pull/3101

### 배경

`speechbrain.utils.data_utils.get_all_files` 는 폴더를 재귀적으로 돌며 파일 목록을 만드는 함수로, 데이터 준비 스크립트와 테스트 도구에서 쓰인다. `match_and` , `match_or` , `exclude_and` , `exclude_or` 네 가지 패턴 인자로 결과를 걸러 낸다. `exclude_and` 는 목록의 패턴이 전부 경로에 들어 있는 파일만 제외하는 옵션이다.

### 원인

`speechbrain/utils/data_utils.py` 141-148행. 파일마다 네 개의 플래그를 다시 계산하는데, `match_and_entry` , `match_or_entry` , `exclude_or_entry` 는 매 파일마다 `False` 로 되돌린 뒤 판정하고 `exclude_and_entry` 만 되돌리지 않는다. 그래서 한 파일이 `exclude_and` 에 걸려 `True` 가 되면 같은 디렉토리에서 그 뒤에 나오는 파일이 전부 제외된다. 예외나 경고는 없고, 몇 개가 빠지는지는 `os.listdir` 순서에 달려 있다. 2020-03 최초 작성 때부터 그대로다.

### 변경 내용

- `speechbrain/utils/data_utils.py` : `exclude_and` 판정 블록 첫 줄에 `exclude_and_entry = False` 추가 (1행). 바로 아래 `exclude_or` 블록과 같은 형태.
- `tests/unittests/test_data_utils.py` 신규: 파일 3개를 만들고 하나씩 `exclude_and` 로 제외했을 때 나머지 2개가 그대로 나오는지 확인. `os.listdir` 순서와 무관하게 수정 전에는 반드시 실패한다.

### 재현 방법

```python
import os, tempfile
from speechbrain.utils.data_utils import get_all_files

d = tempfile.mkdtemp()
for name in ["a.wav", "b.wav", "c.wav"]:
    open(os.path.join(d, name), "w").close()

print(sorted(os.path.basename(f) for f in get_all_files(d, exclude_and=["a.wav"])))
# develop: []  /  수정 후: ['b.wav', 'c.wav']
```

### 검증

- 새 테스트는 `develop` (546bfc9f2) 에서 실패, 수정 후 통과.
- `pytest --doctest-modules speechbrain/utils/data_utils.py` 6 passed, `pytest tests/consistency` 6 passed.
- `pytest tests/unittests` 756 passed, 5 skipped, 5 failed. 실패 5건(`test_filterbank` , `test_g2p` 2건, `test_rescorer` 2건)은 수정을 되돌린 상태에서도 똑같이 실패한다 (torch 2.14.1, `transformers` 미설치 환경).
- `ruff check` , `ruff format --check` (0.12.4) 통과. codespell, yamllint, 통합 테스트, 전체 doctest 는 돌리지 않았다.

### 참고

- 저장소 안에서 `exclude_and` 를 넘기는 호출은 없다 (`exclude_or` 만 쓰인다). 영향은 외부 사용자 코드에 한정된다.
- `exclude_and` 와 `exclude_or` 의 docstring 설명이 서로 바뀌어 있는 것으로 보이지만 이번 변경에는 넣지 않았다.

