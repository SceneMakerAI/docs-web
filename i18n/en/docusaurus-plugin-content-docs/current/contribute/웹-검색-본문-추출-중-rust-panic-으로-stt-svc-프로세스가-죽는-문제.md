---
title: "Issue where the stt_svc process crashes due to a Rust panic while extracting text from web search results"
sidebar_position: 36
slug: "36"
description: "agent-stt: Record of the issue where a Rust html2text panic inside ddgs.extract() causes the process to crash, and the corrective actions taken"
tags: [Issue]
keywords: [Issue]
last_update:
  date: 2026-10-06
---

[https://github.com/SceneMakerAI/agent-stt/issues/3](https://github.com/SceneMakerAI/agent-stt/issues/3)

#### Issue

During the web search phase of the subtitling process (collecting character and player lists), the entire `stt_svc` process crashed while fetching the body of a wiki page (September 21, 2026). Since it was a process `SIGABRT` rather than a Python exception, it was not caught by `try/except`, and other requests being processed by the same process were also interrupted.

#### Cause

We were using `DDGS().extract()` from `ddgs` for text extraction.

- `extract()` pre-computes all formats, such as `text_markdown`, regardless of the requested format.
- That conversion is performed by Rust `html2text` inside `primp`.
- If a panic occurs on the Rust side, it does not raise a Python exception; instead, the process terminates.

Although we were adhering to the design principle that “a single query failure should not disrupt the entire search” using `except Exception`, this type of failure bypasses that defense mechanism. The environment is `ddgs 9.14.4` and `primp 1.3.1`.

#### Action

- Commit 41cc248 — Changed the code to avoid using `DDGS().extract()`. The `ddgs` HTTP client now receives only the raw HTML, and text conversion is handled by a custom function based on `lxml`. Line breaks are inserted after each block element, and table cells are joined using ` | `, ensuring that each row of a list table remains on a single line.
- In the same commit, search for sports and drama profiles was temporarily disabled, then re-enabled in commit 418b75d.

#### Remaining Tasks

- Dead URLs were not logged. Once we obtain the HTML needed for reproduction, we will report a panic to the `primp` (or `ddgs`) upstream.
- There are no regression tests for the new conversion function.
- We need to check for other call sites where native extensions could crash the process.

#### Lessons Learned

Panics in native extensions (Rust·C) are not isolated by `try/except`. When passing untrusted external input to such code, use a pure Python path or isolate it in a separate process.

#### Result

Registered on October 6, 2026. The fix has already been applied, but the issue remains open due to remaining tasks. Since `agent-stt` is a private repository, only authorized users can open the issue link.

