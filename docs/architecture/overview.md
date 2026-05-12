---
id: overview
title: 시스템 아키텍처 개요
sidebar_position: 1
slug: /architecture/overview
---

# 시스템 아키텍처

SceneMakerAI 방송 AI 플랫폼의 상위 수준 아키텍처입니다.

> 🚧 다이어그램과 상세 설명은 추후 추가됩니다.

## 예정 다이어그램

- 시스템 컴포넌트 개요
- 데이터 흐름 (수집 → 분석 → 색인 → 서빙)
- LangGraph 워크플로우 상태 그래프
- vLLM 추론 클러스터 토폴로지

## 기술 스택 한눈에 보기

- **LLM / VLM**: Qwen3.5 (Apache 2.0, MoE 397B / 17B 활성, 262K 컨텍스트)
- **워크플로우 오케스트레이션**: LangGraph (MIT)
- **추론 서버**: vLLM
- **음성 인식**: faster-whisper
- **음성 분석**: librosa
- **벡터 DB**: Qdrant
- **RAG**: LangChain
