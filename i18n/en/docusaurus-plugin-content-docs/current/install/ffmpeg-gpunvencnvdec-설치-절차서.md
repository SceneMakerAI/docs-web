---
title: "FFmpeg GPU (NVENC/NVDEC) Installation Guide"
sidebar_position: 2
slug: "2"
last_update:
  date: 2026-06-15
---

Procedure for replacing FFmpeg to offload video chunk encoding for pre_svc to the GPU (4090).  
**Rule: Do not modify the existing** `/usr/bin/ffmpeg` **code. Place the new build in a separate directory and switch to it via config after verification.** In case of issues, roll back immediately with a single line of `.env`.

> **Verification complete** on actual hardware (RTX 4090 x2, driver 580). 2-hour VP9: CPU ~4 minutes → **GPU 28 seconds** (~8.5x faster); 1,154 chunks, each taking 6.0 seconds—same as before.

### 0. Background / Key Pitfalls

- Even with `r 1` (1 fps), ffmpeg **decodes all** original 30 fps frames and then discards them (2h ≈ 200,000 frames). The bottleneck is this software decoding → passing it to GPU decode (NVDEC) + encode (NVENC), which takes tens of seconds.
- There is no separate product called “nvidia ffmpeg.” You simply need **ffmpeg built with nvenc enabled**.
- ⚠ **Pitfall 1 — Driver vs. NVENC API Version**: The latest build of BtbN `master/latest` requires NVENC SDK 13.1 (driver **610+**). This box uses driver **580**, so it is rejected: `Driver does not support the required nvenc API version. Required: 13.1 Found: 13.0` → You must use an **outdated autobuild**. (Verified: `autobuild-2026-01-31`)
- ⚠ **Pitfall 2 — Keyframes**: With the nvenc + fps filter combination, `force_key_frames` does not work, so segments are split only in GOP units (hundreds of seconds). **At 1 fps**, this is resolved using `g 6 -forced-idr 1` (IDR every 6 frames = 6 seconds).

### Environment (at time of verification)

| Item | Value |
| --- | --- |
| GPU | NVIDIA RTX 4090 x2 |
| Driver | 580.126.20 → Supports NVENC API **13.0** and up |
| Existing FFmpeg | `/usr/bin/ffmpeg`  (7.0.2-static, no nvenc) — Retained |
| Verified GPU Build | BtbN `autobuild-2026-01-31`  linux64-gpl static |
| Installation Location | `/opt/ffmpeg-nvidia/` |

> NVENC/NVDEC is provided by the **driver** → No need to install the CUDA Toolkit separately. As long as `nvidia-smi` is available, it works.

### 1. Preliminary Check

```
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
ffmpeg -version | head -1
```

### 2. Get the BtbN build that matches your driver (★ Use a dated build, not the master branch)

```
mkdir -p /root/down/ffmpeg-install && cd /root/down/ffmpeg-install

URL=$(curl -s "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/tags/autobuild-2026-01-31-12-57" \
  | grep -oE '"browser_download_url": "[^"]*-linux64-gpl\.tar\.xz"' | grep -v shared \
  | grep -oE 'https[^"]*' | head -1)
echo "$URL"
curl -L -o btbn.tar.xz "$URL"
rm -rf build && mkdir build && tar xf btbn.tar.xz -C build --strip-components=1
# → build/bin/ffmpeg, build/bin/ffprobe
```

> If on a closed network, download the tar.xz file from outside and bring it in. If the driver version differs from 580, verify it using the nvenc test in step 3; if it fails, downgrade to an older `autobuild-YYYY-MM-DD` version and retry.

### 3. Verify build functionality + driver compatibility (★ both)

```
FF=/root/down/ffmpeg-install/build/bin/ffmpeg

# 3-1. Check for GPU Support
$FF -hide_banner -encoders | grep -i nvenc        # h264_nvenc
$FF -hide_banner -decoders | grep -i cuvid # vp9_cuvid (decoder matching the input codec)
$FF -hide_banner -filters  | grep scale_cuda      # scale_cuda

# 3-2. ★ Does nvenc actually open with this driver? (Most important)
$FF -y -f lavfi -i testsrc=size=1024x768:rate=30:duration=3 -c:v h264_nvenc /tmp/nvenc_test.mp4 \
  && echo ">>> NVENC OK" || echo ">>> NVENC rejected → Replaced with an older autobuild"
```

> If an `Required: 13.x ... minimum driver 6xx` error occurs, that build is too new for this machine. (Set the test input to a sufficiently large resolution, such as 1024x768—small sizes like 64x64 may trigger false positives because they fall below nvenc’s minimum resolution)

### 4. Verify the entire GPU pipeline using the actual source code

```
FF=/root/down/ffmpeg-install/build/bin/ffmpeg
rm -rf /tmp/gpu && mkdir -p /tmp/gpu
$FF -y -hwaccel cuda -hwaccel_output_format cuda -c:v vp9_cuvid -i output/1/source.mp4 \
   -map 0:a -vn -ac 1 -ar 16000 -c:a pcm_s16le /tmp/gpu/audio.wav \
   -map 0:v -vf "scale_cuda=1024:768,fps=1" -c:v h264_nvenc -g 6 -forced-idr 1 \
   -f segment -segment_time 6 -segment_start_number 0 -reset_timestamps 1 -segment_format mp4 \
   /tmp/gpu/seg%05d.mp4
ls /tmp/gpu/seg*.mp4 | wc -l
ffprobe -v error -show_entries format=duration -of csv=p=0 /tmp/gpu/seg00000.mp4   # Should be 6.0
```

> Success if chunks are split every 6 seconds and the count matches. If `-g 6 -forced-idr 1` is missing, segments are split only by GOP (Pitfall 2).

### 5. Navigate to the installation directory

```
sudo mkdir -p /opt/ffmpeg-nvidia
sudo cp /root/down/ffmpeg-install/build/bin/ffmpeg  /opt/ffmpeg-nvidia/
sudo cp /root/down/ffmpeg-install/build/bin/ffprobe /opt/ffmpeg-nvidia/
sudo chmod +x /opt/ffmpeg-nvidia/ffmpeg /opt/ffmpeg-nvidia/ffprobe
# Leave /usr/bin/ffmpeg as is (for rollback purposes).
```

### 6. Integrate with the app

**6-1. config + .env**

```
# config.py
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")   # Default: existing CPU ffmpeg (rollback default)
FFMPEG_GPU = os.getenv("FFMPEG_GPU", "0") # Pin to a different GPU than STT (e.g., 1)
```

```
# .env  — Switch to GPU
FFMPEG_BIN=/opt/ffmpeg-nvidia/ffmpeg
FFMPEG_GPU=1
```

**6-2. ffmpeg.py command (GPU)**

```
cmd = (
    f"{config.FFMPEG_BIN} -y -hwaccel cuda -hwaccel_output_format cuda "
    f"-hwaccel_device {config.FFMPEG_GPU} -c:v vp9_cuvid -i {src} "
    f"-map 0:a -vn -ac 1 -ar {config.TARGET_SR} -c:a pcm_s16le {audio_out} "
    f"-map 0:v -map 0:a -vf scale_cuda=1024:768,fps=1 -c:v h264_nvenc -g 6 -forced-idr 1 -c:a aac "
    f"-f segment -segment_time 6 -segment_start_number 0 -reset_timestamps 1 -segment_format mp4 {pattern}"
)
```

> Replace `force_key_frames` with `-g 6 -forced-idr 1` (Pitfall 2). `-threads 1` is unnecessary for the CPU. If the chunk contains audio, add `-map 0:a -c:a aac` to output 2. Also change ffprobe in `_duration()` to `/opt/ffmpeg-nvidia/ffprobe`. ⚠ `-c:v vp9_cuvid` is only used when the input is VP9—if codecs are mixed, remove it and let `-hwaccel cuda` handle the selection automatically.

### 7. Speed Measurement / Rollback

```#
 Measurement: Add `time` to command #4 to compare it with the CPU time (about 4 minutes)
# Rollback: Set FFMPEG_BIN to the default value in .env
FFMPEG_BIN=ffmpeg
```

→ Immediately revert to the existing `/usr/bin/ffmpeg` (CPU). It’s fine not to delete the new binary.

### Troubleshooting

- `Unknown encoder 'h264_nvenc'`  → nvenc not included in the build (3-1 failed). Try a different build.
- `Required: 13.1 ... minimum driver 610`  → Build is newer than the driver (Pitfall 1). Use an older autobuild.
- **Segment isn’t clipped at 6 seconds and runs for hundreds of seconds**  → `g 6 -forced-idr 1`  is missing (Pitfall 2).
- `swscaler ... nv12 csp:gbr ... Unsupported`  → Color space quirk when passing from GPU decode to CPU filters. This does not occur if everything is processed on the GPU (`scale_cuda` + `nvenc`).
- **GPU memory contention (STT conflict)**  → Use `hwaccel_device` to specify a GPU different from the one used for STT.

### Safety Notes

- FFmpeg is a **standalone static binary** — it is independent of Python packages such as uv, venv, torch, or CUDA. Installing them will not break FFmpeg.
- Keep the existing `/usr/bin/ffmpeg` → Always fallback.
- Both switching and rolling back use a single line of `.env` (`FFMPEG_BIN`).

