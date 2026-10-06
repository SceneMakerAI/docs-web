---
id: 10분-이상-파일에서-sfinfo-duration-이-지수-표기로-깨지는-문제-수정
title: "10분 이상 파일에서 sf.info() duration 이 지수 표기로 깨지는 문제 수정"
sidebar_position: 32
slug: "32"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## python-soundfile: 10분 이상 파일에서 sf.info() 의 duration 이 지수 표기로 깨지는 문제

링크: https://github.com/bastibe/python-soundfile/pull/497

### 배경

SceneMakerAI 의 STT / LID 벤치마크는 ffmpeg 로 뽑은 16 kHz mono PCM16 WAV(1\~3시간 분량)를 soundfile 로 읽는다. upstream 코드를 읽던 중 `sf.info(file)` 을 출력했을 때 나오는 `duration:` 줄이 10분 이상 길이에서 `2e+01:0.000 min` , `3:2e+01:7.500 h` 처럼 깨진다는 것을 확인했다. 우리 벤치 코드가 `sf.info()` 의 repr 을 직접 쓰지는 않지만(`.duration` 속성 값 자체는 정상), 긴 파일을 점검할 때 바로 마주치는 출력이다.

- 대상: bastibe/python-soundfile `master` 3503941 (0.14.0), 번들 libsndfile 1.2.2
- 형태: PR (포맷 지정자 수정 + 테스트)

### 원인

`soundfile.py` 461-472 행 `_SoundFileInfo._duration_str` 이 시·분을 `.0g` , `02.0g` 로 포맷한다. `g` 에서 정밀도 0 은 유효숫자 1자리라는 뜻이라 10 이상이면 한 자리로 반올림된 뒤 지수 표기로 바뀐다 (`format(15.0, '02.0g')` 은 `'2e+01'` ). 초는 `05.3f` 인데 `d.ddd` 가 이미 5글자라 0 채움이 전혀 적용되지 않는다 (`01:1.000 min` ).

또 반올림 전에 분·초를 나누기 때문에 119.9996초 같은 값은 1분 + 59.9996초로 나뉜 뒤 `01:60.000 min` 으로 찍힌다.

issue #443 에 인용된 `6e+10:4e+01:3.719h` 의 `4e+01` 도 이 포맷 문제다(그 이슈가 다룬 프레임 수 문제는 libsndfile 쪽이라 별개).

### 변경 내용

- 시·분은 `.0f` / `02.0f` , 초는 `06.3f` 로 변경
- 나누기 전에 duration 을 밀리초 단위로 반올림 (`round(self.duration, 3)` )
- `tests/test_soundfile.py` 에 `test_info_duration` (8 케이스, parametrize) 추가. `samples` / `s` 분기와 `duration` 속성은 그대로

| 길이 | 수정 전 | 수정 후 |

|---|---|---|

| 61 s | `01:1.000 min` | `01:01.000 min` |

| 900 s | `2e+01:0.000 min` | `15:00.000 min` |

| 11707.5 s | `3:2e+01:7.500 h` | `3:15:07.500 h` |

| 36000 s | `1e+01:00:0.000 h` | `10:00:00.000 h` |

| 119.9996 s | `01:60.000 min` | `02:00.000 min` |

### 검증

- 수정 전 HEAD 에서 재현 스크립트 실행: 위 표의 "수정 전" 출력 확인 (`repro.txt` )
- 새 테스트를 수정 전 코드에 돌리면 8개 중 6개 실패, 수정 후 8개 통과
- `python -m pytest` 전체: 339 passed (수정 전 331 passed)
- `python -m pyright soundfile.py` : 수정 전후 동일하게 188 행 기존 오류 2건, 신규 없음
- 확인 못 한 것: Windows / macOS / PyPy / free-threaded 3.14 CI 매트릭스 (로컬은 Linux x86_64, CPython 3.11 만)

