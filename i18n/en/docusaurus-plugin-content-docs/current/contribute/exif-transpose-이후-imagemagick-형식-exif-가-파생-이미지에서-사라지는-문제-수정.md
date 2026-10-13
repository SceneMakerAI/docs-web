---
title: "Fixed an issue where ImageMagick-format EXIF data was missing from derived images after calling `exif_transpose()`"
sidebar_position: 46
slug: "46"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-07
---

## Pillow: Issue where ImageMagick-formatted EXIF data disappears entirely after calling `exif_transpose()`

Link: https://github.com/python-pillow/Pillow/pull/10145

### Background

SceneMaker’s image model worker opens frames and uploaded images as `Image.open`, then corrects the orientation using `ImageOps.exif_transpose`, followed by `convert`, `resize`, and `crop`. PNG files created with ImageMagick sometimes store EXIF data as a hex string in a text chunk named `Raw profile type exif` rather than in the standard `eXIf` chunk, and Pillow reads this value as `im.info["Raw profile type exif"]` and parses it in `getexif()`.

### Cause

`Image.getexif()` (`src/PIL/Image.py:1650-1653`) splits this value by line breaks, skips the first three lines (blank line, `exif`, length), and parses the remainder as hexadecimal. However, `ImageOps.exif_transpose()` (`src/PIL/ImageOps.py:748-749`) removes the orientation tag and rewrites this value as a single line of hexadecimal text without a header line. Consequently, when this value is parsed later, the “remaining portion after skipping three lines” is empty, causing not only the orientation tag but all EXIF tags to disappear.

The image returned by `exif_transpose()` appears normal because the `Exif` object is cached. However, images created from that image using `copy()`, `convert()`, `resize()`, and `crop()` are parsed by copying `info`, so `getexif()` returns an empty result. This inconsistency has existed since this branch was added in #5584 in 2021. It went unnoticed because the existing test image contained only a single orientation tag and did not re-parse `info`.

### Changes

- `src/PIL/ImageOps.py`: Rewritten in the same format as when reading the `Raw profile type exif` value (blank line, `exif`, 8-character width, hex data). The only change was expanding the code from one line to four.
- `Tests/test_imageops.py`: Added a check to verify whether the manufacturer tag remains in `copy().getexif()` after `exif_transpose()`, following the creation of a value with two tags: direction and manufacturer.
- `docs/releasenotes/13.0.0.rst`: Added an item to “Other changes.”

### Verification

- Run the reproduction script from `origin/main` (`bfb6b386c`) before the fix: The `getexif()` following `copy()`, `convert()`, and `resize()` are all empty dictionaries.
- The new test fails with `KeyError: 271` before the fix and passes after the fix.
- `python3 -m pytest Tests/ -n 8`: 5132 passed, 1 failed. The single failure (`Tests/test_file_pdf.py::test_save_all_object_ids`) is caused by the absence of OpenJPEG in the local build on this machine; it failed identically even before the fix.
- `pre-commit run` (ruff, black, bandit, sphinx-lint, etc.) and `mypy` passed.
- The C extensions were built directly from the clone. Instead of installing the development headers on the system, I downloaded the RPM and extracted it to the cache disk.

