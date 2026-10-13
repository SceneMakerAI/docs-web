---
title: "Fixed a regression where Exif.tobytes() and saving failed with a struct.error after reading IFD1 (thumbnail IFD)"
sidebar_position: 50
slug: "50"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-12
---

## Pillow: Fixed an issue where `Exif.tobytes()` failed with a `struct.error` after reading an IFD1 file

Link: https://github.com/python-pillow/Pillow/pull/10188

- Repo: python-pillow/Pillow (13,890 stars)
- Type: PR
- Branch: `exif-ifd1-tobytes` (based on `origin/main` 192140806)
- Files changed: `src/PIL/Image.py` 1 line, `Tests/test_image.py` 5 lines

### Background

JPEG’s EXIF contains a second directory, IFD1, which holds thumbnail information. Pillow reads this as `exif.get_ifd(ExifTags.IFD.IFD1)`. However, starting with Pillow 11.1.0, once IFD1 is read, any path that converts the same `Exif` object to bytes results in an exception. `im.save(..., exif=exif)` is a prime example.

```python
from io import BytesIO

from PIL import ExifTags, Image

with Image.open("Tests/images/flower.jpg") as im:
    exif = im.getexif()
    exif.get_ifd(ExifTags.IFD.IFD1)
    im.save(BytesIO(), "JPEG", exif=exif)
```

```text
struct.error: ushort format requires 0 <= number <= 65535
```

According to the release wheel, saving works normally from version 9.4.0 through 11.0.0, but fails in versions 11.1.0, 11.2.1, 11.3.0, 12.0.0, and the current main branch. This is an issue I discovered while reviewing the code; it is not a failure encountered during production.

### Cause

The value of ``ExifTags.IFD.IFD1`` is not the actual tag number but `-1`, which is used for internal identification (``src/PIL/ExifTags.py:359``). ``get_ifd()`` stores the read IFD in the ``_ifds`` dictionary using this value as the key.

PR #8635 (11.1.0, "Keep new IFDs when converting EXIF to bytes") added a loop in `Exif.tobytes()` that writes all entries from `_ifds` that lack a key in the `Exif` object to IFD0 (`src/PIL/Image.py:4219-4221`). This change was intended to prevent the loss of newly created Exif IFDs and GPS IFDs, but IFD1 also met the condition, causing -1 to be entered as the tag number and resulting in a failure during the unsigned short range check in `struct.pack`.

### Changes

The loop now skips only IFD1.

```python
for tag, ifd_dict in self._ifds.items():
    if tag not in self and tag != ExifTags.IFD.IFD1:
        ifd[tag] = ifd_dict
```

Since `tobytes()` did not write to IFD1 even before #8635, the result is the same as when IFD1 was not read. I did not include the actual rewriting of the thumbnail, as that is a separate feature.

I added three lines to the end of the existing test for `test_exif_ifd1`: read IFD1, call `tobytes()`, and read it again to verify the Make tag.

### Verification

- Before the fix: Confirmed that the added test failed at `struct.error`.
- After the fix: The same test passed. All 8 EXIF-related test files (584 test cases) passed; 6 were skipped.
- Out of 5,120 total test cases, 5,019 passed and 1 failed. The failed `test_file_pdf.py::test_save_all_object_ids` test was caused by the absence of OpenJPEG in the local build and is unrelated to the change.
- Passed pre-commit checks (ruff, black, bandit, etc.). Since mypy’s CI dependencies were not installed, it could not be run under the same conditions as CI. The 6 errors found when running it manually were all due to missing stubs and did not occur in the modified lines.

### Duplicate Check

I searched for combinations of IFD1, tobytes, get_ifd, struct.error, and thumbnail in both open and closed issues, and found no matching reports. The closest matches were #10177 (a KeyError inside `get_ifd`, in a different function) and #8635 (the PR that added this loop).

### Items Left Unaddressed

Due to the same loop, after reading Interop and MakerNote, 0xA005 and 0x927C are written to IFD0 one more time. Since this is a section that requires operational judgment and does not raise an exception, I did not include it in this change.

