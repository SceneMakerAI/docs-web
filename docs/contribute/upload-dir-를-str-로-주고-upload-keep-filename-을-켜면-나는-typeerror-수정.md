---
id: upload-dir-를-str-로-주고-upload-keep-filename-을-켜면-나는-typeerror-수정
title: "UPLOAD_DIR 를 str 로 주고 UPLOAD_KEEP_FILENAME 을 켜면 나는 TypeError 수정"
sidebar_position: 28
slug: "28"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## python-multipart: UPLOAD_DIR 를 str 로 주고 UPLOAD_KEEP_FILENAME 을 켜면 TypeError

링크: https://github.com/Kludex/python-multipart/pull/335

- 저장소: Kludex/python-multipart (main, 212819d, 0.0.32 이후)
- 유형: PR (버그 수정)
- 제목: Accept a `str` `UPLOAD_DIR` when `UPLOAD_KEEP_FILENAME` is set

### 배경

SceneMakerAI 의 poc-stt-bench 는 FastAPI 로 영상·오디오 업로드를 받고, 그 multipart 파싱을 python-multipart 가 맡는다. 업로드 경로를 점검하면서 이 라이브러리의 File 클래스 설정을 살펴봤다. File docstring 의 설정 표는 UPLOAD_DIR 타입을 str 로 안내하고, FileConfig 타입 힌트도 str | bytes | None 이다. 그런데 UPLOAD_KEEP_FILENAME=True 와 함께 str 경로를 주면 메모리 한도(MAX_MEMORY_FILE_SIZE)를 넘는 첫 write 에서 예외가 난다. FastAPI 기본 경로는 이 설정을 쓰지 않으므로, File 을 직접 쓰는 코드에서만 만나는 문제다.

| UPLOAD_DIR | UPLOAD_KEEP_FILENAME | 결과 |

|---|---|---|

| str | False | 정상 |

| bytes | True | 정상 |

| str | True | TypeError: Can't mix strings and bytes in path components |

### 원인

`python_multipart/multipart.py` 의 `File._get_disk_file()` (542행) 에서 파일명 유지 분기가 다음과 같이 되어 있다.

```python
path = os.path.join(file_dir, fname)  # type: ignore[arg-type]
```

`fname` 은 항상 bytes 이므로 `file_dir` 이 str 이면 `os.path.join` 이 TypeError 를 던진다. 바로 아래 임시 파일 분기는 str / bytes 를 모두 처리하는데 이 분기만 빠져 있었고, `type: ignore` 가 mypy 경고를 가리고 있었다. TypeError 는 OSError 가 아니라서 `FileError` 로 변환되지도 않는다. 기존 테스트는 이 조합에서 bytes 경로만 사용해 잡히지 않았다.

### 변경 내용

- `os.path.join(os.fsencode(file_dir), fname)` 로 변경하고 `type: ignore` 제거 (1줄). bytes 경로 동작은 그대로.
- `tests/test_file.py` 에 `test_str_upload_dir_with_keep_filename` 추가.

### 검증

- 수정 전: 새 테스트가 위 TypeError 로 실패하는 것 확인.
- 수정 후: `coverage run -m pytest` 163 passed, coverage 100% (저장소 기준 fail_under=100).
- `ruff format --check` , `ruff check` , `mypy --strict` , `check-sdist` , `scripts/rename` (nox) 모두 통과.
- Python 3.11 에서만 실행. CI 매트릭스의 3.12 \~ 3.15 는 로컬에서 돌리지 않음.

### 참고

- 중복 확인: 같은 `_get_disk_file()` 을 건드리는 열린 PR #308 은 `file_name=None` 일 때의 AttributeError 를 다루며 이 건과 원인이 다르다.
- 조사 중 별도로 확인한 것: multipart 에서 base64 / quoted-printable 디코더가 마지막 파트에서만 finalize 되어, 마지막이 아닌 파트의 잘린 base64 는 예외 없이 잘린 채 통과한다. 이번 PR 범위에는 넣지 않았다.

