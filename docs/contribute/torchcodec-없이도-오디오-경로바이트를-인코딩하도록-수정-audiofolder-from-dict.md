---
id: torchcodec-없이도-오디오-경로바이트를-인코딩하도록-수정-audiofolder-from-dict
title: "torchcodec 없이도 오디오 경로·바이트를 인코딩하도록 수정 (audiofolder, from_dict)"
sidebar_position: 38
slug: "38"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## huggingface/datasets: torchcodec 없이도 오디오 경로·바이트를 인코딩할 수 있게 수정

링크: https://github.com/huggingface/datasets/pull/8754

### 배경

STT·언어 식별 벤치마크용 데이터셋을 만들 때 오디오는 대부분 파일 경로로만 넣고(`Audio(decode=False)` ), 디코딩은 별도 도구로 한다. 그런데 torch 와 torchcodec 이 없는 CPU 전용 환경에서는 경로만 담은 데이터셋조차 만들 수 없었다.

- `Audio().encode_example("a.wav")` 가 ImportError (To support encoding audio data, please install 'torchcodec'.)
- `Dataset.from_dict(..., features=Features(audio=Audio(decode=False)))` , `Dataset.from_list` , `IterableDataset.from_generator` 도 같은 오류
- `load_dataset("audiofolder", data_dir=...)` 는 같은 ImportError 가 원인인 DatasetGenerationError
- 반면 `Dataset.from_dict(...).cast_column("audio", Audio(decode=False))` 는 정상 동작

### 원인

`src/datasets/features/audio.py` 의 `Audio.encode_example` 첫 부분(106-110행)에서 값의 종류를 보기도 전에 `torch` 와 `torchcodec.encoders.AudioEncoder` 를 import 한다. 실제로 인코더가 필요한 입력은 두 가지뿐이다: `array` 와 `sampling_rate` 를 담은 dict, 그리고 로컬 `.pcm` 파일. 문자열 경로, `Path` , bytes, path/bytes dict 는 그대로 저장되므로 인코더가 필요 없다. 이 무조건 import 는 soundfile 에서 torchcodec 으로 인코딩을 옮긴 #7761 에서 들어왔다. 같은 저장소의 `Video.encode_example` 은 경로 입력에 torchcodec 을 요구하지 않고, 같은 파일의 `encode_torchcodec_audio` 도 실제로 쓸 때만 import 한다.

### 변경 내용

- import 를 `_import_torch_and_audio_encoder()` 헬퍼로 옮기고, `AudioEncoder` 를 실제로 호출하는 두 분기(array 입력, pcm 파일)에서만 부른다. 오류 메시지는 그대로다.
- 디코딩(`decode_example` )은 건드리지 않았다. 여전히 torchcodec 이 필요하다.
- 테스트 2개 추가 (`tests/features/test_audio.py` ): `torchcodec.encoders` 를 숨긴 상태에서 경로·Path·bytes·dict 인코딩이 되는지, array 입력은 여전히 같은 ImportError 를 내는지.

변경 규모: 2개 파일, +38 / -6.

### 검증

- main(08fb7c83) 에서 새 테스트 6건 실패(ImportError) 확인 후, 수정본에서 통과 확인.
- torch 2.14.1+cpu, torchcodec 0.17.0 설치 환경: `tests/features/test_audio.py` , `tests/packaged_modules/test_audiofolder.py` 97건 통과.
- torchcodec 미설치 환경: 14건 통과, 83건 skip. 재현 스크립트에서 `from_dict` , `from_list` , `IterableDataset.from_generator` , `load_dataset("audiofolder")` 가 모두 정상 동작.
- `ruff check` , `ruff format --check` (CI 와 같은 명령) 통과.
- 전체 테스트 스위트는 돌리지 않았다 (features, audiofolder, webdataset, folder_based_builder, arrow_writer 범위만 실행: 613 통과, 1건은 Pillow 미설치로 인한 무관한 실패).

