---
title: "FFmpeg GPU (NVENC/NVDEC) Installation Guide"
sidebar_position: 2
slug: "2"
last_update:
  date: 2026-06-22
---

## 1. Concepts

- FFmpeg itself is an open-source project. The "GPU version" is not a separate product, but simply a **build compiled with NVENC/NVDEC enabled**.
- GPU encoding/decoding is provided by the NVIDIA **driver**. The CUDA toolkit is not required; `nvidia-smi` is sufficient.
- The default FFmpeg included in distributions (via apt, etc.) usually has nvenc disabled. You must obtain a build with nvenc enabled or compile it yourself.

## 2. Prerequisites

```javascript
# Checking GPU/Driver Operation
> nvidia-smi --query-gpu=name,driver_version --format=csv,noheader

# Existing FFmpeg
> ffmpeg -version | head -1
```

## 3. **Obtaining a Build with nvenc Enabled (Easiest: BtbN)**

```javascript
# The linux64-gpl static build from BtbN/FFmpeg-Builds includes nvenc, cuvid, and scale_cuda.


> mkdir -p ~/ffmpeg-gpu && cd ~/ffmpeg-gpu
> curl -L -o ffmpeg.tar.xz \
  https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz
tar xf ffmpeg.tar.xz --strip-components=1

# Create bin/ffmpeg and bin/ffprobe
# Alternative: Compile manually (after installing nv-codec-headers, use --enable-nvenc --enable-cuda --enable-cuvid --enable-libnpp),
# Or a package that includes nvenc, such as jellyfin-ffmpeg.


```

## 4. Build + Driver Compatibility Check

```javascript
FF=~/ffmpeg-gpu/bin/ffmpeg

# Verify Feature Inclusion
> FF -hide_banner -hwaccels  | grep cuda
> FF -hide_banner -encoders  | grep -i nvenc     # h264_nvenc, hevc_nvenc, av1_nvenc
> FF -hide_banner -decoders  | grep -i cuvid     # h264_cuvid, hevc_cuvid, vp9_cuvid ...
> FF -hide_banner -filters   | grep scale_cuda


# Does nvenc actually open in the driver? (Important)
$FF -y -f lavfi -i testsrc=size=1280x720:rate=30:duration=3 -c:v h264_nvenc /tmp/t.mp4 \
  && echo "NVENC OK" || echo "NVENC failed"

```

- Note — **Driver vs. NVENC SDK Version**: Builds that are too recent require the new NVENC SDK and will be rejected by older drivers.
- If `Driver does not support the required nvenc API version. Required: X.Y` appears, update the driver or obtain an **older build** (BtbN’s date-specific `autobuild-YYYY-MM-DD` releases). 
- Make sure the test input is large enough, such as 1280x720(Very small resolutions may trigger false positives due to falling below the NVENC minimum resolution).

## 5. Basic Usage Patterns

Perform decoding, scaling, and encoding entirely on the GPU:

```javascript
# Transcode (Automatic Hardware Decoding of Input Codecs)
> ffmpeg -hwaccel cuda -hwaccel_output_format cuda -i in.mp4 \
       -c:v h264_nvenc -b:v 5M out.mp4

# GPU Scale
> ffmpeg -hwaccel cuda -hwaccel_output_format cuda -i in.mp4 \
       -vf scale_cuda=1280:720 -c:v h264_nvenc out.mp4

# Specifying a Specific Decoder (When the input codec is known, e.g., VP9)
> ffmpeg -hwaccel cuda -hwaccel_output_format cuda -c:v vp9_cuvid -i in.webm \
       -vf scale_cuda=1280:720 -c:v h264_nvenc out.mp4
```

Frequently used options

- `hwaccel cuda`  : Use hardware decoding
- `hwaccel_output_format cuda`  : Keep decoded frames in GPU memory (required when combined with GPU filters such as scale_cuda)
- `c:v h264_nvenc`  / `hevc_nvenc`  / `av1_nvenc`  : Hardware encoder
- `preset p1` (Fast) ~ `p7` (High Quality), `tune ll` / `ull`: nvenc quality/speed
- `gpu 0` or `hwaccel_device 1`: Specify the ##GPU to use

 **6. For Verification — GPU Engine Utilization**

The GPU-Util(%) value in nvidia-smi refers to compute cores (SMs), so it appears low during hardware transcoding. The actual encoder/decoder utilization is:

```javascript
> nvidia-smi dmon -s u    # View the "enc" and "dec" columns
```

### **Cautions/Pitfalls (General)**

- The default ffmpeg included in most distributions often has nvenc disabled → Check step 4 first.
- If the ffmpeg build is newer than the driver, nvenc will fail → Upgrade the driver or use an older ffmpeg build.
- A cuvid decoder compatible with the input codec is required for GPU decoding (otherwise, it will fall back to CPU decoding or result in an error).
- FFmpeg is an independent static binary, so it can be installed or replaced independently of the system or Python environment.

