---
title: "The issue of punctuation within words splitting them in `word_timestamps`"
sidebar_position: 41
slug: "41"
description: "openai/whisper: When using `word_timestamps`, an issue was raised (in a Q&A discussion) where punctuation within a word—such as the 3.5% or the particle following a quotation mark—splits the word into two parts, with the punctuation attached to the front of the second part."
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

## openai/whisper: Issue with punctuation within words splitting words in `word_timestamps` (Discussion)

Link: https://github.com/openai/whisper/discussions/2875

### Background

When verifying word timestamps in Korean broadcast audio, openai/whisper is used as the reference implementation. In the `words` list of results, we observed that `3.5%` was split into ` 3`, `.5`, and `%`, while `"안녕"이라고` was split into ` "안녕` and `"이라고`. In Korean, particles are attached immediately after closing quotation marks or parentheses, so the closing quotation mark appears before the word containing the particle, and subtitle line breaks (`max_words_per_line`, `highlight_words`) occur in between.

### Cause

`split_tokens_on_spaces` in `whisper/tokenizer.py` (lines 317–325).

- Subwords consisting solely of ASCII punctuation always start a new word, even if there is no preceding space (lines 319–320).
- Since the following subword has no leading whitespace, it is appended to `words[-1]`—that is, the punctuation word just created (line 324). The result is `.5` and `"이라고`.
- `merge_punctuations` (`whisper/timing.py`, line 268) is moved to the preceding word only when the entire word fits within `append_punctuations`, so this form remains unchanged.
- Since `string.punctuation` is ASCII-only and performs a substring check, the double quotation marks `”` are not split, nor is the token `%.`. The same sentence results in different word lists depending on the type of quotation marks used.

### How to Reproduce

- Without a model: `repro_tokens.py` (tokenizer + `merge_punctuations` + `WriteSRT`). The Korean sentence is the result of tokenizing manually entered text and is not model output.
- Actual speech: The first 60 seconds of an English news reading file from Wikimedia Commons (CC BY 2.5) were transcribed using the `tiny` model (CPU). `17.5%` is transcribed as ` 17`, `.5`, `%`, and `wikinews.org,` is transcribed as ` wikinews` and `.org,`.
- The command and original output are shown in `repro.txt`.

### Verification

- Reproduced both scripts on main HEAD 8609812.
- There is one uncommitted change (10 lines) and one test on the local branch `discussion-korean-repro`. The test failed before the change and passed afterward. Passed 20 pytest subsets (such as CI) and passed black/isort.
- This task did not test cases where the model actually outputs ASCII quotes when reading Korean text aloud (the pattern did not appear in the three public Korean readings tested with `tiny/base`).
- The main text of the discussion asks, “Is this intended behavior, or should we accept a patch to revert the change?”

