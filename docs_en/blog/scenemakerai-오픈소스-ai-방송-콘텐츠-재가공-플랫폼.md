---
title: "SceneMakerAI — An open-source AI-powered content repurposing platform for broadcasting"
sidebar_position: 1
slug: "1"
---

SceneMakerAI is a platform that uses open-source AI to automatically repurpose broadcast content.

### What It Does

It takes live broadcast and VOD videos as input and automatically performs the following tasks:

- **Multilingual Subtitle Generation**: High-speed STT based on Qwen3 + automatic translation

- **Scene Analysis**: Understanding video frames using a multimodal LLM

- **Content Repurposing**: Clip extraction, highlight generation, summarization

### Technology Stack

| Layer | Component |

|--------|----------|

| STT | Qwen3-Omni, Whisper |

| Translation | DeepL API |

| Video Processing | FFmpeg |

| Documentation | Docusaurus 3 + Notion Sync |

### Topics Covered in This Blog

- Model benchmark results (specialized for Korean broadcasts)

- Architecture design decisions and rationale

- Open-source contribution guide

