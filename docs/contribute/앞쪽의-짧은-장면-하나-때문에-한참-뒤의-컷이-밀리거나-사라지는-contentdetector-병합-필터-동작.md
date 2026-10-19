---
id: 앞쪽의-짧은-장면-하나-때문에-한참-뒤의-컷이-밀리거나-사라지는-contentdetector-병합-필터-동작
title: "앞쪽의 짧은 장면 하나 때문에 한참 뒤의 컷이 밀리거나 사라지는 ContentDetector 병합 필터 동작"
sidebar_position: 60
slug: "60"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-19
---

## PySceneDetect Discussion: ContentDetector merge 필터가 짧은 장면 하나 뒤로 계속 켜져 있는 문제

한 줄 요약: ContentDetector 의 기본 filter_mode(MERGE)에서, 영상 앞부분에 min_scene_len 보다 짧은 장면이 한 번 생기면 merge 상태가 풀리지 않아 수백 프레임 뒤의 정상 컷이 다른 위치로 밀리거나(400 → 415) 영상 끝 근처면 아예 사라진다. 의도된 동작인지 묻는다.

### 배경 (SceneMaker 에서의 사용)

- worker-prep-vision `src/service/prep/detect.py` 의 `detect_scenes()` 가 PySceneDetect 로 스포츠 중계 영상(청크 단위 mp4)을 장면으로 나눈다. `ContentDetector(threshold=15, min_scene_len=round(1.0 * fps))` , filter_mode 는 기본값(MERGE), 디코딩은 OpenCV(headless) 백엔드. 설정값은 `src/config.py` 의 `prep_threshold=15.0` , `prep_min_sec=1.0` , `prep_max_sec=15.0` .
- 결과 컷은 짧은 장면 병합 → 긴 장면 균등분할 → 0.1초 스냅을 거쳐 t_vision 타일이 되고, 하류 vision 분석·하이라이트의 장면 경계가 된다. 커밋 `0ceaa48e2` (2026-09-03, "document scene split output contract for downstream")에서 "분할 기준을 바꾸면 하류 캡션·장면 경계가 모두 이동한다"고 계약을 문서화했다. 같은 설정에서 컷 위치가 앞쪽의 무관한 플래시 하나 때문에 바뀌면 이 계약이 흔들린다.
- threshold 15 는 기본값(27)보다 낮아 중계 화면의 플래시·리플레이 전환 그래픽 같은 짧은 장면이 잘 생긴다. 실제 장애를 겪은 것은 아니고, 합성 영상으로 테스트하다 발견했다고 쓴다.

### 재현 (scenedetect 0.7.2 최신, 0.7.0·0.6.7 동일)

30fps 흑/백 교대 합성 영상, ContentDetector(threshold=15, min_scene_len=30):

```text
[100, 400, 415] -> [100, 400]
[100, 110, 400, 415] -> [100, 415]   # 110 에 짧은 장면 하나 추가 → 290프레임 뒤 컷이 415 로 이동
[100, 580] -> [100, 580]
[100, 110, 580] -> [100]             # 470프레임 뒤, 끝에서 20프레임 전 컷이 사라짐
```

filter_mode=SUPPRESS 로 바꾸면 네 경우 모두 400 / 580 으로 나온다. 원인(코드 읽음): `FlashFilter._filter_merge` 에서 `_merge_triggered` 가 `_last_above - _merge_start >= min_scene_len` 일 때만 풀리는데, 짧은 장면 하나로는 이 조건이 영원히 안 맞는다. 메인테이너가 #35 에서 설명한 "min-scene-len 동안 컷이 없으면 해제"와 다르다.

### 묻는 것

이것이 의도된 merge 동작인지, 아니면 min_scene_len 동안 컷이 없으면 merge 상태가 풀려야 하는지.

### 우리 쪽 시사점 (업스트림 글에는 안 씀)

답과 무관하게, 청크 끝 1초 안의 컷 유실·컷 위치 흔들림을 피하려면 `filter_mode=SUPPRESS` 를 명시하는 것을 검토할 수 있다. 다만 분할 기준 변경이라 하류 경계가 이동하므로 단독 변경 금지 규칙(0ceaa48e2)에 따라 별도 결정이 필요하다.

링크: https://github.com/Breakthrough/PySceneDetect/discussions/585

