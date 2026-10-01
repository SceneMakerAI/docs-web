---
title: "AWS g7e.24xlarge Initial Setup"
sidebar_position: 4
slug: "4"
last_update:
  date: 2026-09-15
---

## **G7e.24xlarge Local NVMe RAID 0 Configuration and Model Serving Environment Installation Guide**

> **Purpose of this Document**: This installation manual outlines the procedure for configuring a vLLM serving environment by mounting the local NVMe Instance Store (3.8 TB × 2) in a RAID 0 array upon booting a G7e.24xlarge instance and storing model and VOD data on it.

---

### **1. Background**

- In addition to the EBS root volume (`nvme0n1`, 500GB), the G7e.24xlarge instance provides two physically separate local NVMe SSDs (`nvme1n1` and `nvme2n1`, 3.5TB each) as instance storage.
- If the two disks are used separately, I/O for model loading and VOD streaming will be concentrated on one side, causing a bottleneck; therefore, they are **striped using RAID 0** and used as a single logical volume (`/mnt/nvme`).
- Data in Instance Store is **lost upon stop or terminate** (but is retained after a reboot). Therefore, the following procedure must be automatically executed at every boot: RAID configuration → formatting → mounting → model synchronization.

---

### **2. Prerequisites**

- Target instance: `g7e.24xlarge`  (Verify that it has two NVMe Instance Stores installed)
- Ability to log in with root privileges
- Access permissions to the S3 bucket where the model and data are stored (IAM role or credentials)
- Verify that `mdadm` and `xfsprogs` (or the file system tool to be used) can be installed

### 3. Installation

```bash
> dnf install -y mdadm
...
Installed:
  mdadm-4.2-3.amzn2023.0.5.x86_64
  
Complete!
```

---

### **3. Installation Procedure**

#### **3-1. Disk Verification**

```bash
> lsblk -d -o NAME,MODEL,SIZE
NAME    MODEL                             SIZE
nvme0n1 Amazon Elastic Block Store        500G
nvme1n1 Amazon EC2 NVMe Instance Storage  3.5T
nvme2n1 Amazon EC2 NVMe Instance Storage  3.5T
```

- `nvme0n1`: EBS root volume (500 GB)
- `nvme1n1`, `nvme2n1`: Local NVMe Instance Store (3.5 TB each) — RAID 0 target

 #### **3-2. Configuring RAID 0**

```bash
> mdadm --create /dev/md0 --level=0 --raid-devices=2 /dev/nvme1n1 /dev/nvme2n1
mdadm: Defaulting to version 1.2 metadata
mdadm: array /dev/md0 started.


```

- Verify configuration 

```bash
> mdadm --detail /dev/md0
.....
    Number   Major   Minor   RaidDevice State
       0     259        4        0      active sync   /dev/nvme1n1
       1     259        5        1      active sync   /dev/nvme2n1
```

#### **3-3. Formatting and Mounting**

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

- Verify mount: Confirm that approximately 7.0 TB of space is available

```bash
> df -h /mnt/nvme
Filesystem      Size  Used Avail Use% Mounted on
/dev/md0        7.0T   50G  6.9T   1% /mnt/nvme
```

#### **3-4. Boot Automation (systemd)**

- Create an automation script

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
        # Since the kernel may have already automatically mounted the device as md127 or similar upon reboot, scan first
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

- Register with systemd

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

### **4. Validation Checklist**

- [ ] Verify that `md0` is correctly detected in `lsblk`
- [ ] Verify that the capacity is approximately 7.6 TB in `/mnt/nvme`

 

---

### **5. Precautions**

- **When the instance is stopped or terminated**, all data in `/mnt/nvme` will be **permanently lost**. Be sure to back up important artifacts (such as checkpoints and logs) separately to permanent storage, such as S3.
- With RAID 0, the entire volume is corrupted if even a single disk fails. Since instance storage is designed to be rebuilt in the event of a failure, do not store data that requires permanent preservation.
- Although data is preserved during a reboot, existing data may be lost if the systemd unit re-runs `mkfs` at every boot. Therefore, you must include **logic to first check whether the volume is already mounted** in `nvme_prep.sh`.

 

---

### 6. Next Steps

- Test model and data downloads

---

