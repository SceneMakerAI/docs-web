---
title: "Fixed an issue where TextEncoder ignored the `n_most_common` and `min_count` arguments"
sidebar_position: 42
slug: "42"
description: "speechbrain: Fixed an issue where `TextEncoder.limited_labelset_from_iterable` passed a fixed value instead of an argument, causing the label set to remain unrestricted."
tags: [PR]
keywords: [PR]
last_update:
  date: 2026-10-06
---

## speechbrain: Fixed an issue where `TextEncoder.limited_labelset_from_iterable` ignored `n_most_common` and `min_count`

Link: https://github.com/speechbrain/speechbrain/pull/3095

### Background

`speechbrain.dataio.encoder.CategoricalEncoder.limited_labelset_from_iterable` is a method that counts label frequencies and includes only the top N labels (`n_most_common`) or labels with a minimum occurrence count (`min_count`) in the label set. The subclass for text, `TextEncoder` (and `CTCTextEncoder`, which inherits from it), overrides this method solely to change the default value of `sequence_input` to `True`.

### Cause

The override in lines `speechbrain/dataio/encoder.py` 916–922 does not pass the received arguments to the parent but instead passes hard-coded constants.

```python
return super().limited_labelset_from_iterable(
    iterable, sequence_input=True, n_most_common=None, min_count=1
)
```

Consequently, in `TextEncoder`, whatever values are passed to `n_most_common`, `min_count`, and `sequence_input` are silently ignored, and all labels are added to the label set. Since there are no exceptions or warnings, training proceeds under the assumption that the vocabulary size has been limited. The sibling overrides immediately above—`update_from_iterable` and `update_from_didataset`—pass the arguments as-is, so this appears to be a simple oversight (unchanged since initial creation in December 2020).

### Changes

- `speechbrain/dataio/encoder.py`: Modified the override so that `sequence_input`, `n_most_common`, and `min_count` are passed to the parent as-is (line 1 → line 4). The default value for `sequence_input`, `True`, is retained.
- `tests/unittests/test_categorical_encoder.py`: Added `test_text_encoder_limited_labelset` (for the three cases: `n_most_common=2`, `min_count=3`, and `sequence_input=False`).

### Reproduction Steps

```python
from speechbrain.dataio.encoder import TextEncoder

sentences = [["a", "b", "c"], ["a", "b"], ["a"]]
text = TextEncoder()
text.limited_labelset_from_iterable(sentences, n_most_common=2)
print(text.lab2ind)  # Original: includes a, b, and c / After modification: includes only a and b
```

### Verification

- The new test failed in `develop` (89ead74d) but passed after the fix.
- `pytest tests/unittests/test_categorical_encoder.py`: 7 passed; `pytest --doctest-modules speechbrain/dataio/encoder.py`: 5 passed.
- `pytest tests/unittests` Overall: 750 passed, 5 skipped, 7 failed. The 7 failures were due to environmental factors (Torch version, Transformers not installed) that also caused failures in `develop` before the fix.
- `ruff check` and `ruff format --check` (0.12.4) passed. Codespell and Yamllint were not run locally.
- Duplicate check: No identical reports found in issue/PR searches; no open PRs that affect `encoder.py`.

