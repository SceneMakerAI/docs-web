---
title: "Fixed an issue where the `sf.info() duration` value was displayed incorrectly in exponential notation for files longer than 10 minutes"
sidebar_position: 32
slug: "32"
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## python-soundfile: Issue where the duration returned by `sf.info()` in files longer than 10 minutes is displayed in exponential notation

Link: https://github.com/bastibe/python-soundfile/pull/497

### Background

The SceneMakerAI STT/LID benchmark reads 16 kHz mono PCM16 WAV files (ranging from 1 to 3 hours in length), generated using ffmpeg, into `soundfile`. While reviewing the upstream code, I noticed that when `sf.info(file)` is printed, the line containing `duration:` becomes garbled—appearing as `2e+01:0.000 min` or `3:2e+01:7.500 h`—in files longer than 10 minutes. Although our benchmark code does not directly use the `repr` of ``sf.info()`` (the ``.duration`` attribute value itself is normal), this is the output we encounter immediately when checking long files.

- Target: bastibe/python-soundfile `master` 3503941 (0.14.0), bundled libsndfile 1.2.2
- Type: PR (format specifier fix + tests)

### Cause

In lines `soundfile.py` 461–472, `_SoundFileInfo._duration_str` formats the hour and minute as `.0g` and `02.0g`. In `g`, a precision of 0 means one significant digit, so values of 10 or higher are rounded to one digit and then converted to exponential notation (`format(15.0, '02.0g')` is `'2e+01'`). Seconds are `05.3f`, but since `d.ddd` is already 5 characters long, no zero-padding is applied (`01:1.000 min`).

Also, since minutes and seconds are split before rounding, a value like 119.9996 seconds is split into 1 minute + 59.9996 seconds and then printed as `01:60.000 min`.

The `4e+01` in `6e+10:4e+01:3.719h` cited in issue #443 also stems from this formatting issue (the frame count issue addressed in that issue is a separate matter related to libsndfile).

### Changes

- Hours and minutes changed to `.0f` / `02.0f`; seconds changed to `06.3f`
- Round the duration to milliseconds before division (`round(self.duration, 3)`)
- Added `test_info_duration` (8 cases, parametrize) to `tests/test_soundfile.py`. The `samples` / `s` branches and the `duration` property remain unchanged

| Length | Before | After |

|---|---|---|

| 61 s | `01:1.000 min` | `01:01.000 min` |

| 900 s | `2e+01:0.000 min` | `15:00.000 min` |

| 11707.5 s | `3:2e+01:7.500 h` | `3:15:07.500 h` |

| 36,000 s | `1e+01:00:0.000 h` | `10:00:00.000 h` |

| 119.9996 s | `01:60.000 min` | `02:00.000 min` |

### Verification

- Run the reproduction script on the pre-fix HEAD: Verify the "Pre-fix" output in the table above (`repro.txt`)
- When running the new test on the pre-fix code, 6 out of 8 tests fail; after the fix, all 8 pass
- `python -m pytest` Total: 339 passed (331 passed before the fix)
- `python -m pyright soundfile.py`: 188 lines with 2 existing errors before and after the fix; no new errors
- Not verified: Windows / macOS / PyPy / free-threaded 3.14 CI matrix (local environment is Linux x86_64, CPython 3.11 only)

