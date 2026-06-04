---
id: qwen-3x-설치
title: "Qwen 3.x 설치"
sidebar_position: 1
slug: "1"
last_update:
  date: 2026-06-04
---

## AWS 서버 세팅

### EC2 인스턴스 설정

---

#### 기본 정보 (요약)

| 카테고리 | 선택 |
| --- | --- |
| 리전 | **us-west-2 (오레곤)** |
| 애플리케이션 및 OS 이미지 | Deep Learning Base AMI with Single CUDA (Amazon Linux 2023) |
| 인스턴스 유형 | **g7e.4xlarge** (GPU 1장, VRAM 96 GB) |
| 스토리지 | EBS 2 TB (gp3) + 인스턴스 스토어 1.7 TB (NVMe) |

**리전 선택 근거**

신형 GPU 인스턴스(G7e, P5, P6 등)는 **공급이 수요를 못 따라잡는 상태** 입니다. 리전·시간대에 따라 `InsufficientInstanceCapacity` 에러로 인스턴스 프로비저닝이 실패하는 일이 자주 발생합니다.

이런 이유로 리전 선택은 단순히 "가까운 리전"이 아니라, 다음 **두 축을 함께** 따져야 합니다.

1. **Capacity 점유 가능성** — 원할 때 실제로 띄울 수 있는가
1. **한국 응답시간** — 사용자가 체감할 네트워크 지연 


**G7e 제공 리전 비교** (2026-05-19 측정)

| 리전 | Capacity 점수 | 한국 TCP RTT | 종합 |
| --- | --- | --- | --- |
| **us-west-2** (오레곤) ⭐ | **3** | 180 ms | 🟢 균형 (capacity 3점 가용영역 2개) |
| us-east-1 (버지니아) | 3 | 208 ms | 🟢 안정 (capacity 3점 가용영역 2개) |
| us-east-2 (오하이오) | 3 | 213 ms | 🟢 안정 |
| ap-northeast-1 (도쿄) | 1 | 46 ms | 🟠 가깝지만 점유 어려움 |
| ap-northeast-2 (서울) | 1 | 18 ms | 🔴 점유 매우 어려움 |
| eu-west-2 (런던) | 1 | 301 ms | 🔴 멀고 점유 어려움 |

**점수 해석**

- Capacity 점수(g7e.12xl, 1\~10) = AWS **Spot Placement Score** (1=매우 부족 / 10=매우 여유). On-Demand 가용성과도 강한 상관관계
- G7e 제공 6개 리전 모두 점수가 낮은 편 (신형 GPU 공통 현상) → 그중 **점수 3이 현 시점 최선**
- 시간대·요일에 따라 점수가 바뀜 → 운영 전 직접 재측정 권장

**Spot Placement Score 직접 조회**

```bash
aws ec2 get-spot-placement-scores \
  --instance-types g7e.12xlarge \
  --target-capacity 1 \
  --no-single-availability-zone \
  --region-names us-west-2 us-east-1 us-east-2 ap-northeast-1 ap-northeast-2 eu-west-2 \
  --query "sort_by(SpotPlacementScores, &Score) | reverse(@) | [].[Region, Score]" \
  --output table
```

- 필요 권한: `ec2:GetSpotPlacementScores`
- 비용: 무료, 평가 기간: 향후 1시간

**(1) Capacity 측면**

- 한·일 리전(서울·도쿄)은 점수 **1** → 평일 업무시간 기준 잦은 프로비저닝 실패 예상
- 미국 리전 3곳(us-east-1 / us-east-2 / us-west-2)은 점수 **3**
- 그중 **us-west-2와 us-east-1은 점수 3인 가용영역이 2개** (usw2-az1·az3 / use1-az2·az6) → 한 가용영역의 capacity가 소진되어도 다른 가용영역으로 폴백 가능

**(2) 응답시간 측면**

- LLM 서빙은 모델 자체의 첫 토큰 생성에 200\~500 ms 소요 → 네트워크 +150\~200 ms는 실사용자 체감 차이가 거의 없는 수준
- 한국 인접 우선이라면 도쿄가 sweet spot이지만 capacity 제약이 큼

> 🎯 **결론**
>
> - **점유 안정성** 을 우선 고려해 **us-west-2(오레곤) 선택**
>
> - 한국 사용자 인터랙티브 서빙으로 확장 시 ap-northeast-1(도쿄) 멀티리전 또는 **Capacity Block for ML / Capacity Reservation** 예약 검토

---

#### 1. 애플리케이션 및 OS 이미지 (Amazon Machine Image)

**선택한 AMI**

| 항목 | 값 |
| --- | --- |
| 이름 | Deep Learning Base AMI with Single CUDA (Amazon Linux 2023) 20260512 |
| OS | Amazon Linux 2023 (커널 6.1.170) |
| Owner | Amazon |
| 아키텍처 | x86_64 |

**참고: AMI 설명상 지원 인스턴스 목록**

```javascript
G4dn, G5, G6, Gr6, G6e, P4d, P4de, P5, P5e, P5en, P6-B200, P6-B300
```

> ℹ️ 공식 목록에 **G7e가 없음** . 다만 실측 결과 Blackwell 드라이버·CUDA가 정상 작동 확인. 향후 재생성 시에는 G7e를 명시 지원하는 **Deep Learning Base OSS Nvidia Driver GPU AMI** (AL2023) 사용 권장.

---

#### 2. 인스턴스 유형

**선택한 인스턴스** : `g7e.4xlarge`

| 항목 | 값 |
| --- | --- |
| vCPU | 16 |
| RAM | 128 GB |
| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition × 1 |
| VRAM | 96 GB (97,887 MiB 실측) |
| GPU 아키텍처 | Blackwell (sm_120, FP4 네이티브 지원) |
| Network | 50 Gbps |
| 인스턴스 스토어 | NVMe SSD 1.9 TB (`nvme1n1` ) — 인스턴스 유형에 기본 포함 |

<details>
<summary>**g7e 패밀리 비교 (참고)**</summary>

| Type | vCPU | RAM | GPU 수 | VRAM 총량 | Network |
| --- | --- | --- | --- | --- | --- |
| g7e.2xlarge | 8 | 64 GB | 1 | 96 GB | 50 Gbps |
| **g7e.4xlarge** ⭐ | **16** | **128 GB** | **1** | **96 GB** | **50 Gbps** |
| g7e.8xlarge | 32 | 256 GB | 1 | 96 GB | 100 Gbps |
| g7e.12xlarge | 48 | 512 GB | 2 | 192 GB | 400 Gbps |
| g7e.24xlarge | 96 | 1 TB | 4 | 384 GB | 800 Gbps |
| g7e.48xlarge | 192 | 2 TB | 8 | 768 GB | 1600 Gbps |


</details>

**4xlarge 선택 근거**

- Qwen3-Coder-30B-A3B / Qwen3.6-35B-A3B 등 MoE 30\~35B 모델은 bf16에서 \~70GB VRAM → 96GB 1장에 KV 캐시까지 여유
- FP8/FP4 양자화 시 더 큰 모델(80\~120B)도 가능
- 우선 1 GPU로 검증 후 확장 필요 시 12xlarge 이상으로 변경

**모델별 VRAM 요구량**

32k 컨텍스트, 단일 시퀀스 기준. vLLM은 paged KV 캐시를 동적 할당하므로 실제 사용량은 워크로드에 따라 달라집니다.

| 모델 | 총/활성 파라미터 | 정밀도 | 가중치 VRAM | KV 캐시 (32k×1) | 총 VRAM |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5-122B-A10B-GPTQ-Int4 | 122B / 10B (MoE) | Int4 (GPTQ) | \~63 GB | \~3 GB | \~69 GB |
| Qwen3.6-27B-FP8 | 27B (Dense) | FP8 (block 128) | \~29 GB | \~8 GB | \~40 GB |

---

#### 3. 스토리지 구성

**1) 루트 EBS 볼륨 (영구 스토리지)**

| 항목 | 값 |
| --- | --- |
| 크기 | 2,048 GiB (2 TB) |
| 타입 | gp3 |
| IOPS | 16,000 |
| Throughput | 1,000 MB/s |
| 암호화 | 미적용(운영 전환 시 암호화 권장) |
| 디바이스 | `nvme0n1` |
| 마운트 | `/` (루트) |

**용도** : 모델 가중치(영구 보관), Docker 이미지, OS 등

**2) 인스턴스 스토어 (임시 스토리지 — g7e.4xlarge 기본 포함)**

| 항목 | 값 |
| --- | --- |
| 디바이스 | `nvme1n1` |
| 크기 | 1.7 TB |
| 타입 | NVMe SSD (인스턴스 로컬) |
| 마운트 | `/mnt/nvme` (XFS, 수동 마운트 필요 — 아래 NVME 설정 참고) |

> ⚠️ **인스턴스 스토어 데이터 영속성**
>
> | 작업 | 데이터 |
> | --- | --- |
> | Reboot (재부팅) | 유지 |
> | **Stop / Start** | **삭제** |
> | Terminate | 삭제 |
> | 하드웨어 장애 | 삭제 |

**용도 분리 권장**

- **EBS (** `/` **)** : 모델 가중치, 영구 데이터 → 절대 잃으면 안 되는 것
- **인스턴스 스토어 (** `/mnt/nvme` **)** : KV 캐시, 임시 빌드, swap, 추론 로그 → 잃어도 되는 것


---

### NVME 설정

- NVME 는 Cloud 환경에서는 일반 물리서버와 다르게 아래와 같은 특성이 있음
  - 재부팅시 데이터 유지

  - Instance stop→start, terminator 시 데이터 소멸 됨

#### 1. NVME Device 확인

```shell
> lsblk
NAME          MAJ:MIN RM  SIZE RO TYPE MOUNTPOINTS
nvme0n1       259:0    0    2T  0 disk 
├─nvme0n1p1   259:2    0    2T  0 part /
├─nvme0n1p127 259:3    0    1M  0 part 
└─nvme0n1p128 259:4    0   10M  0 part /boot/efi
nvme1n1       259:1    0  1.7T  0 disk 
> 
```


#### 2. 디스크 포멧 및 마운트

```shell
> sudo mkfs.xfs -f /dev/nvme1n1
meta-data=/dev/nvme1n1           isize=512    agcount=16, agsize=28991699 blks
         =                       sectsz=512   attr=2, projid32bit=1
         =                       crc=1        finobt=1, sparse=1, rmapbt=0
         =                       reflink=1    bigtime=1 inobtcount=1 nrext64=0
         =                       exchange=0  
data     =                       bsize=4096   blocks=463867184, imaxpct=5
         =                       sunit=0      swidth=0 blks
naming   =version 2              bsize=4096   ascii-ci=0, ftype=1, parent=0
log      =internal log           bsize=4096   blocks=226497, version=2
         =                       sectsz=512   sunit=0 blks, lazy-count=1
realtime =none                   extsz=4096   blocks=0, rtextents=0
Discarding blocks...Done.
> 
> sudo mkdir -p /mnt/nvme
> sudo mount -o noatime /dev/nvme1n1 /mnt/nvme
> sudo chown -R root:root /mnt/nvme
> df -h /mnt/nvme
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme1n1    1.8T   13G  1.8T   1% /mnt/nvme
>
```



---


## 모델 설치

현실적으로 A100 이나 H100 장비 대여가 쉽지 않은 상황에서 1장으로 운영 가능한 GPU 에서 돌릴 수 있는 서버에서 아래 2개의 모델을 비교 한다. (비교 문서는 추후 배포)

| 모델명 | 모델 가중치 크기 | 실제 GPU | KV 캐시 가용 (90% 활용 기준) |
| --- | --- | --- | --- |
| Qwen3.5-122B-A10B-GPTQ-Int4 | 62GB | 65\~70GB | **\~18GB** |
| Qwen3.6-27B-FP8 | 31GB | 33\~35GB | \~52GB |

- 기본 패키지 설치
- 모델 다운로드
- vllm 설정
- 모델 설정


### 기본 패키지 설치

##### huggingface-cli 설치

```shell
> pip install -U "huggingface_hub[cli]" hf_transfer 
```


##### 환경 변수 설정

```shell
# 다운로드 가속 (멀티스레드)
export HF_XET_HIGH_PERFORMANCE=1

# 저장 위치 - 둘 중 선택
export HF_HOME=/mnt/nvme/hf-cache      # 빠르지만 stop 시 소실
# export HF_HOME=/root/hf-cache        # 또는 EBS (영구)
```


### 모델 다운로드

- 모델을 로컬 디렉토리에 다운로드

```shell
## 첫번째 모델 다운로드
> hf download Qwen/Qwen3.5-122B-A10B-GPTQ-Int4 \
  --local-dir /stg/models/Qwen3.5-122B-A10B-GPTQ-Int4 \
  --max-workers 16  

## 두번째 모델 다운로드
> hf download Qwen/Qwen3.6-27B-FP8 \
  --local-dir /stg/models/Qwen3.6-27B-FP8 \
  --max-workers 16

> ls -al /stg/models  
total 32
drwxr-xr-x. 6 root root   116 May 19 18:46 .
drwxr-xr-x. 3 root root    20 May 19 16:56 ..
-rw-r--r--. 1 root root     0 May 19 17:25 .check_for_update_done
drwxr-xr-x. 3 root root 16384 May 19 17:30 Qwen3.5-122B-A10B-GPTQ-Int4
drwxr-xr-x. 3 root root 16384 May 19 18:46 Qwen3.6-27B-FP8
drwxr-xr-x. 4 root root    92 May 19 18:45 hub
drwxr-xr-x. 4 root root    59 May 19 17:28 xet
```



### VLLM 설치

vllm 은 패키지 의존성을 많이 요구하기 때문에 uv 환경에서 격리 하여 패키지 설치를 권장 함


#### uv 설치

```shell
> curl -LsSf https://astral.sh/uv/install.sh | sh
downloading uv 0.11.15 x86_64-unknown-linux-gnu
installing to /root/.local/bin
  uv
  uvx
everything's installed!
> source ~/.bashrc
> uv --version
uv 0.11.15 (x86_64-unknown-linux-gnu)
>
```


#### vllm 전용 프로젝트 생성 및 설치

```shell
> mkdir -p /usr/service/vllm-svc
> cd /usr/service/vllm-svc

> uv venv --python 3.12
Using CPython 3.12.13 interpreter at: /usr/bin/python3.12
Creating virtual environment at: .venv
Activate with: source .venv/bin/activate

> source .venv/bin/activate
(vllm-svc) > uv pip install vllm --torch-backend=auto
```



##### 테스트

```shell
(vllm-svc) > vllm serve /stg/models/Qwen3.5-122B-A10B-GPTQ-Int4 \
  --served-model-name qwen \
  --port 8000 \
  --tensor-parallel-size 1 \
  --quantization moe_wna16 \
  --max-model-len 32768 \
  --max-num-seqs 8 \
  --gpu-memory-utilization 0.90 \
  --reasoning-parser qwen3 \
  --trust-remote-code
```


```shell
(vllm-svc) >  curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen",
    "messages": [{"role":"user","content":"안녕"}],
    "max_tokens": 100,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
  
  
{"id":"chatcmpl-89cf9de14d6fdfd2","object":"chat.completion","created":1779181606,"prompt_routed_experts":null,"model":"qwen","choices":[{"index":0,"message":{"role":"assistant","content":"안녕하세요! 반갑습니다. 😊\n오늘 어떤 도움이 필요하신가요? 궁금한 점이 있거나 대화하고 싶은 주제가 있다면 언제든지 말씀해 주세요.","refusal":null,"annotations":null,"audio":null,"function_call":null,"tool_calls":[],"reasoning":null},"logprobs":null,"finish_reason":"stop","stop_reason":null,"token_ids":null,"routed_experts":null}],"service_tier":null,"system_fingerprint":"vllm-0.21.0-2426ae93","usage":{"prompt_tokens":14,"total_tokens":49,"completion_tokens":35,"prompt_tokens_details":null},"prompt_logprobs":null,"prompt_token_ids":null,"prompt_text":null,"kv_transfer_params":null}[root@ip-172-31-22-41 models]#
```


#### Service 등록

실행시 /stg/models/Qwen3.5-122B-A10B-GPTQ-Int ⇒ /mnt/nvme/models/Qwen3.5-122B-A10B-GPTQ-Int4 로 모델을 옮기고 nvme 에 있는 모델을 로드 한다.


- Qwen3.5-122B-A10B-GPTQ-Int4 

```shell
[Unit]
Description=vLLM Qwen3.5-122B-A10B-GPTQ-Int4 Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/usr/service/vllm-svc

Environment="PATH=/usr/service/vllm-svc/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
Environment="HF_HOME=/mnt/nvme/hf-cache"
Environment="VLLM_CACHE_ROOT=/mnt/nvme/vllm-cache"

# NVMe 마운트 확인
ExecStartPre=/bin/bash -c 'mountpoint -q /mnt/nvme || (echo "NVMe not mounted" && exit 1)'

# 모델/캐시 디렉토리 준비
ExecStartPre=/bin/mkdir -p /mnt/nvme/models /mnt/nvme/hf-cache /mnt/nvme/vllm-cache

# EBS → NVMe 동기화
ExecStartPre=/usr/bin/rsync -a --delete \
    /stg/models/Qwen3.5-122B-A10B-GPTQ-Int4/ \
    /mnt/nvme/models/Qwen3.5-122B-A10B-GPTQ-Int4/

ExecStart=/usr/service/vllm-svc/.venv/bin/vllm serve \
    /mnt/nvme/models/Qwen3.5-122B-A10B-GPTQ-Int4 \
    --served-model-name qwen \
    --port 8000 \
    --tensor-parallel-size 1 \
    --quantization moe_wna16 \
    --max-model-len 32768 \
    --max-num-seqs 8 \
    --gpu-memory-utilization 0.90 \
    --reasoning-parser qwen3 \
    --trust-remote-code

StandardOutput=append:/usr/service/logs/vllm/qwen_122.log
StandardError=append:/usr/service/logs/vllm/qwen_122.log

TimeoutStartSec=600
TimeoutStopSec=60
Restart=on-failure
RestartSec=10
KillMode=mixed

LimitNOFILE=1048576
LimitNPROC=1048576

[Install]
WantedBy=multi-user.target
```


- Qwen3.6-27B-FP8

```shell
[Unit]
Description=vLLM Qwen3.6-27B-FP8 Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/usr/service/vllm-svc

Environment="PATH=/usr/service/vllm-svc/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
Environment="HF_HOME=/mnt/nvme/hf-cache"
Environment="VLLM_CACHE_ROOT=/mnt/nvme/vllm-cache"

# NVMe 마운트 확인
ExecStartPre=/bin/bash -c 'mountpoint -q /mnt/nvme || (echo "NVMe not mounted" && exit 1)'

# 모델/캐시 디렉토리 준비
ExecStartPre=/bin/mkdir -p /mnt/nvme/models /mnt/nvme/hf-cache /mnt/nvme/vllm-cache

# EBS → NVMe 동기화
ExecStartPre=/usr/bin/rsync -a --delete \
    /stg/models/Qwen3.6-27B-FP8/ \
    /mnt/nvme/models/Qwen3.6-27B-FP8/

ExecStart=/usr/service/vllm-svc/.venv/bin/vllm serve \
    /mnt/nvme/models/Qwen3.6-27B-FP8 \
    --served-model-name qwen \
    --port 8000 \
    --tensor-parallel-size 1 \
    --max-model-len 262144 \
    --max-num-seqs 16 \
    --gpu-memory-utilization 0.92 \
    --enable-prefix-caching \
    --reasoning-parser qwen3 \
    --trust-remote-code

StandardOutput=append:/usr/service/logs/vllm/qwen_27.log
StandardError=append:/usr/service/logs/vllm/qwen_27.log

TimeoutStartSec=600
TimeoutStopSec=60
Restart=on-failure
RestartSec=10
KillMode=mixed
LimitNOFILE=1048576
LimitNPROC=1048576

[Install]
WantedBy=multi-user.target

```



---

## Qwen3-Omni-30B-A3B-Instruct (멀티모달)

앞의 텍스트 모델(Qwen3.5 / 3.6)과 달리 **영상·이미지·오디오를 함께 입력** 받는 옴니 모델. 6초 클립 영상 이해 벤치마크(vision-bench)에 사용한다. 설치 흐름은 위와 동일하되 **오디오 디코더 의존성** 과 **멀티모달 서빙 플래그** 가 추가된다. (vLLM 설치는 위 **VLLM 설치** 섹션과 **동일한 venv 를 재사용** 하며, 여기선 audio deps 만 추가한다.)

### 모델 다운로드

```shell
> hf download Qwen/Qwen3-Omni-30B-A3B-Instruct \
  --local-dir /stg/models/Qwen3-Omni-30B-A3B-Instruct \
  --max-workers 16
```


### 오디오 입력 지원 (필수)

`uv pip install vllm` 기본 설치엔 오디오 디코더가 빠져 있어, 오디오 입력 요청 시 `400 "Invalid or unsupported audio file"` 가 발생한다 (비디오 단독 요청은 정상이라 증상이 헷갈림). 아래 3개를 venv 에 추가해야 한다.

```shell
(vllm-svc) > uv pip install soundfile librosa av
```

- `soundfile` (libsndfile 바인딩) · `librosa` (리샘플링) · `av` (PyAV, 컨테이너 demux) — 셋 다 필요
- 설치 후 **서비스 재기동해야 적용** 된다 (`sudo systemctl restart vllm_omni_i` )
- 클라이언트 요청 본문에 `mm_processor_kwargs: {"use_audio_in_video": true}` 를 넣어야 mp4 안 오디오가 함께 처리된다


### Service 등록

**참고:** 오디오 입력을 쓰려면 `--limit-mm-per-prompt` 에 `audio` 가 포함돼야 하고, venv 엔 위 오디오 deps 가 설치돼 있어야 한다.

```shell
[Unit]
Description=vLLM Qwen3-Omni-30B-A3B-Instruct Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/usr/service/vllm-svc
Environment="PATH=/usr/service/vllm-svc/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"

ExecStart=/usr/service/vllm-svc/.venv/bin/vllm serve \
    /stg/models/Qwen3-Omni-30B-A3B-Instruct \
    --served-model-name qwen \
    --port 8000 \
    --host 0.0.0.0 \
    --dtype bfloat16 \
    --max-model-len 16384 \
    --max-num-seqs 8 \
    --gpu-memory-utilization 0.85 \
    --limit-mm-per-prompt '{"image":3,"video":3,"audio":3}' \
    --allowed-local-media-path / \
    --tensor-parallel-size 1 \
    --trust-remote-code

StandardOutput=append:/usr/service/logs/vllm/qwen_omni.log
StandardError=append:/usr/service/logs/vllm/qwen_omni.log
TimeoutStartSec=900
TimeoutStopSec=60
Restart=on-failure
RestartSec=10
KillMode=mixed
LimitNOFILE=1048576
LimitNPROC=1048576

[Install]
WantedBy=multi-user.target
```


감사합니다.

