---
id: ffmpeg-gpunvencnvdec-설치-절차서
title: "Ffmpeg GPU(NVENC/NVDEC) 설치 절차서"
sidebar_position: 2
slug: "2"
last_update:
  date: 2026-06-24
---

## 1. 개념

- ffmpeg 자체는 하나의 오픈소스다. "GPU 버전"은 별도 제품이 아니라 **NVENC/NVDEC 를 켜서 컴파일한 빌드** 일 뿐이다.
- GPU 인코딩/디코딩은 NVIDIA **드라이버** 가 제공한다. CUDA toolkit 은 필요 없고, `nvidia-smi`  가 되면 된다.
- 배포판 기본 ffmpeg(apt 등)는 보통 nvenc 가 꺼져 있다. nvenc 켜진 빌드를 받거나 직접 컴파일해야 한다.



## 2. 사전 확인

```javascript
# GPU/드라이버 동작 확인
> nvidia-smi --query-gpu=name,driver_version --format=csv,noheader

# 기존 ffmpeg
> ffmpeg -version | head -1
```


## 3. **nvenc 켜진 빌드 받기**

- H.264 (가장 대중적인 포맷)
  - **일반(CPU 사용):** `c:v libx264`

  - **NVENC(GPU 가속):** `c:v h264_nvenc`

- H.265 / HEVC (고화질 고압축 포맷)
  - **일반(CPU 사용):** `c:v libx265`

  - **NVENC(GPU 가속):** `c:v hevc_nvenc`

```javascript
# BtbN/FFmpeg-Builds 의 linux64-gpl static 빌드에 nvenc/cuvid/scale_cuda 가 포함돼 있다.


> mkdir -p /usr/local/ffmpeg-gpu && cd /usr/local/ffmpeg-gpu
> curl -L -o ff.tar.xz \
  https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-01-31-12-57/ffmpeg-N-122607-g50bcc96a75-linux64-gpl.tar.xz
tar xf ff.tar.xz --strip-components=1

# bin/ffmpeg, bin/ffprobe 생성
# 대안: 직접 컴파일(nv-codec-headers 설치 후 --enable-nvenc --enable-cuda --enable-cuvid --enable-libnpp),
# 또는 jellyfin-ffmpeg 같은 nvenc 포함 패키지.

> ls -al bin/
total 578564
drwxr-xr-x. 2 1001 1001        49 Jan 31 21:55 .
drwxr-xr-x. 6 root root        90 Jun 24 15:58 ..
-rwxr-xr-x. 1 1001 1001 196915400 Jan 31 21:55 ffmpeg
-rwxr-xr-x. 1 1001 1001 198827688 Jan 31 21:55 ffplay
-rwxr-xr-x. 1 1001 1001 196698312 Jan 31 21:55 ffprobe
> 


```



## 4. 빌드 + 드라이버 호환 확인

```bash
# 기능 포함 확인
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


# 드라이버에서 nvenc 가 실제로 열리는지 (중요)
> bin/ffmpeg -y -f lavfi -i testsrc=size=1280x720:rate=30:duration=3 -c:v h264_nvenc /tmp/t.mp4 \
  && echo "NVENC OK" || echo "NVENC 실패"
...
...
NVENC OK
> 
```


- 주의 — **드라이버 vs NVENC SDK 버전** : 너무 최신 빌드는 새 NVENC SDK 를 요구해서 구형 드라이버에서 거부된다.
- `Driver does not support the required nvenc API version. Required: X.Y` 가 뜨면, 드라이버를 올리거나 **더 오래된 빌드** (BtbN 의 날짜별 `autobuild-YYYY-MM-DD` 릴리스)를 받는다. 
- 테스트 입력은 1280x720 처럼 충분히 크게 한다(초소형은 nvenc 최소해상도 미달로 오탐).


## 5. 기본 사용 패턴

디코드·스케일·인코드를 모두 GPU 에서:


```javascript
# 트랜스코드 (입력 코덱 자동 하드웨어 디코드)
> ffmpeg -hwaccel cuda -hwaccel_output_format cuda -i in.mp4 \
       -c:v h264_nvenc -b:v 5M out.mp4

# GPU 스케일까지
> ffmpeg -hwaccel cuda -hwaccel_output_format cuda -i in.mp4 \
       -vf scale_cuda=1280:720 -c:v h264_nvenc out.mp4

# 특정 디코더 명시 (입력 코덱을 알 때, 예: VP9)
> ffmpeg -hwaccel cuda -hwaccel_output_format cuda -c:v vp9_cuvid -i in.webm \
       -vf scale_cuda=1280:720 -c:v h264_nvenc out.mp4
```


자주 사용하는 옵션

- `hwaccel cuda`  : 하드웨어 디코드 사용
- `hwaccel_output_format cuda`  : 디코드 프레임을 GPU 메모리에 유지(scale_cuda 등 GPU 필터와 연결 시 필요)
- `c:v h264_nvenc`  / `hevc_nvenc`  / `av1_nvenc`  : 하드웨어 인코더
- `preset p1` (빠름) \~ `p7` (고화질), `tune ll` /`ull`  : nvenc 품질/속도
- `gpu 0`  또는 `hwaccel_device 1`  : 사용할 GPU 지정



## **6. 확인용 — GPU 엔진 사용률**

nvidia-smi 의 GPU-Util(%)은 연산코어(SM)라 하드웨어 트랜스코드 시 낮게 나온다. 실제 인코더/디코더 사용률은:

```javascript
> nvidia-smi dmon -s u    # 컬럼 enc, dec 를 본다
```


### **주의/함정 (일반)**

- 배포판 기본 ffmpeg 는 nvenc 가 꺼진 경우가 많다 → 4  로 먼저 확인.
- 빌드가 드라이버보다 최신이면 nvenc 가 거부된다 → 드라이버 업그레이드 또는 구버전 빌드.
- 입력 코덱에 맞는 cuvid 디코더가 있어야 GPU 디코드가 된다(없으면 CPU 디코드로 폴백되거나 에러).
- ffmpeg 는 독립 static 바이너리라 시스템/파이썬 환경과 무관하게 설치·교체할 수 있다.


