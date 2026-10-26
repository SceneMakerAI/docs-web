---
id: 2026-aichi-nagoya-asian-games-baseball-pilot-service
title: "2026 Aichi-Nagoya Asian Games Baseball Pilot Service"
sidebar_position: 1
slug: "1"
last_update:
  date: 2026-10-26
---

##### 2026 Fall Conference of the Korean Institute of Broadcast and Media Engineers

Paper presented at an academic conference

### Design and Validation of an Automatic Media Video Clip Generation System Using Broadcast Metadata and AI Content Analysis


Authors

##### Kyu-Hyuck Jung · Dongwoon Choi · Jongpil Lee · Minsung Im

SBSI | Kyu-Hyuck Jung · Dongwoon Choi 

SOLBOX | Jongpil Lee · Minsung Im

SBS I SOLBOX

[kyuhuck@sbs.co.kr](mailto:kyuhuck@sbs.co.kr) · [dongwoon.choi@sbs.co.kr](mailto:dongwoon.choi@sbs.co.kr)  
 [jplee@solbox.com](mailto:jplee@solbox.com) · [minsung7336@solbox.com](mailto:minsung7336@solbox.com)

October 2026

Research Presenter: Kyu-Hyuk Jung (SBSI)

---

### Research Background and Acknowledgments

##### Research Background

A vast amount of broadcast content—spanning news, sports, entertainment, and factual programming—is produced daily. Following the initial broadcast, this original content is often repurposed into highlights and short-form videos for various platforms, including mobile, web, OTT services, and social media. However, the process of manually reviewing long-form footage to identify key moments, determining the start and end points for clips, and verifying the synchronization of subtitles and audio remains highly labor-intensive and time-consuming. This challenge is particularly pronounced in environments involving continuous video streams, such as live broadcasts or major sporting events, where maintaining both production speed and consistent quality is difficult to achieve.

Recent achievements in government-funded R&D projects and the growth of the open-source ecosystem have expanded the technical foundation for addressing these real-world challenges. By combining video frame analysis, speech recognition, subtitle and text extraction, natural language processing, and multimodal AI, it is possible to gain a more multidimensional understanding of the events and situations captured in video. Open-source technologies—such as FFmpeg—along with AI-driven analytical tools, provide a framework for integration with existing broadcasting systems. Furthermore, the metadata that broadcasters have accumulated regarding schedules, programs, and sporting events plays a crucial role in interpreting AI analysis results within the specific context of the actual content.

The introduction of AI goes beyond a simple attempt to replace human tasks with machines. Its core purpose is to automate processes like repetitive segment searching and the creation of draft clips—thereby reducing the workload on creators—while enabling humans to focus more on interpreting the meaning and context of scenes, refining the quality of the edit, ensuring suitability for the intended service, and overseeing final quality control. This collaborative framework between humans and AI not only enhances operational efficiency but also plays a vital role in maintaining the credibility of broadcast content and upholding editorial responsibility.

Against this backdrop, this study aimed to design a practical system—integrating broadcast metadata with AI-based video analysis—that encompasses key scene detection, clip segmentation, automated content generation, operator review, and service integration, while also evaluating its feasibility within an actual production environment. It is hoped that this research will serve as a useful reference for enhancing the utility of large-scale broadcast video archives, streamlining repetitive tasks, and fostering the internal adoption of technology within production workflows.

##### Acknowledgments

This research and the implementation of the system were made possible through the expertise and close collaboration of various stakeholders. Above all, I would like to express my deepest gratitude to the team at SOLBOX for their dedicated work in developing the core AI video processing engine. Their efforts in tailoring video analysis technologies to meet field requirements and ensuring stable integration served as a vital foundation for this system.

I also extend my sincere thanks to the team at SBSI for their invaluable contributions—sharing insights and collaborating to resolve challenges throughout the processes of integrating broadcast metadata, developing the system, and verifying its performance for operational deployment. Their collective experience was instrumental in overcoming technical hurdles and enhancing the system’s practical applicability, ultimately allowing this research to evolve into a tangible achievement.

Finally, I would like to express special appreciation to the CEO of SBSI for the interest and support that enabled the presentation of these research findings at an academic conference. I truly value the trust and encouragement shown throughout every stage—from research and development to field validation and final presentation. This achievement is not the result of any single individual’s work, but rather the product of the combined efforts of everyone involved.

October 2026

Research Presenter: Kyu-Hyuk Jung (SBSI)

---

#### Design and Validation of an Automatic Media Video Clip Generation System Using Broadcast Metadata and AI Content Analysis


Authors

##### Kyu-Hyuck Jung · Dongwoon Choi · Jongpil Lee · Minsung Im

SBSI | Kyu-Hyuck Jung · Dongwoon Choi 

SOLBOX | Jongpil Lee · Minsung Im

SBS I SOLBOX

[kyuhuck@sbs.co.kr](mailto:kyuhuck@sbs.co.kr) · [dongwoon.choi@sbs.co.kr](mailto:dongwoon.choi@sbs.co.kr)  
 [jplee@solbox.com](mailto:jplee@solbox.com) · [minsung7336@solbox.com](mailto:minsung7336@solbox.com)

October 2026

Research Presenter: Kyu-Hyuk Jung (SBSI)

##### Abstract

In the broadcasting and media landscape, the growing utilization of secondary content—such as short-form videos and highlights—has created a demand for automated technologies capable of rapidly identifying significant segments within video footage and generating clips. Traditional clip production is a manual, labor-intensive process that requires operators to review entire videos to determine start and end points. This paper proposes a system that integrates broadcasting-domain metadata (held by SBSI) with external AI-based content analysis to automatically detect key segments and generate clips for service. Our contributions include: a hybrid architecture that leverages broadcasting metadata both as a basis for semantic chunking and as a filter for segment retrieval; a "human-in-the-loop" workflow that validates generated segments against the original timeline and incorporates operator feedback (edit history) back into the system; and the definition of a quantitative evaluation protocol based on tIoU (temporal Intersection over Union). The system was empirically tested using baseball matches from the 2026 Aichi-Nagoya Asian Games, resulting in the automated generation of 79 clips across five games. In these initial applications, the generated clips required only minor adjustments—approximately 10%—before being deployed for actual service. Furthermore, we present a scalable architecture designed to be extended across a broader range of SBS media content, including entertainment, news, and factual programming.

Keywords: Broadcasting metadata, AI content analysis, multimodal AI, automated clip generation, media content

##### 1. Introduction

Broadcasters repurpose a single piece of original content for distribution across various channels, including traditional TV, mobile, web, OTT platforms, social media, and short-form video services. The ability to rapidly identify high-value segments within long-form footage and convert them into short clips directly impacts both the speed of content distribution and operational efficiency. However, conventional workflows rely heavily on human experience and manual labor; consequently, in environments where production volume surges—such as during large-scale sporting events—the operational burden escalates rapidly.

The objective of this study is not to enhance the performance of the AI models themselves, but rather to design an integrated architecture that connects a broadcaster’s domain-specific metadata with external AI analysis APIs. This framework automates the entire process—from video analysis and segment extraction to clip generation and service integration—shifting the operator’s role toward reviewing and refining the results proposed by the AI.

1.1 Related Work and Differentiation

Research on the automated generation of sports highlights has primarily focused on selecting key moments by fusing multimodal indicators of excitement, such as crowd cheers, commentary, and athlete reactions [1]. Segment retrieval based on natural language queries has evolved largely through the use of public benchmarks [2], while learning-based models are widely employed for detecting scene boundaries [3]. Existing research, however, has largely prioritized detection accuracy on public datasets, often overlooking the complexities of real-world production pipelines—which must integrate broadcasting schedules, match metadata, service-specific rules, and human review procedures. Rather than proposing a new detection model, this paper presents an integrated architecture that utilizes broadcasting metadata as criteria for segmenting and filtering, validates generated segments against the original video timeline, and incorporates the history of operator-made corrections back into the system as an evaluation metric.

##### 2. Proposed System Design

2.1 Overall Architecture

In terms of the division of roles, the SOLBOX analysis core generates structured scene information from video, audio, OCR, and subtitles, while the SBSI (SOLBOX Service Integration) component manages source content and broadcast metadata, handles integration with analysis APIs, performs segment verification, generates clips, and facilitates service connectivity. As illustrated in Figure 1, the processing workflow consists of four stages: ① multimodal indexing, ② temporal alignment and semantic chunking, ③ segment retrieval and candidate generation, and ④ clip generation and operator review. Each stage utilizes a combination of a source key and a specific time interval (in seconds) as a common identifier. Broadcast metadata is employed twice—as a criterion for chunking in stage ② and as a search filter in stage ③—while any modifications made by operators during stage ④ are recorded as evaluation logs.

![image](/img/achievement/2026-aichi-nagoya-asian-games-baseball-pilot-service/img-00.png)

Figure 1. Overall structure of the proposed system and its four-stage processing flow

2.2 AI Content Analysis Integration

AI analysis utilizes a combination of visual features, audio, OCR, and subtitles. FFmpeg is used to separate video from audio, while pyannote-audio [4] is employed for speaker diarization—detecting speech segments and speaker turns—to establish units for analysis. Since broadcast audio often contains a mix of crowd noise and commentary, initial recognition results are not immediately accepted as final, verified dialogue; instead, they undergo a secondary validation process.

Speech-to-text (STT) transcription and temporal data are generated using Qwen3-ASR [5], with word-level timestamps assigned via Qwen3-ForcedAligner. This produces a preliminary STT transcript consisting of the speaker, start and end times, and the spoken content. Subsequently, a Qwen-series large language model (LLM) is used to detect and correct contextual errors and hallucinations within each dialogue segment to finalize the transcript.

In segments where broadcast subtitles are available, speech recognition is bypassed to reduce both processing costs and potential recognition errors. Representative frames for each scene, along with the corresponding STT, OCR, and subtitle data, are fed into a Qwen-series vision-language model (VLM) to generate scene descriptions [6]. A core design principle is to select and provide only a representative frame for each scene—rather than processing every frame—thereby managing input volume and inference costs. The analysis results are aligned to a timeline (in seconds) relative to the start of the original source; for segmented video clips, the original start offset is added to the local timestamp. The processing stages and the tools employed are summarized in Table 1.

| Processing steps | Technologies and Models Used | role |
| --- | --- | --- |
| Video/Audio Separation | FFmpeg | Separating frames and audio streams from input video |
| Speaker Diarization | **pyannote** | Speaker Turn and Utterance Segment Detection |
| Speech-to-Text (STT) | Qwen3-ASR | Speech-to-Text (STT) Transcription |
|  Word Sorting | Qwen3-ForcedAligner |  Assigning word-level timestamps |
| Contextual Summary | Qwen family of LLMs | Overview of STT Context and Hallucinations |
| Scene Transition Detection | PySceneDetect | Detect cut transition points to determine analysis units |
|  Scene Description and Summary |  Qwen-series VLMs and LLMs | Integrate representative frames and text to describe the meaning of a scene and organize it into searchable units. |

Table 1. Processing Elements for Each Stage of Multimodal Indexing

2.3 Fusion of Broadcast Metadata

General-purpose AI analysis alone is insufficient to capture the scheduling context of a broadcast or the specific objectives of a service. By using identifiers—such as those for programs, episodes, matches, or content—as primary keys, detected events are organized into meaningful units tailored for service use. Since a visual scene transition does not necessarily signify the end of an event, chunks are merged by considering factors such as the continuity of dialogue across adjacent scenes and the context of the match, as illustrated in Figure 2.

Each chunk is structured as follows: {vod_key, segment_id, start_sec, end_sec, transcript, scene_summary, tags}. Embeddings of the scene summaries are stored in a vector database (Milvus) [7], while program and match information are managed as attributes for search filtering. Both the query and the chunks are converted using the same embedding model, and candidate results that meet the specified broadcast criteria are retrieved based on cosine similarity.

![image](/img/achievement/2026-aichi-nagoya-asian-games-baseball-pilot-service/img-01.png)

Figure 2. Conceptual example of original timeline alignment and chunking into meaningful units

**2.4 Automated Clip Generation and Operator Review**

Once candidate key events are selected, the system determines the start (IN) and end (OUT) points for each event and performs automated cutting. The top *k* retrieved chunks are provided as context for Retrieval-Augmented Generation (RAG) [8], enabling an LLM to generate titles and define the candidate segments. The generated results are cross-referenced against the original source keys and their corresponding timestamps; only segments satisfying the condition 0 ≤ IN < OUT ≤ original duration are passed to the FFmpeg extraction stage. This "human-in-the-loop" process allows operators to review and refine the generated clips before they are deployed to the service, with all modifications recorded in an evaluation log.

##### 3. Application to Baseball at the 2026 Aichi-Nagoya Asian Games

The 20th Asian Games were held in Aichi Prefecture and Nagoya City, Japan, from September 19 to October 4, 2026[9]. The baseball tournament concluded on September 27. Baseball is well-suited for this purpose because the game is structured around individual pitches—providing clear event boundaries—and official match records include precise timing information, making it easy to define specific segments. Furthermore, since the tournament concluded before the academic conference presentation, it was possible to conduct a quantitative evaluation using real-world operational data. Consequently, baseball was selected as the initial sport for this demonstration.

3.1 Application Scenario for Baseball

In baseball broadcasts, key moments occur repeatedly throughout a game, and there is a need to produce highlights and short-form content shortly after the game ends. Traditionally, human operators had to manually review the footage to locate and mark significant events, such as home runs, timely hits, or exceptional defensive plays. In the proposed system, once the raw footage is ingested, AI analysis results are combined with SBSI’s match and content metadata to automatically generate potential clips. The demonstration for baseball has been completed; the system was applied to five games during the tournament, resulting in the automatic generation of 79 highlight clips, which were then published on the actual service platform (AI PICK)[10]. Figure 3 shows the interface displaying clips automatically generated from four different games (involving Japan, China, Thailand, and Taiwan).

![image](/img/achievement/2026-aichi-nagoya-asian-games-baseball-pilot-service/img-02.png)

Figure 3. Actual service interface showing automatically generated highlight clips for individual games.

Key events are defined as home runs, timely hits, runs scored, strikeouts, double plays, stolen bases, and spectacular defensive plays. Detection cues include changes in the inning, out count, ball count, or score (via scoreboard OCR); broadcast cut patterns—such as transitions from a batted ball to player reactions or replays; and specific keywords from commentary or sudden spikes in audio energy from crowd cheers. Each clip spans from the moment just before a pitch is thrown until the conclusion of the subsequent reaction or replay.

| Step | Example of application in baseball |
| --- | --- |
| Obtaining the footage | Original source material for generating match VODs and clips, available after the match concludes |
| AI Analysis | Extracting candidate events through commentary, subtitles, scoreboard OCR, and scene analysis |
| SBSI Metadata | Game date, inning, matchup, lineup, content ID, service keyword |
| Automatic processing | Generate IN/OUT points for each event candidate, then merge and cut the replays. |
| Service Usage | Match highlights and short-form content provided; service reflected after operator review. |

Table 2. Scenarios for Applying AI-Automated Clipping to Baseball at the Asian Games

3.2 Empirical Results and Evaluation Methodology

Three approaches—manual processing, AI-only analysis, and a method integrating broadcast metadata—are compared using the same matches. The evaluation covers five baseball games (resulting in 79 generated clips) held between September 19 and 27, including both preliminary and final rounds; games used for parameter tuning are kept separate from those used for evaluation. Ground-truth segments are established based on event timestamps from official match records, then independently refined by at least two operators. A segment is accepted as a consensus ground truth if the temporal Intersection over Union (tIoU) between the two sets of labels is 0.7 or greater. Experimental conditions—including model version, prompts, chunking criteria, the number of retrieval candidates (k), and the hardware used—are documented to ensure reproducibility.

Temporal overlap between a ground-truth segment (G) and a predicted segment (P) is defined as tIoU = |P∩G| / |P∪G|, following standard evaluation protocols in the field of temporal action detection [11]. Precision, recall, and F1-score are calculated based on a one-to-one correspondence, using a threshold of tIoU ≥ 0.5 to define a match. Boundary error is calculated as the mean absolute error between the start and end timestamps of corresponding segments, while instances of missed or redundant detections are tracked separately. Since the comparisons involve paired observations from the same matches, statistical significance is assessed using the Wilcoxon signed-rank test.

The operator correction rate is defined as the number of corrections made divided by the total number of candidates reviewed. The reduction in processing time is calculated as: (manual processing time − proposed method processing time) / manual processing time × 100. Time spent on preprocessing, inference, and encoding is tracked separately from human labor time; the latter also includes time spent on re-searching due to missed candidates or segment errors. In the empirical results, 79 clips—automatically generated from five matches—underwent operator review before being published on the service. During the initial application—specifically for the match between South Korea and Taiwan on September 21—the boundary errors in the generated clips were minimal; operators only needed to make adjustments to about 10% of the content, such as adding missing segments or fine-tuning the boundaries, before the clips were ready for the service. Production time is defined as the duration from segment searching and editing to final upload; under existing manual workflows, this process takes approximately 18 minutes per clip (totaling about 24 hours for 79 clips). The remaining parameters in Table 3 represent target values estimated based on the initial application results, accounting for the time required for review and correction according to the rate of necessary adjustments. The metadata-fusion approach aims to reduce production time by approximately 80%, and this is verified for all 79 clips using the aforementioned protocol.

| condition | **F1** | Boundary error (s) | fertility(%) | Production time (minutes/item) |
| --- | --- | --- | --- | --- |
| Manual (standard) | – | – | – | 18 |
| AI analysis only | 0.80 | 2.6 | 28 | 7 |
| Metadata Fusion | 0.92 | 1.1 | 10 | 3 |

Table 3. Target Performance and Production Time by Condition for Baseball (Manual processing times are based on actual measurements)

3.3 Risk Factors and Mitigation Strategies

The primary risk factors were delays in acquiring source material and an insufficient number of games, as the demonstration was constrained by the tournament schedule. To address this, the processing workflow was structured around individual games, with the pipeline configured to trigger automatically upon the arrival of source data; this ensures that metrics can be generated on a per-game basis, even when the total number of games is limited. To handle the issue of identical scenes recurring during replays, the system merges candidates that are temporally adjacent and share similar scene descriptions into a single event. For scoreboard OCR, the system uses pre-registered, standardized tournament graphic formats, while any segments where recognition fails are supplemented with official match records. In cases where speech recognition quality is degraded by crowd noise or multilingual commentary, the system prioritizes the use of subtitles; if subtitles are unavailable, it infers events by correlating audio energy levels with changes in the score. To manage the risk of erroneous scene descriptions, the system discards candidates that do not meet validity criteria and delegates final verification to human operators. Due to restrictions regarding the use of international broadcast feeds and copyright constraints, the evaluation is conducted within an internal environment.

##### 4. Expansion to SBS Media Content

This system is designed around a common interface that integrates AI-driven analysis results with broadcast-domain metadata, rather than relying on algorithms exclusive to sports. Consequently, as shown in Table 4, the scope of application can be extended beyond sports to various other SBS media genres, such as entertainment, news, and factual programming. Furthermore, the scene-level analysis data can serve as a foundation for integrating advertisements, events, and e-commerce. However, the initial demonstration is limited to the retrieval of key scenes and the generation of clips subject to human verification.

| Content | Examples of AI Analysis | Examples of Service Application |
| --- | --- | --- |
| sports | Scores, players, scoreboard OCR, commentary, and audience reactions | Highlights, short-form content |
| Variety Show | Cast dialogue, subtitles, laughter/reactions, and scene transitions | Highlight scenes, clips by cast member |
| News/Current Affairs | Speech-to-text (STT), subtitles, people, locations, and topics | Sections by topic, search |
| Common Extensions | Objects, products, locations, and conversational context | Advertising, events, commerce, recommendations |

Table 4. Examples of AI Analysis and Service Expansion by Broadcast Genre

##### 5. Conclusion

In this study, we proposed a system that integrates broadcast metadata held by SBSI with external AI-based content analysis technology to automatically detect meaningful segments within media footage and generate clips for service use. The analysis pipeline was constructed primarily using publicly available open-source models and libraries, designed to be portable into a broadcaster’s internal environment.

A pilot test was conducted during the baseball tournament at the 2026 Aichi-Nagoya Asian Games, resulting in the automatic generation and delivery of 79 clips across five matches. In the initial trial matches, the generated clips required only minor adjustments—approximately 10%—before being deployed for actual service, confirming the system's viability for professional broadcasting operations. Future research will involve conducting a quantitative evaluation of all 79 clips, extending the validated framework to other sports as well as entertainment, news, and factual programming, and integrating the results of scene-level semantic analysis with digital services such as search, recommendations, and advertising.

##### Acknowledgment

This research was conducted as part of the "Support Project for Open-Source AI/SW Development and Utilization," funded by the Ministry of Science and ICT and the National IT Industry Promotion Agency (Project ID: PJT-26-040089).

##### References

- Merler et al., “Automatic Curation of Sports Highlights Using Multimodal Excitement Features,” IEEE Trans. Multimedia, vol. 21, no. 5, pp. 1147-1160, 2019.
- Lei, T. L. Berg, and M. Bansal, “QVHighlights: Detecting Moments and Highlights in Videos via Natural Language Queries,” Proc. NeurIPS, 2021.
- Souček and J. Lokoč, “TransNet V2: An Effective Deep Network Architecture for Fast Shot Transition Detection,” Proc. ACM Multimedia, 2024.
- Bredin, "pyannote.audio 2.1 Speaker Diarization Pipeline: Principle, Benchmark, and Recipe," Proc. Interspeech, pp. 1983-1987, 2023.
- Shi et al., "Qwen3-ASR Technical Report," arXiv:2601.21337, 2026.
- Qwen Team, "Qwen3.6 and 8 Open Model Series," GitHub, 2026. Available: [https://github.com/QwenLM/Qwen3.8](https://github.com/QwenLM/Qwen3.8)
- Wang et al., "Milvus: A Purpose-Built Vector Data Management System," Proc. ACM SIGMOD, pp. 2614-2627, 2021.
- Lewis et al., “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,” Proc. NeurIPS, 2020.
- Aichi -Nagoya 2026 Asian Games Organizing Committee, “20th Asian Games Aichi-Nagoya 2026,” 2026.
- SBS, "2026 아이치나고야 아시안게임 야구 AI PICK 클립," SBS Sports, 2026. Available: [https://programs.sbs.co.kr/sports/ag2026/clips/90399](https://programs.sbs.co.kr/sports/ag2026/clips/90399)
- Caba Heilbron et al., “ActivityNet: A Large-Scale Video Benchmark for Human Activity Understanding,” Proc. IEEE CVPR, 2015.

