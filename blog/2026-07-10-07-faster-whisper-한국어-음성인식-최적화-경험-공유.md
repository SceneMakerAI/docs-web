---
title: "07_faster-whisper 한국어 음성인식 최적화 경험 공유"
date: 2026-07-10
slug: 4
authors: [sbin]
description: "이 글은 음성을 글자 변환  (Speech to Text) 하는 과정을 구체적으로 명시한 글이다"
last_update:
  date: 2026-07-15
---

### 들어가며

---

faster-whisper-large-v3 로 음성 인식 작업을 진행하면서, 최적화 작업까지 진행하였다.

<!--truncate-->

간단히 요약하면 

1. transcribe 실행 하여 Specch-to-Text 진행. segment 결과 추출
2. for 루프 검사, 결과물 필터하여 모델 최적화

라고 할 수 있다. 


최적화 경험을 아래에 기재해보겠다.

---

### 1. transcribe 

```python
# poc-stt-bench/ib/audio/whisper/whisper_stt.py
# Line 97

def _do_transcribe(audio_np: np.ndarray, language: str) -> tuple[list, float]:
    """Call faster-whisper transcribe. Returns segments (list) + mean avg_logprob.

    When segments are empty, logprob = -inf (automatic loss in dual comparison).
    """
    segments_gen, _info = _model.transcribe(
        audio_np,
        language=language,
        beam_size=5,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
        condition_on_previous_text=False,
        repetition_penalty=1.2,
        no_repeat_ngram_size=3,
    )
    segs = list(segments_gen)
    if not segs:
        return segs, float("-inf")
    return segs, sum(s.avg_logprob for s in segs) / len(segs)
```

- 해당 파라미터 값 (beam_size, log_prob_threshold 등) 조회 결과, 패키지 함수 시그니처에 있는 것과 동일함을 확인
  - 시그니처란, 해당 오픈 소스에서 설정한 값을 의미

  - PoC 에서도 동일하게 진행


### 2. 결과물 필터

---

있을때와 없을때 비교


---

2-1) # 게이트 1 — VAD pre-filter

2-2) # 게이트 3- LID_TRUST_PROB

2-3) # 게이트 4 — dual transcribe + MIN_DUAL_LOGPROB (-0.6)

2-4) # 게이트 2 — MIN_LOGPROB (-1.0)

2-5)  # 게이트 5 — 한글 char 비율 게이트 (30%)

```python
# poc-stt-bench/ib/audio/whisper/whisper_stt.py


# 게이트 1 — VAD pre-filter
# poc-stt-bench/ib/audio/whisper/whisper_stt.py
# Line 148
    # ── 1) VAD (raw)
    speech_ranges = vad.detect(raw_np, sr=TARGET_SR)
    log.info(f"audio {total_sec:.1f}s → VAD {len(speech_ranges)} speech segments")

    # ── 2) Per-speech LID(raw) + ASR(denoised)
    all_segments: list[dict] = []
    for start_s, end_s in speech_ranges:
        s_idx = int(start_s * TARGET_SR)
        e_idx = int(end_s * TARGET_SR)

# Line 170
        # A low prob like 0.23 means ko/de/ja/zh are all comparable = the model doesn't know -> ko is the natural assumption

# 게이트 3- LID_TRUST_PROB
LID_TRUST_PROB = 0.5     # LID prob below this + non-main lang -> force MAIN_LANG (LID itself untrustworthy)

        if lang_code != MAIN_LANG and prob < LID_TRUST_PROB:
            log.info(f"    LID {lang_code}={prob:.2f} < {LID_TRUST_PROB} → {MAIN_LANG} 강제")
            lang_code = MAIN_LANG
            
# 게이트 4 — dual transcribe + MIN_DUAL_LOGPROB (-0.6)
MIN_DUAL_LOGPROB = -0.6  # if both dual sides fall below this -> drop (hallucination/noise)
SHORT_SEG_S = 3.0        # below this duration and LID != MAIN_LANG -> dual transcribe

        # 2c) transcribe — dual compare (ko vs lid) when short speech + non-main lang
        chunk_dur = end_s - start_s
        if chunk_dur < SHORT_SEG_S and lang_code != MAIN_LANG:
            segs_main, lp_main = _do_transcribe(chunk_den, MAIN_LANG)
            segs_lid, lp_lid = _do_transcribe(chunk_den, lang_code)
            if max(lp_main, lp_lid) < MIN_DUAL_LOGPROB:
                log.info(f"    dual [{_hms(start_s)}~{_hms(end_s)}|{chunk_dur:.1f}s] "
                         f"lp({MAIN_LANG})={lp_main:.2f}, lp({lang_code})={lp_lid:.2f} → 양쪽 약함, drop")
                continue
            if lp_main >= lp_lid:
                segments_out, chosen_lang = segs_main, MAIN_LANG
                log.info(f"    dual [{_hms(start_s)}~{_hms(end_s)}|{chunk_dur:.1f}s] "
                         f"lp({MAIN_LANG})={lp_main:.2f} ≥ lp({lang_code})={lp_lid:.2f} → {MAIN_LANG}")
            else:
                segments_out, chosen_lang = segs_lid, lang_code
                log.info(f"    dual [{_hms(start_s)}~{_hms(end_s)}|{chunk_dur:.1f}s] "
                         f"lp({lang_code})={lp_lid:.2f} > lp({MAIN_LANG})={lp_main:.2f} → {lang_code}")
        else:
            segments_out, _ = _do_transcribe(chunk_den, lang_code)
            chosen_lang = lang_code
            
# Line 197
        for seg in segments_out:
            text = (seg.text or "").strip()
            if not text:
                continue
            abs_start = float(seg.start) + start_s
            abs_end = float(seg.end) + start_s
            dur = abs_end - abs_start
# 게이트 2 — MIN_LOGPROB (-1.0)
MIN_LOGPROB = -1.0       # drop if avg_logprob < this. catch-all for hallucinations
MIN_SEG_S = 0.2          # drop segments shorter than this. preserves short interjections like "네"/"그렇죠"

            if seg.avg_logprob < MIN_LOGPROB:
                log.info(f"    drop [{_hms(abs_start)}~{_hms(abs_end)}|{chosen_lang}] lp={seg.avg_logprob:.2f} | {text[:30]}")
                continue
            if dur < MIN_SEG_S:
                log.info(f"    drop [{_hms(abs_start)}~{_hms(abs_end)}|{chosen_lang}] dur={dur:.2f}s | {text[:30]}")
                continue
# 게이트 5 — 한글 char 비율 게이트 (30%)
# Avoids 1-2s segments in Korean content being misclassified as ja/zh.
MAIN_LANG = "ko"
KO_MIN_HANGUL_RATIO = 0.3  # if Hangul ratio of ko transcription is below this -> drop. Cuts Whisper outputting kana/hanja hallucinations in ko mode

            if chosen_lang == MAIN_LANG:
                ratio = _hangul_ratio(text)
                if ratio < KO_MIN_HANGUL_RATIO:
                    log.info(f"    drop [{_hms(abs_start)}~{_hms(abs_end)}|{chosen_lang}] hangul={ratio:.0%} | {text[:30]}")
                    continue
# 통과한 것만 채택
            all_segments.append({
                "start": abs_start,
                "end": abs_end,
                "text": text,
                "speaker": None,
                "language": chosen_lang,
            })
            
  
```



---


