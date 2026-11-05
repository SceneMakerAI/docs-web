---
id: vllm-서빙-옵션-정리
title: "vLLM 서빙 옵션 정리"
sidebar_position: 5
slug: "5"
last_update:
  date: 2026-11-05
---

## vLLM 서빙 옵션 정리 — SceneMakerAI 운영 기준

> 💡 **GPU 2장 · 모델 4종 동시 서빙 · 옵션별 선택 이유와 운영 중 겪은 문제 정리**
SceneMakerAI는 영상 · 음성 분석 모델을 모두 자체 GPU에서 vLLM으로 서빙합니다. 이 문서는 vLLM의 기본 옵션이 무슨 뜻인지, 우리 워크로드(긴 방송 영상, 이미지 다수 입력, 여러 모델 동시 기동)에서 각 값을 왜 그렇게 정했는지를 정리합니다.

| 항목 | 내용 |
| --- | --- |
| 기준 vLLM 버전 | v0.22.0 |
| 하드웨어 | NVIDIA RTX PRO 6000 Blackwell 96GB × N |

vLLM은 버전마다 옵션 이름과 기본값이 자주 바뀝니다. 다른 버전에서는 공식 문서와 함께 확인해야 합니다.

---


## 1. 개요

### 1.1 서빙구성

| 항목 | 내용 |
| --- | --- |
| 모델 | Qwen3.8-27B-FP8 (Dense 27B, FP8 가중치, 이미지 입력을 지원하는 VLM, Apache 2.0) |
| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition 96GB × 1 (sm_120) |
| 기준 vLLM 버전 | `[확인 필요]` |

배치 원칙은 다음과 같습니다.

- **가장 무거운 추론 모델(27B)은 GPU 하나를 단독으로 씁니다.** 이미지 수십 장이 들어가는 긴 프롬프트라 KV cache를 최대한 확보해야 하기 때문입니다.
- 모든 서비스는 systemd 유닛으로 기동합니다.

### 1.2 사전 개념

| 개념 | 뜻 |
| --- | --- |
| **KV cache** | 모델이 앞에서 읽은 토큰의 계산 결과(어텐션의 Key · Value)를 저장해 두는 GPU 메모리입니다. 프롬프트가 길거나 동시 요청이 많을수록 많이 필요합니다. vLLM은 기동할 때 모델 가중치를 올리고 남은 메모리를 KV cache로 미리 잡아 둡니다. |
| **배치(batch)** | 여러 요청을 한 번에 묶어 GPU에서 동시에 계산하는 것입니다. 동시 요청이 많을수록 GPU 사용률이 올라갑니다. |
| **prefill / decode** | prefill은 입력 프롬프트 전체를 한 번에 읽는 단계, decode는 답을 한 토큰씩 생성하는 단계입니다. 이미지가 많은 우리 요청은 prefill 비중이 큽니다. |
| **TP (tensor parallel)** | 하나의 모델을 여러 GPU에 나눠 올리는 방식입니다. 모델이 GPU 한 장에 들어가면 쓰지 않는 편이 GPU 간 통신 비용이 없어 유리합니다. |
| **thinking (reasoning)** | 답을 내기 전에 추론 과정을 먼저 생성하는 기능입니다. 품질은 오르지만 출력 토큰과 응답 시간이 크게 늘어납니다. |


---

---

## 2. 파라미터 설명

### 2-1. 기본 설명

| 그룹 | 옵션 | 설명 | 설정 |
| --- | --- | --- | --- |
| 기본 | `--served-model-name` | API 요청의 `model` 필드에 쓰는 이름. 같은 서버의 다른 서비스와 겹치지 않는 고유 이름 사용 | `qwen` |
|  | `--port` | API 포트. 서비스마다 고유 포트 사용 | 8603 |
|  | `--host` | API를 열어 둘 네트워크 주소. `0.0.0.0` 이면 외부에서 접속 가능 | 미지정 |
|  | `--trust-remote-code` | 모델 저장소에 포함된 사용자 정의 코드 실행 허용. 신규 모델이 vLLM에 기본 탑재되기 전에 필요하며, 신뢰하는 모델에만 사용 | 사용 |
|  | `--dtype` | 가중치 · 연산 정밀도. FP8 모델은 설정 파일에서 자동 인식 | 자동 |
|  | `--quantization` | 양자화 방식 지정. FP8 체크포인트는 자동 인식되어 지정 불필요 | 자동 |
|  | `--generation-config` | 요청에 값이 없을 때 쓸 생성 기본값(temperature 등)의 출처. 기본값 `auto` 는 모델의 generation_config.json 권장값을 적용 | 기본값 (auto) |
| 메모리 | `--gpu-memory-utilization` | 이 인스턴스가 쓸 수 있는 GPU 전체 메모리의 비율. 가중치 + 작업 메모리 + KV cache를 모두 포함 (같은 GPU의 인스턴스 합계가 1을 넘지 않아야 함) | 0.85 |
|  | `--max-model-len` | 요청 하나가 쓸 수 있는 최대 토큰 수 (입력 + thinking + 출력) | 131072 |
|  | `--max-num-seqs` | 한 번에 동시에 처리하는 요청 수의 상한 | 24 |
|  | `--tensor-parallel-size` | 모델을 나눠 올릴 GPU 수. 하나의 모델을 GPU 여러 장에 나눠 올릴 때 사용 | 1 |
|  | `--kv-cache-dtype` | KV cache 저장 정밀도. `fp8` 로 바꾸면 메모리를 절반 가까이 절약 | 기본값 |
|  | `--max-num-batched-tokens` | 한 번에 처리하는 토큰 양의 상한. 긴 요청의 prefill이 짧은 요청을 오래 막지 않게 조절 | 기본값 |
| 성능 | `--enable-prefix-caching` | 앞부분이 같은 요청끼리 계산 결과(KV cache)를 재사용. 시스템 프롬프트 · 같은 영상 반복 질의에 적합 | 켬 |
|  | `--enforce-eager` | CUDA graph를 끄고 실행. 그래프 관련 오류 우회용이며 속도는 느려짐 | 미사용 |
|  | `--speculative-config` | 추측 디코딩 설정. 모델에 포함된 MTP 가중치로 생성 속도 향상 가능 | 미사용 |
| 멀티모달 | `--limit-mm-per-prompt` | 요청 하나에 넣을 수 있는 이미지 · 영상 · 오디오 개수 상한. 넘으면 요청 거부 | `{"image": 30}` |
|  | `--allowed-local-media-path` | 요청에서 `file://` 경로로 읽을 수 있는 로컬 디렉터리. 이 밖의 경로는 읽을 수 없음 | `/mnt/nvme/vod` |
| 추론 | `--reasoning-parser` | 모델 출력에서 thinking 부분을 분리해 응답의 별도 필드(`reasoning_content` )로 돌려줌 | `qwen3` |
|  | `--default-chat-template-kwargs` | 요청에서 지정하지 않았을 때 쓸 chat template 기본값. 미지정 시 Qwen3.8은 thinking 강도 최대(`xhigh` )로 동작 | 미지정 |
| 환경 변수 | `CUDA_DEVICE_ORDER` | GPU 번호 매기는 기준. `PCI_BUS_ID` 여야 `nvidia-smi` 번호와 일치 | `PCI_BUS_ID` |
|  | `CUDA_VISIBLE_DEVICES` | 이 서비스가 볼 GPU 번호 | `[확인 필요]` |
|  | `HF_HOME` | Hugging Face 캐시 위치 | NVMe 경로 |
|  | `VLLM_CACHE_ROOT` | vLLM 컴파일 캐시 위치. 재기동 시간 단축 | NVMe 경로 |

### 2-2. 요청 파라미터

| 그룹 | 옵션 | 설명 | 예제 |
| --- | --- | --- | --- |
| 요청 파라미터 | `max_tokens` | 출력 토큰 상한. 크게 잡으면 동시 처리 여유가 줄어듦 | 512\~1024 |
|  | `temperature` | 출력의 무작위성. 낮을수록 같은 입력에 같은 답 | 0.1 |
|  | `chat_template_kwargs.enable_thinking` | thinking 켜기 / 끄기 | on/off |
|  | `chat_template_kwargs.reasoning_effort` | thinking 강도. Qwen3.8은 `xhigh` · `medium` · `low` 만 지원 (`high` 는 오류) | low |


### 2-2. 사용 예제

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

## 3. Systemd 설정

### 3-1 항목 설명

| 그룹 | 항목 | 설명 | 설정 |
| --- | --- | --- | --- |
| [Unit] | `Description` | 서비스 설명. `systemctl status` 에 표시됨 | vLLM Qwen3.x-27B-FP8 Service (GPU3) |
|  | `After` | 이 서비스보다 먼저 기동돼야 하는 대상. 순서만 정하고 실패해도 막지 않음 | 네트워크, NVMe 준비, 임베딩 서비스 |
|  | `Wants` | 함께 기동을 시도할 대상. 실패해도 이 서비스는 기동 | 네트워크 |
|  | `Requires` | 반드시 성공해야 하는 대상. 실패하면 이 서비스도 기동하지 않음 | `nvme-prep.service` (NVMe 마운트) |
| [Service] 실행 | `Type=simple` | `ExecStart` 프로세스가 뜨면 바로 기동된 것으로 간주 | simple |
|  | `User` | 서비스를 실행할 계정 | root |
|  | `WorkingDirectory` | 실행 위치. vLLM 가상환경이 있는 디렉터리 | `/usr/service/vllm-svc` |
| [Service] 환경 변수 | `PATH` | 가상환경의 `vllm` 을 먼저 찾도록 `.venv/bin` 을 맨 앞에 둠 | `.venv/bin` 우선 |
|  | `HOME` | 일부 라이브러리가 설정 · 캐시 위치를 찾을 때 사용 | `/root` |
|  | `HF_HOME` | Hugging Face 캐시 위치 | `/usr/service/cache/hf-cache` |
|  | `VLLM_CACHE_ROOT` | vLLM 컴파일 캐시 위치. GPU별로 분리해 인스턴스끼리 충돌하지 않게 함 | `.../vllm-cache/gpu3` |
|  | `TRITON_CACHE_DIR` | Triton 커널 컴파일 캐시 위치. 모델 · GPU별로 분리 | `.../triton-cache/qwen27/gpu3` |
|  | `CUDA_VISIBLE_DEVICES` | 이 서비스가 볼 GPU 번호. 서비스 안에서는 이 GPU가 0번으로 보임 | 3 |
|  | `CUDA_DEVICE_ORDER` | GPU 번호 매기는 기준. `PCI_BUS_ID` 여야 `nvidia-smi` 번호와 일치 | 미설정 (추가 권장) |
| [Service] 기동 | `ExecStartPre` | 본 실행 전 점검. NVMe가 마운트되지 않았으면 기동 중단 | NVMe 마운트 확인 |
|  | `ExecStart` | vLLM 서버 실행 명령. 옵션은 위 옵션 표 참고 | `vllm serve ...` |
|  | `ExecStartPost` | 기동 직후 실행. 첫 요청을 미리 보내 컴파일 · 캐시를 데워 두어 실제 첫 요청이 느려지지 않게 함 | `vllm_warmup.sh qwen 8603` |
|  | `TimeoutStartSec` | 기동 완료까지 기다리는 최대 시간. 모델 로딩 · 컴파일 시간을 고려해 길게 잡음 | 1800초 (30분) |
| [Service] 종료 · 재시작 | `TimeoutStopSec` | 종료 신호 후 강제 종료까지 기다리는 시간 | 60초 |
|  | `KillMode=mixed` | 메인 프로세스에 먼저 종료 신호를 보내고, 남은 하위 프로세스(엔진 등)는 강제 종료. GPU를 점유한 좀비 프로세스 방지 | mixed |
|  | `Restart` | 비정상 종료 시 자동 재시작 | on-failure |
|  | `RestartSec` | 재시작 전 대기 시간 | 10초 |
| [Service] 로그 · 자원 | `StandardOutput` · `StandardError` | 표준 출력 · 오류를 파일에 이어 쓰기 | `.../logs/vllm/qwen_27_gpu3.log` |
|  | `LimitNOFILE` | 열 수 있는 파일 · 소켓 수 상한. 동시 접속이 많을 때 필요 | 1048576 |
|  | `LimitNPROC` | 만들 수 있는 프로세스 · 스레드 수 상한 | 1048576 |
| [Install] | `WantedBy` | `systemctl enable` 시 부팅 때 자동 기동되도록 연결할 대상 | multi-user.target |


### 3-2 예제

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


## 4. 운영 중 겪은 문제와 해결

**GPU 사용률이 거의 0%로 떨어졌습니다 —** `max_tokens` **과다**  
요청에 `max_tokens` 를 65536으로 주었더니 GPU가 거의 일하지 않는 상태가 됐습니다. 출력 상한이 지나치게 커서 요청마다 필요한 KV cache가 크게 잡혔고, 그 결과 동시에 처리할 수 있는 요청 수가 줄어든 것으로 판단했습니다. 실제 출력 길이에 맞춰 512\~1024로 줄이자 정상화됐습니다.

**응답이 끝나지 않을 만큼 길어졌습니다 — thinking 기본값**  
이미지가 많은 긴 프롬프트에서 thinking이 `max-model-len` (131072)을 전부 써 버리고 응답 시간이 과도하게 길어졌습니다. 서버에 chat template 기본값이 없어서, Qwen3.8의 기본 thinking 강도인 `xhigh` 로 동작했기 때문입니다. 서버 기본값(`--default-chat-template-kwargs` ) 또는 요청별 `reasoning_effort` · `enable_thinking` 으로 제어해야 합니다.

**지정한 GPU와 다른 GPU에 모델이 올라갔습니다 — GPU 번호 순서** `CUDA_DEVICE_ORDER` 를 지정하지 않아 프로그램이 보는 GPU 번호와 `nvidia-smi` 의 번호가 달랐습니다. `PCI_BUS_ID` 로 고정해 해결했습니다.

**GPU 메모리가 어디서 쓰이는지 보이지 않았습니다 — 서비스 내부 엔진**  
STT 서비스가 자체 프로세스(약 6GB) 외에 내부에서 vLLM 엔진을 하나 더 띄워 GPU 0에서 약 16GB를 쓰고 있었습니다. 이 엔진은 프로세스 이름이 `VLLM::EngineCore` 로 바뀌어 `ps -ef | grep vllm` 으로는 잡히지 않습니다. GPU 메모리 배분을 계산할 때 이 몫을 함께 넣어야 합니다.

**같은 모델 이름이 충돌했습니다 —** `--served-model-name`  
여러 서비스가 같은 서빙 이름을 써서 호출이 섞였습니다. 서비스마다 고유 이름을 쓰도록 정리했습니다.

**서비스가 부팅 순서 때문에 실패했습니다 — systemd 파일 이름**  
의존성에 적은 유닛 이름(언더스코어)과 실제 파일 이름(하이픈)이 달라 순서가 적용되지 않았습니다. 이름을 맞춰 해결했습니다.

**Qwen3-Omni 배포가 불안정합니다 — vllm-omni (해결 중)**  
Qwen3-Omni는 텍스트를 만드는 단계(thinker) 뒤에 음성을 만드는 단계(talker · code2wav)가 붙어 있습니다. 우리는 텍스트 분석 결과만 필요한데, 배포 설정으로 음성 단계를 끄지 못했습니다. 또 talker 단계에서 CUDA graph 오류가 나면 GPU를 점유한 좀비 프로세스가 남아, 재기동 전에 프로세스를 강제로 정리해야 합니다. 원인을 계속 확인하고 있습니다.

---

---

## 5. 참고

| 자료 | 내용 |
| --- | --- |
| [vLLM 공식 문서](https://docs.vllm.ai/) | 옵션 전체 목록과 버전별 변경 사항 |
| [vLLM GitHub](https://github.com/vllm-project/vllm) | 소스 · Issue · 릴리즈 노트 |
| [Qwen GitHub](https://github.com/QwenLM) | Qwen3 계열 모델의 권장 서빙 설정과 chat template |

---

**관련 문서**

- [Qwen 3.x 설치](https://doc.scenemaker.solbox.com/docs/install/1)
- [오픈소스 기여](https://doc.scenemaker.solbox.com/docs/achievement/3)
- [AWS g7e.24xlarge 초기 세팅](https://doc.scenemaker.solbox.com/docs/install/4)
- [아키텍처](https://doc.scenemaker.solbox.com/docs/architecture)


