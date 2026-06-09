---
title: "[PoC Proposal] Development of an Ultra-High-Speed, Ultra-High-Quality Multilingual AI Subtitling System"
sidebar_position: 1
slug: "1"
last_update:
  date: 2026-06-08
---

## 1. Overview

### 1.1 Objective

A Proof of Concept for **comparing STT (Speech-to-Text) systems** to automatically generate multilingual subtitles for video content.

**Key Question**: For Korean video content across various domains, which open-source STT system is best suited for subtitle production?

**Systems Under Comparison**

<table>
<thead><tr>
<th>System</th>
<th>Model</th>
<th>Remarks</th>
</tr></thead>
<tbody>
<tr>
<th>Whisper</th>
<td><code>Systran/faster-whisper-large-v3</code></td>
<td>CTranslate2 conversion of OpenAI Whisper large-v3 (faster-whisper backend)</td>
</tr>
<tr>
<th>Qwen</th>
<td><code>Qwen3-ASR-1.7B</code> + <code>Qwen3-ForcedAligner-0.6B</code></td>
<td>Alibaba, ASR + separate word timestamps</td>
</tr>
</tbody></table>

table Initially, Gemini STT was also included in the comparison, but it was deemed unsuitable for subtitling due to an issue where timestamp accuracy drifted by minutes and was subsequently excluded. Gemini is used solely in the role of a judge.

**Evaluation Method**

- Gemini 3.5 Flash compares the audio with the STT output segments from each system and assigns a score between -3 and 3 points
- Aggregates score distributions by content/system + subtitle usability rate (≥0 points)
- Derives system recommendations by domain

**Deliverables**

- Content × System Comparison Report (`output/report.csv` )
- Configuration of hallucination/misrecognition handling gates (5 types on the Whisper side)
- Recommended architecture for the production phase

---

### 1.2 Scope

#### Included (Scope of this POC)

- Mono WAV input → Subtitle segments (text + time interval + language code)
- Noise removal (DeepFilterNet v3, atten_lim_db = -30)
- Speech segment detection (Silero VAD)
- Multilingual automatic detection (Whisper LID)
- Multilingual ASR (Whisper / Qwen, 28 / 11 languages)
- Hallucination handling gate (see Chapter 5 for details)
- Gemini Judge evaluation + score aggregation report

#### Not Included (Production-Stage Tasks)

| Item | Reason / Future Action |
| --- | --- |
| Video → WAV Extraction | Assumed to be handled via external preprocessing. Outside the scope of this POC |
| Speaker Segmentation (diarize) | Can be integrated separately via PyAnnote (common audio → single call followed by segment matching). Currently `speaker = None` |
| SRT / VTT Output Format | Only internal `transcript_md` format. Conversion is simple |
| Gemini Correction Stage | Evaluation only. Correction follows production diagram (see Chapter 8) |
| FastAPI / HTTP API | Batch processing only (direct execution of `main.py` / `main_qwen.py`) |
| Job queue (asyncio.Queue, etc.) | Single-process sequential processing |
| Concurrent requests / Multiple clients | Resolved via dynamic batching in the production diagram (Chapter 8) |

---

### 1.3 Evaluation Content Set

We used six types of Korean video content (one title per genre). Pre-processed 16kHz mono WAV files, duration 30 minutes to 2 hours, no ground truth labels (using the match rate proxy method in Section 2.3). 

Although Korean is the primary language, the presence of foreign languages and background noise varies by genre.

| Category | Broadcast | Duration | Characteristics | URL |
| --- | --- | --- | --- | --- |
| News | KBS 9 News | 48:30 | Fast speech, loud BGM/audience cheering, longest content | [https://www.youtube.com/watch?v=rX1P-jOoNmM](https://www.youtube.com/watch?v=rX1P-jOoNmM) |
| Documentary | Superfish Part 1 | 58:40 | Calm narration, some foreign-language interviews | [https://www.youtube.com/watch?v=iNbWqC1iqKw](https://www.youtube.com/watch?v=iNbWqC1iqKw) |
| Drama | KBS Winter Sonata | 1:04:52 | Standard dialogue, background music | [https://www.youtube.com/watch?v=irVKEhb9g8M](https://www.youtube.com/watch?v=irVKEhb9g8M) |
| Historical Drama | Taejo Wang Geon | 54:10 | Multiple speakers, subtitles, sound effects, rapid tone changes | [https://www.youtube.com/watch?v=nmlE2iPWLGM](https://www.youtube.com/watch?v=nmlE2iPWLGM) |
| Variety | Business Trip 15 Days X Starship National Sports Festival Full Version | 1:00:06 | Formal language/archaic expressions, high frequency of Sino-Korean terms | [https://www.youtube.com/watch?v=6wJGpi1nkCg](https://www.youtube.com/watch?v=6wJGpi1nkCg) |
| Sports | 2009 KBO League Korean Series Game 7 | 1:55:22 | Clear pronunciation, mixed with foreign-language interviews/reports | [https://www.youtube.com/watch?v=fP1QEs1Uj5U](https://www.youtube.com/watch?v=fP1QEs1Uj5U) |

#### Summary of Challenges by Content Type

- **baseball**  — Highest risk of hallucinations (BGM/crowd cheers), frequent short interjections
- **docu / news**  — Foreign-language interviews → Risk of misidentifying LID in short utterances
- **hist_drama**  — Sino-Korean terms/formal language → Models tend to hallucinate Chinese/Japanese tokens
- **drama / entertain**  — Multiple speakers + BGM → Risk of false positives in normal speech

**Project Overview:**

Validation of a subtitling pipeline tailored to complex media audio environments such as broadcasts, movies, variety shows, and sports

**Validation Environment:**

Base accelerated environment based on a single NVIDIA RTX 4090 (24GB)

---

## 2. Pipeline Architecture

### 2.1 Overall Flow

```
원본 wav (mono, 16kHz)
   │
   ▼
[1] denoise — DeepFilterNet v3
   │   ↳ output/1_denoise/<stem>.wav  (캐시, 양쪽 시스템 공유)
   ▼
[2] transcribe — 시스템별 (Whisper / Qwen)
   │   ↳ output/{system}/2_transcribe/<stem>.md
   ▼
[3] evaluate — Gemini judge
   │   ↳ output/{system}/evaluate/<stem>.csv
   ▼
[4] report — 시스템 비교 집계
       ↳ output/report.csv
```

Entry point:

<table>
<thead><tr>
<th>Step</th>
<th>Command</th>
</tr></thead>
<tbody>
<tr>
<td>transcribe — Whisper</td>
<td><code>.venv/bin/python main.py</code></td>
</tr>
<tr>
<td>transcribe — Qwen</td>
<td><code>.venv-qwen/bin/python main_qwen.py</code></td>
</tr>
<tr>
<td>evaluate</td>
<td><code>.venv/bin/python evaluate.py [whisper|qwen|all]</code></td>
</tr>
<tr>
<td>report</td>
<td><code>.venv/bin/python report.py</code></td>
</tr>
</tbody></table>

## 2.2 Directory / Output Structure

```
output/
├── 1_denoise/<stem>.wav          # DF 결과 (양쪽 공유, 캐시)
├── whisper/
│   ├── 2_transcribe/<stem>.md    # STT 결과
│   ├── evaluate/<stem>.csv       # Gemini 채점
│   └── timings.csv               # duration / transcribe time / RTF
├── qwen/
│   └── (동일 구조)
└── report.csv                    # 시스템 × 콘텐츠 종합 비교
```

**transcribe MD** — 1 line = 1 segment, custom format:

`[00:02:57.1~00:02:58.4|S???|ko] 넌 가가멜이 무섭지도 않아?`

`S???` is the speaker (currently an unintegrated placeholder). lang is ISO 639-1.

## 3. Core Components

Composed of 5 components. All use GPU (cuda:0). Warm-up runs once at system startup.

| Component | Role | Library / Model |
| --- | --- | --- |
| Denoise | BGM/noise removal | DeepFilterNet v3 |
| VAD | Speech Segment Detection | Silero VAD |
| LID | Automatic Language Detection | Whisper `detect_language`  (large-v3) |
| ASR (Whisper) | Korean/Multilingual Transcription | faster-whisper large-v3 (Systran) |
| ASR (Qwen) | Korean/Multilingual Transcription + Word Timestamp | Qwen3-ASR-1.7B + ForcedAligner-0.6B |
| Judge | Accuracy Scoring (-3 to 3) | Gemini 3.5 Flash |

---

### 3.1 Denoise — DeepFilterNet v3

| Item | Value |
| --- | --- |
| Model | DeepFilterNet v3 (built-in in pip package) |
| Input/Output Sample Rate | Input: Any → Output: 48 kHz int16 |
| `atten_lim_db` | **-30**  (Intensity reduction — Preserves singing/general speech) |
| Chunk processing | Divided into 30-second segments (to avoid VRAM OOM when processing long audio spectrograms) |
| Cache | `output/1_denoise/<stem>.wav`  — Shared between both systems; reused when re-executing the same stem |

**Why atten_lim_db = -30?**  
At full power (`None` ), singing or soft speech is cut off as noise, causing ASR omissions. Limiting intensity to -30dB = ↑ speech preservation.

---

### 3.2 VAD — Silero VAD

| Item | Value |
| --- | --- |
| Model | Silero VAD (`snakers4/silero-vad` , torch.hub) |
| Input | **raw audio**  (Method 2 — to avoid the impact of denoising variations) |
| Output | List of utterance segments `[(start_s, end_s), ...]` |
| Environment Sharing | Same venv for both Whisper and Qwen |

**Role** — The first line of defense against hallucination. Simply preventing silence/BGM segments from being sent to ASR significantly reduces hallucinations (industry standard practice).

---

### 3.3 LID — Whisper `detect_language`

| Item | Value |
| --- | --- |
| Model | Whisper large-v3 (multilingual, `mobiuslabsgmbh/faster-whisper-large-v3-turbo` ) |
| Input | **raw audio chunk**  (speech units segmented by VAD) |
| Output | `(lang_code, prob, all_probs)`  — Top language + probability + probability dictionary for all languages |
| Invocation frequency | Once per utterance chunk (not the entire audio) |

**POC Accuracy Comparison**

| LID Method | raw | denoised |
| --- | --- | --- |
| Whisper `detect_language` | **95.2%**  ✅ | 93.4% |
| VoxLingua107 | 88.9% | 87.0% |

→ **Adopted Whisper LID**. Requires ~1.5GB of additional VRAM, but since it only calls `detect_language` (encoder forward + decoder 1 step), it is lightweight.

**Qwen also uses the same LID** — more accurate than Voxlingua107.

---

### 3.4 ASR

#### 3.4.1 Whisper — faster-whisper large-v3

| Item | Value |
| --- | --- |
| Model | `Systran/faster-whisper-large-v3`  (CT2 conversion of OpenAI Whisper large-v3) |
| Backend | faster-whisper (CTranslate2) |
| Supported languages | Only **Tier 1+2+3 (28)** out of 99 allowed — others are skipped |
| Input | denoised audio chunk |
| Invocation options | `beam_size=5` , `condition_on_previous_text=False` , `repetition_penalty=1.2` , `no_repeat_ngram_size=3` |
| Hallucination post-processing | 5 types of gates (see Figure 5) |

> Use **non-turbo (32-layer)** instead of turbo (4-layer decoder). Accuracy ↑, speed 2–3x ↓. Prioritize accuracy at the POC stage.

#### 3.4.2 Qwen Side — Qwen3-ASR-1.7B + ForcedAligner-0.6B

| Item | Value |
| --- | --- |
| ASR Model | `Qwen3-ASR-1.7B` |
| Timestamp Model | `Qwen3-ForcedAligner-0.6B`  — word-level timestamp separation |
| Backend | qwen-asr (transformers 4.57, torch 2.8) |
| Supported Langs | **ALIGNER_LANGS (11)**  — ko/en/ja/zh/yue/it/es/fr/de/pt/ru |
| Input | denoised audio chunk |
| LID | Whisper detect_language (does not use custom LID — more accurate than Voxlingua107 at 88.9%) |
| Short utterance handling | `main_lang = "ko"`  Hardcoded + short utterance adjacent lang override |

> Separated into venv to avoid dependency conflicts between Whisper and Qwen (`.venv` / `.venv-qwen` ).

---

### 3.5 Judge — Gemini 3.5 Flash

| Item | Value |
| --- | --- |
| Model | `gemini-3.5-flash` |
| Reference | Direct audio (system-independent) |
| Scoring System | -3 to 3 (based on correctability — see Chapter 6) |
| Audio Processing | Single upload + **caching**  (TTL 1 hour, 75% cost reduction) |
| Chunk Size | 20 segments per call (to avoid response token limits) |
| Retry | 1 retry if response segment count mismatches (to compensate for missing end of Flash response) |
| Response schema | `list[ScoreItem]`  (TypedDict) — JSON schema enforced |
| Cost estimate | 6 content items × 2 systems ≈ $1–2 |

**Why use Gemini as the judge?**

- Ensuring objectivity in system comparisons — The same evaluator (Gemini) listens to the same audio and scores the STT results from both systems
- Meaning-based scoring is closer to subtitle usability than text matching (e.g., WER)
- Audio is the ground truth — Evaluation is possible even if segment segmentation differs across STT systems

---

## 4. System Design + Hallucination Handling

The key trial-and-error in the POC was mostly on the Whisper side regarding hallucination handling. The Qwen side focused mainly on language correction patterns.

### 4.1 Whisper Side

#### Model / Basic Settings

| Item | Value |
| --- | --- |
| Model | `Systran/faster-whisper-large-v3`  (single multilingual) |
| Supported language gate | `ALLOWED_LANGS`  — Tier 1+2+3 (28 languages), others skipped |
| Korean fine-tune branch | **Removed**  — Confirmed low accuracy in the documentation domain |
| Decode options | `beam_size=5` , `condition_on_previous_text=False` , `repetition_penalty=1.2` , `no_repeat_ngram_size=3` |

#### Supported Languages (Tier Classification)

Since Whisper is trained on different amounts of data for each language, lower tiers exhibit more severe hallucinations. At Tier 4, translation is nearly impossible, so this tier should be skipped 

- Tier-1 (Word Error Rate < 5%)
  -   English,  Spanish, Italian, French, German, Portuguese

- Tier-2 (WER <5-8%)
  - Korean, Japanese, Chinese, Russian, Polish, Dutch, Turkish, Catalan, Ukrainian

- Tier-3 (WER < 10–20%)
  - Arabic (significant variation by dialect), Hebrew, Hindi, Indonesian, Malay, Vietnamese (weak tones), Greek, Hungarian, Czech, Finnish, Swedish, Danish, Norwegian

- Tier-4 (DROP)
  - Thai, Lao, Khmer, Luxembourgish, Maltese, etc.

#### Three Hallucinations Patterns Identified

##### Gate 1 — VAD pre-filter

<table>
<tbody>
<tr>
<th>Abbreviation</th>
<td><strong>VAD = Voice Activity Detection</strong></td>
</tr>
<tr>
<th>Tool</th>
<td>Silero VAD (<code>snakers4/silero-vad</code>, torch.hub)</td>
</tr>
<tr>
<th>Input</th>
<td>raw audio (full)</td>
</tr>
<tr>
<th>Output</th>
<td>Speech segment <code>[(start_s, end_s), ...]</code></td>
</tr>
<tr>
<th>Action</th>
<td>Non-speech segments (silence/BGM/sound effects) are not sent to ASR</td>
</tr>
</tbody></table>

table*Why is this effective?** — The primary cause of Whisper hallucinations is **generating subtitle patterns learned from silence/BGM segments** (`ご視聴ありがとうございました`, `Thanks for watching`, etc.). This problem disappears entirely when only speech segments are input. Industry-standard tools like WhisperX and stable-ts follow the same pattern.

#### Gate 2 — MIN_LOGPROB (-1.0)

<table>
<tbody>
<tr>
<th>Definition</th>
<td><code>avg_logprob</code> = Average log probability of each transcribed token (per segment)</td>
</tr>
<tr>
<th>Meaning</th>
<td>The closer to 0, the more confident the model; the further into negative values, the less confident</td>
</tr>
<tr>
<th>Threshold</th>
<td><code>< -1.0</code> → segment drop</td>
</tr>
<tr>
<th>Cases detected</th>
<td>Hallucination catch-all (final line of defense against hallucinations not caught by gates 1/3/4)</td>
</tr>
</tbody></table>

table*Meaning of threshold -1.0** — Converted to log probability:

| `avg_logprob` | Average token probability | Interpretation |
| --- | --- | --- |
| -0.3 | 74% | Normal utterance (certain) |
| -0.5 | 61% | Normal utterance |
| -0.7 | 50% | Guesswork |
| **-1.0** | **37%** | **Hallucination region**  ← Threshold |
| -1.5 | 22% | Almost certain hallucination |

- Less than `1.0` = Average probability per token below 37% = Model generates tokens in an uncertain state = Risk of hallucination.

> Unlike the deprecated gate `no_speech_prob`, `avg_logprob` is less sensitive to BGM/denoise residuals → fewer false positives.

#### Gate 3 — LID_TRUST_PROB (0.5)

<table>
<tbody>
<tr>
<th>Abbreviation</th>
<td><strong>LID = Language Identification</strong> (automatic language detection)</td>
</tr>
<tr>
<th>Function</th>
<td>Whisper <code>detect_language()</code> → <code>(lang_code, prob, all_probs)</code> Return</td>
</tr>
<tr>
<th>Threshold</th>
<td><code>prob < 0.5</code> + If the detected language <code>MAIN_LANG (ko)</code> is not</td>
</tr>
<tr>
<th>Action</th>
<td><code>lang_code</code> to <code>MAIN_LANG (ko)</code> . Subsequently, transcribe as a single ko</td>
</tr>
</tbody></table>

table*Why 0.5?** — Cases like LID probability 0.23 = "sounds similar to ko/de/ja/zh" = LID itself is unreliable. Assuming Korean content → assuming ko is natural.

**Example — Actual baseball.wav log**

```
[01:18:43.3~01:18:44.4] LID de=0.23 → pass
    LID de=0.23 < 0.5 → ko 강제      ← 게이트 3 발동
```

If we had used the original LID result as-is, it would have transcribed as German → hallucination. Forced normalization to ko.

---

#### Gate 4 — dual transcribe + MIN_DUAL_LOGPROB (-0.6)

<table>
<tbody>
<tr>
<th>Conditions</th>
<td>Speech length <code>< 3초</code> + LID is non-ko (after passing Gate 3)</td>
</tr>
<tr>
<th>Action 1</th>
<td>Transcribe both ko and LID lang twice → respectively <code>avg_logprob</code> Calculation</td>
</tr>
<tr>
<th>Action 2</th>
<td><code>max(lp_ko, lp_lid)</code> Adopt the larger (more certain) lang</td>
</tr>
<tr>
<th>Action 3 (drop condition)</th>
<td><strong>Both lp </strong><code>< -0.6</code><strong> → Both suspected hallucinations → drop</strong></td>
</tr>
<tr>
<th>Cases where it is captured</th>
<td>ja/zh short hallucinations (1–2 second LID misclassification cases)</td>
</tr>
</tbody></table>

table*Why -0.6?** — Log probability around 50%. If both are below 50%, the model is unsure of either language = higher probability that the short audio is garbled or noise.

**Example — Actual baseball.wav log**

`dual [00:15:26.8~00:15:27.9|1.1s] lp(ko)=-0.89, lp(zh)=-0.71 → 양쪽 약함, drop`

`max(-0.71, -0.89) = -0.71 < -0.6` → drop. A case where, if the original LID had been zh, it would have resulted in a hallucination like `一观测者来交换`.

---

#### Gate 5 — Korean character ratio gate (30%)

<table>
<tbody>
<tr>
<th>Conditions</th>
<td><code>chosen_lang == "ko"</code> + Korean character ratio in the output text <code>< 30%</code></td>
</tr>
<tr>
<th>Behavior</th>
<td>Segment drop</td>
</tr>
<tr>
<th>Cases where it triggers</th>
<td>ko Forced transcription resulted in Japanese tokens (Whisper limitation)</td>
</tr>
</tbody></table>

table*Why 30%?** — Normal Korean speech typically has a Korean character ratio of 70%+ (even when mixed with numbers or English abbreviations). Less than 30% = effectively hallucinated Japanese/Kanji tokens.

**Calculating Hangul Ratio** — The ratio of Hangul syllables (ga-hit) among characters and numbers, excluding spaces and punctuation.

| text | Hangul Ratio | Result |
| --- | --- | --- |
| `生涯ゲスト` | 0% | drop |
| `ちょうちょだが。` | 0% | drop |
| `투수는 이승호, 오늘 투런홈런` | 100% | pass |
| `FA컵 결승` | 33% (FA=2, Cup Final=3) | pass (3% margin) |
| `MVP 수상` | 40% | pass |

> The hallucinations caught by this gate = the inherent limitations of the Whisper model itself. The closest method to prevent this using external code (drop only, cannot be corrected).

#### Drop Policy (Cases that cannot be salvaged)

**Case** — The audio is in Korean, but Whisper outputs Japanese tokens even in Korean mode  
**Principle** — "**Better to drop than to have incorrect subtitles**" → drop

---

#### Final Flow

```
audio_raw + audio_denoised
   │
   ▼  16kHz resample
   │
[VAD 게이트]  raw audio → 발화 구간 [(start, end), ...]
   │
   ▼  각 발화 chunk 마다
[LID]  Whisper.detect_language(raw chunk) → (lang, prob)
   │
   ▼  ALLOWED_LANGS 게이트 (Tier 1+2+3 외 skip)
   │
[LID_TRUST_PROB]  prob<0.5 + 비-ko → ko 강제
   │
   ▼
[transcribe 분기]
   ├─ 짧음(<3s) + 비-ko → dual (ko + lid)
   │   └─ max lp 채택. 양쪽 < -0.6 → drop
   └─ 그 외 → single (lid 그대로)
   │
   ▼  결과 segment loop
[후처리 게이트]
   ├─ avg_logprob < -1.0 → drop
   ├─ duration < 0.2s → drop
   └─ chosen=ko + 한글 < 30% → drop
   │
   ▼
segment 저장 (transcribe MD)
```

---

### 4.2 Qwen Side

#### Model / Default Settings

| Item | Value |
| --- | --- |
| ASR Model | `Qwen3-ASR-1.7B` |
| Timestamp Model | `Qwen3-ForcedAligner-0.6B` |
| Supported Languages | `ALIGNER_LANGS`  (11) — ko/en/ja/zh/yue/it/es/fr/de/pt/ru |
| LID | **Whisper LID adopted**  (POC 95.2% vs Voxlingua107 88.9%) |
| Batch | `max_inference_batch_size=8`  (4090 safety margin) |

#### Supported Languages

Qwen supports approximately 30 languages, but **Qwen3-ForcedAligner, which supports timestamps, can only distinguish 11 languages**

- Korean, Japanese, Chinese (Mandarin), Cantonese, English, Italian, Spanish, French, German, Portuguese, Russian

#### main_lang hardcoding + short utterance override

| Item | Behavior |
| --- | --- |
| `MAIN_LANG = "ko"` | Hardcoded (for consistency with Whisper). Main content in foreign languages can be reverted to majority decision during production |
| Short utterance (< 3s) override | If LID is inaccurate → Use the same language as the preceding/following utterance; otherwise, use `MAIN_LANG` |
| ALIGNER_LANGS gate | Languages other than the 11 → skip (timestamp not possible) |

#### Script-based automatic language correction

**Post-processing language correction based on character types in transcribed text** — Corrects language errors in LID/Qwen.

| Detected script | Corrected language |
| --- | --- |
| Hangul (가-힣) | ko |
| Kana (Hiragana/Katakana) | ja |
| Cyrillic | ru |
| Hanja only (no Kana/Hangul) | zh |
| Latin only + original Latin lang | Keep as is |
| Latin only + original ko/ja/zh/ru | en |
| No script detected (numbers/symbols) | Keep original lang |

→ Similar concept to Whisper’s “Hangul character ratio gate,” but **correction instead of dropping** (Qwen does not forcefully handle LID errors as ko; it simply corrects the lang).

---

## 5. Evaluation Method

Gemini 3.5 Flash compares the audio (ground truth) with the STT output segments to score them. System-independent (Whisper and Qwen are each evaluated using the same audio).

### 5.1 Scoring System (-3 to 3, based on correctability)

Rather than simple match/mismatch, the score reflects whether **"this segment can be salvaged in a subsequent correction stage (e.g., Gemini Correct)"**.

| Score | Name | Description | Example |
| --- | --- | --- | --- |
| **3** | OK | Same meaning, minor differences (spacing/typos/slight differences in particles) | "Aren't you even scared of Gagamel?" Matches correct answer |
| **2** | Same Meaning | Same meaning, different expression (synonyms/word order changes) | Correct answer "went" → STT "went" |
| **1** | Half/Filler | Half the core meaning, or short filler (1-2 characters, harmless) | "Uh," "Hmm," "Ah" / 50%+ chance of correction |
| **0** | Correctable | Sentence is incorrect but 20%+ chance of future correction | Misrecognition like "pitcher" → "sister-in-law" — can be restored via context |
| **-1** | Partially Correct | Only some words are correct, meaning mostly different (Difficult to correct) |  |
| **-2** | Hallucination | Generates text that looks like subtitles but has no corresponding audio | Silence + "Thank you for watching" / Arabic subtitle credits |
| **-3** | Completely Different | Audio speech exists but is completely unrelated to the text | Japanese interview but garbled Korean text |

#### Difference Between -2 and -3

| Category | Presence of Audio Speech | Text |
| --- | --- | --- |
| **-2 Hallucination** | ❌ No speech (silence/BGM) | Generates natural sentences resembling subtitles |
| **-3 Completely Different** | ✅ Speech present | Text completely different from spoken content |

---

### 5.2 Foreign Language +1 Adjustment

For segments in languages other than Korean (lang ≠ ko), add **+1 point** to the score (max 3 points).

| Before adjustment | After adjustment (Foreign Language) |
| --- | --- |
| 2 points | 3 points |
| 1 point | 2 points |
| 0 points | 1 point |
| -1 point | 0 points |
| -2 points | -1 point |
| -3 points | -2 points |

#### Reason

- The ASR system’s accuracy for foreign languages is lower than for Korean — our system’s foreign language processing (assuming Korean content) is best-effort
- English interviews may have some missing words or minor awkwardness → but viewers can still understand via subtitles
- Applying the same standards used for Korean subtitles to foreign languages would be too harsh

#### Example

```
audio: "I go to school"
STT  : "I go to the school"   ← 사소한 단어 추가
원래 점수: 2 (의미동일, 표현 다름)
보정 후 : 3 (외국어 +1)
```

### 5.3 Subtitle Usability Rate (≥0 points)

**Criterion** — If a segment score is 0 or higher, "usable as subtitles"

| Score | Subtitle Processing (during production) |
| --- | --- |
| 3, 2 | ✅ Use as-is |
| 1 | ✅ Refine using Gemini correction |
| 0 | ✅ Attempt to correct with Gemini (20%+ probability) |
| -1, -2, -3 | ❌ Drop (better to omit than to use incorrect subtitles) |

#### Quantitative Metrics

`자막 사용 가능률 = (점수 ≥ 0 인 segment 수) / 전체 segment 수 × 100%`

POC results (see Chapter 7) show that all system × content combinations achieved 90%+. = This suggests that our hallucination gate effectively preemptively blocked cases rated -1 to -3.

#### Why a 0-point threshold?

- Accepted subtitle candidates up to "incorrect but correctable (20%+ probability)"
- During production, attempted to actually retain segments with 20%+ probability at the Gemini correct stage
- For scores below 0, correction cost > value → drop

---

## 6. Results

Execution source: [https://github.com/SceneMakerAI/poc-stt-bench](https://github.com/SceneMakerAI/poc-stt-bench)

### 6.1 Execution Commands

```javascript
cd /usr/service/source/scenemaker/poc/poc-stt-bench

# (필요시) 기존 결과 정리 — denoise 캐시는 유지
\rm -rf output/whisper/2_transcribe output/whisper/evaluate output/whisper/timings.csv
\rm -rf output/qwen/2_transcribe output/qwen/evaluate output/qwen/timings.csv

# 1. Whisper STT
.venv/bin/python main.py

# 2. Qwen STT (별도 venv)
.venv-qwen/bin/python main_qwen.py

# 3. Gemini judge 평가 (whisper + qwen)
.venv/bin/python evaluate.py all

# 4. 종합 비교 리포트
.venv/bin/python report.py
```

Output by processing stage

| Stage | Output |
| --- | --- |
| (1) Whisper | `output/whisper/2_transcribe/*.md`  + `timings.csv` |
| (2) Qwen | `output/qwen/2_transcribe/*.md`  + `timings.csv` |
| (3) evaluate | `output/{whisper,qwen}/evaluate/*.csv` |
| (4) report | `output/report.csv`   |

### 6.2 Comparison of Processing Times

#### 6.2.1 Transcription Times by Content (excluding denoising)

| Content | Length | Whisper (RTF) | Qwen (RTF) | Qwen Speed Comparison |
| --- | --- | --- | --- | --- |
| baseball | 1h 55m | 345.9s (0.050) | 309.0s (0.045) | 1.12× ↑ |
| docu | 58m | 118.2s (0.034) | 54.4s (0.015) | **2.17× ↑** |
| drama | 1h 5m | 88.3s (0.023) | 49.1s (0.013) | **1.80× ↑** |
| entertainment | 1h | 159.8s (0.044) | 193.9s (0.054) | 0.82× (Whisper dominates) |
| historical_drama | 54m | 111.5s (0.034) | 54.1s (0.017) | **2.06× ↑** |
| news | 48m | 149.5s (0.051) | 80.5s (0.028) | 1.86× ↑ |

#### 6.2.2 Observations

- **Qwen is generally 1.8 to 2.2 times faster**  — Qwen3-ASR processes chunks in batches (`max_inference_batch_size=8` )
- **entertain**  is the only category where Whisper outperforms — Qwen’s ForcedAligner produces inaccurate word timestamps in content with many sound effects/interjections → estimated increased reprocessing cost
- **Baseball**  shows similar performance for both systems — Whisper has 1.6 times more segments than Qwen, distributing the processing load (1983 vs. 1250)
- RTF < 0.06 → Both are **more than 20 times faster** than real-time  (ample headroom for production throughput)

### 6.3 Comparison of vRAM Usage

| Component | Whisper | Qwen | Notes |
| --- | --- | --- | --- |
| **ASR Model** | 3 GB<br>(`Systran/faster-whisper-large-v3`, CT2 float16) | 3.5 GB<br>(`Qwen3-ASR-1.7B`, bfloat16, batch=8) |  |
| **Timestamp Model** | — (Included in ASR) | 1.5 GB<br>(`Qwen3-ForcedAligner-0.6B` ) | Word-level timestamp |
| **LID Model** | — (Reuses same instance as ASR) | 1.5 GB<br>(`large-v3-turbo` , float16) | Whisper side uses ASR model to process up to LID |
| **Denoise** | 0.5 GB (DeepFilterNet v3) | 0.5 GB (DeepFilterNet v3) | Common to both |
| **VAD** | 10 MB (Silero VAD) | 10 MB (Silero VAD) | Common to both |
| **Total** | **~3.5 GB** | **~7 GB** |  |
| **GPU Usage (4090 24GB)** | 15% | 30% |  |

### **6.4 Comparison of Quality Results**

#### Summary Table

| Content | Whisper (avg / % used / -3%) | Qwen (avg / % used / -3%) | Winner |
| --- | --- | --- | --- |
| **baseball** | 2.72 / 98.6% / 0.7% | 2.74 / 99.4% / 0.2% | Qwen (slight) |
| **docu** | **2.73**  / **97.6%**  / 1.6% | 2.41 / 92.3% / **6.0%** | 🏆 **Whisper**  (Significant Difference) |
| **drama** | 2.69 / 98.0% / 1.5% | 2.69 / 98.5% / 1.2% | Tie |
| **entertain** | 2.64 / 97.1% / 1.7% | 2.55 / 97.3% / 1.3% | Whisper (Slight) |
| **historical_drama** | 2.58 / 96.1% / 2.4% | 2.52 / 96.1% / 1.1% | Tied |
| **news** | 2.92 / 99.5% / 0.4% | 2.85 / 98.7% / 0.8% | Whisper (Minor) |

#### Comparison of Segment Counts

| Content | Whisper | Qwen | Whisper / Qwen |
| --- | --- | --- | --- |
| baseball | 1983 | 1250 | 1.59× |
| docu | 371 | 401 | 0.93× |
| drama | 402 | 336 | 1.20× |
| entertain | 1150 | 848 | 1.36× |
| hist_drama | 460 | 459 | 1.00× |
| news | 731 | 471 | 1.55× |

### 6.5 Overall Evaluation

1. **When selecting a single system → Whisper recommended**
   - Stable accuracy (superior or on par in 5 out of 6 content categories)

   - Half the VRAM (3.5 GB vs. 7 GB)

   - Production-ready with 5 hallucination gates

   - Clear advantage in risky content like documentaries

2. **Qwen’s Strengths**
   - **Speed**  — 1.8–2.2 times faster than Whisper (batch processing) (Note: Whisper also supports some batch processing)

   - Fast-paced content with strong background noise, such as **baseball**

#### Decision Matrix

| Priority | Choice |
| --- | --- |
| Accuracy + Simplicity | **Whisper alone** |
| Maximum throughput + Good accuracy | Qwen alone + batch tuning |
| Minimum cost (single GPU, small model) | Consider Whisper Turbo as well (accuracy trade-off) |

