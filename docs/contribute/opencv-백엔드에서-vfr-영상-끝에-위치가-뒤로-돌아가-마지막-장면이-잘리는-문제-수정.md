---
id: opencv-백엔드에서-vfr-영상-끝에-위치가-뒤로-돌아가-마지막-장면이-잘리는-문제-수정
title: "OpenCV 백엔드에서 VFR 영상 끝에 위치가 뒤로 돌아가 마지막 장면이 잘리는 문제 수정"
sidebar_position: 63
slug: "63"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-19
---

## PySceneDetect: OpenCV 백엔드에서 VFR 영상 끝에 도달하면 위치가 뒤로 돌아가 마지막 장면이 짧게 잘리는 문제 수정

링크: https://github.com/Breakthrough/PySceneDetect/pull/586

### 배경

PySceneDetect 의 OpenCV 백엔드는 가변 프레임레이트(VFR) 영상을 끝까지 읽은 뒤 `position` 이 마지막으로 읽은 프레임보다 앞 시각으로 되돌아간다. 마지막 `grab()` 이 실패한 뒤 OpenCV 의 `CAP_PROP_POS_MSEC` 가 더 이른 값을 돌려주기 때문이다. `SceneManager` 는 루프가 끝난 뒤의 `video.position` 을 마지막 장면의 끝으로 쓰므로 마지막 장면이 일찍 끝나고, 마지막 컷이 그 시각 뒤에 있으면 끝 시각이 시작보다 앞서게 된다. 메인테이너가 0.7.3 마일스톤에 넣은 이슈 #561 의 "VFR DVD 의 마지막 장면 끝 시각이 잘못됨" 증상이 이것이다. PyAV 백엔드와 고정 프레임레이트 영상에서는 생기지 않는다.

### 재현

리포의 테스트 리소스 `goldeneye-vfr-drop3.mp4` 를 OpenCV 백엔드로 끝까지 읽으면 마지막 프레임 위치는 9.927초인데 읽기가 끝난 뒤 위치는 9.906초다. ffmpeg 로 만든 MPEG-2 MKV(중간에 타임스탬프 공백)에서는 마지막 장면이 PyAV 보다 0.65초 일찍 끝났다.

### 변경 내용

`VideoStreamCv2.read()` 가 마지막으로 읽은 프레임의 timecode 를 기억해 두고, 읽기에 실패한 뒤에는 다음 성공한 읽기·`seek()` ·`reset()` 전까지 그 값을 `position` 으로 돌려준다. 프레임을 읽는 동안의 동작은 바뀌지 않는다. 회귀 테스트 `test_vfr_position_after_eof_opencv` 와 changelog 한 줄을 추가했다.

### 검증

새 테스트는 main 에서 실패하고 수정 후 통과한다. 전체 pytest 460 통과, 실패 2건은 main 에서도 똑같이 실패하는 moviepy 관련 테스트다. ruff check·format, pyright 통과. 신고자의 DVD 파일로는 확인하지 못해서 본문에 #561 을 "고침"이 아니라 "관련"으로 적었다.

