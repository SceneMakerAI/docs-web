---
title: "2026 ADIP 국제학술대회 논문 발표 (SPIE)
"
sidebar_position: 6
slug: "6"
last_update:
  date: 2026-11-18
---

##### Presentation Information

| Item | Details |
| --- | --- |
| Title | Metadata-guided multimodal video analysis for automatic broadcast clip generation: design and production deployment |
| Conference | 8th Asia Digital Image Processing Conference (ADIP 2026) |
| Paper Number | PA5021 |
| Review Result | Passed final review by international panel of reviewers (PASS); final confirmation after incorporating reviews completed |
| Publication / Indexing | To be published in the ADIP 2026 SPIE Conference Proceedings (SPIE Digital Library) following the presentation / Indexed in Scopus / Indexed in EI Compendex |
| Link | [https://adip.org/](https://adip.org/) |
| Date / Location | December 18–21, 2026 / Tokyo, Japan, The University of Electro-Communications |
| Authors | Kyu-Hyuck Jung*, Dongwoon Choi (SBSI) · Jongpil Lee, Minsung Im (SOLBOX)  *Corresponding Author |

[Presentation Photo] (To be uploaded later)

##### Paper Abstract

Broadcasters repurpose long-form programs into highlights and short-form clips for distribution across mobile, web, OTT, and social media channels. However, during major sports broadcasts with a high volume of action, the workload cannot be handled by manually searching for and editing scenes.

This paper does not propose a new detection model. Instead, we designed and demonstrated an integrated architecture that combines the results of multimodal analyses—such as shot transition detection, representative frame analysis, audio and subtitle processing, scoreboard OCR, and VLM scene descriptions—with the broadcasters’ existing programming and match metadata. Metadata serves two purposes. First, it acts as a criterion for grouping meaningful chunks across shot boundaries; second, it serves as a filter to restrict similarity searches to the specific program or game. The generated candidate segments are verified against the original timeline, published after review by an operator, and revision history is recorded in the operational log.

We applied this system to five baseball games at the 20th Aichi-Nagoya Asian Games and published 79 clips in live service. These results expand upon a presentation at a domestic academic conference (Korean Society of Broadcasting and Media Engineering, 4 pages), adding full-scale validation across all five games, operational metrics, failure analysis, and operational settings.

##### Key Contributions

- **Metadata-Based Time Fusion Structure**: Broadcast metadata is utilized twice within a single pipeline. ① It serves as the criterion for chunking into meaningful units that transcend shot transitions, ensuring that event boundaries follow the game structure (innings, at-bats) rather than camera cuts. ② It is used as a structured filter in the search phase to restrict candidates to the relevant program or game before calculating semantic similarity.
- **Original Timeline Validation and Human-in-the-Loop Review System**: All candidate segments must pass a validity check (0 ≤ IN < OUT ≤ original length) before extraction. Since operator modification history is recorded in evaluation logs, the review stage serves as both a quality control gate and an operational metrics tool.
- **Operational Evaluation Framework**: We have separated metrics measured directly from operational logs (production time, operator modification rate) from offline detection accuracy metrics (tIoU, boundary error, Precision/Recall/F1). This is to avoid presenting incomplete accuracy estimates as if they were validated results.
- **Live Service Validation, Not Offline Experiments**: We generated, reviewed, and publicly posted 79 clips from five Asian Games baseball games. We report on the actual operational performance metrics, observed failure types, and countermeasures implemented during operations.

##### System Architecture

Each stage is linked solely by a common identifier: **the original key (vod_key) + a time interval in seconds based on the original timeline**. This allows individual components to be replaced without affecting the rest of the pipeline.

1. **Multimodal Indexing**: We separate video and audio using FFmpeg, segment speakers using pyannote.audio, recognize speech using Qwen3-ASR, and align word-level timestamps using Qwen3-ForcedAligner. Next, a Qwen-series LLM contextually corrects the transcript; PySceneDetect detects shot transitions; and a Qwen-series VLM generates scene descriptions by combining representative frames with the text. If broadcast subtitles are available, the STT step is skipped.
2. **Temporal Alignment and Semantic Chunking**: Adjacent scenes are merged based on dialogue continuity and scene semantic similarity. Game units (innings, at-bats) are treated as unbreakable boundaries.
3. **Segment Search and Candidate Generation**: Metadata (program, episode, game, and event tags) is first applied as a hard filter, and cosine similarity between scene summary embeddings is calculated only for the remaining candidates (Milvus). Based on the top k chunks, RAG generates clip titles and candidate segments.
4. **Clip Generation and Operator Review**: Only segments that pass the validity criteria are extracted using FFmpeg. After operator review and editing, they are published, and the revision history is recorded in the evaluation log.

##### Pilot Results

- **79 highlight clips were automatically generated from 5 baseball games** at the 2026 Aichi-Nagoya Asian Games and posted on SBS’s live service **“AI PICK”**. The clips included full-game highlights and short-form clips organized by inning, and processing was performed in batches after the games ended.
- **The operator correction rate was approximately 11%** (about 9 out of 79). Most edits were concentrated in the initial operational phase and primarily involved adjusting boundaries and restoring missing scenes. After fine-tuning the operational settings based on early cases, almost no further edits were required.
- **Production time per clip was reduced from approximately 15 minutes to 3–4 minutes (a reduction of about 75%)**. This is based on end-to-end processing time, including exploration, editing, review, and upload.
- Remaining tasks include completing a tIoU-based quantitative evaluation of all 79 clips (compared to AI alone) and expanding the system to other sports (soccer, basketball) as well as drama, variety, and news genres.

##### Resources

- Paper PDF: 
  <div class="notion-file"><a class="notion-file__link" href="/files/achievement/2026-adip-%EA%B5%AD%EC%A0%9C%ED%95%99%EC%88%A0%EB%8C%80%ED%9A%8C-%EB%85%BC%EB%AC%B8-%EB%B0%9C%ED%91%9C-spie/ADIP2026_PA5021_Final_Reviewer_fix.pdf" target="_blank" rel="noopener noreferrer"><span class="notion-file__ext">PDF</span><span class="notion-file__name">ADIP2026_PA5021_Final_Reviewer_fix.</span><span class="notion-file__size">pdf 461.1 KB</span></a></div>

div Conference Website: [ADIP 2026](https://adip.org/)
- Service Details: [SBS Asian Games Baseball AI PICK](https://programs.sbs.co.kr/sports/ag2026/clips/90399)
- Previous Presentation: [Paper Presentation at the 2026 Fall Conference of the Korean Institute of Broadcasting and Media Engineering](https://doc.scenemaker.solbox.com/docs/achievement/2)

> This research was conducted as part of the “Open-Source AI and Software Development and Utilization Support Project” by the Ministry of Science and ICT and the National IT Industry Promotion Agency. (Project ID: PJT-26-040089)

---

