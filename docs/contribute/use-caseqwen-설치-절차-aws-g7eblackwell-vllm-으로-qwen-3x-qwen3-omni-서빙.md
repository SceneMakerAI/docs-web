---
id: use-caseqwen-설치-절차-aws-g7eblackwell-vllm-으로-qwen-3x-qwen3-omni-서빙
title: "[Use Case][Qwen] 설치 절차 — AWS g7e(Blackwell) + vLLM 으로 Qwen 3.x · Qwen3-Omni 서빙"
sidebar_position: 10
slug: "10"
description: "AWS g7e(Blackwell) + vLLM 으로 Qwen 3.x · Qwen3-Omni 서빙"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

GitHub Discussion: [https://github.com/QwenLM/Qwen3-Omni/discussions/182](https://github.com/QwenLM/Qwen3-Omni/discussions/182)

Qwen 3.x 를 AWS g7e 인스턴스에 올리면서 걸렸던 부분을 적어 둔다. 전체 절차는 [설치 문서](https://doc.scenemaker.solbox.com/docs/install/1) 에 있어서, 여기에는 문서를 따라가다 멈췄던 지점만 모았다.

|  |  |
| --- | --- |
| 인스턴스 | `g7e.4xlarge` (us-west-2) |
| GPU | RTX PRO 6000 Blackwell Server Edition 1장, 96 GB |
| OS | Amazon Linux 2023 (Deep Learning Base AMI with Single CUDA) |
| 런타임 | Python 3.12 (`uv` ), torch 2.11.0+cu130, vLLM 0.22.0 |
| 모델 | Qwen3.5-122B-A10B (GPTQ-Int4), Qwen3.6-27B (FP8), Qwen3-Omni-30B-A3B-Instruct |

#### 리전부터 막힌다

G7e 는 물량이 없어서 서울·도쿄에서는 `InsufficientInstanceCapacity` 가 자주 난다. Spot Placement Score 를 찍어 보면 2026-05-19 기준 미국 3개 리전이 3점, 서울·도쿄가 1점이었다. 응답 지연이 180 ms 쯤 늘지만 LLM 첫 토큰이 원래 수백 ms 라 체감 차이는 크지 않아서 us-west-2 로 갔다.

모델 가중치는 EBS 에, KV 캐시와 임시 파일은 인스턴스 스토어(NVMe)에 둔다. 인스턴스 스토어는 Stop/Start 하면 지워진다.

#### torch 를 먼저 깔고 고정한다

Blackwell 은 `sm_120` 커널이 들어 있는 휠이어야 한다. 설치하고 바로 확인한다.

```bash
uv pip install torch==2.11.0 torchaudio==2.11.0 torchvision==0.26.0 \
    --index-url https://download.pytorch.org/whl/cu130
python -c "import torch; print(torch.cuda.get_arch_list())"
# ['sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120']
```

그다음 vLLM 을 깔 때 torch 버전이 바뀌지 않게 constraint 를 건다. 이걸 안 하면 vLLM 이 torch 를 갈아치울 수 있다.

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

#### Qwen3-Omni 에 오디오를 넣으면 400

`400 "Invalid or unsupported audio file"` 이 나온다. 비디오만 보내면 멀쩡해서 원인이 헷갈리는데, `uv pip install vllm` 기본 설치에 오디오 디코더가 빠져 있어서다.

```bash
uv pip install soundfile librosa av
```

설치 후 서비스를 재기동해야 적용된다. mp4 안의 오디오까지 같이 넣으려면 요청 본문에 `mm_processor_kwargs: {"use_audio_in_video": true}` 가 있어야 한다.

#### AMI 지원 목록에 G7e 가 없다

AMI 설명에는 없지만 드라이버와 CUDA 는 정상 동작했다. 새로 만든다면 G7e 를 명시 지원하는 Deep Learning Base OSS Nvidia Driver GPU AMI 쪽이 낫다.

#### 서빙 명령 (Qwen3-Omni)

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

같은 장비에서 Qwen3-Omni 를 돌리다 `use_audio_in_video` 와 멀티모달 프로세서 캐시가 충돌하는 문제를 만나 vLLM 에 올렸다(당시 0.21.0): https://github.com/vllm-project/vllm/issues/44538

모델: https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Instruct

