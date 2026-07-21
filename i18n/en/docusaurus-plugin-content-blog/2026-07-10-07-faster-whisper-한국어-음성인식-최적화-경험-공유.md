---
title: "07_faster-whisper: Sharing Our Experience with Optimizing Korean Speech Recognition"
date: 2026-07-10T12:07:00
slug: 4
authors: [sbin]
description: "This article provides a detailed explanation of the speech-to-text conversion process."
tags: [Fast-Whisper, Hugging face]
last_update:
  date: 2026-07-20
---

### Introduction

If you

---

apply `faster-whisper large-v3` directly to Korean broadcast content, the subtitles do not appear as intended.

<!--truncate-->

```text
# Sample Extraction Results
[01:12:30.9~01:12:32.7|S???|ko] He said that after a while
[01:12:34.2–01:12:37.7|S???|ja] Thank you for watching     # Nobody said that
[01:12:38.7–01:12:40.3|S???|ko] Circle
```

The log above shows a subtitle pattern from the training data appearing in a section where there is no speech. 

While conducting a proof-of-concept (PoC) to compare models and test accuracy, I encountered this failure multiple times and came to understand the **importance of optimization**.

This post documents how I addressed those failures one by one. However, rather than listing the techniques in chronological order, I’ve grouped them under the theme of **“What to Optimize”**. 

---

#### Optimization Criteria

I’ve broadly divided them into four categories. 

| Optimization Target | Applied Technique |
| --- | --- |
| **① Accuracy** | Adopted `large-v3` · Separated raw and denoised inputs |
| **② Hallucination Suppression** | Tuned three types of iterative parameters · VAD pre-filter · `MIN_LOGPROB` |
| **③ Language Misclassification** | LID low confidence → Force Korean · dual transcribe · Hangul ratio gate |
| **④ Speed (RTF)** | Batch inference · Language-specific silent streams |

`large-v3` itself is merely a starting point. The quality was achieved by the rules layered **on top of** this model.

For the base model, we selected `Systran/faster-whisper-large-v3` with a focus on accuracy. `turbo` (4-layer decoder) was 23 times faster but suffered significant accuracy losses in multilingual mixed content, and the Korean fine-tuning branch, while strong for news, actually performed worse in documentaries and variety shows. Versatility won out.

When this model was applied to six types of Korean broadcasts (news, documentaries, dramas, historical dramas, variety shows, and sports), three recurring failures emerged.

1

. **Phantom subtitles** — Subtitle patterns from the training data pop up during silent sections or BGM segments where no speech occurs. `ご視聴ありがとうございました`, `Thanks for watching`, even Arabic subtitle credits
2

... **Infinite Loops** — `감사합니다 감사합니다 감사합니다...` (did not actually occur, but was deemed possible)
3

. **Language Misclassification** — 12 seconds of Korean are recognized as Japanese or Chinese, or the system outputs Kana and Kanji while in Korean mode.

Optimization consisted entirely of addressing these three issues on separate axes.

---

#### 1. Accuracy — Split the input into two parts

> 

**Optimization Goals: LID Accuracy ↑ + ASR Hallucinations ↓**

The first insight was, “**You shouldn’t use denoised audio at every stage**.”

Noise removal (DeepFilterNet v3) reduces ASR hallucinations. However, when we fed the same denoised audio into **language detection (LID)**, accuracy actually dropped. The denoising process altered the subtle acoustic signals in the speech, clouding the LID decision. We confirmed this through measurements.

| Input | Whisper LID Accuracy |
| --- | --- |
| raw audio | **95.2%** |
| denoised audio | 93.4% |

Therefore, we split the inputs. **VAD, LID, and speaker identification use raw audio, while only ASR uses denoised audio.**

```text
        ┌─ VAD  (Speech Segment Detection)   ← raw
raw ────┼─ LID  (Language Detection) ← raw
        └─ Speaker Identification ← raw

denoised ─ ASR (speech recognition) ← denoised
```

We also adjusted the denoising intensity to `atten_lim_db = -30` to ensure that songs and normal speech were preserved and not erased along with the noise.

```python
# worker/worker-prep_stt/lib/service/stt_service.py
# Line 130-151

def _load_audio(audio_path: str, job_dir: Path = None):
    """Input wav → (raw_np, den_np). Both are 16k mono float32, length-aligned.

    Strategy 2: VAD/LID/speaker classification = raw, ASR = denoised.
    To preserve quality, apply denoising to the original SR file (48k), then downsample it to 16k.
    """
    orig, osr = sf.read(str(audio_path), dtype="float32")
    if orig.ndim > 1:
        orig = orig.mean(axis=1)                       # → mono

    raw_np = _to_16k(orig, osr) # For VAD/LID/speaker
    den48, dsr = denoise.process(orig, osr) # Apply denoising to the original → 48k
    den_np = _to_16k(den48, dsr) # 16k for ASR

    n = min(len(raw_np), len(den_np)) # Handle length differences safely
    return raw_np[:n], den_np[:n]
```

---

#### 2. Hallucination Suppression

I implemented a three-layered defense against “non-existent subtitles” caused by silence and repetition.

##### 2-1) Repetition Hallucination — Tuning of 3 Official Parameters

> 

**Optimization Target: Repetition Loops**

We adjusted the three formula parameters in `transcribe()` that directly affect repetition from their default values. (Based on the default values in faster-whisper 1.2.1)

| Parameter | Default | Our Value | Role |
| --- | --- | --- | --- |
| `condition_on_previous_text` | `True` | `False` | Block iteration propagation between windows |
| `repetition_penalty` | `1.0` | `1.2` | Soft penalty for repeated tokens |
| `no_repeat_ngram_size` | `0` | `3` | Hard prohibition of 3-gram repetition |

The key is `condition_on_previous_text=False`. 

By default, Whisper uses the recognition result from the previous window as context for the next window. However, once repetition begins, that text propagates to the next segment and spreads like a snowball. 

By breaking the context, each window is processed independently, and **the chain reaction itself disappears.** The other two methods suppress recurrence at the token decoding stage—one using a soft penalty and the other using a hard n-gram constraint.

Since they address different levels (windows vs. tokens, soft vs. hard), all three had to be used together to be effective.

```python
# poc/poc-stt-bench/lib/audio/whisper/whisper_stt.py
# Line 97-116

> def _do_transcribe(audio_np: np.ndarray, language: str) - tuple[list, float]:
    """Call faster-whisper transcribe. Returns segments (list) + mean avg_logprob."""
    segments_gen, _info = _model.transcribe(
        audio_np,
        language=language,
        beam_size=5,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
        condition_on_previous_text=False,   # Changed. Was previously True. Process each window independently.
        repetition_penalty=1.2, # Changed from the previous value of 1.0. Tokens that have already appeared are penalized by 20%.
        no_repeat_ngram_size=3, # Changed. Previously 0. Strictly prohibits repetition in 3-grams.
    )
    segs = list(segments_gen)
    if not segs:
        return segs, float("-inf") # An empty result automatically loses in a dual comparison
    return segs, sum(s.avg_logprob for s in segs) / len(segs)
```

---

##### 2-2) Phantom Subtitles — VAD Pre-filter

> 

**Optimization Target: Hallucinations in silent intervals (most effective)**

**The primary cause of hallucinations is segments without speech**. 

Therefore, if silent or BGM segments are excluded from the ASR process from the outset, most of the problems disappear. We used Silero VAD to extract only the speech segments and passed them to the ASR model.

We also adjusted the parameters to suit the Korean language.

```python
# worker/worker-prep_stt/lib/audio/vad.py
# Line 26-28, 46-63

# Utterance Length Constraints — Balancing LID Accuracy and Post-Processing Load
MIN_SPEECH_S = 1.0     # If too short, LID becomes inaccurate (monosyllabic hallucinations like "Yeah")
MAX_SPEECH_S = 30.0    # Too long causes processing overhead (Whisper 30-second window limit)
MIN_SILENCE_S = 0.3    # Silences shorter than this are ignored (adjacent utterances are merged)


> def detect(audio_np: np.ndarray, sr: int = 16000) - list[tuple[float, float]]:
    """Extracts timestamps for speech segments. Returns: [(start_sec, end_sec), ...]"""
    if _model is None:
        load_model()
    audio_t = torch.from_numpy(audio_np).float()
    ts_list = _get_speech_timestamps(
        audio_t, _model, sampling_rate=sr,
        min_speech_duration_ms=int(MIN_SPEECH_S * 1000),
        max_speech_duration_s=MAX_SPEECH_S,
        min_silence_duration_ms=int(MIN_SILENCE_S * 1000),
    )
    return [(t["start"] / sr, t["end"] / sr) for t in ts_list]
```

---

##### 2-3) Low-Confidence Cut — MIN_LOGPROB

> 

**Optimization Target: Catch-all hallucinations**

Even so, some hallucinations still slipped through. Subtitles like `Thank you` passed through without issue. So I filtered the **transcription results** one more time—if the average log-likelihood of a segment is `avg_logprob < -1.0` (probability of about 37%), I discard it. This is the final net to catch hallucinations spewed without confidence.

---

#### 3. Language Misclassification

From here on, these are not “hallucinations” but **“errors caused by selecting the wrong language”**. These are gates unique to this project, tailored specifically for Korean-language main content.

##### 3-1) Low LID Confidence → Force Korean

> 

**Optimization Target: Incorrect language classification of short utterances**

If the language detection probability is below `0.5` and the result is a non-Korean language, it is forced to Korean. 

A value like prob 0.23 means “ko/ja/zh are all similar = the model cannot tell.” For content primarily in Korean, **assuming Korean when the model is uncertain was the safest approach**.

```python
# worker/worker-prep_stt/lib/service/stt_service.py
# Line 162-184

def _classify_languages(raw, ranges):
    """Each segment LID (raw) → language-specific time range group { lang: [(start_s, end_s), ...] }.

    Applied the ALLOWED_LANGS gate + LID_TRUST_PROB (low trust in non-primary language → force use of primary language).
    """
    sr, main = config.TARGET_SR, MAIN_LANG
    groups: dict[str, list] = {}
    for start_s, end_s in ranges:
        chunk = raw[int(start_s * sr):int(end_s * sr)]   # ← LID is taken from raw
        # Extraction using #detech_language
        lang, prob = whisper.detect_language(chunk)

        if lang is not in ALLOWED_LANGS: # Discard Tier 4-5
            continue
        if lang != main and prob < LID_TRUST_PROB: # Low trust → Force primary language
            lang = main
-------------------------------------------------------------------
# def_lang.py

# Allowed = Tier 1 ∪ 2 ∪ 3. Other than these
ALLOWED_LANGS: frozenset[str] = TIER1_LANGS | TIER2_LANGS | TIER3_LANGS
# (Tier 4: Weak, Tier 5: Not Supported) is skipped.

# Tier 1 — Highly accurate (WER < 5%). Virtually no hallucinations.
TIER1_LANGS:     "en", "es", "it", "fr", "de", "pt"

# Tier 2 — Good (WER 5–10%). Main coverage (including Korean). Requires post-processing but is reliable.
TIER2_LANGS:     "ko", "ja", "zh", "ru", "nl", "pl", "tr", "ca", "uk"

# Tier 3 — Moderate (WER 10–20%). Accept with caution — short utterances may be hallucinations.
TIER3_LANGS:     "ar", "he", "hi", "id", "ms", "vi", "el", "hu", "cs", "fi", "sv", "da", "no"


```

---

##### 3-2) dual transcribe — ko vs. detected language

> 

**Optimization Target: Acoustic Confusion Between ko / ja / zh**

If a utterance shorter than 3 seconds is detected as a non-Korean language, transcribe it **both as Korean and as the detected language**, then adopt the one with the higher `avg_logprob` value. If both values are below -0.6, it is treated as noise and discarded. This is a mechanism to prevent 12-second Korean utterances from being misclassified as Japanese or Chinese based on acoustic features.

```python
# poc/poc-stt-bench/lib/audio/whisper/whisper_stt.py
# Lines 60–61 (constant), 175–194 (dual branch)

SHORT_SEG_S = 3.0 # If shorter than this and LID != ko, then → dual transcribe
MIN_DUAL_LOGPROB = -0.6  # If both values are below this → drop (hallucination/noise)

# ── Inside transcribe(), looping through each segment ──
chunk_dur = end_s - start_s
if chunk_dur < SHORT_SEG_S and lang_code != MAIN_LANG:
    segs_main, lp_main = _do_transcribe(chunk_den, MAIN_LANG)   # In Korean
    segs_lid, lp_lid = _do_transcribe(chunk_den, lang_code)   # In the detected language

    if max(lp_main, lp_lid) < MIN_DUAL_LOGPROB: # Both are weak → noise
        continue
    if lp_main >= lp_lid: # Select the one with the higher logprob
        segments_out, chosen_lang = segs_main, MAIN_LANG
    else:
        segments_out, chosen_lang = segs_lid, lang_code
else:
    segments_out, _ = _do_transcribe(chunk_den, lang_code)
    chosen_lang = lang_code
```

---

##### 3-3) Hangul Ratio Gate

> 

**Optimization Target: Kana and Kanji Token Hallucinations**

If the speech is recognized as Korean but the proportion of Hangul in the result text is less than `30%`, it is discarded. This accurately filters out cases where Whisper outputs Kana and Kanji tokens as hallucinations in Korean mode.

```python
# poc/poc-stt-bench/lib/audio/whisper/whisper_stt.py
# Line 63 (constant), 88–94 (_hangul_ratio), 196–215 (post-processing loop)

KO_MIN_HANGUL_RATIO = 0.3

# ── Post-processing Loop — Catches hallucinations missed by the default options using its own gate ──
for seg in segments_out:
    text = (seg.text or "").strip()
    if not text:
        continue

    if seg.avg_logprob < MIN_LOGPROB: # 2-3. Low-confidence cut (-1.0)
        continue
    if dur < MIN_SEG_S: # Segment is too short; cut it
        continue
    if chosen_lang == MAIN_LANG: # 3-3. Korean Language Threshold
        if _hangul_ratio(text) < KO_MIN_HANGUL_RATIO:    # Less than 0.3
            continue
            
> def _hangul_ratio(text: str) - float:
    """The ratio of Korean syllables to alphanumeric characters (excluding spaces and punctuation). If the denominator is 0, the value is 1.0 (validation skipped)."""
    chars = [c for c in text if c.isalnum()]
    if not chars:
        return 1.0
    return sum(1 for c in chars if '가' <= c <= '힣') / len(chars)
```

> 

For reference, language tiering has also been implemented. Based on faster-whisper’s WER by language, only Tier 13 is allowed (Korean is Tier 2), and sections detected as other weaker languages are skipped entirely.

These gates are rules I created one by one while actually reviewing Korean content—rules not found in the official documentation. **"What hallucinations were observed → and which gate blocked them"** is the essence of this project’s optimization.

---

#### 4. Speed — and Conflicts Between Axes

> 

**Optimization Target: RTF (Processing Time / Audio Length)**

During the proof-of-concept (PoC) phase, accuracy was the primary goal, so speech segments were processed sequentially, one by one. Speed wasn’t a concern. However, for production, speed is the top priority (due to HTTP blocking), so the architecture had to be changed.

- **Batch Inference** — Load 16 30-second windows onto the GPU in parallel using `BatchedInferencePipeline`.
- **Silence Streams by Language** — Create full-length streams where segments outside the target language are filled with 0 (silence), enabling batch transcription for each language at once. Since the internal VAD skips silence, only speech in that language is recognized.

As a result, **RTF ≈ 0.042** — 1 hour of input is processed in approximately 150 seconds.

```python
# worker/worker-prep_stt/lib/service/stt_service.py
# Line 187-205

def _transcribe_batched(den, groups):
    """Create a "stream of the total length with sections outside that language silenced" for each language and perform batch transcription.

    Since the internal VAD skips silence, it recognizes only speech in that language, and the timestamp remains the same as the original time.
    """
    sr = config.TARGET_SR
    out = []
    for lang, lang_ranges in groups.items():
        # 1. Complete Silence
        stream = np.zeros_like(den)  
        # 2. Restore only the language segment in question 
        for start_s, end_s in lang_ranges:              
            i, j = int(start_s * sr), int(end_s * sr)
            stream[i:j] = den[i:j]
        words = whisper.transcribe_batched(stream, language=lang)
        for w in words:
            w["lang"] = lang
        out.extend(words)
    return out
```

The silent stream works thanks to `vad_filter=True`. Since the internal VAD skips entire segments filled with 0s, even when a full-length stream is fed in, the actual computation is limited to the utterances in that language.

```python
# worker/worker-prep_stt/lib/audio/whisper.py
# Line 26, 41, 67-80

BATCH_SIZE = 16   # Number of 30-second windows loaded onto the GPU simultaneously
_batched = BatchedInferencePipeline(model=_model)

segments_gen, _info = _batched.transcribe(
    audio,
    language=language,
    batch_size=BATCH_SIZE,
    beam_size=5,
    condition_on_previous_text=False,
    repetition_penalty=1.2,
    no_repeat_ngram_size=3,
    vad_filter=True, # Skip silent intervals (key to handling silent streams)
    word_timestamps=True,   # Word-level timestamps → The caller must resegment based on speaker/sentence
)
```

#### Conclusion

---

`large-v3` was the starting point. Four key factors drove the improvement in Korean speech recognition quality.

- **① Accuracy** — LID is raw, ASR is denoised (95.2% vs. 93.4%)
- **② Hallucination Suppression** — Blocking nonexistent subtitles using iterative parameters, VAD, and logprob
- **③ Language Misclassification** — Reducing errors from a Korean perspective via LID enforcement, dual mode, and Korean text ratio
- **④ Speed** — RTF of 0.042 in batch mode; instead, deciding which gates to discard

Looking back, what took the most time wasn’t tweaking parameters, but figuring out **“why this hallucination occurred”** by analyzing the logs. Until I understood why `ご視聴ありがとうございました` appeared, no parameter adjustment was the solution. Conversely, once I knew the cause, the solution usually came down to just two or three lines of conditional code.

The parameters listed in the official documentation accounted for only half of the solution; the other half came from **rules I developed by actually analyzing Korean content**. I hope this trial-and-error process serves as a shortcut for others facing the same challenges.

---

#### Preview of the Next Post

I plan to write about building the RAG pipeline, as well as the speech analysis process and results.

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

