---
title: "Summary of vLLM Serving Options"
sidebar_position: 5
slug: "5"
last_update:
  date: 2026-11-05
---

## Summary of vLLM Serving Options — SceneMakerAI Operational Guidelines

> 💡 **2 GPUs · Simultaneous Serving of 4 Models · Summary of Reasons for Option Selection and Issues Encountered During Operation**
SceneMakerAI serves both video and audio analysis models as vLLMs on its own GPUs. This document explains what the default vLLM options mean and why we set each value the way we did for our specific workload (long broadcast videos, multiple image inputs, and simultaneous operation of multiple models).

| Item | Description |
| --- | --- |
| Reference vLLM Version | v0.22.0 |
| Hardware | NVIDIA RTX PRO 6000 Blackwell 96GB × N |

Option names and default values for vLLM change frequently with each version. For other versions, please refer to the official documentation.

---

## 1. Overview

### 1.1 Serving Configuration

| Item | Description |
| --- | --- |
| Model | Qwen3.8-27B-FP8 (Dense 27B, FP8 weights, VLM supporting image input, Apache 2.0) |
| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition 96GB × 1 (sm_120) |
| Reference vLLM Version | `[확인 필요]` |

The deployment principles are as follows:

- **The heaviest inference model (27B) uses a single GPU exclusively.** This is because the long prompts, which contain dozens of images, require maximizing the KV cache.
- All services are started as systemd units.

### 1.2 Preliminary Concepts

| Concept | Meaning |
| --- | --- |
| **KV cache** | GPU memory where the model stores the calculation results (attention keys and values) of tokens read earlier. The longer the prompt or the more concurrent requests there are, the more KV cache is required. When vLLM starts up, it loads the model weights and pre-allocates the remaining memory for the KV cache. |
| **Batch** | Grouping multiple requests together to be processed simultaneously on the GPU. The more concurrent requests there are, the higher the GPU utilization. |
| **prefill / decode** | Prefill is the stage where the entire input prompt is read at once; decode is the stage where the response is generated one token at a time. Since our requests contain many images, the prefill stage accounts for a large portion of the process. |
| **TP (tensor parallel)** | This is a method of distributing a single model across multiple GPUs. If a model fits on a single GPU, it is more efficient not to split it, as this eliminates communication overhead between GPUs. |
| **Thinking (Reasoning)** | This feature generates the reasoning process before producing the answer. While it improves quality, it significantly increases the number of output tokens and response time. |

---

---

## 2. Parameter Descriptions

### 2-1. Basic Description

| Group | Option | Description | Setting |
| --- | --- | --- | --- |
| Default | `--served-model-name` | Name used in the `model` field of API requests. Use a unique name that does not conflict with other services on the same server | `qwen` |
|  | `--port` | API port. Use a unique port for each service | 8603 |
|  | `--host` | Network address to which the API is exposed. Set to `0.0.0.0` to allow external access | Not Specified |
|  | `--trust-remote-code` | Allow execution of custom code included in the model repository. Required before new models are pre-installed in vLLM; use only for trusted models | Enabled |
|  | `--dtype` | Weight and computational precision. FP8 models are automatically detected in the configuration file | Auto |
|  | `--quantization` | Specifies the quantization method. FP8 checkpoints are automatically detected, so no specification is required | Auto |
|  | `--generation-config` | Source of default generation values (e.g., temperature) to use when no value is provided in the request. The default value `auto` applies the recommended value from the model’s `generation_config.json` | Default (auto) |
| Memory | `--gpu-memory-utilization` | Percentage of total GPU memory available to this instance. Includes weights + working memory + KV cache (the sum of all instances on the same GPU must not exceed 1) | 0.85 |
|  | `--max-model-len` | Maximum number of tokens a single request can use (input + thinking + output) | 131072 |
|  | `--max-num-seqs` | Upper limit on the number of requests processed simultaneously | 24 |
|  | `--tensor-parallel-size` | Number of GPUs to distribute the model across. Used when distributing a single model across multiple GPUs | 1 |
|  | `--kv-cache-dtype` | KV cache storage precision. Changing this to `fp8` saves nearly half the memory | Default |
|  | `--max-num-batched-tokens` | Upper limit on the number of tokens processed at a time. Adjusts to prevent prefilling for long requests from blocking short requests for too long | Default |
| Performance | `--enable-prefix-caching` | Reuses computation results (KV cache) for requests with identical prefixes. Suitable for system prompts and repeated queries on the same image | On |
|  | `--enforce-eager` | Runs with CUDA graph disabled. Bypasses graph-related errors but results in slower performance | Not used |
|  | `--speculative-config` | Speculative decoding setting. Can improve generation speed using MTP weights included in the model | Not used |
| Multimodal | `--limit-mm-per-prompt` | Upper limit on the number of images, videos, and audio files that can be included in a single request. Requests exceeding this limit will be rejected | `{"image": 30}` |
|  | `--allowed-local-media-path` | Local directory accessible via the `file://` path in the request. Paths outside this directory cannot be read | `/mnt/nvme/vod` |
| Inference | `--reasoning-parser` | Separates the “thinking” portion from the model’s output and returns it as a separate field (`reasoning_content`) in the response | `qwen3` |
|  | `--default-chat-template-kwargs` | Default chat template to use when not specified in the request. If unspecified, Qwen3.8 operates with maximum “thinking” intensity (`xhigh`) | Unspecified |
| Environment Variable | `CUDA_DEVICE_ORDER` | GPU numbering scheme. Must be `PCI_BUS_ID` to match the `nvidia-smi` number | `PCI_BUS_ID` |
|  | `CUDA_VISIBLE_DEVICES` | GPU number visible to this service | `[확인 필요]` |
|  | `HF_HOME` | Hugging Face cache location | NVMe path |
|  | `VLLM_CACHE_ROOT` | vLLM compilation cache location. Reduces restart time | NVMe path |

### 2-2. Request Parameters

| Group | Option | Description | Example |
| --- | --- | --- | --- |
| Request Parameters | `max_tokens` | Upper limit on output tokens. Setting this value too high reduces concurrency capacity | 512–1024 |
|  | `temperature` | Output randomness. Lower values yield the same answer for the same input | 0.1 |
|  | `chat_template_kwargs.enable_thinking` | Enable/ off | on/off |
|  | `chat_template_kwargs.reasoning_effort` | “thinking” intensity. Qwen3.8 supports only `xhigh`, `medium`, and `low` (`high` results in an error) | low |

### 2-2. Usage Examples

```bash
ExecStart=/usr/service/vllm-svc/.venv/bin/vllm serve \
    /mnt/nvme/models/Qwen3.8-27B-FP8 \
    --served-model-name qwen \
    --port 8603 \
    --tensor-parallel-size 1 \
    --max-model-len 131072 \
    --max-num-seqs 24 \
    --gpu-memory-utilization 0.85 \
    --allowed-local-media-path /mnt/nvme/vod \
    --limit-mm-per-prompt '{"image":30}' \
    --enable-prefix-caching \
    --reasoning-parser qwen3 \
    --trust-remote-code
```

---

## 3. Systemd Configuration

### 3-1 Item Descriptions

| Group | Item | Description | Setting |
| --- | --- | --- | --- |
| [Unit] | `Description` | Service description. Displayed in `systemctl status` | vLLM Qwen3.x-27B-FP8 Service (GPU3) |
|  | `After` | Targets that must start before this service. Only specifies the order; failure is allowed | Network, NVMe preparation, Embedding service |
|  | `Wants` | Targets to attempt starting together. This service will start even if they fail | Network |
|  | `Requires` | Entities that must succeed. If they fail, this service will not start | `nvme-prep.service` (NVMe mount) |
| [Service] Execution | `Type=simple` | Considered started as soon as the `ExecStart` process appears | simple |
|  | `User` | Account to run the service | root |
|  | `WorkingDirectory` | Execution location. Directory containing the vLLM virtual environment | `/usr/service/vllm-svc` |
| [Service] Environment Variables | `PATH` | Place `.venv/bin` at the beginning so that the virtual environment’s `vllm` is searched for first | `.venv/bin` Priority |
|  | `HOME` | Used by some libraries when locating configuration and cache locations | `/root` |
|  | `HF_HOME` | Hugging Face cache location | `/usr/service/cache/hf-cache` |
|  | `VLLM_CACHE_ROOT` | vLLM compilation cache location. Separated by GPU to prevent conflicts between instances | `.../vllm-cache/gpu3` |
|  | `TRITON_CACHE_DIR` | Triton kernel compilation cache location. Separated by model and GPU | `.../triton-cache/qwen27/gpu3` |
|  | `CUDA_VISIBLE_DEVICES` | The GPU number visible to this service. Within the service, this GPU appears as number 0 | 3 |
|  | `CUDA_DEVICE_ORDER` | GPU numbering scheme. Must be `PCI_BUS_ID` to match the `nvidia-smi` number | Not set (recommended to add) |
| [Service] Startup | `ExecStartPre` | Pre-execution check. Abort startup if NVMe is not mounted | Check NVMe mount |
|  | `ExecStart` | Command to run the vLLM server. Refer to the options table above for options | `vllm serve ...` |
|  | `ExecStartPost` | Executed immediately after startup. Sends the first request in advance to warm up the compiler and cache, preventing the actual first request from being slowed down | `vllm_warmup.sh qwen 8603` |
|  | `TimeoutStartSec` | Maximum time to wait for startup to complete. Set to a long duration to account for model loading and compilation times | 1800 seconds (30 minutes) |
| [Service] Shutdown and Restart | `TimeoutStopSec` | Time to wait after a shutdown signal is sent before forcing termination | 60 seconds |
|  | `KillMode=mixed` | First sends a termination signal to the main process; remaining child processes (such as the engine) are forcibly terminated. Prevents zombie processes from occupying the GPU | mixed |
|  | `Restart` | Automatic restart upon abnormal termination | on-failure |
|  | `RestartSec` | Wait time before restart | 10 seconds |
| [Service] Logs · Resources | `StandardOutput` · `StandardError` | Append standard output and errors to a file | `.../logs/vllm/qwen_27_gpu3.log` |
|  | `LimitNOFILE` | Maximum number of files and sockets that can be opened. Required when there are many concurrent connections | 1048576 |
|  | `LimitNPROC` | Maximum number of processes and threads that can be created | 1048576 |
| [Install] | `WantedBy` | Target to link to so that `systemctl enable` starts automatically at boot | multi-user.target |

### 3-2 Example

```bash
[Unit]
Description=vLLM Qwen3.x-27B-FP8 Service (GPU3)
After=network-online.target nvme-prep.service vllm-qwen-embed.service
Wants=network-online.target
Requires=nvme-prep.service

[Service]
Type=simple
User=root
WorkingDirectory=/usr/service/vllm-svc

Environment="PATH=/usr/service/vllm-svc/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="HOME=/root"
Environment="HF_HOME=/usr/service/cache/hf-cache"
Environment="VLLM_CACHE_ROOT=/usr/service/cache/vllm-cache/gpu3"
Environment=TRITON_CACHE_DIR=/usr/service/cache/triton-cache/qwen27/gpu3
Environment=CUDA_VISIBLE_DEVICES=3

ExecStartPre=/bin/bash -c 'mountpoint -q /mnt/nvme || (echo "NVMe not mounted" && exit 1)'

ExecStart=/usr/service/vllm-svc/.venv/bin/vllm serve \
    /mnt/nvme/models/Qwen3.8-27B-FP8 \
    --served-model-name qwen \
    --port 8603 \
    --tensor-parallel-size 1 \
    --max-model-len 131072 \
    --max-num-seqs 24 \
    --gpu-memory-utilization 0.85 \
    --allowed-local-media-path /mnt/nvme/vod \
    --limit-mm-per-prompt '{"image":30}' \
    --enable-prefix-caching \
    --reasoning-parser qwen3 \
    --trust-remote-code

#    --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}' \
StandardOutput=append:/usr/service/logs/vllm/qwen_27_gpu3.log
StandardError=append:/usr/service/logs/vllm/qwen_27_gpu3.log
TimeoutStartSec=1800
TimeoutStopSec=60
Restart=on-failure
RestartSec=10
KillMode=mixed
LimitNOFILE=1048576
LimitNPROC=1048576

ExecStartPost=/bin/bash /usr/service/start_server/vllm_warmup.sh qwen 8603


[Install]
WantedBy=multi-user.target

```

---

## 4. Issues Encountered During Operation and Their Resolutions

**GPU utilization dropped to nearly 0% —** `max_tokens` **Excessive**  
When I set `max_tokens` to 65536 for requests, the GPU became virtually idle. We determined that the output limit was set too high, causing the KV cache required for each request to be allocated excessively large, which in turn reduced the number of requests that could be processed simultaneously. The issue was resolved by reducing the limit to 512–1024 to match the actual output length.

**The response became so long that it never finished — default “thinking” value**  
In a long prompt containing many images, “thinking” used up all of `max-model-len` (131072), causing the response time to become excessively long. This occurred because the server lacked a default `chat` template setting, causing it to operate at Qwen 3.8’s default `thinking` intensity of `xhigh`. This should be controlled using the server default (`--default-chat-template-kwargs`) or per-request settings `reasoning_effort` and `enable_thinking`.

**The model was deployed to a different GPU than the one specified — GPU number sequence** Since `CUDA_DEVICE_ORDER` was not specified, the GPU number visible to the program differed from the number in `nvidia-smi`. This was resolved by fixing it to `PCI_BUS_ID`.

**Could not see where GPU memory was being used — Internal service engine**  
In addition to its own process (approximately 6 GB), the STT service was running another vLLM engine internally, which was using approximately 16 GB on GPU 0. Since this engine’s process name was changed to `VLLM::EngineCore`, it was not detected as `ps -ef | grep vllm`. This portion must be included when calculating GPU memory allocation.

**Conflict with the same model name —** `--served-model-name`  
Calls were mixed up because multiple services were using the same serving name. We reorganized them so that each service uses a unique name.

**Service failed due to boot order — systemd filename**  
The unit name (underscore) listed in the dependencies differed from the actual filename (hyphen), so the order was not applied correctly. We resolved this by aligning the names.

**Qwen3-Omni deployment is unstable — vllm-omni (being resolved)**  
Qwen3-Omni consists of a text-generation stage (thinker) followed by a speech-generation stage (talker · code2wav). We only need the text analysis results, but we were unable to disable the speech generation stage via the deployment settings. Additionally, if a CUDA graph error occurs during the talker stage, a zombie process that occupies the GPU remains, requiring us to force-terminate the process before restarting. We are continuing to investigate the cause.

---

---

## 5. References

| Resource | Content |
| --- | --- |
| [vLLM Official Documentation](https://docs.vllm.ai/) | Complete list of options and version-specific changes |
| [vLLM GitHub](https://github.com/vllm-project/vllm) | Source · Issues · Release Notes |
| [Qwen GitHub](https://github.com/QwenLM) | Recommended serving configurations and chat templates for Qwen 3 series models |

---

**Related Documentation**

- [Installing Qwen 3.x](https://doc.scenemaker.solbox.com/docs/install/1)
- [Contributing to Open Source](https://doc.scenemaker.solbox.com/docs/achievement/3)
- [AWS g7e.24xlarge Initial Setup](https://doc.scenemaker.solbox.com/docs/install/4)
- [Architecture](https://doc.scenemaker.solbox.com/docs/architecture)

