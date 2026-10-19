---
id: crop-박스-모서리가-5-일-때-위치에-따라-잘리는-크기가-달라지는-문제-짝수-반올림
title: "crop() 박스 모서리가 .5 일 때 위치에 따라 잘리는 크기가 달라지는 문제 (짝수 반올림)"
sidebar_position: 59
slug: "59"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-19
---

## Pillow Discussion (Q&A): Image.crop() 의 .5 좌표 반올림이 위치에 따라 크기를 바꿈

### 한 줄 요약

`Image.crop()` 은 박스의 네 모서리를 각각 Python `round()` 로 반올림하는데, Python 3 의 `round()` 는 0.5 를 짝수 쪽으로 보내므로(banker's rounding) 같은 폭의 박스라도 위치에 따라 결과 크기가 1px 씩 커지거나 작아지고, 1px 폭 박스는 빈 이미지가 되기도 한다. 의도된 동작인지 묻는다.

### 배경 (SceneMaker 에서 어디에 쓰는지)

- worker-img_models 의 야구 파이프라인은 검출 모델(DETR 계열)이 낸 float 박스로 프레임에서 스코어보드 영역을 잘라 다음 단계(분류·세부 검출)에 PIL 이미지 그대로 넘긴다.
  - `lib/model_baseball/detect/board_detect.py` `_clip()` 이 `int(round(x))` , `int(round(x + w))` 로 좌표를 정수로 만들고 `make_crops()` 가 `im.crop((left, top, right, bottom))` 을 부른다.

  - `lib/model_baseball/detect/board_detail.py` 도 같은 방식, `lib/http/http_util.py` `save_crops()` 는 계산된 고정 박스로 `im.crop()` 후 저장.

- 우리 코드도 Pillow 내부와 같은 `round()` 를 쓰므로 같은 성질을 갖는다. 장애를 겪은 것은 아니고, 박스→crop 변환을 점검하다 발견했다 (본문에도 "noticed while checking" 로 씀).

### 재현 (Pillow 13.0.0, 2026-10-16 릴리스 / main b7e8a46fb 동일)

```python
from PIL import Image
im = Image.new("RGB", (200, 100))
for cx in (100, 101, 102, 103):
    box = (cx - 15.5, 10, cx + 15.5, 20)
    print(box, im.crop(box).size)
print(im.crop((1.5, 0, 2.5, 1)).size)
print(im.crop((2.5, 0, 3.5, 1)).size)
```

결과: 폭 31 박스가 중심 위치에 따라 32 / 30 / 32 / 30 으로 나오고, 1px 박스 (1.5..2.5) 는 폭 0, (2.5..3.5) 는 폭 2.

원인: `Image._crop()` 의 `x0, y0, x1, y1 = map(int, map(round, box))` . 반올림은 2016년 #1745 (이슈 #1744, float 박스가 float size 를 만들던 문제) 에서 들어왔는데, 당시 Pillow 는 Python 2 를 지원했고 Python 2 의 `round()` 는 0.5 를 0 에서 먼 쪽으로 보냈다. Python 3 전환 후 짝수 반올림이 된 것으로 보인다.

### 묻는 것

crop() 의 half-to-even 동작이 의도된 것인지, 아니면 `floor(x + 0.5)` 처럼 0.5 를 일관되게 처리하는 변경을 받아 줄지.

### 중복 확인

issue/PR/discussion 을 crop float·round·rounding·banker's rounding·half to even·crop coordinates 등으로 검색. 가장 가까운 것: #1744/#1745 (반올림 도입, 짝수 반올림 언급 없음), Discussion #6272 (비율 좌표 crop 제안, 다른 주제), #10228/#10229 (ImageDraw 음수 좌표의 truncation, crop 아님).

링크: https://github.com/python-pillow/Pillow/discussions/10242

