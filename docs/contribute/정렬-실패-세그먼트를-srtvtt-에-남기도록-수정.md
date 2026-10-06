---
id: 정렬-실패-세그먼트를-srtvtt-에-남기도록-수정
title: "정렬 실패 세그먼트를 SRT/VTT 에 남기도록 수정"
sidebar_position: 39
slug: "39"
description: "whisperX: 이슈 #1490 의 수정 PR. align() 이 정렬하지 못해 words 가 빈 세그먼트를 SRT·VTT 에서도 큐로 출력"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## whisperX: 정렬 실패 세그먼트를 SRT/VTT 에 남기도록 수정

링크: https://github.com/m-bain/whisperX/pull/1491

이슈 https://github.com/m-bain/whisperX/issues/1490 로 보고한 문제의 수정 PR 이다. `iterate_subtitles()` 에서 `words` 가 비어 있고 텍스트가 있는 세그먼트를 세그먼트 자체의 시작·끝 시각을 가진 단어 하나로 취급해 큐로 출력한다. 테스트 4건을 추가했다.

### 배경

SceneMakerAI는 한국어 방송 오디오를 `whisperx.load_model(...).transcribe()` → `whisperx.align()` → `whisperx/utils.py` 의 writer 로 SRT/VTT/JSON 을 만든다. Whisper 가 아주 짧은 구간에 긴 문장을 붙이는 경우(환각, 타임스탬프 오류) wav2vec2 프레임 수가 글자 수보다 적어 정렬이 실패하고, 로그에 `Failed to align segment (...): backtrack failed, resorting to original` 이 찍힌다. 로그 문구는 원본을 유지한다고 하지만, 실제로는 같은 결과에서 만든 `.txt` , `.tsv` , `.json` 에는 문장이 있고 `.srt` , `.vtt` 에는 없다.

### 원인

- `whisperx/alignment.py:221-227` : 모든 출력 세그먼트를 `"words": []` 로 초기화한다. 정렬 실패 경로 세 곳(`:236-239` 사전에 있는 글자 없음, `:241-244` 시작 시각이 오디오 길이 초과, `:294-297` backtrack 실패)은 이 상태 그대로 결과에 넣는다. 즉 `text` , `start` , `end` 는 남고 `words` 만 빈 리스트다.
- `whisperx/utils.py:308` : 첫 번째 세그먼트에 `words` 키가 있으면 단어 기반 경로를 탄다.
- `whisperx/utils.py:269-270` : `iterate_subtitles()` 는 `segment["words"]` 만 순회해 자막 큐를 만든다. 빈 리스트면 아무 단어도 추가되지 않아 해당 세그먼트는 큐가 생성되지 않는다. 이 경로에서는 `segment["text"]` 를 전혀 보지 않는다.
- #1347 에서 추가된 세그먼트 시각 폴백(`utils.py:313-321` )은 단어는 있는데 `start` /`end` 가 없는 경우만 처리하므로 빈 `words` 에는 도달하지 않는다.

### 재현 방법

모델 없이 표준 라이브러리만으로 재현된다(`repro_writer.py` ). 세 세그먼트 중 가운데 것의 `words` 를 빈 리스트로 둔 결과 dict 를 `WriteTXT` , `WriteTSV` , `WriteSRT` , `WriteVTT` 에 넘기면 TXT/TSV 는 3줄, SRT/VTT 는 2개 큐만 나온다.

실제 `align()` 경로도 확인했다(`repro_align.py` ). 26글자 세그먼트에 5프레임만 돌려주는 stub wav2vec2 모델을 넣어 backtrack 실패를 유도하면 `align()` 이 `words: []` 세그먼트를 반환하고, 이어서 `WriteSRT` 가 그 문장을 누락한다.

### 제안한 수정 (로컬 브랜치, 미커밋)

`iterate_subtitles()` 에서 `words` 가 비어 있고 `text` 가 비어 있지 않은 세그먼트를, 세그먼트의 `start` /`end` 를 가진 단어 하나로 취급한다. `whisperx/utils.py` 6줄 추가, 테스트 `tests/test_subtitles_unaligned_segments.py` 4건 추가.

남은 결정 사항: `--highlight_words` 사용 시 정렬 실패 문장 전체에 밑줄이 그어진다. 플레이스홀더에서 `start` /`end` 를 빼면 일반 큐로 출력되지만 세그먼트 병합 모드에서 큐 시각 정확도가 떨어진다. 그래서 PR 대신 Issue 로 먼저 올리고 메인테이너 의견을 받는다.

### 검증

- upstream `main` HEAD `771b4a1` (3.8.7rc1), Python 3.12, torch 2.8.0+cpu 에서 재현.
- 수정 전 신규 테스트 4건 중 3건 실패(나머지 1건은 빈 텍스트 세그먼트를 건너뛰는 기존 동작 확인용이라 수정 전에도 통과).
- 수정 후 `pytest tests/` 16건 전부 통과.
- 실제 wav2vec2 모델과 실제 오디오로는 돌리지 않았다(모델 다운로드 없이 stub 으로 검증).
- 중복 확인: #75, #404, #230, #1089, #1478, #1315, #1347, #1456, #1458, #1487 을 확인했고 같은 내용은 없었다.

