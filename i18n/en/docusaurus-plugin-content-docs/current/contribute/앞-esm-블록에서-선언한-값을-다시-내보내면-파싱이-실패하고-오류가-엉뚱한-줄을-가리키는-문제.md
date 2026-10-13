---
title: "An issue where re-exporting a value declared in a previous ESM block causes parsing to fail and the error to point to the wrong line"
sidebar_position: 48
slug: "48"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-08
---

## micromark-extension-mdxjs-esm Issue Draft: If a value declared in a previous ESM block is re-exported in the next block, an error occurs in an unexpected location

Link: https://github.com/micromark/micromark-extension-mdxjs-esm/issues/3

### Background

- Target: `@mdx-js/mdx` 3.1.1 (same in main 52285a6); the actual code is in dependency `micromark-extension-mdxjs-esm` 3.0.0.
- MDX parses `import` and `export` blocks—which are separated by blank lines—individually using acorn.
- Exporting a name imported from a previous block back into the export list of a subsequent block was fixed in Issue #1 of micromark-extension-mdxjs-esm in 2020 and now works correctly. However, the same handling is missing for names declared as `export const` / `export function` in a previous block.
- Format: Issue (micromark/micromark-extension-mdxjs-esm, bug report). The root cause is in this extension, and Issue #1 regarding the import side with the same symptom was also reported and fixed here. (Updated in the mdx-js/mdx Discussion during revalidation on 2026-10-08)

### Steps to Reproduce

```javascript
import {compile} from '@mdx-js/mdx'

// A: Failure
await compile('export const a = 1\n\nexport {a as b}\n\n# hi\n')
// B: It will work if you just remove the blank lines
await compile('export const a = 1\nexport {a as b}\n\n# hi\n')
// Using "import" instead of a C: declaration works
await compile("import {a} from './a.js'\n\nexport {a as b}\n\n# hi\n")
// If there is no text after "D:", a different error occurs
await compile('export const a = 1\n\nexport {a as b}\n')
```

Actual output:

```text
A: 5:2: Could not parse import/exports with acorn (cause: Unexpected character ' ')
B: ok
C: ok
D: 3:9: Could not parse import/exports with acorn (cause: Export 'a' is not defined)
```

The error location 5:2 in A is a space following ``#`` in a perfectly valid header line, and the message does not include the name “a,” which is the cause of the issue.

### Cause

- Lines 265–275 of ``micromark-extension-mdxjs-esm`` (``dev/lib/syntax.js``, relative to `main`): It collects the local names from the preceding block into ``definedModuleSpecifiers`` and appends them as a declaration (``var``) before the next block, but it only collects the specifiers from ``ImportDeclaration``. Names created by `export` declarations are omitted.
- Consequently, acorn, which has only parsed the second block, throws an `Export 'a' is not defined` error. This check is performed at the end of the program, so `raisedAt` corresponds to the end of the source (verified directly with acorn 8.19.0: pos 8, raisedAt 15, length 15).
- Lines 81–82 of `micromark-util-events-to-acorn`’s `dev/lib/index.js` interpret the error encountered at the end of the source as “may be resolved if more content follows” (`swallow`). The ESM syntax swallows the body beyond the blank line, and ultimately, an error reported while parsing the title line as JavaScript is raised.

### Proposal

- Question: Is A intentionally unsupported?
- If not, I’d like to ask whether it’s acceptable to submit a PR to `micromark-extension-mdxjs-esm` that adds the name declared in `export const/let/var/function/class` to `definedModuleSpecifiers`. I haven’t written the patch yet.
- If it is indeed not supported, I expect it to be reported with at least the same location (3:9) and message as in D.

### Verification

- Confirmed identical output by running the same script in both the npm release 3.1.1 and the main branch (52285a6) versions of `packages/mdx`. The original output is `repro.txt`.
- `micromark-extension-mdxjs-esm` In main (3fdf3d3), `syntax.js` differs from the 3.0.0 release only in the JSDoc header; the logic is the same.
- Duplicate search: Issues, PRs, and discussions in mdx-js/mdx, micromark-extension-mdxjs-esm, micromark-extension-mdx-expression, micromark, and mdast-util-mdxjs-esm. The closest match is Issue #1 in micromark-extension-mdxjs-esm (fixed only for import cases; closed).
- Not implemented: `npm test` in the repository (not applicable since there were no code changes).

