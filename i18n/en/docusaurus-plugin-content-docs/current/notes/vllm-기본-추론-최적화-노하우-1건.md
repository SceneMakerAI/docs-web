---
title: "Best Practices for Optimizing Basic Inference in vLLMs"
sidebar_position: 10
slug: "10"
last_update:
  date: 2026-11-06
---

### Introduction

---

This article summarizes the configurations SceneMaker applied to both the vLLM server and the requesting side in an effort to **process more requests with the same GPU and fewer computations**.

SceneMaker listens to video (transcription, correction, summarization, speaker identification), analyzes it visually (cut detection, sequences, scenes), and selects scenes based on queries (programming). The language models, embeddings, and transcription inference required for these tasks are handled by a single vLLM running on a single GPU server. Models that run outside the vLLM, such as speaker separation or face recognition, are not covered in this article.

![image](/img/notes/vllm-기본-추론-최적화-노하우-1건/img-00.jpg)

- The GPU server has four 96GB GPUs and runs five vLLM engines. These consist of three language models (Qwen3.8-27B-FP8), one embedding model (Qwen3-Embedding-4B), and one speech recognition engine (Qwen3-ASR-1.7B) embedded within the transcription server.
- There are many requests. Episode 10 of the drama contained 12,540 cuts, and the language model is called once for each cut. On top of that, there are calls for correction, summarization, speaker names, sequences, scenes, and scheduling.
- Therefore, rather than simply making a single call faster, it is important to **keep the GPU busy and reduce its workload**.

This article covers the following topics:

1. Where time is spent during inference
2. Saving memory to process more data
3. Batching multiple requests to fully utilize the GPU
4. Avoiding redundant calculations
5. Reducing the number of tokens to generate
6. Reduce the number of calls

Sections 1 and 2 cover server configuration, while Section 3 and beyond cover both server configuration and **client-side configuration**.

---

#### 1. Where Time Is Spent in Inference

Language model inference is divided into two stages.

- **Input Reading (Prefill):** Reads prompts, dialogue, and screen text all at once and stores them in the KV cache. Since thousands of tokens are processed simultaneously, **computational load** is the bottleneck.
- **Decoding:** Tokens are generated one by one. Since the model weights and KV cache must be re-read from memory each time a token is generated, **memory reads** are the bottleneck.

![image](/img/notes/vllm-기본-추론-최적화-노하우-1건/img-01.jpg)

vLLM uses kernel-level optimizations such as Flash Attention and PagedAttention by default. This article covers only **configurable options** on top of those.

---

#### 2. Saving Memory to Upload More Data

**2-1. FP8 Weights**

- The size of the model weights is calculated by multiplying the number of parameters by the number of bytes per parameter. If you load a 27B model in BF16 (2 bytes), it takes up about 54GB; **in FP8 (1 byte), it takes up about 27GB**. Since even FP8 models typically leave certain parts (such as the input and output layers, and the image-reading components) in BF16, the actual weight size is a few GB larger than these figures.
- The amount saved becomes available space in the KV cache. The larger the KV cache, the more requests can be processed simultaneously (Section 3).

![image](/img/notes/vllm-기본-추론-최적화-노하우-1건/img-02.jpg)

- Quantization is determined separately for each model. The dictation model is uploaded as-is in BF16 without quantization. According to records in the code comments, on the Korean speech evaluation dataset (FLEURS), the error rate, which was 6.89% at 8-bit, rose to 19.95% when reduced to 4-bit.

**2-2. Memory Allocation Ratio** (`--gpu-memory-utilization` )

- When vLLM starts up, it allocates this percentage of GPU memory. After loading the weights and measuring the workspace required for computation, it **pre-allocates the entire remaining space as a KV cache**.
- The language model is allocated 0.85 (approximately 82 GB), and the embeddings are allocated 0.10 (approximately 10 GB). The dictation engine uses a value of 0.4 from the sample configuration file; since this ratio is based on total GPU memory, it must be readjusted if the GPU is changed.
- The word visual aligner for the transcription engine runs on Transformers rather than vLLM, using approximately 1.2 GB beyond the allocated ratio. Other engines using the same GPU must leave that much headroom.

**2-3. One Model per GPU** (`--tensor-parallel-size 1` )

- The 27B FP8 model fits entirely on a single GPU (96GB). Therefore, the model is not split across multiple GPUs (tensor parallelism). If it were split, the GPUs would have to exchange computation results between layers; however, since it all fits on a single GPU, that communication is eliminated.
- Instead, **three instances of the same model are run** to handle requests in parallel (data parallelism). We’ll see in Section 3 how the requesting side utilizes these three instances.

**2-4. Maximum Length** (`--max-model-len` )

- The language model has 131,072 tokens, and the embedding has 2,048 tokens.
- vLLM allocates the KV cache in small blocks as needed (PagedAttention). Therefore, even if the maximum length is set high, short requests only use as much space as they actually require.
- Since embeddings only handle short text, such as a scene summary or a single line of dialogue, they are kept small.

---

#### 3. Batching Multiple Requests to Fill the GPU

- Generating a response involves reading weights from memory for each token. If only one request is processed at a time, that read operation is dedicated to a single token.
- vLLM **calculates ongoing requests in batches every step** (continuous batching). It uses weights read once to generate tokens for multiple requests simultaneously. When a completed request is removed, a pending request immediately takes its place.
- The upper limit for batch size (`--max-num-seqs`) is 24 for language models and 4 for embeddings.
- For the server to batch requests, the client must **send multiple requests simultaneously**. If you send one request, wait for the response, and then send the next, the batch size is always one. Conversely, sending too many at once lengthens the server queue and delays responses. Therefore, all three services **set an upper limit on the number of concurrent requests** and send as many as possible simultaneously within that limit.

![image](/img/notes/vllm-기본-추론-최적화-노하우-1건/img-03.jpg)

**3-1. Subtitle Service: 8 concurrent requests for the entire service**

- The subtitle service receives a single language model address and sends requests to that single engine.
- The concurrent limit of 8 applies to **the entire service**, not on a per-step basis. All calls—including cast list search, correction, hallucination detection, summarization, and speaker name identification—share this limit.
- For summarization on a per-minute basis, the segments are **divided into 8 chunks and processed simultaneously**. Within each chunk, the three most recent summaries must be passed as context, so they run sequentially. The number of chunks was set to match the concurrent limit. Splitting them further would only result in them waiting at the limit.
- The reason for choosing this structure, along with measurement data, is documented in the code comments. Summarizing 115 intervals in sequence took 3 minutes and 56 seconds. Bundling multiple intervals into a single call and making only 8 calls reduced the time to 43 seconds, but the summary length decreased by 30%, empty summaries appeared, and content from different intervals became mixed. Therefore, **we kept the number of calls the same and sent them simultaneously**, letting the server group them.

**3-2. Screen Analysis · Scheduling Service: Set a Concurrency Cap for Each Engine and Route to the Least Busy One**

- Both services receive a **list** of language model engines. A separate concurrent limit is set for each engine, and each time a request is sent, the system selects **the engine with the lowest load rate (requests in progress ÷ concurrent limit)**. The limit is set to match that engine’s batching limit; the value in the sample configuration file is 8.
- The Screen Analysis Service also notes whether each engine accepts images. Cut determinations involving images are sent only to engines that accept images, while requests containing only text are routed first to engines that do not accept images. This is to conserve resources for image processing.
- Engines that continuously generate errors are removed from the list, and requests are routed to the remaining engines.
- Cut determinations display all target cuts at once, and this upper limit controls the actual number of cuts that are output.

---

#### 4. Avoiding Redundant Calculations

- Reading input is a computational bottleneck. However, SceneMaker requests **often have identical prefixes.** The same instructions are sent thousands of times.
- When prefix caching (`--enable-prefix-caching`) is enabled, vLLM compares the beginning of the input in blocks; if a block has been calculated previously, **it uses the stored KV cache as-is and skips the calculation.** Although this is enabled by default in the latest vLLM engine, it is explicitly specified in the execution settings.
- Reuse is only possible **from the very beginning up to the point where the content matches**. If even a single character differs in the middle, everything after that is recalculated. Therefore, the requesting side places **unchanging content at the beginning and content that changes each time at the end**.

![image](/img/notes/vllm-기본-추론-최적화-노하우-1건/img-04.jpg)

- **Editing:** Place video information, the glossary, and the character list after the editing instructions and at the beginning. These four elements are the same for every page within an episode. The 30 lines of dialogue that change per page come afterward.
- **Cut Assessment:** Attach the episode’s cast and synopsis to the end of the assessment rules and place them at the beginning. All cuts within an episode share the same introductory section. The sequence context, dialogue, time, and camera angles—which change with each cut—come afterward.
- **Sequence Adjustment · Scene Grouping:** Use the stage directions and the episode’s characters and synopsis as a common opening section, and place the summary, cuts, and dialogue that change for each sequence afterward.

---

#### 5. Reducing the Number of Tokens Created

Writing an answer involves creating tokens one by one. **The fewer tokens created,** the faster the call ends, and that space is used by the next request. There are three ways to reduce this.

- **Disable Thinking:** The Qwen3 series includes lengthy thought processes before the answer. Since this is unnecessary for tasks with fixed answers—such as judgment or correction—we disable it for each call. For screen analysis services, we also set the “temperature” to 0 to ensure the same input produces the same answer.
- **Call-specific answer length limit:** The required length varies by day. Instead of using a single fixed value, it is set for each call. For cut judgments—which consist of four lines (explanation, location, type, and character)—the limit is set to 240 tokens. Since this value applies to all cuts in a given round, the upper limit for a single call determines the total generation volume.
- **Enforce formatting only where necessary:** Enforcing JSON formatting adds a format check for every token. Use it only for answers that the machine must read (search term generation, correction, and hallucination detection). List extraction is intentionally handled as plain text. This eliminates the cost of format checking and allows the results to be directly appended to correction instructions.

![image](/img/notes/vllm-기본-추론-최적화-노하우-1건/img-05.jpg)

**5-1. Sequencing: Enable Reasoning for Only One Call; Limit by Time**

- In sequencing, the call that enables reasoning is **only the scene selection**. Since this involves comparing candidate scenes in a sequence to select the one that best matches the query, reasoning improves the quality of the answer. All other calls have reasoning turned off. If the global switch is turned off, this call is also processed without reasoning.
- When reasoning is enabled, the reasoning and the answer share the same upper limit, so the upper limit is set high (32,768). Instead, **the call is terminated based on time, not tokens.** If it does not complete within 480 seconds or the body is empty, the request is canceled, and the query is retried with critical thinking disabled.
- The reason for the time-based cutoff is explained in the code comments. A stalled call took hundreds of seconds and still returned an empty response, while a retry with "accident" disabled returned the same answer in just 1 second. The prolonged duration of the "accident" was due to the call being in a stalled state, not the process of arriving at an answer.
- When a request is canceled, vLLM removes that request from the batch and frees up the resource. A request that never completes does not continue to tie up GPU resources.
- The number of requests is determined by configuration. The value in the sample configuration file is “low.”

![image](/img/notes/vllm-기본-추론-최적화-노하우-1건/img-06.jpg)

---

#### 6. Reducing the Number of Calls

Each call incurs fixed costs, such as request transmission, queuing, and input reading. Performing the same task with **fewer calls** reduces those costs. However, as summarized in Section 3-1, combining too many tasks reduces the quality of the answer. Therefore, for each task, we determined **the amount to include in a single call** while maintaining quality.

- **Proofreading in 30-line batches:** Dialogue is divided into 30-line segments and proofread in a single pass. Since names and terminology must be corrected within context—which requires viewing the preceding and following lines together—we do not send lines one at a time. Instead, we send batches of 30 lines simultaneously (Section 3).
- **64 entries per embedding request:** When creating an index, we bundle 64 text entries into a single request and send them to the embedding engine.
- **Sequences and scenes: by sequence:** Scene division and scene descriptions are called once per sequence, not per cut. Sequence correction intervals are set once per episode.
- **Frames: Only as many as needed, via path:** For cut detection, only 1 to 3 frames are sent per cut. For cuts 3 seconds or shorter, all frames are sent; for longer cuts, 3 frames are sent—one at the beginning, one in the middle, and one at the end. Since images are tokenized proportionally to their resolution, the cost of reading input increases with the number of frames. Frames are downsampled to 1280×720 when extracted from the video.
- Images are sent as **file paths** rather than the file contents themselves. Since the frame files are already stored on the GPU server’s disk, there is no time spent encoding and transferring the images, nor is there any request size overhead. The server is configured to read only files under the allowed paths (`--allowed-local-media-path`).

---

### Conclusion

---

SceneMaker’s vLLM optimization follows two approaches.

- **Preventing GPU idle time:** We reduce weights to FP8 to free up space in the KV cache, and have the requesting side send data simultaneously within the engine’s batch size limit so the server can batch and compute it.
- **Reducing the GPU’s workload:** Prepend fixed content to reuse input computations; disable reasoning and set the answer length per call to reduce generated tokens; and limit the amount loaded per call to reduce the number of calls.

Server configuration alone is only half the story. Batch processing and cache reuse are effective **only when the client sends requests simultaneously and maintains the same prefix.**

Reference Links)

- [https://docs.vllm.ai/](https://docs.vllm.ai/)
- [https://huggingface.co/Qwen/Qwen3-Embedding-4B](https://huggingface.co/Qwen/Qwen3-Embedding-4B)

*This article presents the results of research conducted with support from the Ministry of Science and ICT and the National IT Industry Promotion Agency’s “2026 Open-Source AI and Software Development and Utilization Support Project.”*

