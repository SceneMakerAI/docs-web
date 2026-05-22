---
title: "Qwen 3.x Installation"
sidebar_position: 1
slug: "1"
---

## AWS Server Setup

### EC2 Instance Configuration

---

#### Basic Information (Summary)

| Category | Selection |
| --- | --- |
| Region | **us-west-2 (Oregon)** |
| Application and OS Image | Deep Learning Base AMI with Single CUDA (Amazon Linux 2023) |
| Instance Type | **g7e.4xlarge** (1 GPU, 96 GB VRAM) |
| Storage | EBS 2 TB (gp3) + Instance Store 1.7 TB (NVMe) |

**Region Selection Rationale**

Next-generation GPU instances (G7e, P5, P6, etc.) are in a state where **supply cannot keep up with demand**. Depending on the region and time of day, instance provisioning frequently fails with `InsufficientInstanceCapacity` errors.

For this reason, region selection should not simply be "the nearest region" — two axes must be considered together:

1. **Capacity availability** — Can you actually launch an instance when you need it?

1. **Korea response time** — Network latency perceived by end users

<br />

**G7e Region Comparison** (measured 2026-05-19)

| Region | Capacity Score | Korea TCP RTT | Overall |
| --- | --- | --- | --- |
| **us-west-2** (Oregon) ⭐ | **3** | 180 ms | 🟢 Balanced (2 AZs with capacity score 3) |
| us-east-1 (Virginia) | 3 | 208 ms | 🟢 Stable (2 AZs with capacity score 3) |
| us-east-2 (Ohio) | 3 | 213 ms | 🟢 Stable |
| ap-northeast-1 (Tokyo) | 1 | 46 ms | 🟠 Close but hard to provision |
| ap-northeast-2 (Seoul) | 1 | 18 ms | 🔴 Very hard to provision |
| eu-west-2 (London) | 1 | 301 ms | 🔴 Far and hard to provision |

**Score Interpretation**

- Capacity score (g7e.12xl, 1\~10) = AWS **Spot Placement Score** (1=very scarce / 10=very available). Strongly correlated with On-Demand availability as well.

- All 6 G7e regions have low scores (common for next-gen GPUs) → **Score 3 is currently the best available**

- Scores change by time of day and day of week → measure again directly before production deployment

**Checking Spot Placement Score**

```bash
aws ec2 get-spot-placement-scores \
  --instance-types g7e.12xlarge \
  --target-capacity 1 \
  --no-single-availability-zone \
  --region-names us-west-2 us-east-1 us-east-2 ap-northeast-1 ap-northeast-2 eu-west-2 \
  --query "sort_by(SpotPlacementScores, &Score) | reverse(@) | [].[Region, Score]" \
  --output table
```

- Required permission: `ec2:GetSpotPlacementScores`

- Cost: Free, evaluation period: next 1 hour

**(1) Capacity perspective**

- Korea/Japan regions (Seoul, Tokyo) score **1** → frequent provisioning failures expected during weekday business hours

- Three US regions (us-east-1 / us-east-2 / us-west-2) score **3**

- Among these, **us-west-2 and us-east-1 have 2 AZs with score 3** (usw2-az1·az3 / use1-az2·az6) → if one AZ's capacity is exhausted, fallback to another AZ is possible

**(2) Latency perspective**

- LLM serving takes 200\~500 ms for the model itself to generate the first token → an additional +150\~200 ms network overhead is barely perceptible to real users

- If Korea proximity is the top priority, Tokyo is the sweet spot, but it has capacity constraints

> 🎯 **Conclusion**
>
> - **Prioritizing provisioning stability**, selected **us-west-2 (Oregon)**
>
> - When scaling to interactive serving for Korean users, consider ap-northeast-1 (Tokyo) multi-region or **Capacity Block for ML / Capacity Reservation**

---

#### 1. Application and OS Image (Amazon Machine Image)

**Selected AMI**

| Item | Value |
| --- | --- |
| Name | Deep Learning Base AMI with Single CUDA (Amazon Linux 2023) 20260512 |
| OS | Amazon Linux 2023 (kernel 6.1.170) |
| Owner | Amazon |
| Architecture | x86_64 |

**Note: Supported instance list per AMI description**

```javascript
G4dn, G5, G6, Gr6, G6e, P4d, P4de, P5, P5e, P5en, P6-B200, P6-B300
```

> ℹ️ **G7e is not in the official list.** However, testing confirmed that the Blackwell driver and CUDA work correctly. For future deployments, the **Deep Learning Base OSS Nvidia Driver GPU AMI** (AL2023) that explicitly supports G7e is recommended.

---

#### 2. Instance Type

**Selected instance**: `g7e.4xlarge`

| Item | Value |
| --- | --- |
| vCPU | 16 |
| RAM | 128 GB |
| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition × 1 |
| VRAM | 96 GB (97,887 MiB measured) |
| GPU Architecture | Blackwell (sm_120, native FP4 support) |
| Network | 50 Gbps |
| Instance Store | NVMe SSD 1.9 TB (`nvme1n1`) — included by default with instance type |

<details>
<summary>**g7e family comparison (reference)**</summary>

| Type | vCPU | RAM | GPUs | Total VRAM | Network |
| --- | --- | --- | --- | --- | --- |
| g7e.2xlarge | 8 | 64 GB | 1 | 96 GB | 50 Gbps |
| **g7e.4xlarge** ⭐ | **16** | **128 GB** | **1** | **96 GB** | **50 Gbps** |
| g7e.8xlarge | 32 | 256 GB | 1 | 96 GB | 100 Gbps |
| g7e.12xlarge | 48 | 512 GB | 2 | 192 GB | 400 Gbps |
| g7e.24xlarge | 96 | 1 TB | 4 | 384 GB | 800 Gbps |
| g7e.48xlarge | 192 | 2 TB | 8 | 768 GB | 1600 Gbps |


</details>

**Rationale for 4xlarge**

- MoE 30\~35B models such as Qwen3-Coder-30B-A3B / Qwen3.6-35B-A3B require \~70 GB VRAM in bf16 → fits on a single 96 GB GPU with KV cache headroom

- With FP8/FP4 quantization, larger models (80\~120B) are also possible

- Start with 1 GPU validation, scale to 12xlarge or larger if needed

**VRAM requirements by model**

32k context, single sequence. vLLM uses paged KV cache with dynamic allocation, so actual usage varies by workload.

| Model | Total/Active Params | Precision | Weight VRAM | KV Cache (32k×1) | Total VRAM |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5-122B-A10B-GPTQ-Int4 | 122B / 10B (MoE) | Int4 (GPTQ) | \~63 GB | \~3 GB | \~69 GB |
| Qwen3.6-27B-FP8 | 27B (Dense) | FP8 (block 128) | \~29 GB | \~8 GB | \~40 GB |

---

#### 3. Storage Configuration

**1) Root EBS Volume (persistent storage)**

| Item | Value |
| --- | --- |
| Size | 2,048 GiB (2 TB) |
| Type | gp3 |
| IOPS | 16,000 |
| Throughput | 1,000 MB/s |
| Encryption | Not applied (recommended for production) |
| Device | `nvme0n1` |
| Mount | `/` (root) |

**Usage**: Model weights (permanent), Docker images, OS, etc.

**2) Instance Store (temporary storage — included with g7e.4xlarge)**

| Item | Value |
| --- | --- |
| Device | `nvme1n1` |
| Size | 1.7 TB |
| Type | NVMe SSD (instance-local) |
| Mount | `/mnt/nvme` (XFS, manual mount required — see NVMe setup below) |

> ⚠️ **Instance store data persistence**
>
> | Action | Data |
> | --- | --- |
> | Reboot | Preserved |
> | **Stop / Start** | **Lost** |
> | Terminate | Lost |
> | Hardware failure | Lost |

**Recommended storage split**

- **EBS (`/`)**: Model weights, persistent data → anything that must not be lost

- **Instance store (`/mnt/nvme`)**: KV cache, temporary builds, swap, inference logs → anything that can be lost

<br />

---

### NVMe Setup

NVMe in cloud environments differs from physical servers:
- Data is preserved on reboot
- Data is lost on instance stop→start or termination

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

<br />

#### 2. Format and Mount the Disk

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

<br />

<br />

---

<br />

## Model Installation

Given that renting A100 or H100 hardware is not easily available in practice, we compare the following two models that can run on a single affordable GPU server. (Comparison document to be published separately.)

| Model | Weight Size | Actual GPU VRAM | KV Cache Available (at 90% utilization) |
| --- | --- | --- | --- |
| Qwen3.5-122B-A10B-GPTQ-Int4 | 62 GB | 65\~70 GB | **\~18 GB** |
| Qwen3.6-27B-FP8 | 31 GB | 33\~35 GB | \~52 GB |

- Base package installation

- Model download

- vLLM configuration

- Model configuration

<br />

### Base Package Installation

##### Install huggingface-cli

```shell
> pip install -U "huggingface_hub[cli]" hf_transfer 
```

<br />

##### Set environment variables

```shell
# Enable accelerated download (multi-threaded)
export HF_XET_HIGH_PERFORMANCE=1

# Storage location — choose one
export HF_HOME=/mnt/nvme/hf-cache      # Fast but lost on stop
# export HF_HOME=/root/hf-cache        # Or EBS (persistent)
```

<br />

### Model Download

- Download models to local directory

```shell
## Download first model
> hf download Qwen/Qwen3.5-122B-A10B-GPTQ-Int4 \
  --local-dir /stg/models/Qwen3.5-122B-A10B-GPTQ-Int4 \
  --max-workers 16  

## Download second model
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

<br />

<br />

### vLLM Installation

vLLM requires many package dependencies, so isolated installation in a uv environment is recommended.

<br />

#### Install uv

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

<br />

#### Create vLLM project and install

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

<br />

<br />

##### Test

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

<br />

```shell
(vllm-svc) >  curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen",
    "messages": [{"role":"user","content":"Hello"}],
    "max_tokens": 100,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
  
  
{"id":"chatcmpl-89cf9de14d6fdfd2","object":"chat.completion","created":1779181606,"model":"qwen","choices":[{"index":0,"message":{"role":"assistant","content":"Hello! Nice to meet you. 😊\nIs there anything I can help you with today? Feel free to ask if you have any questions or topics you'd like to discuss.","refusal":null},"finish_reason":"stop"}],"usage":{"prompt_tokens":14,"total_tokens":49,"completion_tokens":35}}
```

<br />

#### Register as a Service

At runtime, move the model from `/stg/models/Qwen3.5-122B-A10B-GPTQ-Int4` to `/mnt/nvme/models/Qwen3.5-122B-A10B-GPTQ-Int4` and load the model from NVMe.

<br />

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

# Check NVMe mount
ExecStartPre=/bin/bash -c 'mountpoint -q /mnt/nvme || (echo "NVMe not mounted" && exit 1)'

# Prepare model/cache directories
ExecStartPre=/bin/mkdir -p /mnt/nvme/models /mnt/nvme/hf-cache /mnt/nvme/vllm-cache

# EBS → NVMe sync
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

<br />

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

# Check NVMe mount
ExecStartPre=/bin/bash -c 'mountpoint -q /mnt/nvme || (echo "NVMe not mounted" && exit 1)'

# Prepare model/cache directories
ExecStartPre=/bin/mkdir -p /mnt/nvme/models /mnt/nvme/hf-cache /mnt/nvme/vllm-cache

# EBS → NVMe sync
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

<br />
