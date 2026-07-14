---
title: "07_faster-whisper 한국어 음성인식 최적화 경험 공유"
date: 2026-07-10
slug: 4
authors: [sbin]
description: "이 글은 음성을 글자 변환  (Speech to Text) 하는 과정을 구체적으로 명시한 글이다"
last_update:
  date: 2026-07-14
---

### 들어가며

---


음성인식 최적화 경험은 해당 PoC 참고하여 재기재

<!--truncate-->

[https://doc.scenemaker.solbox.com/docs/poc/audio-bench/1](https://doc.scenemaker.solbox.com/docs/poc/audio-bench/1)

**4. 시스템 설계 + 환각 처리  > 4.1 Whisper 측** 

내용을 기재하면 됨. 

- poc/poc-stt-bench 내부 코드 확인
- 레퍼런스 글 확인 및  간단 정리

| 최적화 | 무엇 | 효과 |
| --- | --- | --- |
| **Strategy 2** | VAD/LID=raw, STT=denoise | 감지 정확도 + 전사 품질 둘 다 |
| **언어 티어링** | Whisper 못하는 언어 버림 (nl/zh/vi 오판 차단) | 환각 제거 |
| **LID 신뢰도 게이트** | 저신뢰 비-한국어 → 한국어 강제 | 한국어 특화 |
| **logprob 필터** | 확신 낮은 세그먼트 drop | 환각 제거 |
| **VAD 튜닝** | 단음절 버림, 발화 단위 분할 | 경계 오류 방지 |
| **LLM 후처리 교정** | Qwen 1차 교정 (물고지→물고기) | 오탈자·동음이의 |

### 마무리

---


