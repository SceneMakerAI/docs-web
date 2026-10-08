---
id: 프레임-수가-없는-영상파이프-webmmkv-raw-h264이-1프레임음수-메타데이터로-로드되는-문제
title: "프레임 수가 없는 영상(파이프 WebM/MKV, raw H.264)이 1프레임·음수 메타데이터로 로드되는 문제"
sidebar_position: 47
slug: "47"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-08
---

## vLLM: 프레임 수가 기록되지 않은 영상(스트리밍 WebM/MKV, raw H.264)이 1프레임으로 잘리거나 샘플러에서 실패하는 문제

링크: https://github.com/vllm-project/vllm/issues/60518

- 대상: vllm-project/vllm (기본 브랜치 main, 확인 커밋 9dba339d0 / 릴리스 0.31.0)
- 형태: Issue (bug report 양식, 제목 접두어 `[Bug]:` )
- 로컬 브랜치: `fix/opencv-unknown-frame-count` (커밋하지 않은 프로토타입 수정 + 테스트)

### 배경

vLLM 의 기본 영상 디코더는 OpenCV(FFMPEG 백엔드)다. 요청에 포함된 `video_url` 은 `VideoMediaIO` 를 거쳐 `decode_opencv` 로 들어가고, 여기서 컨테이너 메타데이터(전체 프레임 수, fps, 길이)를 읽은 뒤 모델별 샘플러(`opencv` , `qwen3_vl` , `qwen2_vl` 등)가 어느 프레임을 뽑을지 계산한다.

컨테이너에 길이나 프레임 수가 기록되지 않는 영상이 있다. 대표적으로 파이프(탐색 불가능한 출력)로 내보낸 WebM/Matroska 와 raw H.264 / MPEG-4 elementary stream 이다. 이런 파일은 재생과 디코딩에는 아무 문제가 없고 `ffprobe -count_frames` 로도 20프레임이 정상적으로 읽힌다.

### 원인

`vllm/multimodal/video_decoders/opencv.py` 의 `get_video_metadata` (79행) 는 `cap.get(cv2.CAP_PROP_FRAME_COUNT)` 값을 검증 없이 `total_frames_num` 으로 쓴다. 프레임 수가 없는 컨테이너에서 OpenCV 는 이 값을 매우 큰 음수(예: -92233720368547760)로 돌려준다.

- 90행의 edit-list 보정(#48608)은 `total_frames_num > 0` 일 때만 동작해서 이 경우를 건너뛴다.
- 102행에서 길이도 음수로 계산된다.
- `vllm/multimodal/video.py` 232행: 기본 샘플러는 `max(1, min(..., 음수))` 가 되어 인덱스 0 하나만 뽑는다. 188\~190행에서 음수 프레임 수와 음수 길이가 그대로 HF 프로세서용 메타데이터로 전달된다.
- 381\~382행(`qwen3_vl` )과 642행(`qwen2_vl` )은 음수를 `np.linspace` / `torch.arange` 에 넘겨 예외가 난다.

### 재현 방법

```bash
S="-f lavfi -i testsrc=s=64x64:r=10:d=2"
ffmpeg -loglevel error -y $S -c:v libvpx seekable.webm
ffmpeg -loglevel error -y $S -c:v libvpx -f webm pipe:1 > streamed.webm
ffmpeg -loglevel error -y $S -c:v libx264 -pix_fmt yuv420p -f matroska pipe:1 > streamed.mkv
ffmpeg -loglevel error -y $S -c:v libx264 -pix_fmt yuv420p -f h264 raw.h264
python repro.py streamed.webm
```

```text
$ python repro.py seekable.webm
source metadata: VideoSourceMetadata(total_frames_num=20, original_fps=10.0, duration=2.0)
opencv (default): frames=20 total_num_frames=20 duration=2.0 ...
qwen3_vl: frames=4 total_num_frames=20 duration=2.0 frames_indices=[0, 6, 13, 19]
qwen2_vl: frames=4 total_num_frames=20 duration=2.0 frames_indices=[0, 5, 10, 15]

$ python repro.py streamed.webm
source metadata: VideoSourceMetadata(total_frames_num=-92233720368547760, original_fps=10.0, duration=-9223372036854776.0)
opencv (default): frames=1 total_num_frames=-92233720368547760 duration=-9223372036854776.0 frames_indices=[0]
qwen3_vl: ValueError: Number of samples, -92233720368547760, must be non-negative.
qwen2_vl: RuntimeError: upper bound and lower bound inconsistent with step sign
```

정리하면 다음과 같다.

| 로더 | 정상 WebM | 스트리밍 WebM / MKV / raw H.264 |

| --- | --- | --- |

| opencv (기본 샘플러) | 20프레임, 길이 2.0초 | 에러 없이 1프레임만 반환, 프레임 수와 길이가 음수 |

| qwen3_vl | 4프레임 | ValueError (numpy 메시지 그대로 노출) |

| qwen2_vl | 4프레임 | RuntimeError (에러 매핑상 500) |

기본 샘플러의 경우가 가장 나쁘다. 요청은 성공하지만 모델은 영상의 첫 프레임 하나만 본다.

### 제안 (이슈 본문에서 메인테이너에게 질문)

1. 헤더의 프레임 수가 0 이하일 때 별도 캡처로 `cap.grab()` 을 끝까지 돌려 실제 프레임 수를 세고 그 값으로 샘플링한다. 로컬 프로토타입이 이 방식이다.
2. 또는 명확한 `ValueError` (400)로 조기 거부한다.

어느 쪽을 택할지는 디코딩 비용 상한(#57525)과 맞물린 설계 결정이라 PR 대신 Issue 로 준비했다.

### 검증

- 릴리스 0.31.0 휠과 main db6e3cd8c 양쪽에서 같은 출력 확인 (CPU 전용 환경, GPU 없음).
- 프로토타입 적용 후: 스트리밍 WebM/MKV 가 정상 WebM 과 같은 프레임과 메타데이터를 반환, raw H.264 는 20프레임 반환.
- 새 테스트 `test_video_backend_handles_stream_without_frame_count` 는 수정 전 실패(`assert -192153584101141 == 12` ), 수정 후 통과.
- `tests/multimodal/test_video.py` , `tests/multimodal/media/test_video.py` : 123 passed, 6 skipped.
- `ruff check` , `ruff format --check` (0.14.0) 통과. mypy 와 전체 pre-commit 은 실행하지 않음.
- 확인하지 못한 것: 실제 서버를 띄운 HTTP 상태 코드(500 여부는 `create_error_response` 매핑으로만 확인), GPU 디코더(pynvvideocodec, deepstream), 브라우저 MediaRecorder 로 녹화한 실제 파일.

### 중복 확인

`CAP_PROP_FRAME_COUNT` , `get_video_metadata` , `total_frames_num` , `webm` , `matroska` , `mkv` , `MediaRecorder` , `raw h264` , `frame count negative` , `unknown frame count` 등으로 이슈, PR, 디스커션을 검색했다. 가장 가까운 것은 #48608(edit-list, 병합됨), #48332(opencv_dynamic 샘플러 한정, 열린 이슈), #54390(fps 0), #58353(1프레임 클립), #60212(DeepStream) 이며 모두 원인이나 입력이 다르다.

