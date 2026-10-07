---
id: 29975994-fps-에서-contentdetector-가-min-scene-len-만큼-떨어진-컷을-버리는-07-회귀
title: "29.97/59.94 fps 에서 ContentDetector 가 min_scene_len 만큼 떨어진 컷을 버리는 0.7 회귀"
sidebar_position: 45
slug: "45"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-07
---

## PySceneDetect: 29.97/59.94 fps 영상에서 ContentDetector 가 min_scene_len 프레임만큼 떨어진 컷을 버린다

링크: https://github.com/Breakthrough/PySceneDetect/issues/577

- 리포: Breakthrough/PySceneDetect (스타 약 5.2k, 기본 브랜치 `main` , HEAD `81c414c` , 버전 0.7.1)
- 유형: Issue (버그 리포트, "Python API" 템플릿). 스타 1만 미만이라 PR 은 준비하지 않았고 클론에 코드 수정도 없다.

### 배경

worker-prep-vision 은 방송 영상(29.97/59.94 fps)을 `ContentDetector(threshold, min_scene_len=round(min_sec * fps))` 로 샷 분할한다. `prep_min_sec=1.0` 이면 `min_scene_len` 은 30(29.97 fps) 또는 60(59.94 fps) 프레임이다.

0.7 부터 이 값들에서 "직전 컷으로부터 정확히 `min_scene_len` 프레임 뒤"에 있는 컷이 버려진다. API 기본값 15 도 같은 경우에 해당한다. 0.6.7 에서는 정상이었다.

### 원인

`scenedetect/detector.py` 의 `FlashFilter` (179-181행, 194-196행).

- 0.7 의 VFR 지원 작업(#540)에서 `FlashFilter` 가 프레임 수 대신 시간(초)으로 비교하도록 바뀌었다.
- 정수 프레임 길이는 `self._filter_length / float(frame_rate)` 로 초로 바꾼 뒤, 경과 시간 `(timecode - self._last_above)` 과 float 로 비교한다.
- NTSC 계열은 `float(frame_rate)` 가 정확하지 않아 몫이 참값보다 1 ulp 크게 나올 수 있다. 30000/1001 fps 에서 15 프레임은 경과 시간이 `0.5005` , 기준값이 `0.5005000000000001` 이라 `>=` 가 False 가 된다.
- 정확한 PTS(PyAV) 기준으로 N = 3, 6, 12, 15, 24, 25, 30, 39, 48, 50, 59, 60 이 항상 해당한다 (N 60 이하에서 확인, 29.97 과 59.94 동일).
- OpenCV 백엔드는 위치를 마이크로초로 반올림하기 때문에, 프레임 길이가 정수 마이크로초가 아닌 프레임률(30, 23.976, 29.97, 59.94)에서 N 이 3의 배수가 아니면 시작 위치에 따라 1 µs 모자라 같은 현상이 난다. 예: 29.97 fps, `min_scene_len=17` 에서 OpenCV 는 17 프레임 뒤 컷을 버리고 PyAV 는 유지한다.
- `HistogramDetector` , `HashDetector` , `AdaptiveDetector` , `ThresholdDetector` 는 `FrameTimecode >= int` 로 프레임 번호끼리 비교해서 영향이 없다.

### 재현 방법

영상 없이 재현된다 (`repro_min.py` ). 30000/1001 fps 스트림에서 PyAV 백엔드가 돌려주는 위치를 그대로 만들어 `FlashFilter(length=15)` 에 15 프레임마다 컷 신호를 넣는다.

```text
gap.frame_num          : 15
gap.seconds            : 0.5005
15 / float(fps)        : 0.5005000000000001
gap >= 15 / float(fps) : False  <- what FlashFilter evaluates
gap >= 15              : True  <- what the other detectors evaluate
MERGE    cuts every 15 frames -> []
SUPPRESS cuts every 15 frames -> [30, 60, 90, 120, 150, 180, 210, 240, 270]
```

기대값은 두 모드 모두 15, 30, 45, ..., 285 이고, 0.6.7 의 `FlashFilter` 는 그렇게 돌려준다.

실제 파일로도 확인했다 (`repro.py` ). ffmpeg 로 샷 길이가 정확히 15 프레임인 150 프레임 클립을 다섯 가지 프레임률로 만들고 `min_scene_len=15` 로 검출했다.

| 프레임률 | ContentDetector (HEAD) | HistogramDetector / AdaptiveDetector (HEAD) | ContentDetector (0.6.7) |

|---|---|---|---|

| 25, 30, 24000/1001 | 9컷 | 9컷 | 9컷 |

| 30000/1001 | 0컷 | 9컷 | 9컷 |

| 60000/1001 | 0컷 | 9컷 | 9컷 |

HEAD 는 OpenCV, PyAV 두 백엔드 결과가 같다. PyPI 의 0.7 과 0.6.7 은 OpenCV 백엔드로만 돌렸고, 0.7 은 HEAD 와 같은 결과다. 0.6.7 의 HistogramDetector 는 첫 컷(15)을 내지 않아 8컷인데 이번 건과 무관하다.

### 검증

- HEAD `81c414c` (editable 설치), PyPI `scenedetect==0.7` , `scenedetect==0.6.7` 세 환경에서 같은 스크립트를 돌렸다. 원문 출력은 `repro.txt` .
- `repro_timing.py` 로 프레임률·백엔드별로 영향받는 N 목록을 뽑았다.
- 돌리지 않은 것: 리포의 pytest 전체(테스트 영상 리소스 필요), `TransNetV2Detector` (`FlashFilter` 를 쓰므로 같은 동작일 것으로 보이나 실행하지 않음).
- 수정 방향은 본문에 한 문단으로만 적었다 (정수 길이는 `Fraction` 으로 정확히 계산하거나 프레임 수로 비교, OpenCV 의 마이크로초 반올림에는 프레임 미만의 허용 오차). #540 이 의도적으로 시간 단위로 바꾼 부분이라 메인테이너 판단이 필요하다.

### 중복 확인

- #540 (머지): `FlashFilter` 를 시간 단위로 바꾼 PR. 이번 건은 그때 들어간 float 변환 문제.
- #408, #571 (머지), #557 (닫힘): `AdaptiveDetector` 가 현재 프레임 기준으로 `min_scene_len` 을 검사하던 문제. 다른 검출기, 다른 원인.
- #569 (열림): VFR 에서 `frame_num` 이 근사값인 문제. 이번 건은 CFR.
- #477 (열림): CLI 기본값 0.6s 와 API 기본값 15 프레임의 차이에 대한 질문.
- #539 (열림): 0.6.7 에서 마지막 장면이 1 프레임인 문제.
- 검색어: min_scene_len, min-scene-len, FlashFilter, filter_secs, floating point, off-by-one, 29.97, NTSC, 30000/1001, time-based units, ContentDetector regression, missing cuts, fewer scenes 0.7

