---
id: ifd1썸네일-ifd을-읽은-뒤-exiftobytes저장이-structerror-로-실패하는-회귀-수정
title: "IFD1(썸네일 IFD)을 읽은 뒤 Exif.tobytes()·저장이 struct.error 로 실패하는 회귀 수정"
sidebar_position: 50
slug: "50"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-12
---

## Pillow: IFD1 을 읽은 뒤 Exif.tobytes() 가 struct.error 로 실패하는 문제 수정

링크: https://github.com/python-pillow/Pillow/pull/10188

- 리포: python-pillow/Pillow (스타 13,890)
- 유형: PR
- 브랜치: `exif-ifd1-tobytes` (기준 `origin/main` 192140806)
- 변경 파일: `src/PIL/Image.py` 1줄, `Tests/test_image.py` 5줄

### 배경

JPEG 의 EXIF 에는 썸네일 정보를 담는 두 번째 디렉터리 IFD1 이 있다. Pillow 에서는 `exif.get_ifd(ExifTags.IFD.IFD1)` 로 읽는다. 그런데 Pillow 11.1.0 부터는 IFD1 을 한 번 읽고 나면 같은 `Exif` 객체를 바이트로 바꾸는 모든 경로가 예외로 끝난다. `im.save(..., exif=exif)` 가 대표적이다.

```python
from io import BytesIO

from PIL import ExifTags, Image

with Image.open("Tests/images/flower.jpg") as im:
    exif = im.getexif()
    exif.get_ifd(ExifTags.IFD.IFD1)
    im.save(BytesIO(), "JPEG", exif=exif)
```

```text
struct.error: ushort format requires 0 <= number <= 65535
```

릴리스 휠로 확인한 결과 9.4.0 부터 11.0.0 까지는 정상 저장되고, 11.1.0, 11.2.1, 11.3.0, 12.0.0, 현재 main 에서 실패한다. 코드를 읽다가 찾은 문제이고, 운영 중에 겪은 장애는 아니다.

### 원인

`ExifTags.IFD.IFD1` 의 값은 실제 태그 번호가 아니라 내부 표시용 -1 이다 (`src/PIL/ExifTags.py:359` ). `get_ifd()` 는 읽은 IFD 를 `_ifds` 사전에 이 값을 키로 넣어 둔다.

PR #8635 (11.1.0, "Keep new IFDs when converting EXIF to bytes") 가 `Exif.tobytes()` 에 `_ifds` 의 항목 중 `Exif` 객체에 키가 없는 것을 전부 IFD0 에 써 넣는 반복문을 추가했다 (`src/PIL/Image.py:4219-4221` ). 새로 만든 Exif IFD, GPS IFD 를 잃지 않게 하려는 변경이었는데, IFD1 도 조건에 걸려 -1 이 태그 번호로 들어가고 `struct.pack` 의 unsigned short 범위 검사에서 실패한다.

### 변경 내용

반복문에서 IFD1 만 건너뛴다.

```python
for tag, ifd_dict in self._ifds.items():
    if tag not in self and tag != ExifTags.IFD.IFD1:
        ifd[tag] = ifd_dict
```

`tobytes()` 는 #8635 이전에도 IFD1 을 쓰지 않았으므로, 결과는 IFD1 을 읽지 않았을 때와 같아진다. 썸네일을 실제로 다시 써 주는 것은 별도 기능이라 넣지 않았다.

기존 테스트 `test_exif_ifd1` 끝에 IFD1 을 읽은 뒤 `tobytes()` 를 호출하고 다시 읽어 Make 태그를 확인하는 세 줄을 붙였다.

### 검증

- 수정 전: 추가한 테스트가 `struct.error` 로 실패하는 것을 확인.
- 수정 후: 같은 테스트 통과. EXIF 관련 테스트 파일 8개 584건 통과, 6건 건너뜀.
- 전체 테스트 5120건 통과, 1건 실패. 실패한 `test_file_pdf.py::test_save_all_object_ids` 는 로컬 빌드에 OpenJPEG 가 없어서 나는 것으로 변경과 무관하다.
- pre-commit (ruff, black, bandit 등) 통과. mypy 는 CI 용 의존성을 설치하지 않아 CI 와 같은 조건으로는 돌리지 못했다. 직접 돌린 결과의 오류 6건은 모두 스텁 누락이고 변경한 줄에는 없다.

### 중복 확인

열린 것과 닫힌 것 모두에서 IFD1, tobytes, get_ifd, struct.error, thumbnail 조합으로 검색했고 같은 제보는 없었다. 가장 가까운 것은 #10177 (get_ifd 안의 KeyError, 다른 함수) 과 #8635 (이 반복문을 넣은 PR) 이다.

### 남겨 둔 것

같은 반복문 때문에 Interop, MakerNote 를 읽은 뒤에는 0xA005, 0x927C 가 IFD0 에도 한 번 더 쓰인다. 예외는 나지 않고 동작 판단이 필요한 부분이라 이번 변경에는 넣지 않았다.

