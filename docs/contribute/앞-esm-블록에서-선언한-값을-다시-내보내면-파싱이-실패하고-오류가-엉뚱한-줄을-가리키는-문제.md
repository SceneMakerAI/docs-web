---
id: 앞-esm-블록에서-선언한-값을-다시-내보내면-파싱이-실패하고-오류가-엉뚱한-줄을-가리키는-문제
title: "앞 ESM 블록에서 선언한 값을 다시 내보내면 파싱이 실패하고 오류가 엉뚱한 줄을 가리키는 문제"
sidebar_position: 48
slug: "48"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-08
---

## micromark-extension-mdxjs-esm Issue 초안: 앞 ESM 블록에서 선언한 값을 다음 블록에서 재-export 하면 엉뚱한 위치의 오류가 난다

링크: https://github.com/micromark/micromark-extension-mdxjs-esm/issues/3

### 배경

- 대상: `@mdx-js/mdx` 3.1.1 (main 52285a6 에서도 동일), 실제 코드는 의존성 `micromark-extension-mdxjs-esm` 3.0.0 에 있다.
- MDX 는 빈 줄로 나뉜 `import` /`export` 블록을 블록마다 따로 acorn 으로 파싱한다.
- 앞 블록에서 import 한 이름을 뒤 블록에서 export 목록으로 다시 내보내는 것은 2020년 micromark-extension-mdxjs-esm 이슈 1번에서 고쳐져 동작한다. 그런데 앞 블록에서 `export const` / `export function` 으로 선언한 이름은 같은 처리가 빠져 있다.
- 형태: Issue (micromark/micromark-extension-mdxjs-esm, 버그 양식). 원인 코드가 이 확장에 있고, 같은 증상의 import 쪽 이슈 1번도 여기서 접수·수정됐다. (2026-10-08 재검증 때 mdx-js/mdx Discussion 에서 변경)

### 재현 방법

```javascript
import {compile} from '@mdx-js/mdx'

// A: 실패
await compile('export const a = 1\n\nexport {a as b}\n\n# hi\n')
// B: 빈 줄만 없애면 성공
await compile('export const a = 1\nexport {a as b}\n\n# hi\n')
// C: 선언 대신 import 면 성공
await compile("import {a} from './a.js'\n\nexport {a as b}\n\n# hi\n")
// D: 뒤에 본문이 없으면 다른 오류
await compile('export const a = 1\n\nexport {a as b}\n')
```

실제 출력:

```text
A: 5:2: Could not parse import/exports with acorn (cause: Unexpected character ' ')
B: ok
C: ok
D: 3:9: Could not parse import/exports with acorn (cause: Export 'a' is not defined)
```

A 의 오류 위치 5:2 는 아무 문제 없는 제목 줄의 `#` 다음 공백이고, 메시지에는 원인인 이름 a 가 나오지 않는다.

### 원인

- `micromark-extension-mdxjs-esm` 의 `dev/lib/syntax.js` 265-275행 (main 기준): 앞 블록의 지역 이름을 `definedModuleSpecifiers` 에 모아 다음 블록 앞에 `var` 선언으로 붙여 주는데, `ImportDeclaration` 의 specifier 만 모은다. export 선언으로 만든 이름은 빠진다.
- 그래서 둘째 블록만 파싱한 acorn 이 `Export 'a' is not defined` 를 던진다. 이 검사는 프로그램 끝에서 수행되어 `raisedAt` 이 소스 끝과 같다 (acorn 8.19.0 으로 직접 확인: pos 8, raisedAt 15, 길이 15).
- `micromark-util-events-to-acorn` 의 `dev/lib/index.js` 81-82행은 소스 끝에서 난 오류를 "내용이 더 오면 해결될 수 있음" 으로 판단한다 (`swallow` ). ESM 구문이 빈 줄 너머 본문까지 삼키고, 결국 제목 줄을 JavaScript 로 파싱하다 난 오류가 보고된다.

### 제안 내용

- 질문: A 는 의도적으로 지원하지 않는 것인가.
- 아니라면 `export const/let/var/function/class` 로 선언한 이름도 `definedModuleSpecifiers` 에 넣는 PR 을 `micromark-extension-mdxjs-esm` 에 보내도 되는지 문의. 패치는 작성하지 않았다.
- 지원하지 않는 것이 맞다면 최소한 D 와 같은 위치(3:9)와 메시지로 보고되기를 기대.

### 검증

- npm 배포본 3.1.1 과 main (52285a6) 의 `packages/mdx` 양쪽에서 같은 스크립트를 실행해 동일한 출력 확인. 원본 출력은 `repro.txt` .
- `micromark-extension-mdxjs-esm` main (3fdf3d3) 의 `syntax.js` 는 배포본 3.0.0 과 JSDoc 머리말만 다르고 로직은 같다.
- 중복 검색: mdx-js/mdx, micromark-extension-mdxjs-esm, micromark-extension-mdx-expression, micromark, mdast-util-mdxjs-esm 의 이슈·PR·Discussion. 가장 가까운 것은 micromark-extension-mdxjs-esm 이슈 1번 (import 경우만 수정, 종료됨).
- 실행하지 않은 것: 저장소의 `npm test` (코드 변경이 없어 해당 없음).

