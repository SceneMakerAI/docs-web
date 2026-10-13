---
title: "[Use Case][Whisper] Unit Test Results — Comparison of faster-whisper large-v3 and Qwen3-ASR Across 6 Korean Broadcast Channels"
sidebar_position: 8
slug: "8"
description: "Faster-Whisper Large-v3 vs. Qwen3-ASR Across 6 Korean Broadcast Channels"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

GitHub Discussion: [https://github.com/SYSTRAN/faster-whisper/discussions/1663](https://github.com/SYSTRAN/faster-whisper/discussions/1663)

These are the results of running faster-whisper large-v3 and Qwen3-ASR on Korean broadcasts under the same conditions. The code and result files are available at [`poc-stt-bench`](https://github.com/SceneMakerAI/poc-stt-bench).

- Whisper: `Systran/faster-whisper-large-v3`
- Qwen: `Qwen3-ASR-1.7B` + `Qwen3-ForcedAligner-0.6B`
- Data: One episode each of news, documentaries, dramas, historical dramas, variety shows, and sports; total runtime of approximately 6 hours and 20 minutes
- Hardware: RTX 4090 24GB

|  | Whisper | Qwen |
| --- | --- | --- |
| Average Score (-3 to 3) | 2.71 | 2.63 |
| Subtitle Usability Rate (0 points or higher) | 97.8% | 97.0% |
| Hallucination Rate (-3 points) | 1.4% | 1.8% |
| Average RTF | 0.042 | 0.032 |
| VRAM | Approx. 3.5 GB | Approx. 7 GB |

Overall, Whisper was slightly more accurate, and the gap widened in the documentary (hallucination rate of 1.6% vs. 6.0%). Qwen was faster and had a slight edge in fast-paced content, such as baseball broadcasts. Whisper’s VRAM usage is half that of Qwen.

#### Scoring was not done by humans.

Since there were no ground-truth subtitles, we provided Gemini with both the audio and segmented text and had it assign scores ranging from -3 to 3. Therefore, the scores above should not be interpreted as absolute accuracy but rather as a measure of how the two systems compare when evaluated by the same standard.

#### Pipeline

```text
raw wav
 → denoise (DeepFilterNet v3, atten_lim_db=-30)
 → VAD (Silero, raw)
 → LID (Whisper detect_language, raw)
 → ASR (Whisper / Qwen, denoised)
 → Post-processing
 → Grading
```

VAD and LID are run on the original audio, while ASR is run on denoised audio. Accuracy drops (95.2% → 93.4%) when language detection is performed on denoised audio. This comparison can be found in [#35](https://github.com/SceneMakerAI/docs-web/discussions/35).

#### Reducing Whisper Hallucinations

Listed in order of effectiveness.

1. Use VAD to completely exclude silence and BGM segments from being sent to ASR. This has the greatest impact.
2. Discard segments marked with `avg_logprob < -1.0`.
3. If the language detection probability is less than 0.5 but the system identifies it as a language other than Korean, force it to be Korean.
4. For non-Korean utterances shorter than 3 seconds, transcribe them in both Korean and the detected language, then use the one with the higher `avg_logprob` score. If both are below -0.6, discard them.
5. If the utterance is classified as Korean but the proportion of Hangul is less than 30%, discard it. This occurs when Kana or Kanji appear unexpectedly in Korean mode.

#### To test it,

```bash
uv venv .venv --python 3.11 && .venv/bin/uv sync
uv venv .venv-qwen --python 3.12
.venv-qwen/bin/uv pip install -r pyproject-qwen.toml

.venv/bin/python main.py
.venv-qwen/bin/python main_qwen.py
.venv/bin/python evaluate.py all
.venv/bin/python report.py
```

Due to dependency conflicts with Qwen, I set up a separate venv for it.

Content-specific metrics are available at [`output/report.csv`](https://github.com/SceneMakerAI/poc-stt-bench/blob/HEAD/output/report.csv), and the tuning process is on my [blog](https://doc.scenemaker.solbox.com/blog/3).

