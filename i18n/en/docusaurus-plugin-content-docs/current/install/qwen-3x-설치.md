---
title: "Installing Qwen 3.x"
sidebar_position: 1
slug: "1"
last_update:
  date: 2026-07-07
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
| Storage | 2 TB EBS (gp3) + 1.7 TB Instance Store (NVMe) |

**Reasons for Region Selection**

Supply of the new GPU instance types (G7e, P5, P6, etc.) **cannot keep up with demand**. Depending on the region and time of day, instance provisioning often fails with an `InsufficientInstanceCapacity` error.

For this reason, region selection should not be based solely on “proximity,” but must consider the following **two factors together**.

1

. **Capacity Availability** — Can the instance actually be launched when needed
1

? **Response Time in Korea** — Network latency as perceived by the user 

**Comparison of Regions Offering G7e** (Measured on May 19, 2026)

| Region | Capacity Score | Korea TCP RTT | Overall |
| --- | --- | --- | --- |
| **us-west-2** (Oregon) ⭐ | **3** | 180 ms | 🟢 Balanced (2 availability zones with a capacity score of 3) |
| us-east-1 (Virginia) | 3 | 208 ms | 🟢 Stable (2 availability zones with a capacity score of 3) |
| us-east-2 (Ohio) | 3 | 213 ms | 🟢 Stable |
| ap-northeast-1 (Tokyo) | 1 | 46 ms | 🟠 Close but difficult to secure |
| ap-northeast-2 (Seoul) | 1 | 18 ms | 🔴 Very difficult to secure |
| eu-west-2 (London) | 1 | 301 ms | 🔴 Far away and difficult to secure |

**Score Interpretation**

- Capacity score (g7e.12xl, 1–10) = AWS **Spot Placement Score** (1 = very scarce / 10 = very abundant). Strong correlation with On-Demand availability
- Scores are generally low across all 6 regions offering G7e (a common phenomenon for newer GPUs) → Among these, **a score of 3 is currently the best available**
- Scores vary by time of day and day of the week → We recommend remeasuring yourself before deployment

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
- Cost: Free; Evaluation period: Next 1 hour

**(1) Capacity**

- The South Korea and Japan regions (Seoul and Tokyo) have a score of **1** → Frequent provisioning failures are expected during weekday business hours
- The three U.S. regions (us-east-1 / us-east-2 / us-west-2) have a score of **3**
- Among these, **us-west-2 and us-east-1 have two availability zones with a score of 3** (usw2-az1·az3 / use1-az2·az6) → Even if capacity in one availability zone is exhausted, a fallback to another availability zone is possible

**(2) Response Time**

- LLM serving takes 200–500 ms for the model to generate its first token → An additional 150–200 ms for the network is negligible in terms of user experience
- If proximity to South Korea is a priority, Tokyo is the sweet spot, but capacity constraints are significant

:::tip
🎯 **Conclusion**

- Prioritizing **availability stability**, **select us-west-2 (Oregon)**
- When scaling for interactive serving to Korean users, consider a multi-region setup using ap-northeast-1 (Tokyo) or **Capacity Block for ML / Capacity Reservation**
:::

---

#### 1. Application and OS Image (Amazon Machine Image)

**Selected AMI**

| Item | Value |
| --- | --- |
| Name | Deep Learning Base AMI with Single CUDA (Amazon Linux 2023) 20260512 |
| OS | Amazon Linux 2023 (Kernel 6.1.170) |
| Owner | Amazon |
| Architecture | x86_64 |

**Note: List of supported instance types in the AMI description**

```javascript
G4dn, G5, G6, Gr6, G6e, P4d, P4de, P5, P5e, P5en, P6-B200, P6-B300
```

:::warning
ℹ️ **G7e is not listed** in the official list. However, actual testing confirmed that the Blackwell driver and CUDA function normally. When recreating the AMI in the future, we recommend using the **Deep Learning Base OSS NVIDIA Driver GPU AMI** (AL2023), which explicitly supports the G7e.
:::

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
| Instance Store | 1.9 TB NVMe SSD (`nvme1n1` ) — Included by default with this instance type |

<details>
<summary><strong>g7e Family Comparison (for reference)</strong></summary>

| Type | vCPU | RAM | Number of GPUs | Total VRAM | Network |
| --- | --- | --- | --- | --- | --- |
| g7e.2xlarge | 8 | 64 GB | 1 | 96 GB | 50 Gbps |
| **g7e.4xlarge** ⭐ | **16** | **128 GB** | **1** | **96 GB** | **50 Gbps** |
| g7e.8xlarge | 32 | 256 GB | 1 | 96 GB | 100 Gbps |
| g7e.12xlarge | 48 | 512 GB | 2 | 192 GB | 400 Gbps |
| g7e.24xlarge | 96 | 1 TB | 4 | 384 GB | 800 Gbps |
| g7e.48xlarge | 192 | 2 TB | 8 | 768 GB | 1600 Gbps |

</details>

details*Reasons for Choosing 4xlarge**

- MoE models with 30–35B parameters, such as Qwen3-Coder-30B-A3B and Qwen3.6-35B-A3B, require ~70 GB of VRAM in bf16 mode → a single 96 GB card provides ample capacity, even with a KV cache
- With FP8/FP4 quantization, even larger models (80–120B) are possible
- First, validate with 1 GPU; if scaling is needed, switch to 12xlarge or larger

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
| Encryption | None (encryption recommended upon production deployment) |
| Device | `nvme0n1` |
| Mount | `/` (root) |

**Purpose**: Model weights (permanent storage), Docker images, OS, etc.

**2) Instance Store (Temporary Storage — Included by default on g7e.4xlarge)**

| Item | Value |
| --- | --- |
| Device | `nvme1n1` |
| Size | 1.7 TB |
| Type | NVMe SSD (instance-local) |
| Mount | `/mnt/nvme` (XFS, manual mount required — see NVMe settings below) |

:::caution
⚠️ **Instance Store Data Persistence**

| Action | Data |
| --- | --- |
| Reboot | Persisted |
| **Stop / Start** | **Deleted** |
| Terminate | Deleted |
| Hardware Failure | Deleted |
:::

**Separation of Uses Recommended**

- **EBS (** `/` **)**: Model weights, persistent data → Data that must never be lost
- **Instance Store (** `/mnt/nvme` **)**: KV cache, temporary builds, swap, inference logs → Data that can be lost

 

---

### NVMe Configuration

- In a cloud environment, NVMe has the following characteristics that differ from those on a typical physical server:
  - Data is retained upon reboot

  - Data is lost when the instance is stopped and restarted, or when it is terminated

#### 1. Verify NVMe Device

```shell
> lsblk
NAME          MAJ:MIN RM  SIZE RO TYPE MOUNTPOINTS
nvme0n1       259:0    0    2T  0 disk 
├─nvme0n1p1   259:2    0    2T  0 part /
├─nvme0n1p127 259:3    0    1M  0 part 
└─nvme0n1p128 259:4    0   10M  0 part /boot/efi
nvme1n1       259:1    0  1.7T  0 disk 
> lsblk -d -o NAME,MODEL,SIZE
NAME    MODEL                             SIZE
nvme0n1 Amazon Elastic Block Store        300G
nvme1n1 Amazon EC2 NVMe Instance Storage  3.5T
```

 

#### 2. Disk Formatting and Mounting

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

Given that it is not easy to rent A100 or H100 hardware in practice, we will compare the following two models on a server capable of running on a single GPU. (Comparison document to be released later)

| Model Name | Model Weight Size | Actual GPU | KV Cache Availability (based on 90% utilization) |
| --- | --- | --- | --- |
| Qwen3.5-122B-A10B-GPTQ-Int4 | 62GB | 65–70GB | **~18GB** |
| Qwen3.6-27B-FP8 | 31GB | 33–35GB | ~52GB |

- Install the base package
- Download the model
- Configure VLLM
- Configure the model

### Install the base package

##### Install huggingface-cli

```shell
> pip install -U "huggingface_hub[cli]" hf_transfer 
```

##### Set Environment Variables

```shell
# Download Acceleration (Multithreaded)
export HF_XET_HIGH_PERFORMANCE=1

# Save Location - Choose One of the Two
export HF_HOME=/mnt/nvme/hf-cache # Fast, but data is lost when the process stops
# export HF_HOME=/root/hf-cache # or EBS (persistent)
```

### Download the Model

- Download the model to a local directory
- After downloading, the model can be uploaded to S3.

```shell
## Download the First Model
> hf download Qwen/Qwen3.5-122B-A10B-GPTQ-Int4 \
  --local-dir /stg/models/Qwen3.5-122B-A10B-GPTQ-Int4 \
  --max-workers 16  

## Download the Second Model
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

 

### Installing VLLM

Since VLLM requires many package dependencies, it is recommended to install the packages in an isolated UV environment.

- Target: RTX PRO 6000 Blackwell (sm_120) / CUDA 13.0 / Python 3.12 / AL2023 

```text
vllm==0.22.0
torch==2.11.0+cu130
torchaudio==2.11.0+cu130
torchvision==0.26.0+cu130
flashinfer-python==0.6.12
transformers==5.8.1
```

#### Installing uv

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

#### Setting up the environment 

```shell
# Creating a Directory
> mkdir -p /usr/service/vllm-svc
> cd /usr/service/vllm-svc

# UV Sae-eong
> uv venv --python 3.12
Using CPython 3.12.13 interpreter at: /usr/bin/python3.12
Creating virtual environment at: .venv
Activate with: source .venv/bin/activate

# Confirm
> source .venv/bin/activate
(vllm-svc) > python --version
Python 3.12.13
(vllm-svc) > 
```

#### Installing Torch

- Do not proceed under any circumstances if sm_120 is not included (required for Blackwell GPUs)
  - sm_100 / sm_120: Architectures supporting Blackwell, RTX 5090, 5080, and other RTX 50 series GPUs

```bash
(vllm-svc) > uv pip install \
    torch==2.11.0 torchaudio==2.11.0 torchvision==0.26.0 \
    --index-url https://download.pytorch.org/whl/cu130
    
(vllm-svc) > python - <<'PY'
import torch
al = torch.cuda.get_arch_list()
print("torch", torch.__version__, "| cuda", torch.version.cuda)
print("arch_list", al)
assert torch.__version__.endswith("+cu130"), "❌ Not the cu130 wheel"
assert "sm_120" in al, "❌ sm_120 not included → No Blackwell kernel"
print("✅ torch OK")
PY

torch 2.11.0+cu130 | cuda 13.0
arch_list ['sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120']
✅ torch OK
(vllm-svc) >


# Since VLLM can change the Torch version, we'll install it with a fixed version.
(vllm-svc) > cat > /tmp/torch-constraint.txt <<'EOF'
torch==2.11.0+cu130
torchaudio==2.11.0+cu130
torchvision==0.26.0+cu130
EOF

(vllm-svc) > uv pip install vllm==0.22.0 \
    --constraint /tmp/torch-constraint.txt \
    --extra-index-url https://download.pytorch.org/whl/cu130 \
    --index-strategy unsafe-best-match

# Check the Final Version
(vllm-svc) > .venv/bin/vllm --version
0.22.0
(vllm-svc) >
```

#### Add Multimodal Features

```bash
(vllm-svc) > uv pip install ninja 
(vllm-svc) > which ninja
/usr/service/vllm-svc/.venv/bin/ninja
(vllm-svc) > 
```

#### Create Cache Directory

```bash
(vllm-svc) > mkdir -p /usr/service/cache/flashinfer
(vllm-svc) > mkdir -p /usr/service/cache/vllm-cache
(vllm-svc) > mkdir -p /usr/service/cache/hf-cache
```

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

```shell
(vllm-svc) >  curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen",
    "messages": [{"role":"user","content":"Hello"}],
    "max_tokens": 100,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
  
  
{"id":"chatcmpl-89cf9de14d6fdfd2","object":"chat.completion","created":1779181606,"prompt_routed_experts":null,"model":"qwen","choices":[{"index":0,"message":{"role":"assistant","content":"Hello! Nice to meet you. 😊\nHow can I help you today? If you have any questions or topics you’d like to discuss, please feel free to let me know.","refusal":null,"annotations":null,"audio":null,"function_call":null,"tool_calls":[],"reasoning":null},"logprobs":null,"finish_reason":"stop","stop_reason":null,"token_ids":null,"routed_experts":null}],"service_tier":null,"system_fingerprint":"vllm-0.21.0-2426ae93","usage":{"prompt_tokens":14,"total_tokens":49,"completion_tokens":35,"prompt_tokens_details":null},"prompt_logprobs":null,"prompt_token_ids":null,"prompt_text":null,"kv_transfer_params":null}[root@ip-172-31-22-41 models]#
```

#### Register service

- Qwen3.6-27B-FP8

```shell
[Unit]
Description=vLLM Qwen3.6-27B-FP8 Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=vllm
WorkingDirectory=/usr/service/vllm-svc

Environment="PATH=/usr/service/vllm-svc/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
Environment="HF_HOME=/mnt/nvme/hf-cache"
Environment="VLLM_CACHE_ROOT=/mnt/nvme/vllm-cache"

# Check NVMe Mount
ExecStartPre=/bin/bash -c 'mountpoint -q /mnt/nvme || (echo "NVMe not mounted" && exit 1)'

# Preparing the Model/Cache Directory
ExecStartPre=/bin/mkdir -p /mnt/nvme/models /mnt/nvme/hf-cache /mnt/nvme/vllm-cache

# EBS → NVMe Synchronization
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

Unlike the previous text models (Qwen3.5 / 3.6), this is an omni model that **accepts video, images, and audio as joint inputs**. It is used for the 6-second video clip understanding benchmark (vision-bench). The installation process is the same as above, but **audio decoder dependencies** and **multimodal serving flags** are added. (For vLLM installation, **reuse the same venv** as in the **vLLM Installation** section above; here, only the audio dependencies are added.)

### Model Download

```shell
> hf download Qwen/Qwen3-Omni-30B-A3B-Instruct \
  --local-dir /stg/models/Qwen3-Omni-30B-A3B-Instruct \
  --max-workers 16
```

### Audio Input Support (Required)

`uv pip install vllm` The default installation does not include an audio decoder, so an `400 "Invalid or unsupported audio file"` error occurs when an audio input request is made (since video-only requests work normally, this symptom can be confusing). You must add the following three items to the venv.

```shell
(vllm-svc) > uv pip install ninja 
(vllm-svc) > which ninja
/usr/service/vllm-svc/.venv/bin/ninja
(vllm-svc) > 
(vllm-svc) > uv pip install soundfile librosa av
```

- `soundfile` (libsndfile bindings) · `librosa` (resampling) · `av` (PyAV, container demux) — All three are required
- **You must restart the service** after installation for the changes to take effect (`sudo systemctl restart vllm_omni_i` )
- You must include `mm_processor_kwargs: {"use_audio_in_video": true}` in the client request body for the audio within the MP4 file to be processed

#### Manual Testing

- Run the test while in the venv shell.

```bash
(vllm-svc) > export VLLM_CACHE_ROOT=/usr/service/cache/vllm-cache
export HF_HOME=/usr/service/cache/cache/hf-cache

PATH="/usr/service/vllm-svc/.venv/bin:$PATH" \
vllm serve /mnt/nvme/models/Qwen3-Omni-30B-A3B-Instruct \
    --served-model-name qwen \
    --port 8000 --host 0.0.0.0 \
    --dtype bfloat16 \
    --max-model-len 16384 \
    --max-num-seqs 8 \
    --gpu-memory-utilization 0.90 \
    --mm-encoder-attn-backend TORCH_SDPA \
    --moe-backend triton \
    --allowed-local-media-path /mnt/nvme/vod \
    --limit-mm-per-prompt '{"image":1,"video":1,"audio":1}' \
    --tensor-parallel-size 1 \
    --trust-remote-code
```

 

### Service Registration

**Note:** To use audio input, `--limit-mm-per-prompt` must include `audio`, and the audio dependencies listed above must be installed in the venv.

```shell
[Unit]
Description=vLLM Qwen3-Omni-30B-A3B-Instruct Service
After=network-online.target nvme-prep.service
Wants=network-online.target
Requires=nvme-prep.service

[Service]
Type=simple
User=vllm
WorkingDirectory=/usr/service/vllm-svc

Environment="PATH=/usr/service/vllm-svc/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="HOME=/root"
Environment="HF_HOME=/usr/service/cache/hf-cache"
Environment="VLLM_CACHE_ROOT=/usr/service/cache/vllm-cache"
Environment="FLASHINFER_WORKSPACE_BASE=/usr/service/cache"

# Check the NVMe directory and copy the model from S3 to NVMe
ExecStartPre=/bin/bash -c 'mountpoint -q /mnt/nvme || (echo "NVMe not mounted" && exit 1)'
ExecStartPre=/bin/bash /usr/service/start_server/s3_sync_omni.sh

ExecStart=/usr/service/vllm-svc/.venv/bin/vllm serve /mnt/nvme/models/Qwen3-Omni-30B-A3B-Instruct \
    --served-model-name qwen \
    --port 8000 \
    --host 0.0.0.0 \
    --dtype bfloat16 \
    --max-model-len 16384 \
    --max-num-seqs 8 \
    --gpu-memory-utilization 0.82 \
    --mm-encoder-attn-backend TORCH_SDPA \
    --moe-backend triton \
    --allowed-local-media-path /mnt/nvme/vod \
    --limit-mm-per-prompt "{\"image\":1,\"video\":1,\"audio\":1}" \
    --tensor-parallel-size 1 \
    --trust-remote-code

ExecStartPost=/bin/bash /usr/service/start_server/vllm_warmup.sh

StandardOutput=append:/usr/service/logs/vllm/qwen_omni.log
StandardError=append:/usr/service/logs/vllm/qwen_omni.log
TimeoutStartSec=1800
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

