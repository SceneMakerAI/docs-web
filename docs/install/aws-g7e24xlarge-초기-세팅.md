---
id: aws-g7e24xlarge-초기-세팅
title: "AWS g7e.24xlarge 초기 세팅"
sidebar_position: 4
slug: "4"
last_update:
  date: 2026-09-15
---

## **G7e.24xlarge 로컬 NVMe RAID 0 구성 및 모델 서빙 환경 설치 가이드**

> **문서 목적** : G7e.24xlarge 인스턴스 부팅 시 로컬 NVMe Instance Store(3.8TB × 2)를 RAID 0으로 묶어 마운트하고, 그 위에 모델/VOD 데이터를 올려 vLLM 서빙 환경을 구성하는 절차를 정리한 설치 매뉴얼입니다.

---

### **1. 배경**

- G7e.24xlarge는 EBS 루트 볼륨(`nvme0n1` , 500GB) 외에 물리적으로 분리된 로컬 NVMe SSD 2개(`nvme1n1` , `nvme2n1` , 각 3.5TB)를 인스턴스 스토어로 제공합니다.
- 두 디스크를 분리해서 쓰면 모델 로딩·VOD 스트리밍 I/O가 한쪽에 쏠려 병목이 발생하므로, **RAID 0으로 스트라이핑** 하여 하나의 논리 볼륨(`/mnt/nvme` )으로 사용합니다.
- 인스턴스 스토어는 **stop/terminate 시 데이터가 소실** 됩니다(reboot은 유지). 따라서 부팅 시마다 RAID 구성 → 포맷 → 마운트 → 모델 동기화 절차가 자동 실행되어야 합니다.

---

### **2. 사전 조건**

- 대상 인스턴스: `g7e.24xlarge`  (NVMe Instance Store 2개 탑재 확인)
- 루트 권한(root) 접속 가능
- 모델/데이터가 저장된 S3 버킷 접근 권한(IAM Role 또는 자격 증명) 확보
- `mdadm` , `xfsprogs` (또는 사용할 파일시스템 도구) 설치 가능 여부 확인


### 3. 설치

```bash
> dnf install -y mdadm
...
Installed:
  mdadm-4.2-3.amzn2023.0.5.x86_64
  
Complete!
```



---

### **3. 설치 절차**

#### **3-1. 디스크 확인**

```bash
> lsblk -d -o NAME,MODEL,SIZE
NAME    MODEL                             SIZE
nvme0n1 Amazon Elastic Block Store        500G
nvme1n1 Amazon EC2 NVMe Instance Storage  3.5T
nvme2n1 Amazon EC2 NVMe Instance Storage  3.5T
```

- `nvme0n1` : EBS 루트 볼륨 (500G)
- `nvme1n1` , `nvme2n1` : 로컬 NVMe Instance Store (각 3.5T) — RAID 0 대상

#### **3-2. RAID 0 구성**

```bash
> mdadm --create /dev/md0 --level=0 --raid-devices=2 /dev/nvme1n1 /dev/nvme2n1
mdadm: Defaulting to version 1.2 metadata
mdadm: array /dev/md0 started.


```

- 구성 확인 

```bash
> mdadm --detail /dev/md0
.....
    Number   Major   Minor   RaidDevice State
       0     259        4        0      active sync   /dev/nvme1n1
       1     259        5        1      active sync   /dev/nvme2n1
```


#### **3-3. 포맷 및 마운트**

```bash
> mkfs.xfs /dev/md0
log stripe unit (524288 bytes) is too large (maximum is 256KiB)
log stripe unit adjusted to 32KiB
meta-data=/dev/md0               isize=512    agcount=96, agsize=19327104 blks
         =                       sectsz=512   attr=2, projid32bit=1
         =                       crc=1        finobt=1, sparse=1, rmapbt=0
         =                       reflink=1    bigtime=1 inobtcount=1 nrext64=0
         =                       exchange=0  
data     =                       bsize=4096   blocks=1855401984, imaxpct=5
         =                       sunit=128    swidth=256 blks
naming   =version 2              bsize=4096   ascii-ci=0, ftype=1, parent=0
log      =internal log           bsize=4096   blocks=521728, version=2
         =                       sectsz=512   sunit=8 blks, lazy-count=1
realtime =none                   extsz=4096   blocks=0, rtextents=0
Discarding blocks...Done.

> mkdir -p /mnt/nvme
> mount /dev/md0 /mnt/nvme
```

- 마운트 확인: 약 7.0 TB 확보되는지 확인

```bash
> df -h /mnt/nvme
Filesystem      Size  Used Avail Use% Mounted on
/dev/md0        7.0T   50G  6.9T   1% /mnt/nvme
```


#### **3-4. 부팅 자동화(systemd)**

- 자동화 스크립트 생성

```bash
> mkdir -p /usr/service/start_server; cd /usr/service/start_server
> vi nvem_prep.sh
#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

MOUNT_POINT=/mnt/nvme

mapfile -t NVME_DEVS < <(lsblk -dno NAME,MODEL | grep -i "Amazon EC2 NVMe Instance Storage" | awk '{print "/dev/"$1}')

if [ "${#NVME_DEVS[@]}" -eq 0 ]; then
    echo "No instance store NVMe found"
    exit 1
fi

mkdir -p "$MOUNT_POINT"

if mountpoint -q "$MOUNT_POINT"; then
    echo "$MOUNT_POINT already mounted, skip"
else
    if [ "${#NVME_DEVS[@]}" -eq 1 ]; then
        TARGET_DEV="${NVME_DEVS[0]}"
    else
        # 재부팅 시 커널이 이미 md127 등으로 자동 조립했을 수 있으므로 먼저 스캔
        mdadm --assemble --scan 2>/dev/null

        TARGET_DEV=$(mdadm --detail --scan 2>/dev/null | awk '{print $2}' | head -n1)

        if [ -z "$TARGET_DEV" ]; then
            echo "Creating RAID0 across: ${NVME_DEVS[*]}"
            mdadm --create /dev/md0 --level=0 --raid-devices="${#NVME_DEVS[@]}" "${NVME_DEVS[@]}" --run
            TARGET_DEV=/dev/md0
        else
            echo "Reusing existing array: $TARGET_DEV"
        fi
    fi

    if ! blkid "$TARGET_DEV" &>/dev/null; then
        echo "Formatting $TARGET_DEV as xfs"
        mkfs -t xfs -f "$TARGET_DEV"
    fi

    mount -o noatime "$TARGET_DEV" "$MOUNT_POINT"
fi

chmod 777 "$MOUNT_POINT"
mkdir -p "$MOUNT_POINT/models" "$MOUNT_POINT/vod"

echo "NVMe prep done"



> chmod 755 nvem_prep.sh
>
```


- systemd 등록

```bash
> cd /etc/systemd/system
> vi nvme-prep.service
[Unit]
Description=NVMe Instance Store Prepare (format + mount)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
TimeoutStartSec=0
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStartPre=/bin/bash -c ': > /usr/service/logs/start_server/nvme_prep.log'
ExecStart=/bin/bash /usr/service/start_server/nvme_prep.sh
# ExecStart=/bin/bash /usr/service/start_server/s3_sync_models.sh
StandardOutput=file:/usr/service/logs/start_server/nvme_prep.log
StandardError=file:/usr/service/logs/start_server/nvme_prep.log

[Install]
WantedBy=multi-user.target
>  
> mkdir -p /usr/service/logs/start_server
> systemctl daemon-reload
> systemctl enable nvme-prep
> systemctl start nvme-prep

```



---

### **4. 검증 체크리스트**

- [ ] `lsblk` 에서 `md0` 가 정상적으로 잡히는지 확인
- [ ] `/mnt/nvme`  용량이 약 7.6TB로 잡히는지 확인

---

### **5. 주의사항**

- **인스턴스 stop/terminate 시** `/mnt/nvme`  **데이터가 전부 소실** 됩니다. 중요 산출물(체크포인트, 로그 등)은 반드시 S3 등 영구 스토리지에 별도 백업하세요.
- RAID 0은 디스크 중 하나라도 장애가 나면 전체 볼륨이 손상됩니다. 인스턴스 스토어 특성상 장애 시 재구성이 전제이므로, 영구 보존이 필요한 데이터는 두지 않습니다.
- reboot(재부팅)은 데이터가 유지되지만, systemd 유닛이 매 부팅 시 `mkfs` 를 다시 실행하면 기존 데이터가 날아갈 수 있으니 **이미 마운트된 상태인지 먼저 체크하는 로직** 을 `nvme_prep.sh` 에 포함해야 합니다.


---

### 6. 이후 작업

- 모델 , 데이터 다운로드 테스트

---


