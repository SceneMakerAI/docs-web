---
title: "Sharing My Experience with Optimizing \"faster-whisper\" for Korean Speech Recognition"
sidebar_position: 3
slug: "3"
last_update:
  date: 2026-11-06
---

### Introduction

---

If you run ``faster-whisper large-v3`` directly on Korean broadcast content, the subtitles do not appear as intended.

```text
# Sample Extraction Results
[01:12:30.9–01:12:32.7|S???|ko] That’s what happened after a while
[01:12:34.2–01:12:37.7|S???|ja] Thank you for watching.     # Nobody said that
[01:12:38.7–01:12:40.3|S???|ko] Circle
```

The log above shows a subtitle pattern from the training data appearing in a section where there is no speech. 

While conducting a proof of concept (PoC) to compare models and test accuracy, I encountered this failure multiple times and came to understand the **importance of optimization**.

This post documents how I addressed those failures one by one. However, rather than listing the techniques in chronological order, I’ve grouped them under the theme of **“What to Optimize”**. 

---

#### Optimization Criteria

I divided them into four broad categories. 

| Optimization Target | Applied Technique |
| --- | --- |
| **① Accuracy** | Adoption of `large-v3` · Separation of raw and denoised inputs |
| **② Hallucination Suppression** | Tuning of three types of iterative parameters · VAD pre-filter · `MIN_LOGPROB` |
| **③ Language Misclassification** | LID low confidence → Force Korean · dual transcribe · Hangul ratio gate |
| **④ Speed (RTF)** | Batch inference · Language-specific silent streams |

`large-v3` itself is merely a starting point. The quality was achieved by the rules layered **on top of** this model.

For the base model, we selected `Systran/faster-whisper-large-v3` with a focus on accuracy. `turbo` (a 4-layer decoder) was 23 times faster but suffered significant accuracy losses in multilingual mixed content, and while the Korean fine-tuning branch performed well with news, its performance actually declined in documentaries and variety shows. Versatility won out.

When this model was applied to six types of Korean broadcasts (news, documentaries, dramas, historical dramas, variety shows, and sports), three recurring failures emerged.

1. **Phantom Subtitles** — Subtitle patterns from the training data pop up during silent sections or background music (BGM) where no speech occurs. `ご視聴ありがとうございました`, `Thanks for watching`, and even Arabic subtitle credits.
2. **Infinite Loop** — `감사합니다 감사합니다 감사합니다...` (Did not actually occur, but was deemed possible)
3. **Language Misclassification** — 12 seconds of Korean are recognized as Japanese or Chinese, or the system outputs Kana and Kanji while in Korean mode.

Optimization consisted entirely of preventing these three issues on separate axes.

---

#### 1. Accuracy — Split the input into two parts

> **Optimization Goals: LID Accuracy ↑ + ASR Hallucinations ↓**

The first insight was, “**You shouldn’t use denoised audio at every stage**.”

Noise reduction (DeepFilterNet v3) reduces ASR hallucinations. However, when we fed the same denoised audio into **language detection (LID)**, accuracy actually dropped. The denoising process altered the subtle acoustic signals in the speech, clouding the LID decision. We confirmed this through measurements.

| Input | Whisper LID Accuracy |
| --- | --- |
| raw audio | **95.2%** |
| denoised audio | 93.4% |

Therefore, we split the inputs. **VAD, LID, and speaker recognition use raw audio, while ASR uses denoised audio.**

```text
        ┌─ VAD  (Speech Segment Detection)   ← raw
raw ────┼─ LID  (Language Detection) ← raw
        └─ Speaker Identification ← raw

denoised ─ ASR (automatic speech recognition) ← denoised
```

We also adjusted the denoising intensity to `atten_lim_db = -30` to ensure that singing and normal speech were preserved and not erased along with the noise.

---

#### 2. Hallucination Suppression

I implemented a three-layered defense against “non-existent subtitles” caused by silence and repetition.

##### 2-1) Repetition Hallucination — Tuning of 3 Formula Parameters

> **Optimization Target: Repetition Loops**

We adjusted the default values of three official parameters in `transcribe()` that directly affect repetition. (Based on the default values in faster-whisper 1.2.1)

| Parameter | Default | Our Value | Role |
| --- | --- | --- | --- |
| `condition_on_previous_text` | `True` | `False` | Block propagation of repetition between windows |
| `repetition_penalty` | `1.0` | `1.2` | Soft penalty for repeated tokens |
| `no_repeat_ngram_size` | `0` | `3` | Hard prohibition of 3-gram repetition |

The key is `condition_on_previous_text=False`. 

By default, Whisper uses the recognition result from the previous window as context for the next window. However, once repetition begins, that text propagates to the next segment and snowballs. 

If the context is broken, each window is processed independently, and **the chain itself disappears.** The other two methods suppress recurrence at the token decoding stage—one using a soft penalty and the other using a hard n-gram penalty.

Since they cover different levels (windows vs. tokens, soft vs. hard), all three had to be used together to be effective.

---

##### 2-2) Ghost Subtitles — VAD Pre-filter

> **Optimization Target: Hallucinations in silent intervals (most effective)**

**The primary cause of hallucinations is segments without speech**. 

Therefore, if silent or BGM segments are excluded from the ASR process from the outset, most of the problems disappear. We used Silero VAD to extract only the speech segments and passed them to the ASR model.

We also adjusted the parameters to suit the Korean language.

---

##### 2-3) Low-Confidence Cut — MIN_LOGPROB

> **Optimization Target: Catch-all Hallucinations**

Even so, some hallucinations still slipped through. Subtitles like `Thank you` passed through without issue. So I filtered the **transcription results** one more time — if the segment’s average log-likelihood is `avg_logprob < -1.0` (probability approx. 37%), it’s discarded. This is the final filter to catch hallucinations spewed without confidence.

---

#### 3. Language Misclassification

From this point on, these aren’t “hallucinations” but **“errors caused by selecting the wrong language”**. These are gates unique to this project, tailored specifically for Korean-language main content.

##### 3-1) Low LID Confidence → Force Korean

> **Optimization Target: Incorrect Language Classification of Short Utterances**

If the language detection probability is below `0.5` and the result is a non-Korean language, it is forced to Korean. 

A value like prob 0.23 means “ko/ja/zh are all similar = the model doesn’t know.” For content primarily in Korean, **assuming Korean when the model is unsure was the safest approach**.

---

##### 3-2) dual transcribe — ko vs. detected language

> **Optimization Target: Acoustic Confusion Between ko / ja / zh**

If a utterance shorter than 3 seconds is detected as a non-Korean language, transcribe it **both as Korean and as the detected language**, then adopt the one with the higher `avg_logprob` value. If both values are below -0.6, it is treated as noise and discarded. This mechanism prevents a 12-second Korean utterance from being misclassified as Japanese or Chinese based on acoustic features.

---

##### 3-3) Hangul Ratio Gate

> **Optimization Target: Kana and Kanji Token Hallucinations**

If the speech is recognized as Korean but the proportion of Hangul in the result text is less than `30%`, it is discarded. This accurately filters out cases where Whisper outputs Kana and Kanji tokens as hallucinations in Korean mode.

> For reference, language tiering was also implemented. Based on faster-whisper’s WER by language, only Tier 13 is allowed (Korean is Tier 2), and segments detected as other weaker languages are skipped entirely.

These gates are rules I created one by one while actually reviewing Korean content—rules not found in the official documentation. **"What hallucinations were observed → and which gate blocked them"** is the essence of this project’s optimization.

---

#### 4. Speed — and Conflicts Between Metrics

> **Optimization Target: RTF (Processing Time / Audio Length)**

During the proof-of-concept (PoC) phase, accuracy was the primary goal, so speech segments were processed sequentially, one by one. Speed wasn’t a concern. However, for production, speed is the top priority (due to HTTP blocking), so the architecture had to be changed.

- **Batch Inference** — Using `BatchedInferencePipeline`, 16 30-second windows are loaded onto the GPU in parallel.
- **Silence Streams by Language** — Create full-length streams where segments outside the target language are filled with 0 (silence), enabling batch transcription for each language at once. Since the internal VAD skips silence, only speech in that language is recognized.

As a result, **RTF ≈ 0.042** — one hour of input is processed in approximately 150 seconds.

The silent stream works thanks to `vad_filter=True`. Since the internal VAD skips entire segments filled with 0s, even when a full-length stream is fed in, the actual computation is limited to the utterances in that language.

#### Conclusion

---

`large-v3` was the starting point. Four key factors drove the improvement in Korean speech recognition quality.

- **① Accuracy** — LID is raw, ASR is denoised (95.2% vs. 93.4%)
- **② Hallucination Suppression** — Blocking nonexistent subtitles using iterative parameters, VAD, and logprob
- **③ Language Misclassification** — Reducing errors from a Korean perspective via LID enforcement, dual mode, and Korean text ratio
- **④ Speed** — RTF of 0.042 in batch mode; instead, deciding which gates to discard

Looking back, what took the longest wasn’t tweaking parameters, but figuring out **“why this hallucination occurred”** by analyzing the logs. Until I understood why `ご視聴ありがとうございました` appeared, no parameter adjustment was the solution. Conversely, once I knew the cause, the gate was usually just two or three lines of conditional code.

The parameters listed in the official documentation accounted for only half of the solution; the other half consisted of **rules I developed by actually analyzing Korean content**. I hope this trial-and-error process serves as a shortcut for others facing the same challenges.

---

#### Preview of the Next Post

I plan to write about building the RAG pipeline, as well as the voice analysis process and results.

---

**References**

- faster-whisper: [https://github.com/SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- Systran/faster-whisper-large-v3: [https://huggingface.co/Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3)
- OpenAI Whisper: [https://github.com/openai/whisper](https://github.com/openai/whisper)
- DeepFilterNet: [https://github.com/Rikorose/DeepFilterNet](https://github.com/Rikorose/DeepFilterNet)
- Silero VAD: [https://github.com/snakers4/silero-vad](https://github.com/snakers4/silero-vad)
- pyannote-audio: [https://github.com/pyannote/pyannote-audio](https://github.com/pyannote/pyannote-audio)
- Complete STT PoC benchmark results: [https://doc.scenemaker.solbox.com/docs/poc/audio-bench/1](https://doc.scenemaker.solbox.com/docs/poc/audio-bench/1)

*This article presents research results conducted with support from the Ministry of Science and ICT and the National IT Industry Promotion Agency under the “2026 Open-Source AI and Software Development and Utilization Support Project.”*

