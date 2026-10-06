---
id: word-timestamps-에서-단어-안의-구두점이-단어를-쪼개는-문제
title: "word_timestamps 에서 단어 안의 구두점이 단어를 쪼개는 문제"
sidebar_position: 41
slug: "41"
description: "openai/whisper: word_timestamps 사용 시 3.5% 나 따옴표 뒤 조사처럼 단어 안의 구두점이 단어를 둘로 나누고 구두점이 뒤 조각 앞에 붙는 문제 제기 (Q&A discussion)"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-06
---

## openai/whisper: word_timestamps 에서 단어 내부 구두점이 단어를 쪼개는 문제 (Discussion)

링크: https://github.com/openai/whisper/discussions/2875

### 배경

한국어 방송 음성의 단어 타임스탬프를 검증할 때 openai/whisper 를 기준 구현으로 쓴다. `word_timestamps=True` 결과의 `words` 목록에서 `3.5%` 가 ` 3` , `.5` , `%` 로, `"안녕"이라고` 가 ` "안녕` , `"이라고` 로 나뉘는 것을 확인했다. 한국어는 닫는 따옴표·괄호 바로 뒤에 조사가 붙기 때문에 닫는 따옴표가 조사 쪽 단어 앞에 붙고, 자막 줄바꿈(`max_words_per_line` , `highlight_words` )이 그 사이에서 일어난다.

### 원인

`whisper/tokenizer.py` 의 `split_tokens_on_spaces` (317-325행).

- ASCII 구두점만으로 된 서브워드는 앞에 공백이 없어도 항상 새 단어를 시작한다 (319-320행).
- 그 다음 서브워드는 공백이 없으므로 `words[-1]` , 즉 방금 만든 구두점 단어 뒤에 이어 붙는다 (324행). 결과가 `.5` , `"이라고` .
- `merge_punctuations` (`whisper/timing.py` 268행)는 단어 전체가 `append_punctuations` 에 들어 있을 때만 앞 단어로 옮기므로 이 형태는 그대로 남는다.
- `string.punctuation` 은 ASCII 전용이고 부분 문자열 검사라서, 둥근 따옴표 `”` 는 쪼개지지 않고 토큰 `%.` 도 쪼개지지 않는다. 같은 문장이 따옴표 종류에 따라 다른 단어 목록이 된다.

### 재현 방법

- 모델 없이: `repro_tokens.py` (tokenizer + `merge_punctuations` + `WriteSRT` ). 한국어 문장은 직접 입력한 텍스트를 토크나이즈한 것이며 모델 출력이 아니다.
- 실제 음성: Wikimedia Commons 의 CC BY 2.5 영어 뉴스 낭독 파일 앞 60초를 `tiny` 모델(CPU)로 전사. `17.5%` 가 ` 17` , `.5` , `%` , `wikinews.org,` 가 ` wikinews` , `.org,` 로 나온다.
- 명령과 원본 출력은 `repro.txt` .

### 검증

- main HEAD 8609812 에서 두 스크립트 모두 재현.
- 로컬 브랜치 `discussion-korean-repro` 에 커밋하지 않은 수정(10행)과 테스트 1개가 있다. 테스트는 수정 전 실패, 수정 후 통과. CI 와 같은 pytest 부분집합 20개 통과, black/isort 통과.
- 한국어 음성으로 모델이 실제로 ASCII 따옴표를 출력하는 경우는 이 작업에서 실행해 보지 않았다 (tiny/base 로 시도한 공개 한국어 낭독 3개에서는 해당 패턴이 나오지 않음).
- Discussion 본문은 "의도된 동작인지, 아니면 재결합하는 수정을 받아줄지"를 묻는 형식이다.

