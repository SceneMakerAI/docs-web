---
id: textencoder-boseos-인덱스-추가-시-정수-텐서가-float-로-바뀌는-문제-수정
title: "TextEncoder BOS/EOS 인덱스 추가 시 정수 텐서가 float 로 바뀌는 문제 수정"
sidebar_position: 58
slug: "58"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-16
---

## speechbrain: TextEncoder.prepend_bos_index / append_eos_index 가 정수 텐서를 float 로 바꿔 돌려주는 문제 수정

링크: https://github.com/speechbrain/speechbrain/pull/3108

### 배경

`speechbrain.dataio.encoder.TextEncoder` 는 seq2seq 학습용 레이블 인코더로, 토큰 id 시퀀스 앞뒤에 BOS·EOS 인덱스를 붙이는 `prepend_bos_index` , `append_eos_index` 를 제공한다. 독스트링은 "입력이 텐서면 텐서를 돌려준다"고만 적고 있고, 토큰 id 는 당연히 정수(LongTensor)로 쓰인다.

### 원인

`speechbrain/dataio/encoder.py` 1024행, 1040행. 텐서 입력일 때 BOS·EOS 인덱스를 `torch.Tensor([idx])` 로 만든다. `torch.Tensor` 는 항상 CPU 의 float32 이므로 `torch.cat` 의 타입 승격 때문에 결과 전체가 float 가 된다. 그래서 LongTensor 를 넣으면 `tensor([2., 0., 1.])` 처럼 float 가 나오고, 이를 `nn.Embedding` 에 넣으면 "indices 는 Long 또는 Int 여야 한다"는 RuntimeError 가 난다. 같은 이유로 CUDA 텐서를 넣으면 장치 불일치가 난다 (GPU 가 없어 meta 텐서로만 확인). 저장소 안의 통합 테스트 5곳과 `lobes/models/g2p/dataio.py` 는 결과에 `.long()` 을 붙여 우회하고 있다. 2020-12 최초 작성 때부터 그대로다.

### 변경 내용

- `speechbrain/dataio/encoder.py` : `torch.Tensor([...])` 를 `x.new_tensor([...])` 로 바꿔 입력 텐서의 dtype 과 device 를 그대로 따르게 했다 (2행).
- `tests/unittests/test_categorical_encoder.py` : `device` 픽스처를 쓰는 테스트 1개 추가. LongTensor 를 넣었을 때 두 메서드 결과의 dtype, device, 값을 확인한다.
- 기존 호출부의 `.long()` 은 그대로 두었다 (수정 후에도 무해함).

### 재현 방법

```python
import torch
from speechbrain.dataio.encoder import TextEncoder

encoder = TextEncoder()
encoder.update_from_iterable([["a", "b"]])
encoder.add_bos_eos()
tokens = torch.LongTensor(encoder.encode_sequence(["a", "b"]))
print(encoder.prepend_bos_index(tokens))  # develop: tensor([2., 0., 1.])  수정 후: tensor([2, 0, 1])
print(encoder.append_eos_index(tokens))   # develop: tensor([0., 1., 3.])  수정 후: tensor([0, 1, 3])
```

### 검증

- 새 테스트는 develop(c0241278f) 에서 실패, 수정 후 통과.
- `test_categorical_encoder.py` 8 passed, `encoder.py` doctest 5 passed, `tests/consistency` 6 passed, 통합 테스트 `ASR_seq2seq` 통과 (`ASR_Transducer` 는 numba 미설치로 skip).
- `tests/unittests` 전체 759 passed, 5 failed. 실패 5건은 기존과 같은 환경 문제(transformers 미설치, `test_filterbank` )로 encoder 와 무관.
- `pre-commit run --files` (ruff 0.12.4, ruff-format, codespell 등 CI 와 같은 훅) 통과.
- GPU 가 없어 CUDA 장치에서는 돌려 보지 못했다.

### 참고

- 중복 확인: `prepend_bos_index` , `append_eos_index` , `bos_index` , `TextEncoder dtype` 등 키워드로 이슈·PR(열림·닫힘) 검색 결과 같은 보고 없음. 열린 PR 가운데 `encoder.py` 를 건드리는 것은 #3102 하나인데, 그 diff 는 이미 머지된 #3095 의 변경이 섞여 보이는 것뿐이다.
- 우리 계정의 기존 speechbrain PR(#3093, #3095, #3101)과 겹치는 줄 없음. #3095 는 같은 파일의 `limited_labelset_from_iterable` 이다.

