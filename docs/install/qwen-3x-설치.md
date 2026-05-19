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

신형 GPU 인스턴스(G7e, P5, P6 등)는 공급이 수요를 못 따라잡는 상태 입니다. 리전·시간대에 따라 InsufficientInstanceCapacity 에러로 인스턴스 프로비저닝이 실패하는 일이 자주 발생합니다.

이런 이유로 리전 선택은 단순히 "가까운 리전"이 아니라, 다음 두 축을 함께 따져야 합니다.

G7e 제공 리전 비교 (2026-05-19 측정)

점수 해석

- Capacity 점수(g7e.12xl, 1~10) = AWS Spot Placement Score (1=매우 부족 / 10=매우 여유). On-Demand 가용성과도 강한 상관관계
- G7e 제공 6개 리전 모두 점수가 낮은 편 (신형 GPU 공통 현상) → 그중 점수 3이 현 시점 최선
- 시간대·요일에 따라 점수가 바뀜 → 운영 전 직접 재측정 권장
Spot Placement Score 직접 조회

```bash
aws ec2 get-spot-placement-scores \
  --instance-types g7e.12xlarge \
  --target-capacity 1 \
  --no-single-availability-zone \
  --region-names us-west-2 us-east-1 us-east-2 ap-northeast-1 ap-northeast-2 eu-west-2 \
  --query "sort_by(SpotPlacementScores, &Score) | reverse(@) | [].[Region, Score]" \
  --output table
```

- 필요 권한: ec2:GetSpotPlacementScores
- 비용: 무료, 평가 기간: 향후 1시간
(1) Capacity 측면

- 한·일 리전(서울·도쿄)은 점수 1 → 평일 업무시간 기준 잦은 프로비저닝 실패 예상
- 미국 리전 3곳(us-east-1 / us-east-2 / us-west-2)은 점수 3
- 그중 us-west-2와 us-east-1은 점수 3인 가용영역이 2개 (usw2-az1·az3 / use1-az2·az6) → 한 가용영역의 capacity가 소진되어도 다른 가용영역으로 폴백 가능
(2) 응답시간 측면

- LLM 서빙은 모델 자체의 첫 토큰 생성에 200~500 ms 소요 → 네트워크 +150~200 ms는 실사용자 체감 차이가 거의 없는 수준
- 한국 인접 우선이라면 도쿄가 sweet spot이지만 capacity 제약이 큼
> 결론

---

### 1. 애플리케이션 및 OS 이미지 (Amazon Machine Image)

선택한 AMI

참고: AMI 설명상 지원 인스턴스 목록

```javascript
G4dn, G5, G6, Gr6, G6e, P4d, P4de, P5, P5e, P5en, P6-B200, P6-B300
```

> 공식 목록에 G7e가 없음 . 다만 실측 결과 Blackwell 드라이버·CUDA가 정상 작동 확인. 향후 재생성 시에는 G7e를 명시 지원하는 Deep Learning Base OSS Nvidia Driver GPU AMI (AL2023) 사용 권장.

---

### 2. 인스턴스 유형

선택한 인스턴스 : g7e.4xlarge

- g7e 패밀리 비교 (참고)
4xlarge 선택 근거

- Qwen3-Coder-30B-A3B / Qwen3.6-35B-A3B 등 MoE 30~35B 모델은 bf16에서 ~70GB VRAM → 96GB 1장에 KV 캐시까지 여유
- FP8/FP4 양자화 시 더 큰 모델(80~120B)도 가능
- 우선 1 GPU로 검증 후 확장 필요 시 12xlarge 이상으로 변경
모델별 VRAM 요구량

32k 컨텍스트, 단일 시퀀스 기준. vLLM은 paged KV 캐시를 동적 할당하므로 실제 사용량은 워크로드에 따라 달라집니다.

---

### 3. 스토리지 구성

1) 루트 EBS 볼륨 (영구 스토리지)

용도 : 모델 가중치(영구 보관), Docker 이미지, OS 등

2) 인스턴스 스토어 (임시 스토리지 — g7e.4xlarge 기본 포함)

> 인스턴스 스토어 데이터 영속성

용도 분리 권장

- EBS (/) : 모델 가중치, 영구 데이터 → 절대 잃으면 안 되는 것
- 인스턴스 스토어 (/mnt/nvme ) : KV 캐시, 임시 빌드, swap, 추론 로그 → 잃어도 되는 것
---

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

---

## 모델 설치

현실적으로 A100 이나 H100 장비 대여가 쉽지 않은 상황에서 1장으로 운영 가능한 GPU 에서 돌릴 수 있는 서버에서 아래 2개의 모델을 비교 한다. (비교 문서는 추후 배포)

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

