---
id: tga-32비트-컬러맵-이미지-로드-실패-수정
title: "TGA 32비트 컬러맵 이미지 로드 실패 수정"
sidebar_position: 57
slug: "57"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-15
---

## Pillow: 32비트 컬러맵 TGA 를 열면 load 단계에서 ValueError

링크: https://github.com/python-pillow/Pillow/pull/10211

### 배경

TGA 는 팔레트(컬러맵) 항목 크기로 15/16, 24, 32비트를 쓸 수 있다. Pillow 의 `TgaImagePlugin` 은 세 경우 모두에 분기를 두고 있지만, 32비트 분기는 실제로 한 번도 동작하지 않는 상태였다. 테스트에도 16비트(`p_16.tga` )와 24비트만 있고 32비트는 없다.

### 원인

`src/PIL/TgaImagePlugin.py` 133\~136행. 32비트 컬러맵은 `ImagePalette.raw("BGRA", ...)` 로 읽는데 팔레트 mode 는 기본값 "RGB" 로 남는다. 이미지를 load 할 때 `Image.load()` 가 `putpalette("RGB", "BGRA", ...)` 를 호출하고, C 쪽 unpacker 표에 RGB ← BGRA 조합이 없어 `ValueError: unrecognized raw mode` 가 난다. 바로 위 16비트 분기는 2024년 수정(#7965 등)에서 `self.palette.mode = "RGBA"` 를 넣어 해결돼 있다.

### 변경 내용

- 32비트 분기에도 `self.palette.mode = "RGBA"` 한 줄 추가 (16비트 분기와 동일한 처리).
- `Tests/test_file_tga.py` 에 `test_palette_depth_32` 추가: 2x1 컬러맵 TGA 를 바이트로 만들어 열고, mode P / 팔레트 mode RGBA / RGBA 변환 결과(불투명 빨강, 투명 파랑)를 확인한다.

### 검증

- main: 재현 스크립트가 `ValueError: unrecognized raw mode` 로 실패, 새 테스트도 실패.
- 수정 후: 새 테스트 통과, `Tests/test_file_tga.py` 전체 43건 통과, 전체 테스트 5198 passed (로컬 빌드에 없는 OpenJPEG·AVIF 등은 skip).
- 같은 바이트를 ffmpeg 로 디코드한 RGBA 값과 수정 후 Pillow 결과가 일치.
- pre-commit(ruff, black, bandit 등)과 mypy 통과.
- 중복: TGA 관련 issue/PR 전체를 훑었고 32비트 컬러맵 건은 없음. 열린 #8158 은 16비트 줄만 바꿈.

