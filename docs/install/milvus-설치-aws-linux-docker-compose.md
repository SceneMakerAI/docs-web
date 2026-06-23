---
id: milvus-설치-aws-linux-docker-compose
title: "Milvus 설치 (AWS Linux + Docker Compose)"
sidebar_position: 3
slug: "3"
last_update:
  date: 2026-06-22
---


## 1. 개요

- AWS Linux 설치
- Mulvus Compose 버전 설치
- Attu 설치



---

## 2. Docker 설치

### 2.1 Docker Engine 설치 및 시작

```javascript
# 1. 패키지 시스템 업데이트
> dnf update -y

# 2. 내장된 Docker 패키지 설치
> dnf install -y docker

# 4. Docker 정상 작동 확인 (버전이 출력되면 성공)
> docker --version
Docker version 25.0.14, build 0bab007
>
```



### 2.2 Docker Compose 설치 (플러그인 방식)

Amazon Linux 2023의 기본 저장소에는 `docker-compose` 플러그인이 빠져 있음.

docker-compose 를 별도 설치 한다.

```javascript
# 1. Docker CLI 플러그인 폴더 생성
> mkdir -p /usr/local/lib/docker/cli-plugins

# 2. GitHub 공식 저장소에서 최신 Linux용 Docker Compose 다운로드
> curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" -o /usr/local/lib/docker/cli-plugins/docker-compose

# 3. 실행 권한 부여
> chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# 4. Docker Compose 정상 작동 확인
> docker compose version
Docker Compose version v5.1.4
> 
```



---

## 3. Milvus 설치

### 3.1 Mulvus 설치

```javascript
> mkdir -p /usr/service/milvus-standalone
> cd /usr/service/milvus-standalone
> wget https://github.com/milvus-io/milvus/releases/download/v2.6.18/milvus-standalone-docker-compose.yml -O docker-compose.yml
> sudo docker compose up -d
Creating milvus-etcd  ... done
Creating milvus-minio ... done
Creating milvus-standalone ... done

# 설치 내역 확인
> docker compose ps
WARN[0000] /usr/service/milvus-standalone/docker-compose.yml: the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion 
NAME                IMAGE                                      COMMAND                  SERVICE      CREATED          STATUS                    PORTS
milvus-etcd         quay.io/coreos/etcd:v3.5.25                "etcd -advertise-cli…"   etcd         44 seconds ago   Up 43 seconds (healthy)   2379-2380/tcp
milvus-minio        minio/minio:RELEASE.2024-12-18T13-15-44Z   "/usr/bin/docker-ent…"   minio        44 seconds ago   Up 43 seconds (healthy)   0.0.0.0:9000-9001->9000-9001/tcp, [::]:9000-9001->9000-9001/tcp
milvus-standalone   milvusdb/milvus:v2.6.18                    "/tini -- milvus run…"   standalone   44 seconds ago   Up 42 seconds (healthy)   0.0.0.0:9091->9091/tcp, [::]:9091->9091/tcp, 0.0.0.0:19530->19530/tcp, [::]:19530->19530/tcp

```



### 3.2 Attu 설치

```javascript
> docker run -d -p 8000:3000 --name milvus-attu --restart always zilliz/attu:v2.4.11
>  docker ps
CONTAINER ID   IMAGE                                      COMMAND                  CREATED          STATUS                   PORTS                                                                                      NAMES
ec239dd454e8   zilliz/attu:v2.4.11                        "docker-entrypoint.s…"   43 seconds ago   Up 40 seconds            0.0.0.0:8000->3000/tcp, :::8000->3000/tcp                                                  milvus-attu
99ffb6e7f8ef   milvusdb/milvus:v2.6.18                    "/tini -- milvus run…"   7 minutes ago    Up 7 minutes (healthy)   0.0.0.0:9091->9091/tcp, :::9091->9091/tcp, 0.0.0.0:19530->19530/tcp, :::19530->19530/tcp   milvus-standalone
affc1daa2946   quay.io/coreos/etcd:v3.5.25                "etcd -advertise-cli…"   7 minutes ago    Up 7 minutes (healthy)   2379-2380/tcp                                                                              milvus-etcd
8a3195901674   minio/minio:RELEASE.2024-12-18T13-15-44Z   "/usr/bin/docker-ent…"   7 minutes ago    Up 7 minutes (healthy)   0.0.0.0:9000-9001->9000-9001/tcp, :::9000-9001->9000-9001/tcp                              milvus-minio


```



### 3.3 부팅시 자동 설정

#### Docker 재 시작

```javascript
> systemctl enable docker
```



#### Milvus 재시작

Docker Compose로 묶인 서비스들은 서버가 꺼졌다가 켜졌을 때 자동으로 안 일어나는 경우가 종종 있음.

공식 `docker-compose.yml` 파일 내부의 각 서비스들에 `restart: always` 옵션이 확실하게 들어있는지 확인하고 적용

```javascript
> cd /usr/service/milvus-standalone  # 아까 컴포즈가 있던 폴더 경로
> vi docker-compose.yml
# docker-compose.yml 편집 예시
services:
  etcd:
    container_name: milvus-etcd
    image: quay.io/coreos/etcd:v3.5.25
    restart: always  # 👈 여기에 추가!
    # ... 하단 생략 ...

  minio:
    container_name: milvus-minio
    image: minio/minio:RELEASE.2024-12-18T13-15-44Z
    restart: always  # 👈 여기에 추가!
    # ... 하단 생략 ...

  standalone:
    container_name: milvus-standalone
    image: milvusdb/milvus:v2.6.18
    restart: always  # 👈 여기에 추가!
    # ... 하단 생략 ...
    
```



#### Attu 재시작

```javascript
# 아래 restart always 명령어 확인
> docker run -d -p 8000:3000 --name milvus-attu --restart always zilliz/attu:v2.4.11
```



---

## 4. 설정

### 4.1 Attu 설정

- AWS 방화벽 Open
- 접근 : [http://<HOST_IP>:8000/](http://54.116.216.7:8000/#/connect)
- docker 로 서로 격리된 상태라  127.0.0.1 은 안됨.

![image](/img/install/milvus-설치-aws-linux-docker-compose/img-00.png)



### 4.2 데이터 Backup 디렉토리

```javascript
# 주기적으로 Backup 필요
> /usr/service/milvus-standalone/volumes
```


