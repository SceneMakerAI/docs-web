---
id: ffmpeg-gpunvencnvdec-설치-절차서
title: "Ffmpeg GPU(NVENC/NVDEC) 설치 절차서"
sidebar_position: 2
slug: "2"
last_update:
  date: 2026-06-22
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



## 3. **nvenc 켜진 빌드 받기 (가장 쉬움: BtbN)**

```javascript
# BtbN/FFmpeg-Builds 의 linux64-gpl static 빌드에 nvenc/cuvid/scale_cuda 가 포함돼 있다.


> mkdir -p ~/ffmpeg-gpu && cd ~/ffmpeg-gpu
> curl -L -o ffmpeg.tar.xz \
  https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz
tar xf ffmpeg.tar.xz --strip-components=1

# bin/ffmpeg, bin/ffprobe 생성
# 대안: 직접 컴파일(nv-codec-headers 설치 후 --enable-nvenc --enable-cuda --enable-cuvid --enable-libnpp),
# 또는 jellyfin-ffmpeg 같은 nvenc 포함 패키지.


```



## 4. 빌드 + 드라이버 호환 확인

```javascript
FF=~/ffmpeg-gpu/bin/ffmpeg

# 기능 포함 확인
> FF -hide_banner -hwaccels  | grep cuda
> FF -hide_banner -encoders  | grep -i nvenc     # h264_nvenc, hevc_nvenc, av1_nvenc
> FF -hide_banner -decoders  | grep -i cuvid     # h264_cuvid, hevc_cuvid, vp9_cuvid ...
> FF -hide_banner -filters   | grep scale_cuda


# 드라이버에서 nvenc 가 실제로 열리는지 (중요)
$FF -y -f lavfi -i testsrc=size=1280x720:rate=30:duration=3 -c:v h264_nvenc /tmp/t.mp4 \
  && echo "NVENC OK" || echo "NVENC 실패"

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


