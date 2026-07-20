---
title: "07_faster-whisper 한국어 음성인식 최적화 경험 공유"
date: 2026-07-10
slug: 4
authors: [sbin]
description: "이 글은 음성을 글자 변환  (Speech to Text) 하는 과정을 구체적으로 명시한 글이다"
tags: [Fast-Whisper]
last_update:
  date: 2026-07-20
---

### 들어가며

---

`faster-whisper large-v3` 를 한국 방송 콘텐츠에 그대로 돌리면 자막이 원하는대로  나오지 않는다.

<!--truncate-->

```text
# 일부 추출 결과
[01:12:30.9~01:12:32.7|S???|ko] 길다가 저랬다고
[01:12:34.2~01:12:37.7|S???|ja] ご視聴ありがとうございました     # 아무도 이런 말을 하지 않았다
[01:12:38.7~01:12:40.3|S???|ko] 서클
```

위 로그는, 발화가 없는 구간에 학습 데이터의 자막 패턴이 튀어나온 것이다. 

PoC 로 모델별 비교 / 정확도 테스트를 하면서 위 실패를 여러차례 만났고, **최적화의 중요성** 을 알게 되었다.

이 글은 그 실패들을 하나씩 잡아간 기록이다. 다만 기법을 시간순으로 나열하는 대신, **"무엇을 최적화하는가"** 라는 축으로 묶었다. 

---

#### 최적화 기준

크게 4가지로 나누어 보았다. 

| 최적화 대상 | 적용한 기법 |
| --- | --- |
| **① 정확도** | `large-v3` 채택 · raw / denoised 입력 분리 |
| **② 환각 억제** | 반복 파라미터 3종 튜닝 · VAD pre-filter · `MIN_LOGPROB` |
| **③ 언어 오분류** | LID 저신뢰 → 한국어 강제 · dual transcribe · 한글 비율 게이트 |
| **④ 속도(RTF)** | 배치 추론 · 언어별 묵음 스트림 |

`large-v3` 자체는 출발점일 뿐이다. 품질을 만든 건 이 모델 **위에** 얹은 규칙들이었다.

베이스 모델은 정확도 우선으로 `Systran/faster-whisper-large-v3` 를 골랐다. `turbo` (4-layer 디코더)는 23배 빠르지만 다국어 혼재 콘텐츠에서 정확도 손해가 컸고, 한국어 파인튜닝 브랜치는 뉴스체엔 강해도 다큐·예능에서 오히려 떨어졌다. 범용성이 이겼다.

그리고 이 모델을 한국 방송 6종(뉴스·다큐·드라마·사극·예능·스포츠)에 붙이자, 반복되는 실패 세 가지가 드러났다.

1. **유령 자막** — 발화 없는 침묵/BGM 구간에 학습 데이터의 자막 패턴이 튀어나온다. `ご視聴ありがとうございました` , `Thanks for watching` , 아랍어 자막 크레딧까지.
2. **무한 반복** — `감사합니다 감사합니다 감사합니다...` (실제 발생하지는 않았으나, 가능하다 판단)
3. **언어 오분류** — 12초 한국어가 일본어/중국어로 인식되거나, 한국어 모드인데 가나·한자를 뱉는다.

이 셋을 각각 다른 축에서 막는 것이 최적화의 전부였다.

---

#### 1. 정확도 — 입력을 둘로 나눈다

> **최적화 대상: LID 정확도 ↑ + ASR 환각 ↓**

첫 인사이트는 "**denoise 한 오디오를 모든 단계에 쓰면 안 된다** " 였다.

잡음 제거(DeepFilterNet v3)는 ASR 환각을 줄여준다. 그런데 같은 denoised 오디오를 **언어 감지(LID)** 에 넣었더니 정확도가 오히려 떨어졌다. denoise 가 음성의 미세한 음향 신호를 변형시켜 LID 판단을 흐린 것이다. 측정으로 확인했다.

| 입력 | Whisper LID 정확도 |
| --- | --- |
| raw audio | **95.2%** |
| denoised audio | 93.4% |

그래서 입력을 갈랐다. **VAD·LID·화자 구분은 raw, ASR 만 denoised.**

```text
        ┌─ VAD  (발화 구간 검출)   ← raw
raw ────┼─ LID  (언어 감지)        ← raw
        └─ 화자 구분                ← raw

denoised ─ ASR  (받아쓰기)         ← denoised
```

denoise 는 감쇠 강도도 `atten_lim_db = -30` 으로 완화해, 노래·정상 발화가 잡음과 함께 지워지지 않게 보존했다.

```python
# worker/worker-prep_stt/lib/service/stt_service.py
# Line 130-151

def _load_audio(audio_path: str, job_dir: Path = None):
    """입력 wav → (raw_np, den_np). 둘 다 16k mono float32, 길이 정렬.

    Strategy 2: VAD/LID/화자 구분 = raw, ASR = denoised.
    품질 보존을 위해 원본 sr 에 denoise 를 걸고(48k), 그 뒤 16k 로 다운샘플.
    """
    orig, osr = sf.read(str(audio_path), dtype="float32")
    if orig.ndim > 1:
        orig = orig.mean(axis=1)                       # → mono

    raw_np = _to_16k(orig, osr)                        # VAD/LID/speaker 용
    den48, dsr = denoise.process(orig, osr)            # 원본에 denoise → 48k
    den_np = _to_16k(den48, dsr)                       # ASR 용 16k

    n = min(len(raw_np), len(den_np))                  # 길이 차 안전 처리
    return raw_np[:n], den_np[:n]
```

---

#### 2. 환각 억제

침묵과 반복이 만드는 "없는 자막"을 세 겹으로 막았다.

##### 2-1) 반복 환각 — 공식 파라미터 3종 튜닝

> **최적화 대상: 반복 루프**

`transcribe()` 의 공식 파라미터 중 반복에 직접 작용하는 세 개를 기본값에서 바꿨다. (faster-whisper 1.2.1 기본값 기준)

| 파라미터 | 기본값 | 우리 값 | 역할 |
| --- | --- | --- | --- |
| `condition_on_previous_text` | `True` | `False` | 윈도우 간 반복 전파 차단 |
| `repetition_penalty` | `1.0` | `1.2` | 반복 토큰 소프트 페널티 |
| `no_repeat_ngram_size` | `0` | `3` | 3-gram 반복 하드 금지 |

핵심은 `condition_on_previous_text=False` 다. 

Whisper 는 기본적으로 직전 윈도우의 인식 결과를 다음 윈도우의 문맥으로 넣는다. 그런데 한 번 반복이 시작되면 그 텍스트가 다음 구간으로 전파되며 눈덩이처럼 번진다. 

문맥을 끊으면 각 윈도우가 독립 처리되어 **연쇄 고리 자체가 사라진다.** 나머지 둘은 토큰 디코딩 단계에서 반복을 각각 소프트(penalty)·하드(n-gram)로 누른다.

서로 다른 층위(윈도우 vs 토큰, 소프트 vs 하드)를 덮기 때문에 셋을 함께 써야 효과가 났다.

```python
# poc/poc-stt-bench/lib/audio/whisper/whisper_stt.py
# Line 97-116

def _do_transcribe(audio_np: np.ndarray, language: str) -> tuple[list, float]:
    """Call faster-whisper transcribe. Returns segments (list) + mean avg_logprob."""
    segments_gen, _info = _model.transcribe(
        audio_np,
        language=language,
        beam_size=5,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
        condition_on_previous_text=False,   # 변경. 기존 True. 각 윈도우를 독립 처리
        repetition_penalty=1.2,             # 변경. 기존 1.0. 이미 등장한 토큰은 20% 불리하게
        no_repeat_ngram_size=3,             # 변경. 기존 0. 3-gram 반복 하드 금지
    )
    segs = list(segments_gen)
    if not segs:
        return segs, float("-inf")          # 빈 결과 = dual 비교에서 자동 패배
    return segs, sum(s.avg_logprob for s in segs) / len(segs)
```

---

##### 2-2) 유령 자막 — VAD pre-filter

> **최적화 대상: 무음 구간 환각 (가장 효과 큼)**

**환각의 최대 원인은 발화 없는 구간이다** . 

그러니 침묵/BGM 구간을 애초에 ASR 에 넣지 않으면 문제 대부분이 사라진다. Silero VAD 로 발화 구간만 뽑아 ASR 에 넘겼다.

파라미터도 한국어에 맞게 조정했다.

```python
# worker/worker-prep_stt/lib/audio/vad.py
# Line 26-28, 46-63

# 발화 길이 제약 — LID 정확도와 후속 처리 부하 균형
MIN_SPEECH_S = 1.0     # 너무 짧으면 LID 부정확 ("Yeah" 같은 단음절 환각)
MAX_SPEECH_S = 30.0    # 너무 길면 처리 부하 (Whisper 30s 윈도우 한계)
MIN_SILENCE_S = 0.3    # 이보다 짧은 침묵은 무시 (인접 발화 병합)


def detect(audio_np: np.ndarray, sr: int = 16000) -> list[tuple[float, float]]:
    """발화 구간 타임스탬프 추출. Returns: [(start_sec, end_sec), ...]"""
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

##### 2-3) 저신뢰 컷 — MIN_LOGPROB

> **최적화 대상: 환각 catch-all**

그래도 새는 환각이 있었다. `Thank you` 같은 자막이 멀쩡히 통과했다. 그래서 transcribe **결과** 를 한 번 더 걸렀다 — 세그먼트 평균 로그확률 `avg_logprob < -1.0` (확률 약 37%)이면 버린다. 확신 없이 뱉은 환각을 잡는 마지막 그물이다.

---

#### 3. 언어 오분류

여기서부터는 "환각"이 아니라 **"언어를 잘못 골라서 생기는 오류"** 다. 한국어 메인 콘텐츠에 특화된, 이 프로젝트만의 게이트들이다.

##### 3-1) LID 저신뢰 → 한국어 강제

> **최적화 대상: 짧은 발화의 언어 오판**

언어 감지 확률이 `0.5` 미만이면서 비-한국어로 나오면 한국어로 강제한다. 

prob 0.23 같은 값은 "ko/ja/zh 가 다 비슷하다 = 모델이 모른다" 는 뜻이다. 한국어 메인 콘텐츠에서는 **모를 때 한국어로 두는 것이 가장 안전한 가정** 이었다.

```python
# worker/worker-prep_stt/lib/service/stt_service.py
# Line 162-184

def _classify_languages(raw, ranges):
    """각 구간 LID(raw) → 언어별 시간범위 그룹 { lang: [(start_s, end_s), ...] }.

    ALLOWED_LANGS 게이트 + LID_TRUST_PROB(비-주언어 저신뢰 → 주언어 강제) 적용.
    """
    sr, main = config.TARGET_SR, MAIN_LANG
    groups: dict[str, list] = {}
    for start_s, end_s in ranges:
        chunk = raw[int(start_s * sr):int(end_s * sr)]   # ← LID 는 raw 에서
        # detech_language 이용 추출
        lang, prob = whisper.detect_language(chunk)

        if lang not in ALLOWED_LANGS:                    # Tier 4-5 버림
            continue
        if lang != main and prob < LID_TRUST_PROB:       # 저신뢰 → 주언어 강제
            lang = main
-------------------------------------------------------------------
# def_lang.py

# 허용 = Tier 1 ∪ 2 ∪ 3. 이 밖
ALLOWED_LANGS: frozenset[str] = TIER1_LANGS | TIER2_LANGS | TIER3_LANGS
# (Tier 4 약함, Tier 5 미지원)은 skip.

# Tier 1 — 매우 정확 (WER < 5%). 거의 환각 없음.
TIER1_LANGS:     "en", "es", "it", "fr", "de", "pt"

# Tier 2 — 양호 (WER 5-10%). 주 커버리지 (ko 포함). 후처리 필요하나 신뢰 가능.
TIER2_LANGS:     "ko", "ja", "zh", "ru", "nl", "pl", "tr", "ca", "uk"

# Tier 3 — 보통 (WER 10-20%). 조심해서 수용 — 짧은 발화는 환각 가능.
TIER3_LANGS:     "ar", "he", "hi", "id", "ms", "vi", "el", "hu", "cs", "fi", "sv", "da", "no"


```

---

##### 3-2) dual transcribe — ko vs 감지 언어

> **최적화 대상: ko / ja / zh 음향적 혼동**

3초 미만 발화가 비-한국어로 감지되면, **한국어로도 · 감지 언어로도** 둘 다 전사한 뒤 `avg_logprob` 이 높은 쪽을 채택한다. 양쪽 다 -0.6 미만이면 잡음으로 보고 버린다. 12초짜리 한국어가 음향적으로 일본어/중국어로 오분류되는 것을 막는 장치다.

```python
# poc/poc-stt-bench/lib/audio/whisper/whisper_stt.py
# Line 60-61 (상수), 175-194 (dual 분기)

SHORT_SEG_S = 3.0        # 이보다 짧고 LID != ko 면 → dual transcribe
MIN_DUAL_LOGPROB = -0.6  # 양쪽 다 이 아래면 → drop (환각/잡음)

# ── transcribe() 안, 구간별 루프 ──
chunk_dur = end_s - start_s
if chunk_dur < SHORT_SEG_S and lang_code != MAIN_LANG:
    segs_main, lp_main = _do_transcribe(chunk_den, MAIN_LANG)   # 한국어로
    segs_lid,  lp_lid  = _do_transcribe(chunk_den, lang_code)   # 감지 언어로

    if max(lp_main, lp_lid) < MIN_DUAL_LOGPROB:                 # 양쪽 다 약함 → 잡음
        continue
    if lp_main >= lp_lid:                                       # logprob 높은 쪽 채택
        segments_out, chosen_lang = segs_main, MAIN_LANG
    else:
        segments_out, chosen_lang = segs_lid, lang_code
else:
    segments_out, _ = _do_transcribe(chunk_den, lang_code)
    chosen_lang = lang_code
```

---

##### 3-3) 한글 비율 게이트

> **최적화 대상: 가나·한자 토큰 환각**

한국어로 인식됐는데 결과 텍스트의 한글 비율이 `30%` 미만이면 버린다. Whisper 가 한국어 모드에서 가나(かな)·한자 토큰을 환각으로 출력하는 케이스를 정확히 잘라낸다.

```python
# poc/poc-stt-bench/lib/audio/whisper/whisper_stt.py
# Line 63 (상수), 88-94 (_hangul_ratio), 196-215 (후처리 루프)

KO_MIN_HANGUL_RATIO = 0.3

# ── 후처리 루프 — 기본 옵션이 놓친 환각을 자체 게이트로 잡는다 ──
for seg in segments_out:
    text = (seg.text or "").strip()
    if not text:
        continue

    if seg.avg_logprob < MIN_LOGPROB:                    # 2-3. 저신뢰 컷 (-1.0)
        continue
    if dur < MIN_SEG_S:                                  # 너무 짧은 세그먼트 컷
        continue
    if chosen_lang == MAIN_LANG:                         # 3-3. 한글 비율 게이트
        if _hangul_ratio(text) < KO_MIN_HANGUL_RATIO:    # 0.3 미만
            continue
            
def _hangul_ratio(text: str) -> float:
    """영숫자 중 한글 음절의 비율 (공백·문장부호 제외). 분모 0 이면 1.0 (검증 skip)."""
    chars = [c for c in text if c.isalnum()]
    if not chars:
        return 1.0
    return sum(1 for c in chars if '가' <= c <= '힣') / len(chars)
```

> 참고로 언어 티어링도 함께 뒀다. faster-whisper 의 언어별 WER 을 기준으로 Tier 13만 허용하고 (한국어는 Tier 2), 그 밖의 약한 언어로 감지된 구간은 통째로 skip 한다.

이 게이트들은 공식 문서에 없는, 한국어 콘텐츠를 실제로 보며 하나씩 만든 규칙이다. **"어떤 환각을 봤고 → 어떤 게이트로 막았나"** 가 이 프로젝트 최적화의 실체다.

---

#### 4. 속도 — 그리고 축 간의 충돌

> **최적화 대상: RTF (처리시간 / 오디오 길이)**

검증(PoC) 단계는 정확도가 목적이라 발화 구간을 하나씩 순차 처리했다. 느려도 됐다. 하지만 운영은 속도가 최우선(HTTP 블로킹)이라 구조를 바꿔야 했다.

- **배치 추론** — `BatchedInferencePipeline` 으로 30초 윈도우 16개를 GPU 에 병렬 적재.
- **언어별 묵음 스트림** — 해당 언어 외 구간을 0(묵음)으로 채운 전체 길이 스트림을 만들어 언어당 한 번에 배치 전사. 내부 VAD 가 묵음을 건너뛰므로 그 언어 발화만 인식된다.

결과적으로 **RTF ≈ 0.042** — 1시간 입력을 약 150초에 처리한다.

```python
# worker/worker-prep_stt/lib/service/stt_service.py
# Line 187-205

def _transcribe_batched(den, groups):
    """언어별로 '그 언어 외 구간을 묵음 처리한 전체 길이 스트림'을 만들어 배치 transcribe.

    내부 VAD 가 묵음을 건너뛰므로 그 언어 발화만 인식 + timestamp 는 원본 시각 그대로.
    """
    sr = config.TARGET_SR
    out = []
    for lang, lang_ranges in groups.items():
        # 1. 전체 묵음
        stream = np.zeros_like(den)  
        # 2. 해당 언어 구간만 복원                   
        for start_s, end_s in lang_ranges:              
            i, j = int(start_s * sr), int(end_s * sr)
            stream[i:j] = den[i:j]
        words = whisper.transcribe_batched(stream, language=lang)
        for w in words:
            w["lang"] = lang
        out.extend(words)
    return out
```

묵음 스트림이 성립하는 건 `vad_filter=True` 덕분이다. 내부 VAD 가 0 으로 채운 구간을 통째로 건너뛰므로, 전체 길이 스트림을 던져도 실제 연산은 그 언어 발화에만 든다.

```python
# worker/worker-prep_stt/lib/audio/whisper.py
# Line 26, 41, 67-80

BATCH_SIZE = 16   # 동시에 GPU 에 올리는 30s 윈도우 수
_batched = BatchedInferencePipeline(model=_model)

segments_gen, _info = _batched.transcribe(
    audio,
    language=language,
    batch_size=BATCH_SIZE,
    beam_size=5,
    condition_on_previous_text=False,
    repetition_penalty=1.2,
    no_repeat_ngram_size=3,
    vad_filter=True,        # 묵음 구간 건너뛰기 (묵음 스트림 처리의 핵심)
    word_timestamps=True,   # 단어 단위 타임스탬프 → 호출측이 화자/문장 기준 재분할
)
```

#### 마무리

---

`large-v3` 는 출발점이었다. 한국어 음성인식 품질을 만든 건 네 개의 축이었다.

- **① 정확도** — LID 는 raw, ASR 는 denoised (95.2% vs 93.4%)
- **② 환각 억제** — 반복 파라미터 · VAD · logprob 로 없는 자막 차단
- **③ 언어 오분류** — LID 강제 · dual · 한글 비율로 한국어 관점의 오류 컷
- **④ 속도** — 배치로 RTF 0.042, 대신 어떤 게이트를 버릴지 결정

돌아보면 가장 오래 붙잡고 있었던 건 파라미터가 아니라 **"이 환각은 왜 생겼나"** 를 로그에서 찾아내는 일이었다. `ご視聴ありがとうございました` 가 왜 나오는지 이해하기 전까지는 어떤 파라미터도 답이 아니었다. 반대로 원인을 알고 나면 게이트는 대개 조건문 두세 줄이었다.

공식 문서가 알려주는 파라미터는 절반이고, 나머지 절반은 **한국어 콘텐츠를 실제로 보며 만든 규칙** 이었다. 같은 고민을 하는 분들께 이 시행착오가 지름길이 되길 바란다.

---

#### 다음 글 예고

RAG 파이프라인 구축 부분 및, 음성분석 처리 과정 및 결과 를 적어보고자 한다

---

**참고**

- faster-whisper: [https://github.com/SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- Systran/faster-whisper-large-v3: [https://huggingface.co/Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3)
- OpenAI Whisper: [https://github.com/openai/whisper](https://github.com/openai/whisper)
- DeepFilterNet: [https://github.com/Rikorose/DeepFilterNet](https://github.com/Rikorose/DeepFilterNet)
- Silero VAD: [https://github.com/snakers4/silero-vad](https://github.com/snakers4/silero-vad)
- pyannote-audio: [https://github.com/pyannote/pyannote-audio](https://github.com/pyannote/pyannote-audio)
- STT PoC 벤치마크 전체 수치: [https://doc.scenemaker.solbox.com/docs/poc/audio-bench/1](https://doc.scenemaker.solbox.com/docs/poc/audio-bench/1)

*본 글은 과학기술정보통신부·정보통신산업진흥원 「2026년 오픈소스 AI·SW 개발·활용 지원사업」의 지원으로 수행된 연구 결과입니다.*

