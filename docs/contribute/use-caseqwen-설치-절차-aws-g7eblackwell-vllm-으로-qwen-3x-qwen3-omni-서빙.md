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

GitHub Discussion: [https://github.com/SceneMakerAI/docs-web/discussions/31](https://github.com/SceneMakerAI/docs-web/discussions/31)

월별 계획 6월 항목 "Use Case Report 설치 절차 (Qwen)"에 해당하는 글입니다. 한국 방송 영상 분석용으로 Qwen 3.x 계열을 AWS 에 올리면서 정리한 절차와, 문서에 없어서 막혔던 지점을 공유합니다.

### 환경

| 항목 | 값 |
| --- | --- |
| 인스턴스 | AWS `g7e.4xlarge` (us-west-2) |
| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition × 1, VRAM 96 GB |
| OS | Amazon Linux 2023 (Deep Learning Base AMI with Single CUDA) |
| 런타임 | Python 3.12 (`uv` venv), torch 2.11.0+cu130, vLLM 0.22.0 |
| 모델 | Qwen3.5-122B-A10B (GPTQ-Int4), Qwen3.6-27B (FP8), Qwen3-Omni-30B-A3B-Instruct |

### 절차 요약

1. 리전 선택: G7e 는 공급이 부족해 `InsufficientInstanceCapacity` 가 잦습니다. Spot Placement Score 로 비교해 us-west-2 를 골랐습니다 (2026-05-19 측정: 미국 3개 리전 3점, 서울·도쿄 1점).
2. 스토리지: 모델 가중치는 EBS(gp3 2 TB), KV 캐시·임시 파일은 인스턴스 스토어(NVMe)로 분리했습니다. 인스턴스 스토어는 Stop/Start 때 지워집니다.
3. torch 를 먼저 설치하고 버전을 고정한 뒤 vLLM 을 설치합니다.
4. `vllm serve` 로 수동 확인 후 systemd 서비스로 등록합니다.

### 막혔던 지점

**1. Blackwell GPU 는 `sm_120` 커널이 든 torch 휠이 필요합니다.**

```bash
uv pip install torch==2.11.0 torchaudio==2.11.0 torchvision==0.26.0 \
    --index-url https://download.pytorch.org/whl/cu130
python -c "import torch; print(torch.cuda.get_arch_list())"
# ['sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120']  ← sm_120 이 있어야 함
```

**2. vLLM 설치가 torch 버전을 바꿀 수 있어 constraint 로 고정했습니다.**

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

**3. Qwen3-Omni 에 오디오를 넣으면 `400 "Invalid or unsupported audio file"` 이 납니다.**

`uv pip install vllm` 기본 설치에는 오디오 디코더가 빠져 있습니다. 비디오만 보낸 요청은 정상이라 원인을 찾기 어려웠습니다. 아래를 추가하고 서비스를 재기동하면 해결됩니다.

```bash
uv pip install soundfile librosa av
```

mp4 안의 오디오를 함께 처리하려면 요청 본문에 `mm_processor_kwargs: {"use_audio_in_video": true}` 를 넣어야 합니다.

**4. AMI 설명의 지원 인스턴스 목록에 G7e 가 없습니다.**

실측으로는 드라이버와 CUDA 가 정상 동작했습니다. 새로 만든다면 G7e 를 명시 지원하는 Deep Learning Base OSS Nvidia Driver GPU AMI 를 권합니다.

### Qwen3-Omni 서빙 명령

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

### 증적

- 설치 문서 전문: https://doc.scenemaker.solbox.com/docs/install/1
- 모델: https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Instruct
- 같은 장비에서 Qwen3-Omni 를 서빙하다 발견해 업스트림에 보고한 이슈(당시 vLLM 0.21.0): https://github.com/vllm-project/vllm/issues/44538 (`use_audio_in_video` + 멀티모달 프로세서 캐시)

같은 구성에서 다른 문제를 겪으셨다면 댓글로 알려 주세요.

