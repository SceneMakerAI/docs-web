---
id: qwen-3x-설치
title: "Qwen 3.x 설치"
sidebar_position: 1
---

## AWS 서버 셑팅

## EC2 인스턴스 설정

---

### 기본 정보 (요약)

리전 선택 근거

G7e 제공 리전 비교  (2026-05-19 측정)

점수 해석

---

### 1. 애플리케이션 및 OS 이미지(Amazon Machine Image)

### 2. 인스턴스 유형

### 3. 스토리지 구성

## NVME 설정

- NVME 는 Cloud 환경에서는 일반 물리서버와 다르게 아래와 같은 특성이 있음
### 1. NVME Device 확인

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

### 2. 디스크 포멧 및 마운트

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

## 모델 설치

- 기본 패키지 설치
- 모델 다운로드
- vllm 설정
- 모델 설정
## 기본 패키지 설치

```shell
> pip install -U "huggingface_hub[cli]" hf_transfer 
```

```shell
# 다운로드 가속 (멀티스레드)
export HF_XET_HIGH_PERFORMANCE=1

# 저장 위치 - 둘 중 선택
export HF_HOME=/mnt/nvme/hf-cache      # 빠르지만 stop 시 소실
# export HF_HOME=/root/hf-cache        # 또는 EBS (영구)
```

## 모델 다운로드

- 모델을 로컬 디렉토리에 다운로드
```shell
> hf download Qwen/Qwen3.5-122B-A10B-GPTQ-Int4 \
  --local-dir /stg/models/Qwen3.5-122B-A10B-GPTQ-Int4 \
  --max-workers 16  
> ls -al /stg/models
total 16
drwxr-xr-x. 5 root root    93 May 19 08:30 .
drwxr-xr-x. 3 root root    20 May 19 07:56 ..
-rw-r--r--. 1 root root     0 May 19 08:25 .check_for_update_done
drwxr-xr-x. 3 root root 16384 May 19 08:30 Qwen3.5-122B-A10B-GPTQ-Int4
drwxr-xr-x. 3 root root    55 May 19 08:28 hub
drwxr-xr-x. 4 root root    59 May 19 08:28 xet
>   
```

## VLLM 설치

vllm 은 패키지 의존성을 많이 요구하기 때문에 uv 환경에서 격리 하여 패키지 설치를 권장 함

### uv 설치

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

### vllm 전용 프로젝트 생성 및 설치

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

