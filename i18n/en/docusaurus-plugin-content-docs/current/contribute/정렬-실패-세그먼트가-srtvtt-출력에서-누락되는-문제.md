---
title: "Issue where misaligned segments are missing from SRT/VTT output"
sidebar_position: 16
slug: "16"
description: "whisperX: Reported an issue where segments that `align()` failed to align remain in TXT and TSV files but are omitted from SRT and VTT files without any warning"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-06
---

## whisperX: Issue where segments that failed alignment are entirely missing from SRT/VTT

Link: https://github.com/m-bain/whisperX/issues/1490

### Background

SceneMakerAI generates SRT, VTT, and JSON files from Korean broadcast audio using the following writers: `whisperx.load_model(...).transcribe()` → `whisperx.align()` → `whisperx/utils.py`. When Whisper attaches a long sentence to a very short segment (due to hallucinations or timestamp errors), the number of wav2vec2 frames is fewer than the number of characters, causing the alignment to fail and `Failed to align segment (...): backtrack failed, resorting to original` to appear in the log. Although the log message states that the original text is preserved, in reality, the `.txt`, `.tsv`, and `.json` files generated from the same result contain sentences, while the `.srt` and `.vtt` files do not.

### Causes

- `whisperx/alignment.py:221-227`: Initializes all output segments to `"words": []`. The three cases where sorting fails (`:236-239`: no characters in the dictionary; `:241-244`: start time exceeds audio length; `:294-297`: backtrack failure) are included in the results as-is. In other words, `text`, `start`, and `end` remain, while only `words` is an empty list.
- `whisperx/utils.py:308`: If the first segment contains the `words` key, it follows the word-based path.
- `whisperx/utils.py:269-270`: `iterate_subtitles()` iterates only through `segment["words"]` to create the subtitle queue. If the list is empty, no words are added, so no queue is created for that segment. In this path, `segment["text"]` is not checked at all.
- The segment timestamp fallback (`utils.py:313-321`) added in #1347 only handles cases where a word exists but `start` / `end` are missing, so it never reaches an empty `words`.

### Reproduction

This can be reproduced using only the standard library, without a model (`repro_writer.py`). When the `words` of the middle segment among the three is set to an empty list, passing the resulting dict to `WriteTXT`, `WriteTSV`, `WriteSRT`, `WriteVTT`, the output consists of only 3 lines for TXT/TSV and 2 queues for SRT/VTT.

I also verified the actual `align()` path (`repro_align.py`). If you insert a stub wav2vec2 model that returns only 5 frames for a 26-character segment to trigger a backtrack failure, `align()` returns the `words: []` segment, and subsequently, `WriteSRT` omits that sentence.

### Proposed fix (local branch, uncommitted)

In `iterate_subtitles()`, treat segments where `words` is empty and `text` is not empty as a single word containing the segment’s `start` /`end`. `whisperx/utils.py` Added 6 lines; added 4 test cases `tests/test_subtitles_unaligned_segments.py`.

Outstanding decisions: When using `--highlight_words`, the entire sentence where the sort fails is underlined. Removing `start` /`end` from placeholders outputs them to the regular queue, but this reduces the temporal accuracy of the queue in segment merging mode. Therefore, I’m raising this as an issue first instead of a PR to get feedback from the maintainer.

### Verification

- Reproduced on upstream `main` HEAD `771b4a1` (3.8.7rc1), Python 3.12, and torch 2.8.0+cpu.
- Before the fix, 3 out of 4 new tests failed(The remaining one was a test to verify the existing behavior of skipping empty text segments, so it passed even before the fix).
- After the fix, all 16 `pytest tests/` tests passed.
- Not tested with an actual wav2vec2 model and real audio (verified using a stub without downloading the model).
- Duplicate check: I reviewed #75, #404, #230, #1089, #1478, #1315, #1347, #1456, #1458, and #1487 and found no duplicates.

