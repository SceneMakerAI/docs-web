---
title: "Modified to encode audio paths and bytes even without torchcodec (audiofolder, from_dict)"
sidebar_position: 38
slug: "38"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## huggingface/datasets: Modified to allow encoding of audio paths and bytes without torchcodec

Link: https://github.com/huggingface/datasets/pull/8754

### Background

When creating datasets for STT and language identification benchmarks, audio is typically included only as file paths (`Audio(decode=False)`), and decoding is performed using a separate tool. However, in CPU-only environments without torch and torchcodec, it was not even possible to create a dataset containing just the paths.

- `Audio().encode_example("a.wav")` resulted in an ImportError (To support encoding audio data, please install 'torchcodec.')
- `Dataset.from_dict(..., features=Features(audio=Audio(decode=False)))`, `Dataset.from_list`, and `IterableDataset.from_generator` also produced the same error
- `load_dataset("audiofolder", data_dir=...)` resulted in a DatasetGenerationError caused by the same ImportError
- In contrast, `Dataset.from_dict(...).cast_column("audio", Audio(decode=False))` functioned normally

### Cause

In the first part of `Audio.encode_example` in `src/datasets/features/audio.py` (lines 106–110), `torch` and `torchcodec.encoders.AudioEncoder` are imported before the type of the values is even checked. In fact, the encoder requires only two types of input: a dict containing `array` and `sampling_rate`, and the local `.pcm` file. String paths, `Path`, bytes, and path/bytes dicts are stored as-is and therefore do not require an encoder. This unconditional import was introduced in #7761, which moved encoding from `soundfile` to `torchcodec`. In the same repository, ``Video.encode_example`` does not require `torchcodec` for path inputs, and ``encode_torchcodec_audio`` in the same file is only imported when it is actually used.

### Changes

- Moved the import to the `_import_torch_and_audio_encoder()` helper and call it only in the two branches (array input, PCM file) that actually invoke `AudioEncoder`. The error messages remain unchanged.
- Decoding (`decode_example`) was left untouched. torchcodec is still required.
- Added 2 tests (`tests/features/test_audio.py` ): Verify that encoding works for paths, Paths, bytes, and dictionaries while `torchcodec.encoders` is hidden, and that array input still raises the same ImportError.

Scope of changes: 2 files, +38 / -6.

### Verification

- Confirmed that 6 new tests failed (ImportError) in main(08fb7c83), then verified they passed in the revised version.
- In an environment with torch 2.14.1+cpu and torchcodec 0.17.0 installed: `tests/features/test_audio.py` and `tests/packaged_modules/test_audiofolder.py` passed 97 tests.
- In an environment without torchcodec installed: 14 tests passed, 83 skipped. In the reproduction script, `from_dict`, `from_list`, `IterableDataset.from_generator`, and `load_dataset("audiofolder")` all functioned normally.
- `ruff check` and `ruff format --check` (commands identical to those in CI) passed.
- The entire test suite was not run (only the features, audiofolder, webdataset, folder_based_builder, and arrow_writer scopes were executed: 613 passed; 1 unrelated failure due to Pillow not being installed).

