---
title: "Installing Qwen 3.x"
sidebar_position: 1
slug: "1"
last_update:
  date: 2026-06-04
---

## AWS Server Setup

### Configuring an EC2 Instance

---

#### Basic Information (Summary)

| Category | Selection |
| --- | --- |
| Region | **us-west-2 (Oregon)** |
| Application and OS Image | Deep Learning Base AMI with Single CUDA (Amazon Linux 2023) |
| Instance Type | **g7e.4xlarge** (1 GPU, 96 GB VRAM) |
| Storage | EBS 2 TB (gp3) + Instance Store 1.7 TB (NVMe) |

**Reasons for Region Selection**

New GPU instance types (G7e, P5, P6, etc.) are currently in a state where **supply cannot keep up with demand**. Depending on the region and time of day, instance provisioning often fails with an `InsufficientInstanceCapacity` error.

For this reason, region selection should not be based solely on "proximity," but must consider the following **two factors together**.

1. **Capacity Availability** — Can the instance actually be launched when needed?
1. **Response Time in Korea** — Network latency as perceived by the user 

**Comparison of Regions Offering G7e** (Measured on 2026-05-19)

| Region | Capacity Score | Korea TCP RTT | Overall |
| --- | --- | --- | --- |
| **us-west-2** (Oregon) ⭐ | **3** | 180 ms | 🟢 Balanced (2 availability zones with a capacity score of 3) |
| us-east-1 (Virginia) | 3 | 208 ms | 🟢 Stable (2 availability zones with 3-point capacity) |
| us-east-2 (Ohio) | 3 | 213 ms | 🟢 Stable |
| ap-northeast-1 (Tokyo) | 1 | 46 ms | 🟠 Close but difficult to secure |
| ap-northeast-2 (Seoul) | 1 | 18 ms | 🔴 Very difficult to secure |
| eu-west-2 (London) | 1 | 301 ms | 🔴 Far away and difficult to secure |

**Score Interpretation**

- Capacity score (g7e.12xl, 1–10) = AWS **Spot Placement Score** (1=Very scarce / 10=Very abundant). Strong correlation with On-Demand availability
- Scores are generally low across all 6 regions offering G7e (a common phenomenon with newer GPUs) → Among them, **a score of 3 is currently the best available**
- Scores vary by time zone and day of the week → We recommend re-measuring manually before deployment

**Check the Spot Placement Score Yourself**

```bash
aws ec2 get-spot-placement-scores \
  --instance-types g7e.12xlarge \
  --target-capacity 1 \
  --no-single-availability-zone \
  --region-names us-west-2 us-east-1 us-east-2 ap-northeast-1 ap-northeast-2 eu-west-2 \
  --query "sort_by(SpotPlacementScores, &Score) | reverse(@) | [].[Region, Score]" \
  --output table
```

- Required permissions: `ec2:GetSpotPlacementScores`
- Cost: Free, Evaluation period: Next 1 hour

**(1) Capacity Aspect**

- The Korea and Japan regions (Seoul and Tokyo) have a score of **1** → Frequent provisioning failures are expected during weekday business hours
- The three US regions (us-east-1 / us-east-2 / us-west-2) have a score of **3**
- Among these, **us-west-2 and us-east-1 have two availability zones with a score of 3** (usw2-az1·az3 / use1-az2·az6) → If capacity is exhausted in one availability zone, a fallback to another is possible

**(2) Response Time**

- LLM serving takes 200–500 ms for the model to generate the first token → An additional 150–200 ms for the network is negligible in terms of user experience
- If proximity to Korea is a priority, Tokyo is the sweet spot, but capacity constraints are significant

> 🎯 **Conclusion**
>
> - **Prioritizing availability stability**, **select us-west-2 (Oregon)**
>
> - When scaling for interactive serving to Korean users, consider ap-northeast-1 (Tokyo) multi-region deployment or **Capacity Block for ML / Capacity Reservation**

---

#### 1. Application and OS Image (Amazon Machine Image)

**Selected AMI**

| Item | Value |
| --- | --- |
| Name | Deep Learning Base AMI with Single CUDA (Amazon Linux 2023) 20260512 |
| OS | Amazon Linux 2023 (Kernel 6.1.170) |
| Owner | Amazon |
| Architecture | x86_64 |

**Note: List of supported instances according to the AMI description**

```javascript
G4dn, G5, G6, Gr6, G6e, P4d, P4de, P5, P5e, P5en, P6-B200, P6-B300
```

> ℹ️ **G7e is not listed** in the official list. However, actual testing confirmed that the Blackwell driver and CUDA function normally. When recreating the AMI in the future, we recommend using the **Deep Learning Base OSS Nvidia Driver GPU AMI** (AL2023), which explicitly supports G7e.

---

#### 2. Instance Type

**Selected Instance** : `g7e.4xlarge`

| Item | Value |
| --- | --- |
| vCPU | 16 |
| RAM | 128 GB |
| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition × 1 |
| VRAM | 96 GB (97,887 MiB measured) |
| GPU Architecture | Blackwell (sm_120, native FP4 support) |
| Network | 50 Gbps |
| Instance Store | NVMe SSD 1.9 TB (`nvme1n1` ) — Included by default with this instance type |

<details>
<summary><strong>g7e Family Comparison (Reference)</strong></summary>

| Type | vCPU | RAM | Number of GPUs | Total VRAM | Network |
| --- | --- | --- | --- | --- | --- |
| g7e.2xlarge | 8 | 64 GB | 1 | 96 GB | 50 Gbps |
| **g7e.4xlarge** ⭐ | **16** | **128 GB** | **1** | **96 GB** | **50 Gbps** |
| g7e.8xlarge | 32 | 256 GB | 1 | 96 GB | 100 Gbps |
| g7e.12xlarge | 48 | 512 GB | 2 | 192 GB | 400 Gbps |
| g7e.24xlarge | 96 | 1 TB | 4 | 384 GB | 800 Gbps |
| g7e.48xlarge | 192 | 2 TB | 8 | 768 GB | 1600 Gbps |

</details>**Reasons for Choosing 4xlarge**

- MoE models with 30–35 billion parameters, such as Qwen3-Coder-30B-A3B and Qwen3.6-35B-A3B, require ~70 GB of VRAM in bf16 mode → A single 96 GB card provides ample capacity, including KV cache
- Larger models (80–120B) are also possible with FP8/FP4 quantization
- First verify with 1 GPU; if scaling is needed, switch to 12xlarge or larger

**VRAM Requirements by Model**

Based on 32k contexts and a single sequence. Since vLLM dynamically allocates paged KV cache, actual usage varies depending on the workload.

| Model | Total/Active Parameters | Precision | Weight VRAM | KV Cache (32k×1) | Total VRAM |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5-122B-A10B-GPTQ-Int4 | 122B / 10B (MoE) | Int4 (GPTQ) | ~63 GB | ~3 GB | ~69 GB |
| Qwen3.6-27B-FP8 | 27B (Dense) | FP8 (block 128) | ~29 GB | ~8 GB | ~40 GB |

---

#### 3. Storage Configuration

**1) Root EBS Volume (Persistent Storage)**

| Item | Value |
| --- | --- |
| Size | 2,048 GiB (2 TB) |
| Type | gp3 |
| IOPS | 16,000 |
| Throughput | 1,000 MB/s |
| Encryption | Not applied (encryption recommended upon production deployment) |
| Device | `nvme0n1` |
| Mount | `/` (Root) |

**Purpose**: Model weights (long-term storage), Docker images, OS, etc.

**2) Instance Store (Temporary Storage — Included by default on g7e.4xlarge)**

| Item | Value |
| --- | --- |
| Device | `nvme1n1` |
| Size | 1.7 TB |
| Type | NVMe SSD (instance-local) |
| Mount | `/mnt/nvme` (XFS, manual mount required — see NVMe settings below) |

> ⚠️ **Instance Store Data Persistence**
>
> | Action | Data |
> | --- | --- |
> | Reboot | Persistent |
> | **Stop / Start** | **Deleted** |
> | Terminate | Deleted |
> | Hardware Failure | Deleted |

**Recommended Use Case Segregation**

- **EBS (** `/` **)** : Model weights, persistent data → Data that must never be lost
- **Instance Store (** `/mnt/nvme` **)** : KV cache, temporary builds, swap, inference logs → Data that can be lost

---

### NVMe Configuration

- In a cloud environment, NVMe has the following characteristics that differ from those of a standard physical server:
  - Data is retained upon reboot

  - Data is lost when the instance is stopped→started or terminated

#### 1. Check NVMe Device

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

#### 2. Disk Format and Mount

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

## Model Installation

Given that renting A100 or H100 hardware is not practical, we will compare the following two models on a server capable of running on a single GPU. (Comparison documentation will be released later)

| Model Name | Model Weight Size | Actual GPU | KV Cache Availability (based on 90% utilization) |
| --- | --- | --- | --- |
| Qwen3.5-122B-A10B-GPTQ-Int4 | 62GB | 65–70GB | **~18GB** |
| Qwen3.6-27B-FP8 | 31GB | 33–35GB | ~52GB |

- Install required packages
- Download models
- Configure VLLM
- Configure models

### Install required packages

##### Installing huggingface-cli

```shell
> pip install -U "huggingface_hub[cli]" hf_transfer 
```

##### Setting Environment Variables

```shell
# 다운로드 가속 (멀티스레드)
export HF_XET_HIGH_PERFORMANCE=1

# 저장 위치 - 둘 중 선택
export HF_HOME=/mnt/nvme/hf-cache      # 빠르지만 stop 시 소실
# export HF_HOME=/root/hf-cache        # 또는 EBS (영구)
```

### Downloading the Model

- Download the model to a local directory

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

### Install VLLM

Since VLLM requires many package dependencies, it is recommended to install the packages in an isolated UV environment.

#### Install UV

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

#### Create and install a dedicated VLLM project

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

##### Testing

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

#### Service Registration

At runtime, /stg/models/Qwen3.5-122B-A10B-GPTQ-Int ⇒ /mnt/nvme/models/Qwen3.5-122B-A10B-GPTQ-Int4 and loads the model from the NVMe drive.

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

## Qwen3-Omni-30B-A3B-Instruct (Multimodal)

Unlike the text models mentioned earlier (Qwen3.5 / 3.6), this is an omni model that **accepts video, images, and audio as input together**. It is used for the 6-second video understanding benchmark (vision-bench). The installation process is the same as above, but **audio decoder dependencies** and **multimodal serving flags** are added. (For vLLM installation, **reuse the same venv** as in the **VLLM Installation** section above; here, only the audio dependencies are added.)

### Model Download

```shell
> hf download Qwen/Qwen3-Omni-30B-A3B-Instruct \
  --local-dir /stg/models/Qwen3-Omni-30B-A3B-Instruct \
  --max-workers 16
```

### Audio Input Support (Required)

`uv pip install vllm` The default installation does not include an audio decoder, so an `400 "Invalid or unsupported audio file"` error occurs when an audio input request is made (since video-only requests work normally, this symptom can be confusing). The following three items must be added to the venv.

```shell
(vllm-svc) > uv pip install soundfile librosa av
```

- `soundfile` (libsndfile bindings) · `librosa` (resampling) · `av` (PyAV, container demux) — All three are required
- **You must restart the service** after installation for the changes to take effect (`sudo systemctl restart vllm_omni_i`)
- You must include `mm_processor_kwargs: {"use_audio_in_video": true}` in the client request body for the audio in the MP4 to be processed

### Service Registration

**Note:** To use audio input, `--limit-mm-per-prompt` must include `audio`, and the audio dependencies listed above must be installed in the venv.

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

Thank you.

