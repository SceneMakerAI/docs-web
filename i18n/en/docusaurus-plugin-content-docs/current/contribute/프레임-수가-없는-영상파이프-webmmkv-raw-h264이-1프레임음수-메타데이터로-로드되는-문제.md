---
title: "Issue where videos without frame numbers (WebM/MKV streams, raw H.264) are loaded with 1 frame or negative metadata"
sidebar_position: 47
slug: "47"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-08
---

## vLLM: Issue where videos without recorded frame counts (streaming WebM/MKV, raw H.264) are truncated to 1 frame or fail in the sampler

Link: https://github.com/vllm-project/vllm/issues/60518

- Target: vllm-project/vllm (default branch: main, reference commit: 9dba339d0 / release: 0.31.0)
- Type: Issue (bug report form, title prefix `[Bug]:`)
- Local branch: `fix/opencv-unknown-frame-count` (uncommitted prototype fixes + tests)

### Background

vLLM’s default video decoder is OpenCV (FFMPEG backend). The `video_url` included in the request passes through `VideoMediaIO` and enters `decode_opencv`, where the container metadata (total number of frames, fps, duration) is read, and the model-specific samplers(`opencv`, `qwen3_vl`, `qwen2_vl`, etc.) calculate which frames to extract.

Some video files do not have their duration or frame count recorded in the container. Typical examples include WebM/Matroska files exported via a pipe (non-navigable output) and raw H.264/MPEG-4 elementary streams. These files pose no issues for playback or decoding, and 20 frames are read normally by `ffprobe -count_frames`.

### Cause

The `vllm/multimodal/video_decoders/opencv.py` function’s `get_video_metadata` (line 79) writes the `cap.get(cv2.CAP_PROP_FRAME_COUNT)` value to `total_frames_num` without validation. For containers without a frame count, OpenCV returns this value as a very large negative number (e.g., -92233720368547760).

- The edit-list correction on line 90 (#48608) only works when `total_frames_num > 0` is true, so it skips this case.
- On line 102, the length is also calculated as a negative number.
- Line 232 (`vllm/multimodal/video.py`): The default sampler becomes `max(1, min(..., 음수))` and extracts only a single index 0. On lines 188–190, the negative frame count and negative length are passed as-is to the metadata for the HF processor.
- Lines 381–382 (`qwen3_vl`) and line 642 (`qwen2_vl`) pass negative values to `np.linspace` / `torch.arange`, causing an exception.

### Reproduction Steps

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

To summarize:

| Loader | Normal WebM | Streaming WebM / MKV / raw H.264 |

| --- | --- | --- |

| opencv (default sampler) | 20 frames, duration 2.0 seconds | Returns only 1 frame without error; frame count and duration are negative |

| qwen3_vl | 4 frames | ValueError (displays the NumPy message as-is) |

| qwen3_vl | 4 frames | RuntimeError (mapped to 500 in the error mapping) |

The default sampler performs the worst. The request succeeds, but the model only sees the very first frame of the video.

### Proposal (Question to the maintainer in the issue body)

1. When the frame count in the header is 0 or less, use a separate capture to run `cap.grab()` until the end, count the actual number of frames, and sample using that value. The local prototype uses this approach.
2. Alternatively, reject the request early with a clear `ValueError` (400).

Since choosing between these options is a design decision tied to the decoding cost limit (#57525), I’ve prepared this as an issue rather than a PR.

### Verification

- Confirmed identical output on both the 0.31.0 release wheel and the main db6e3cd8c branch (CPU-only environment, no GPU).
- After applying the prototype: Streaming WebM/MKV returned the same frames and metadata as standard WebM; raw H.264 returned 20 frames.
- The new test `test_video_backend_handles_stream_without_frame_count` failed before the fix (`assert -192153584101141 == 12`) but passed after the fix.
- `tests/multimodal/test_video.py`, `tests/multimodal/media/test_video.py`: 123 passed, 6 skipped.
- `ruff check`, `ruff format --check` (0.14.0) passed. Did not run mypy or the full pre-commit.
- Items not verified: HTTP status codes when running on a live server (whether it returns a 500 error was verified only via the `create_error_response` mapping), GPU decoders (pynvvideocodec, deepstream), and actual files recorded using the browser’s MediaRecorder.

### Duplicate checks

Issues such as `CAP_PROP_FRAME_COUNT`, `get_video_metadata`, `total_frames_num`, `webm`, `matroska`, `mkv`, `MediaRecorder`, `raw h264`, `frame count negative`, and `unknown frame count`, PRs, and discussions. The closest ones are #48608 (edit-list, merged), #48332 (limited to opencv_dynamic sampler, open issue), #54390 (0 fps), #58353 (1-frame clip), and #60212 (DeepStream), all of which have different causes or inputs.

