---
id: exif-transpose-이후-imagemagick-형식-exif-가-파생-이미지에서-사라지는-문제-수정
title: "exif_transpose() 이후 ImageMagick 형식 EXIF 가 파생 이미지에서 사라지는 문제 수정"
sidebar_position: 46
slug: "46"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-07
---

## Pillow: exif_transpose() 이후 ImageMagick 형식 EXIF 가 통째로 사라지는 문제

링크: https://github.com/python-pillow/Pillow/pull/10145

### 배경

SceneMaker 의 이미지 모델 워커는 프레임과 업로드 이미지를 `Image.open` 으로 연 뒤 `ImageOps.exif_transpose` 로 방향을 바로잡고, 이어서 `convert` , `resize` , `crop` 을 거친다. ImageMagick 으로 만든 PNG 는 EXIF 를 표준 `eXIf` 청크가 아니라 `Raw profile type exif` 라는 텍스트 청크에 16진 문자열로 담는 경우가 있고, Pillow 는 이 값을 `im.info["Raw profile type exif"]` 로 읽어 `getexif()` 에서 해석한다.

### 원인

`Image.getexif()` (`src/PIL/Image.py:1650-1653` ) 는 이 값을 줄바꿈으로 나눈 뒤 앞의 세 줄(빈 줄, `exif` , 길이)을 건너뛰고 나머지를 16진으로 해석한다. 그런데 `ImageOps.exif_transpose()` (`src/PIL/ImageOps.py:748-749` ) 는 방향 태그를 지운 뒤 이 값을 머리줄 없이 16진 문자열 한 줄로만 다시 써 넣는다. 그래서 다음에 이 값을 해석하면 "세 줄을 건너뛴 나머지"가 비어 있어 방향 태그뿐 아니라 모든 EXIF 태그가 사라진다.

`exif_transpose()` 가 돌려준 이미지 자체는 `Exif` 객체가 캐시되어 있어 정상으로 보인다. 하지만 그 이미지에서 `copy()` , `convert()` , `resize()` , `crop()` 으로 만든 이미지는 `info` 를 복사해 다시 해석하므로 `getexif()` 가 빈 결과를 돌려준다. 2021년 #5584 에서 이 분기가 추가될 때부터 있던 불일치다. 기존 테스트 이미지는 태그가 방향 하나뿐이고 `info` 를 다시 해석하지도 않아서 드러나지 않았다.

### 변경 내용

- `src/PIL/ImageOps.py` : `Raw profile type exif` 값을 읽을 때와 같은 형식(빈 줄, `exif` , 8칸 폭 길이, 16진 데이터)으로 다시 쓴다. 한 줄이던 코드를 네 줄로 바꾼 것이 전부다.
- `Tests/test_imageops.py` : 방향과 제조사 두 태그를 가진 값을 만들어 `exif_transpose()` 후 `copy().getexif()` 에 제조사 태그가 남아 있는지 확인하는 `test_exif_transpose_raw_profile` 추가.
- `docs/releasenotes/13.0.0.rst` : "Other changes" 에 항목 추가.

### 검증

- 수정 전 `origin/main` (`bfb6b386c` ) 에서 재현 스크립트 실행: `copy()` , `convert()` , `resize()` 뒤의 `getexif()` 가 모두 빈 딕셔너리.
- 새 테스트는 수정 전 `KeyError: 271` 로 실패, 수정 후 통과.
- `python3 -m pytest Tests/ -n 8` : 5132 통과, 1 실패. 실패 1건(`Tests/test_file_pdf.py::test_save_all_object_ids` )은 이 머신의 로컬 빌드에 OpenJPEG 가 없어서 나는 것으로 수정 전에도 똑같이 실패한다.
- `pre-commit run` (ruff, black, bandit, sphinx-lint 등)과 `mypy` 통과.
- C 확장은 클론에서 직접 빌드했다. 개발용 헤더는 시스템에 설치하지 않고 RPM 을 내려받아 캐시 디스크에 풀어 썼다.

