---
id: collect-env-가-uv-환경에서-다른-환경의-패키지를-읽거나-죽는-문제-수정
title: "collect_env 가 uv 환경에서 다른 환경의 패키지를 읽거나 죽는 문제 수정"
sidebar_position: 18
slug: "18"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

[https://github.com/vllm-project/vllm/pull/60191](https://github.com/vllm-project/vllm/pull/60191)

#### 목적

uv 로 만든 가상환경에는 `pip` 이 없어서, `collect_env` 는 `uv pip list --format=freeze` 로 대신 패키지 목록을 읽는다. 그런데 이 호출이 어느 환경을 볼지 지정하지 않아 uv 가 작업 디렉토리 기준으로 환경을 고른다. 그 결과 두 가지가 잘못된다.

1. **엉뚱한 패키지가 보고된다.** 가상환경을 활성화하지 않고 실행하면(`.venv/bin/python -m vllm.collect_env` , systemd 등) 다른 환경의 목록이 나온다. 실제 가상환경은 `torch==2.14.1+cpu` / `numpy==2.5.3` 인데 시스템 환경의 `numpy==2.2.6` 과 `nvidia-*` 가 출력됐다. 오류 없이 조용히 틀리고, 그대로 버그 리포트에 붙는다.
2. **명령이 실패하면 죽는다.** `uv` 가 `PATH` 에 없거나 환경을 못 찾으면 `AttributeError: 'NoneType' object has no attribute 'splitlines'` 로 종료된다. vllm#44538 을 올릴 때 환경 정보를 수동으로 적어야 했던 원인이다.

이 PR 은 `--python sys.executable` 을 넘겨 스크립트를 실행 중인 인터프리터의 패키지를 읽게 하고, 명령이 실패하면 죽는 대신 기존 관례대로 `[pip3] Could not collect` 를 출력하게 한다. uv 대체 경로를 추가한 #13888 / #15792 의 후속 수정이다.

**중복이 아닙니다.** 열린 PR 을 `collect_env` , `13888 in:body` 로 검색했다. #48354 는 `get_pkg_version` (리눅스 외 플랫폼), #39817 은 ROCm 표시를 다루고, `get_pip_packages` 를 고치는 PR 은 없다.

#### 변경 파일

- `vllm/collect_env.py`
- `tests/test_collect_env_pip.py` (신규)

#### 테스트 플랜

```bash
pytest tests/test_collect_env_pip.py -v
ruff check vllm/collect_env.py tests/test_collect_env_pip.py
ruff format --check vllm/collect_env.py tests/test_collect_env_pip.py
```

pip 없는 uv 가상환경에서 수동 확인:

```bash
# uv 가 PATH 에 없을 때
env PATH=/usr/bin:/bin .venv/bin/python -m vllm.collect_env
# 가상환경을 활성화하지 않고 다른 디렉토리에서
cd /tmp && /path/to/.venv/bin/python -m vllm.collect_env
```

#### 시험 결과

```text
2 passed
ruff: All checks passed! / 2 files left unchanged
```

두 테스트 모두 `main` 에서는 위 `AttributeError` 로 실패한다.

| 상황 | 수정 전 | 수정 후 |

| --- | --- | --- |

| `uv` 가 `PATH` 에 없음 | `AttributeError` 로 종료 | `[pip3] Could not collect` |

| 가상환경 미활성 | 시스템 패키지 (`numpy==2.2.6` , `nvidia-*` ) | 가상환경 패키지 (`numpy==2.5.3` , `torch==2.14.1+cpu` ) |

