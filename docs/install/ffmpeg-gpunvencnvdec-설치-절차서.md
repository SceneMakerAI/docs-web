---
id: ffmpeg-gpunvencnvdec-설치-절차서
title: "Ffmpeg GPU(NVENC/NVDEC) 설치 절차서"
sidebar_position: 2
slug: "2"
last_update:
  date: 2026-06-15
---

pre_svc 의 영상 청크 인코딩을 GPU(4090)로 돌리기 위한 ffmpeg 교체 절차.  
**원칙: 기존** `/usr/bin/ffmpeg` **는 건드리지 않는다. 새 빌드는 별도 경로에 두고, 검증 후 config 로 전환한다.** 문제 시 `.env` 한 줄로 즉시 롤백.

> 실제 박스(RTX4090x2, 드라이버 580)에서 **검증 완료** . 2시간 VP9: CPU \~4분 → **GPU 28초** (\~8.5배), 청크 1154개·각 6.0초 동일.

### 0. 배경 / 핵심 함정

- `r 1` (1fps)이라도 ffmpeg 는 원본 30fps 프레임을 **전부 디코딩** 한 뒤 버린다(2h≈20만 프레임). 병목은 이 소프트웨어 디코딩 → GPU 디코드(NVDEC)+인코드(NVENC)로 넘기면 수십 초.
- "nvidia ffmpeg" 라는 별도 제품은 없다. **nvenc 켜서 빌드한 ffmpeg**  가 필요할 뿐.
- ⚠ **함정 1 — 드라이버 vs NVENC API 버전** : BtbN `master/latest`  최신 빌드는 NVENC SDK 13.1(드라이버 **610+** )을 요구. 이 박스는 드라이버 **580**  이라 거부됨: `Driver does not support the required nvenc API version. Required: 13.1 Found: 13.0`  → **날짜 지난 autobuild**  를 받아야 한다. (검증된 것: `autobuild-2026-01-31` )
- ⚠ **함정 2 — 키프레임** : nvenc + fps 필터 조합에선 `force_key_frames`  가 안 먹어 segment 가 GOP(수백 초) 단위로만 잘린다. **1fps 에선** `g 6 -forced-idr 1` (6프레임=6초마다 IDR)로 해결.

### 환경 (검증 시점)

| 항목 | 값 |
| --- | --- |
| GPU | NVIDIA RTX 4090 x2 |
| 드라이버 | 580.126.20 → NVENC API **13.0**  까지 지원 |
| 기존 ffmpeg | `/usr/bin/ffmpeg`  (7.0.2-static, nvenc 없음) — 유지 |
| 검증된 GPU 빌드 | BtbN `autobuild-2026-01-31`  linux64-gpl static |
| 설치 위치 | `/opt/ffmpeg-nvidia/` |

> NVENC/NVDEC 는 **드라이버** 가 제공 → CUDA toolkit 별도 설치 불필요. `nvidia-smi` 만 되면 됨.

### 1. 사전 확인

```
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
ffmpeg -version | head -1
```

### 2. 드라이버에 맞는 BtbN 빌드 받기 (★ master 말고 날짜빌드)

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

> 폐쇄망이면 tar.xz 외부에서 받아 반입. 드라이버가 580과 다르면 3번 nvenc 테스트로 확인하고, 거부되면 더 오래된 `autobuild-YYYY-MM-DD` 로 내려가며 재시도.

### 3. 빌드 기능 + 드라이버 호환 확인 (★ 둘 다)

```
FF=/root/down/ffmpeg-install/build/bin/ffmpeg

# 3-1. GPU 기능 포함 확인
$FF -hide_banner -encoders | grep -i nvenc        # h264_nvenc
$FF -hide_banner -decoders | grep -i cuvid        # vp9_cuvid (입력 코덱에 맞는 디코더)
$FF -hide_banner -filters  | grep scale_cuda      # scale_cuda

# 3-2. ★ 이 드라이버에서 nvenc 실제로 열리나 (가장 중요)
$FF -y -f lavfi -i testsrc=size=1024x768:rate=30:duration=3 -c:v h264_nvenc /tmp/nvenc_test.mp4 \
  && echo ">>> NVENC OK" || echo ">>> NVENC 거부 → 더 오래된 autobuild 로 교체"
```

> `Required: 13.x ... minimum driver 6xx` 에러면 그 빌드는 이 박스엔 너무 최신. (테스트 입력은 1024x768 처럼 충분히 크게 — 64x64 같은 소형은 nvenc 최소해상도 미달로 오탐)

### 4. 실제 소스로 전체 GPU 파이프라인 검증

```
FF=/root/down/ffmpeg-install/build/bin/ffmpeg
rm -rf /tmp/gpu && mkdir -p /tmp/gpu
$FF -y -hwaccel cuda -hwaccel_output_format cuda -c:v vp9_cuvid -i output/1/source.mp4 \
   -map 0:a -vn -ac 1 -ar 16000 -c:a pcm_s16le /tmp/gpu/audio.wav \
   -map 0:v -vf "scale_cuda=1024:768,fps=1" -c:v h264_nvenc -g 6 -forced-idr 1 \
   -f segment -segment_time 6 -segment_start_number 0 -reset_timestamps 1 -segment_format mp4 \
   /tmp/gpu/seg%05d.mp4
ls /tmp/gpu/seg*.mp4 | wc -l
ffprobe -v error -show_entries format=duration -of csv=p=0 /tmp/gpu/seg00000.mp4   # 6.0 이어야 함
```

> 청크가 6초 단위로 잘리고 개수가 맞으면 성공. `-g 6 -forced-idr 1` 빠지면 segment 가 GOP 단위로만 잘림(함정 2).

### 5. 설치 위치로 이동

```
sudo mkdir -p /opt/ffmpeg-nvidia
sudo cp /root/down/ffmpeg-install/build/bin/ffmpeg  /opt/ffmpeg-nvidia/
sudo cp /root/down/ffmpeg-install/build/bin/ffprobe /opt/ffmpeg-nvidia/
sudo chmod +x /opt/ffmpeg-nvidia/ffmpeg /opt/ffmpeg-nvidia/ffprobe
# /usr/bin/ffmpeg 는 그대로 둔다(롤백용).
```

### 6. 앱 연동

**6-1. config + .env**

```
# config.py
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")   # 기본=기존 CPU ffmpeg(롤백 기본값)
FFMPEG_GPU = os.getenv("FFMPEG_GPU", "0")         # STT 와 다른 GPU 로 핀 (예: 1)
```

```
# .env  — GPU 로 전환
FFMPEG_BIN=/opt/ffmpeg-nvidia/ffmpeg
FFMPEG_GPU=1
```

**6-2. ffmpeg.py 명령 (GPU)**

```
cmd = (
    f"{config.FFMPEG_BIN} -y -hwaccel cuda -hwaccel_output_format cuda "
    f"-hwaccel_device {config.FFMPEG_GPU} -c:v vp9_cuvid -i {src} "
    f"-map 0:a -vn -ac 1 -ar {config.TARGET_SR} -c:a pcm_s16le {audio_out} "
    f"-map 0:v -map 0:a -vf scale_cuda=1024:768,fps=1 -c:v h264_nvenc -g 6 -forced-idr 1 -c:a aac "
    f"-f segment -segment_time 6 -segment_start_number 0 -reset_timestamps 1 -segment_format mp4 {pattern}"
)
```

> `force_key_frames` → `-g 6 -forced-idr 1` 로 교체(함정 2). CPU 의 `-threads 1` 불필요. 청크에 소리 포함 시 출력2에 `-map 0:a -c:a aac` . `_duration()` 의 ffprobe 도 `/opt/ffmpeg-nvidia/ffprobe` 로. ⚠ `-c:v vp9_cuvid` 는 입력이 VP9 일 때만 — 코덱 섞이면 빼고 `-hwaccel cuda` 자동선택에 맡길 것.

### 7. 속도 측정 / 롤백

```
# 측정: 4번 명령에 time 붙여 CPU(약 4분) 대비 확인
# 롤백: .env 에서 FFMPEG_BIN 을 기본값으로
FFMPEG_BIN=ffmpeg
```

→ 즉시 기존 `/usr/bin/ffmpeg` (CPU) 복귀. 새 바이너리 삭제 안 해도 무방.

### 트러블슈팅

- `Unknown encoder 'h264_nvenc'`  → 빌드에 nvenc 없음(3-1 실패). 다른 빌드.
- `Required: 13.1 ... minimum driver 610`  → 빌드가 드라이버보다 최신(함정 1). 더 오래된 autobuild.
- **segment 가 6초로 안 잘리고 수백 초**  → `g 6 -forced-idr 1`  누락(함정 2).
- `swscaler ... nv12 csp:gbr ... Unsupported`  → GPU 디코드 후 CPU 필터로 내릴 때 색공간 quirk. 전부 GPU(`scale_cuda` +`nvenc` )로 처리하면 안 생김.
- **GPU 메모리 경합(STT 충돌)**  → `hwaccel_device`  로 STT 와 다른 GPU 지정.

### 안전성 메모

- ffmpeg 는 **독립 static 바이너리**  — uv/venv/torch/CUDA 파이썬 패키지와 무관. 설치해도 그쪽 안 깨짐.
- 기존 `/usr/bin/ffmpeg`  유지 → 항상 fallback.
- 전환/롤백 모두 `.env` (`FFMPEG_BIN` ) 한 줄.


