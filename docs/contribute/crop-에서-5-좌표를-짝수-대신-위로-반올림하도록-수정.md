---
id: crop-에서-5-좌표를-짝수-대신-위로-반올림하도록-수정
title: "crop() 에서 .5 좌표를 짝수 대신 위로 반올림하도록 수정"
sidebar_position: 62
slug: "62"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-19
---

## Pillow PR: crop() 의 .5 좌표를 위로 반올림

### 한 줄 요약

`Image.crop()` 이 float 좌표를 Python `round()` 로 정수로 바꾸는데, Python 3 의 `round()` 는 0.5 를 짝수 쪽으로 보내서 같은 크기의 박스도 위치에 따라 1px 크거나 작게 잘렸다. .5 를 항상 위로 반올림(`math.floor(v + 0.5)` )하도록 고쳤다.

### 배경

SceneMaker 의 검출 모델(worker-img_models 의 board_detect, board_detail)이 float 박스를 정수로 만든 뒤 `crop()` 을 부른다. 이 동작을 Discussion #10242 로 먼저 물었고, 메인테이너 radarhere 가 비슷한 ImageDraw 건(#10228, PR #10229)을 알려 줬다. #10229 는 ImageDraw 의 음수 좌표 처리를 C 에서 고치는 것이라 `crop()` 은 다루지 않는다.

### 변경

- `src/PIL/Image.py` `_crop()` : `map(int, map(round, box))` → `math.floor(v + 0.5)`
- `Tests/test_image_crop.py` : `test_crop_float_half` 추가 (수정 전 4건 실패, 수정 후 통과)
- `docs/releasenotes/13.1.0.rst` 새로 만들고 "Other changes" 에 한 단락 (AGENTS.md: 사용자에게 보이는 변경은 릴리스 노트 필수)

### 검증

- 최신 main(b7e8a46fb) 기준 worktree 를 따로 빌드해 전체 테스트 5262 passed, selftest 59 passed, pre-commit 통과
- 수정 전 (84.5 / 85.5 시작, 폭 31) → (32, 1) / (30, 1), 1px 박스 (0, 1). 수정 후 모두 (31, 1) / (1, 1)

링크: https://github.com/python-pillow/Pillow/pull/10243

