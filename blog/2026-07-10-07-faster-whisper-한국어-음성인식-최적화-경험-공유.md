---
title: "07_faster-whisper 한국어 음성인식 최적화 경험 공유"
date: 2026-07-10
slug: 4
authors: [sbin]
description: "이 글은 음성을 글자 변환  (Speech to Text) 하는 과정을 구체적으로 명시한 글이다"
last_update:
  date: 2026-07-16
---

### 들어가며

---

PoC 통해 모델 별 비교 및 정확도 테스트 해보았다. 

<!--truncate-->

그 과정에서 최적화의 중요성을 알게 되었다 

이 블로그에서는 그 과정을 조금 더 자세히 말해보겠다. 


오탐 예시) 

```python
[01:12:28.9~01:12:30.9|S???|ko] 길다가 길다가 왔다 갔다
[01:12:30.9~01:12:32.7|S???|ko] 길다가 저랬다고
[01:12:34.2~01:12:37.7|S???|ja] ご視聴ありがとうございました     <- 
[01:12:38.7~01:12:40.3|S???|ko] 서클
```

---


최적화도 다양하게 분류 된다는 것을 알았고, 

블로그 글을 쓰며 내용 정리를 해보기로 했다.

---

크게 나누면 아래 세가지였다.

- **최적화 1**   | 정확도 — raw/denoised 분리 (95.2% vs 93.4%)
- **최적화 2**  | 환각 억제 — 공식 파라미터 3개 튜닝 (반복 환각, 검증한 기본값 표 포함) / VAD pre-filter · MIN_LOGPROB
- **최적화 3**  | 언어 오분류 — LID 저신뢰→ko 강제 · dual transcribe · 한글 비율 게이트

---


---

1. 각 부분 코드 또는 로그로 나타내기

---

### 1. **최적화 2**  

파라미터 부터 보자

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
        condition_on_previous_text=False,      # 변경. 기존 True. 각 윈도우를 독립적으로 처리로 변경
        repetition_penalty=1.2,                # 변경. 기존 1.0. 이미 등장한 토큰은 20% 불리하게. 같은 토큰 연달아 덜뽑음
        no_repeat_ngram_size=3,                # 변경. 기존 0. 
    )
    segs = list(segments_gen)
    if not segs:
        return segs, float("-inf")
    return segs, sum(s.avg_logprob for s in segs) / len(segs)
```

| 파라미터 | 기본값 | 우리 값 | 역할 |
| --- | --- | --- | --- |
| `condition_on_previous_text` | `True` | `False` | 윈도우 간 반복 전파 차단 |
| `repetition_penalty` | `1.0` | `1.2` | 반복 토큰 소프트 페널티 |
| `no_repeat_ngram_size` | `0` | `3` | 3-gram 반복 하드 금지 |


### 2. **최적화 3**

---

있을때와 없을때 비교


---

#### 2-1) # 게이트 1 — VAD pre-filter

- Whisper 환각의 최대 원인 = 무음 구간에서 학습된 자막 패턴 생성을 막기 위해 사용한다

```python
# poc-stt-bench/ib/audio/whisper/whisper_stt.py
# Line 148
    # ── 1) VAD (raw)
    speech_ranges = vad.detect(raw_np, sr=TARGET_SR)
    log.info(f"audio {total_sec:.1f}s → VAD {len(speech_ranges)} speech segments")
```



---

#### 2-2) # 게이트 2 — dual transcribe + MIN_DUAL_LOGPROB (-1.0)

세그먼트 평균 로그확률이 -1.0 (확률로 약 37%) 미만이면 버린다. 확신 없이 뱉은 환각의 catch-all.

```python
# poc-stt-bench/ib/audio/whisper/whisper_stt.py
# 게이트 2 — MIN_LOGPROB (-1.0)
MIN_LOGPROB = -1.0       # drop if avg_logprob < this. catch-all for hallucinations
MIN_SEG_S = 0.2          # drop segments shorter than this. preserves short interjections like "네"/"그렇죠"
        for seg in segments_out:
            text = (seg.text or "").strip()
            if not text:
                continue
            abs_start = float(seg.start) + start_s
            abs_end = float(seg.end) + start_s
            dur = abs_end - abs_start
            
            if seg.avg_logprob < MIN_LOGPROB:
                log.info(f"    drop [{_hms(abs_start)}~{_hms(abs_end)}|{chosen_lang}] lp={seg.avg_logprob:.2f} | {text[:30]}")
                continue
            if dur < MIN_SEG_S:
                log.info(f"    drop [{_hms(abs_start)}~{_hms(abs_end)}|{chosen_lang}] dur={dur:.2f}s | {text[:30]}")
                continue
```


---

#### 2-3) # 게이트 3- LID_TRUST_PROB

언어 감지 확률이 0.5 미만이면서 비-한국어로 나오면 한국어로 강제한다.  
prob 0.23 같은 값은 "ko/ja/zh 가 다 비슷하다 = 모델이 모른다" 는 뜻이고,  
한국어 메인 콘텐츠에서는 **한국어로 두는 것이 가장 안전한 가정** 이다.

```python
# 게이트 3- LID_TRUST_PROB
# poc-stt-bench/ib/audio/whisper/whisper_stt.py
# Line 170
LID_TRUST_PROB = 0.5     # LID prob below this + non-main lang -> force MAIN_LANG (LID itself untrustworthy)

        if lang_code != MAIN_LANG and prob < LID_TRUST_PROB:
            log.info(f"    LID {lang_code}={prob:.2f} < {LID_TRUST_PROB} → {MAIN_LANG} 강제")
            lang_code = MAIN_LANG
```

---


#### 2-4) # 게이트4 — MIN_LOGPROB (-1.0)

3초 미만 발화가 비-한국어로 감지되면, **한국어로도 · 감지 언어로도** 둘 다 전사한 뒤  
`avg_logprob` 이 높은 쪽을 채택한다. 양쪽 다 -0.6 미만이면 잡음으로 보고 버린다.  
1\\~2초짜리 한국어가 음향적으로 일본어/중국어로 오분류되는 것을 막는 장치다.

```python
# 게이트 4 — dual transcribe + MIN_DUAL_LOGPROB (-0.6)
# poc-stt-bench/ib/audio/whisper/whisper_stt.py
# Line 176
MIN_DUAL_LOGPROB = -0.6  # if both dual sides fall below this -> drop (hallucination/noise)
SHORT_SEG_S = 3.0        # below this duration and LID != MAIN_LANG -> dual transcribe
MAIN_LANG = "ko"

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
```


---


#### 2-5)  # 게이트 5 — 한글 char 비율 게이트 (30%)

한국어로 인식됐는데 결과 텍스트의 한글 비율이 30% 미만이면 버린다.  
Whisper 가 한국어 모드에서 가나·한자 토큰을 환각으로 출력하는 케이스를 정확히 잘라낸다.

```python
# 게이트 5 — 한글 char 비율 게이트 (30%)
# poc-stt-bench/ib/audio/whisper/whisper_stt.py
# Line 211
# Avoids 1-2s segments in Korean content being misclassified as ja/zh.
MAIN_LANG = "ko"
KO_MIN_HANGUL_RATIO = 0.3  # if Hangul ratio of ko transcription is below this -> drop. Cuts Whisper outputting kana/hanja hallucinations in ko mode

            if chosen_lang == MAIN_LANG:
                ratio = _hangul_ratio(text)
                if ratio < KO_MIN_HANGUL_RATIO:
                    log.info(f"    drop [{_hms(abs_start)}~{_hms(abs_end)}|{chosen_lang}] hangul={ratio:.0%} | {text[:30]}")
                    continue
```

> 이 다섯은 공식 문서에 없는, 한국어 콘텐츠를 보며 하나씩 만든 규칙이다.
"어떤 환각을 봤고 → 어떤 게이트로 막았나" 가 이 프로젝트 최적화의 실체다.


---


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
MAIN_LANG = "ko"

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


