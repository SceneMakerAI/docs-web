---
id: copy-skip-cache-에서-save-filename-이-무시되어-label-encoder-가-로드되지-않는-문제
title: "COPY_SKIP_CACHE 에서 save_filename 이 무시되어 label encoder 가 로드되지 않는 문제"
sidebar_position: 19
slug: "19"
description: "speechbrain: COPY_SKIP_CACHE 전략에서 fetch() 가 없는 경로를 반환해 VoxLingua107 라벨 인코더가 조용히 비는 문제 보고"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-06
---

## speechbrain: COPY_SKIP_CACHE 전략에서 save_filename 이 무시되어 label encoder 가 조용히 로드되지 않는 문제

링크: https://github.com/speechbrain/speechbrain/issues/3091

### 배경

SceneMakerAI 는 `EncoderClassifier.from_hparams("speechbrain/lang-id-voxlingua107-ecapa")` 로 방송 오디오의 언어 식별을 수행한다. 모델 파일을 HF 캐시 심볼릭 링크가 아니라 `savedir` 에 실제 파일로 두려고 `local_strategy=LocalStrategy.COPY_SKIP_CACHE` 를 쓰면, 모델 로딩은 에러 없이 끝나지만 `classify_batch` 첫 호출에서 `KeyError: 16` 같은 예외가 난다. 라벨 인코더가 비어 있기 때문이다.

- 저장소: speechbrain/speechbrain, 기본 브랜치 `develop` , HEAD `89ead74d`
- 유형: Issue (수정안과 단위 테스트는 로컬 브랜치 `fix/fetch-copy-skip-cache-save-filename` 에 미커밋 상태로 준비)

### 원인

`speechbrain/utils/fetching.py` 의 `fetch()` (417-424행) 는 COPY_SKIP_CACHE 일 때 `hf_hub_download` 에 `local_dir=savedir` , `force_filename=save_filename` 을 넘겨서 "savedir 에 save_filename 이름으로 저장" 을 huggingface_hub 에 맡긴다. 그런데 huggingface_hub 는 그렇게 동작하지 않는다.

- 최신 버전 (0.33.4, 2.1.1 확인): `force_filename` 을 경고와 함께 무시하고 `savedir/filename` 으로 저장한다.
- 구버전 (0.19.4, 0.22.2, 0.23.0 확인): `force_filename` 이 있으면 legacy 캐시 경로로 빠져 `local_dir` 를 무시하고 HF 캐시 디렉토리에 저장한다. `savedir` 는 비어 있다.

`download_file_hf` 는 COPY_SKIP_CACHE 일 때 `hf_hub_download` 의 반환 경로를 버리고, `fetch()` 는 존재 여부를 확인하지 않은 `savedir/save_filename` 을 반환한다.

`Pretrainer.collect_files` 는 항상 `save_filename = 로더블이름 + ".ckpt"` 로 호출하므로, `paths` 의 파일명이 다른 항목 (voxlingua107 의 `label_encoder.txt` ) 이 영향을 받는다. `.ckpt` 가중치는 이름이 같아 정상 로드되고, 라벨 인코더는 `CategoricalEncoder.load_if_possible` 이 없는 파일에 대해 False 만 반환하므로 조용히 건너뛴다.

### 재현 방법

```python
import os, tempfile
from speechbrain.utils.fetching import fetch, LocalStrategy

with tempfile.TemporaryDirectory() as d:
    p = fetch("label_encoder.txt", source="speechbrain/lang-id-voxlingua107-ecapa",
              savedir=d, save_filename="label_encoder.ckpt",
              local_strategy=LocalStrategy.COPY_SKIP_CACHE)
    print(p, p.exists(), sorted(os.listdir(d)))
```

HEAD 결과: 반환 경로는 `label_encoder.ckpt` 인데 `exists` 는 False, 디렉토리에는 `label_encoder.txt` 만 있다.

엔드투엔드 (`repro_e2e.py` ): SYMLINK 전략은 라벨 107개, `text_lab` 정상. COPY_SKIP_CACHE 전략은 라벨 0개, `classify_batch` 에서 `KeyError: 16` .

### 변경 내용 (로컬 수정안, 미제출)

- `fetch()` : `force_filename` 전달 제거.
- `download_file_hf()` : COPY_SKIP_CACHE 에서 `hf_hub_download` 가 돌려준 경로가 `destination` 과 다르면 `shutil.move` 로 옮긴다.
- `tests/unittests/test_fetch.py` : `hf_hub_download` 를 대체한 회귀 테스트 1건 추가.

`local_dir_use_symlinks=False` 제거 (huggingface_hub 최소 버전 상향과 묶임) 와 라벨 인코더의 조용한 스킵 자체는 메인테이너 결정 사항이라 이슈 본문에 따로 적었다.

### 검증

- HEAD 에서 버그 재현: huggingface_hub 2.1.1, 0.33.4, 0.22.2 (원본 출력은 `repro.txt` ).
- 회귀 테스트: 수정 전 FileNotFoundError 로 실패, 수정 후 통과.
- 수정 후 `fetch()` 재현 스크립트: huggingface_hub 0.19.4, 0.22.2, 0.23.0, 0.33.4, 2.1.1 모두 파일 존재.
- 수정 후 엔드투엔드: 라벨 107개, 분류 정상.
- `pytest tests/unittests` : 750 통과, 7 실패. 7건은 수정 전 HEAD 에서도 동일하게 실패 (torch 2.14.1 호환 문제와 transformers 미설치) 하며 이번 변경과 무관.
- `ruff check` , `ruff format --check` (0.12.4) 통과.
- 미실행: `pre-commit run -a` 전체, 통합 테스트, CI 와 동일한 torch 2.6.0 환경.

| 상황 | 수정 전 | 수정 후 |
| --- | --- | --- |
| `uv` 가 `PATH` 에 없음 | `AttributeError` 로 종료 | `[pip3] Could not collect` |
| 가상환경 미활성 | 시스템 패키지 (`numpy==2.2.6` , `nvidia-*` ) | 가상환경 패키지 (`numpy==2.5.3` , `torch==2.14.1+cpu` ) |

