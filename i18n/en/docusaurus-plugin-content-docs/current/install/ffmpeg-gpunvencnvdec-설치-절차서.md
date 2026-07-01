---
title: "FFmpeg GPU (NVENC/NVDEC) Installation Guide"
sidebar_position: 2
slug: "2"
last_update:
  date: 2026-06-24
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

## 3. **Obtaining a Build with nvenc Enabled**

- H.264 (the most common format)
  - **Standard (CPU-based):** `c:v libx264`

  - **NVENC (GPU-accelerated):** `c:v h264_nvenc`

- H.265 / HEVC (High-quality, high-compression format)
  - **Standard (CPU-based):** `c:v libx265`

  - **NVENC (GPU-accelerated):** `c:v hevc_nvenc`

```javascript
# The linux64-gpl static build from BtbN/FFmpeg-Builds includes nvenc, cuvid, and scale_cuda.


> mkdir -p /usr/local/ffmpeg-gpu && cd /usr/local/ffmpeg-gpu
> curl -L -o ff.tar.xz \
  https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-01-31-12-57/ffmpeg-N-122607-g50bcc96a75-linux64-gpl.tar.xz
tar xf ff.tar.xz --strip-components=1

# Create bin/ffmpeg and bin/ffprobe
# Alternative: Compile manually (after installing nv-codec-headers, use --enable-nvenc --enable-cuda --enable-cuvid --enable-libnpp),
# Or a package that includes nvenc, such as jellyfin-ffmpeg.

> ls -al bin/
total 578564
drwxr-xr-x. 2 1001 1001        49 Jan 31 21:55 .
drwxr-xr-x. 6 root root        90 Jun 24 15:58 ..
-rwxr-xr-x. 1 1001 1001 196915400 Jan 31 21:55 ffmpeg
-rwxr-xr-x. 1 1001 1001 198827688 Jan 31 21:55 ffplay
-rwxr-xr-x. 1 1001 1001 196698312 Jan 31 21:55 ffprobe
> 


```

## 4. Verify Build + Driver Compatibility

```bash
# Verify Feature Inclusion
> bin/ffmpeg -hide_banner -hwaccels  | grep cuda
cuda
> bin/ffmpeg -hide_banner -encoders  | grep -i nvenc   
 V....D av1_nvenc            NVIDIA NVENC av1 encoder (codec av1)
 V....D h264_nvenc           NVIDIA NVENC H.264 encoder (codec h264)
 V....D hevc_nvenc           NVIDIA NVENC hevc encoder (codec hevc) 
> bin/ffmpeg -hide_banner -decoders  | grep -i cuvid
 V..... av1_cuvid            Nvidia CUVID AV1 decoder (codec av1)
 V..... h264_cuvid           Nvidia CUVID H264 decoder (codec h264)
 V..... hevc_cuvid           Nvidia CUVID HEVC decoder (codec hevc)
 V..... mjpeg_cuvid          Nvidia CUVID MJPEG decoder (codec mjpeg)
 V..... mpeg1_cuvid          Nvidia CUVID MPEG1VIDEO decoder (codec mpeg1video)
 V..... mpeg2_cuvid          Nvidia CUVID MPEG2VIDEO decoder (codec mpeg2video)
 V..... mpeg4_cuvid          Nvidia CUVID MPEG4 decoder (codec mpeg4)
 V..... vc1_cuvid            Nvidia CUVID VC1 decoder (codec vc1)
 V..... vp8_cuvid            Nvidia CUVID VP8 decoder (codec vp8)
 V..... vp9_cuvid            Nvidia CUVID VP9 decoder (codec vp9)
 
 > bin/ffmpeg -hide_banner -filters   | grep scale_cuda
 .. scale_cuda        V->V       GPU accelerated video resizer


# Does nvenc actually open in the driver? (Important)
> bin/ffmpeg -y -f lavfi -i testsrc=size=1280x720:rate=30:duration=3 -c:v h264_nvenc /tmp/t.mp4 \
  && echo "NVENC OK" || echo "NVENC failed"
...
...
NVENC OK
> 
```

- Note — **Driver vs. NVENC SDK Version**: Builds that are too recent require the new NVENC SDK and will be rejected by older drivers.
- If `Driver does not support the required nvenc API version. Required: X.Y` appears, update your driver or use an **older build** (BtbN’s `autobuild-YYYY-MM-DD` releases sorted by date). 
- Make sure the test input is large enough, such as 1280x720 (very small sizes may trigger false positives due to falling below the NVENC minimum resolution).

## 5. Basic Usage Pattern

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

Frequently Used Options

- `hwaccel cuda`  : Use hardware decoding
- `hwaccel_output_format cuda`  : Keep decoded frames in GPU memory(required when chained with GPU filters such as `scale_cuda`)
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
- FFmpeg is a standalone static binary, so it can be installed or replaced independently of the system or Python environment.

