---
title: "[Use Case][Qwen] Installation Procedure — Serving Qwen 3.x and Qwen3-Omni on AWS g7e (Blackwell) + vLLM"
sidebar_position: 10
slug: "10"
description: "Serving Qwen 3.x and Qwen3-Omni using AWS g7e (Blackwell) + vLLM"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

GitHub Discussion: [https://github.com/QwenLM/Qwen3-Omni/discussions/182](https://github.com/QwenLM/Qwen3-Omni/discussions/182)

I’m documenting the issues I encountered while deploying Qwen 3.x on an AWS g7e instance. The full procedure is available in the [installation guide](https://doc.scenemaker.solbox.com/docs/install/1), so this post only covers the points where I got stuck while following the guide.

|  |  |
| --- | --- |
| Instance | `g7e.4xlarge` (us-west-2) |
| GPU | 1 RTX PRO 6000 Blackwell Server Edition, 96 GB |
| OS | Amazon Linux 2023 (Deep Learning Base AMI with Single CUDA) |
| Runtime | Python 3.12 (`uv`), torch 2.11.0+cu130, vLLM 0.22.0 |
| Model | Qwen3.5-122B-A10B (GPTQ-Int4), Qwen3.6-27B (FP8), Qwen3-Omni-30B-A3B-Instruct |

#### It’s already blocked at the region level

Since there’s no G7e inventory, `InsufficientInstanceCapacity` errors frequently occur in Seoul and Tokyo. Checking the Spot Placement Score as of May 19, 2026, showed that three U.S. regions scored 3 points, while Seoul and Tokyo scored 1 point. Although response latency increases by about 180 ms, since the first token of an LLM typically takes several hundred ms anyway, the perceived difference isn’t significant, so I went with us-west-2.

Model weights are stored on EBS, while the KV cache and temporary files are stored on Instance Store (NVMe). Data on Instance Store is erased when the instance is stopped or started.

#### Install and lock in `torch` first.

The Blackwell wheel must contain the ``sm_120`` kernel. Install it and verify immediately.

```bash
uv pip install torch==2.11.0 torchaudio==2.11.0 torchvision==0.26.0 \
    --index-url https://download.pytorch.org/whl/cu130
python -c "import torch; print(torch.cuda.get_arch_list())"
# ['sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120']
```

Next, set a constraint to prevent the Torch version from changing when installing vLLM. If you don’t do this, vLLM may overwrite Torch.

```bash
cat > /tmp/torch-constraint.txt <<'TXT'
torch==2.11.0+cu130
torchaudio==2.11.0+cu130
torchvision==0.26.0+cu130
TXT
uv pip install vllm==0.22.0 \
    --constraint /tmp/torch-constraint.txt \
    --extra-index-url https://download.pytorch.org/whl/cu130 \
    --index-strategy unsafe-best-match
```

#### When audio is added to Qwen3-Omni, a `400 "Invalid or unsupported audio file"` error occurs.

Since it works fine when only video is sent, the cause is confusing; however, this is because the default installation of `uv pip install vllm` lacks an audio decoder.

```bash
uv pip install soundfile librosa av
```

You must restart the service after installation for the changes to take effect. To include the audio from the MP4 file, the request body must contain `mm_processor_kwargs: {"use_audio_in_video": true}`.

#### G7e is not listed in the AMI support list

Although not mentioned in the AMI description, the driver and CUDA functioned normally. If creating a new one, it’s better to use the “Deep Learning Base OSS Nvidia Driver GPU AMI,” which explicitly supports G7e.

#### Serving Command (Qwen3-Omni)

```bash
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

While running Qwen3-Omni on the same hardware, I encountered an issue where `use_audio_in_video` conflicted with the multimodal processor cache, so I uploaded it to vLLM (version 0.21.0 at the time): https://github.com/vllm-project/vllm/issues/44538

Model: https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Instruct

