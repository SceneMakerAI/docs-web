---
title: "Analysis of GPU Infrastructure Costs"
sidebar_position: 2
slug: "2"
description: "Comparison of Cloud GPU Instances for LLM and VLM Inference and Estimation of Monthly Costs"
last_update:
  date: 2026-11-13
---

### 1. Overview

This document calculates the costs of running SceneMaker’s inference layer (vLLM-based text LLM, VLM, and embeddings; GPU workers) in the cloud.

This report compares major GPU instances on AWS, Azure, and GCP using the same criteria and summarizes the monthly costs in Korean won based on continuous operation.

---

### 2. Calculation Criteria

| Item | Criteria |
| --- | --- |
| Pricing Type | On-Demand, Linux, no commitments or discounts applied |
| Reference Regions | **Seoul → Tokyo → US East** in that order. Only instances not available in Seoul are charged at the unit price of the next region in the order |
| Storage | Calculated separately from instance costs (see 3.2) |
| Exchange Rate | **1 USD = 1,400 KRW** (A conservative estimate accounting for exchange rate fluctuations. The reference rate on the Seoul foreign exchange market as of late October 2026 was approximately 1,338 won) |
| Calculation Formula | Monthly Cost (won) = Hourly Rate × 30 days × Exchange Rate, rounded to the nearest 1,000 won |

Since storage (EBS) is charged even when the instance is stopped, the full monthly amount per instance is added separately, regardless of uptime. Network egress, snapshot, and S3 costs are excluded.

---

### 3. Price Comparison

#### 3.1 Instance Costs

| Purpose | Provider | Instance Name | GPU | VRAM (GB) | Available Regions | Price (USD/H) | Price (KRW/Month) (30 days) | Features |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LLM | AWS | g7e.4xlarge | RTX PRO 6000 Blackwell × 1 | 96 | Seoul | 4.916 | 4,955,000 | Single GPU 96 GB, lowest VRAM unit price |
|  |  | g7e.12xlarge | RTX PRO 6000 Blackwell × 2 | 192 | Seoul | 10.187 | 10,268,000 | Simultaneously runs LLM and VLM on separate GPUs. PCIe connection between GPUs |
|  |  | g7e.24xlarge | RTX PRO 6000 Blackwell × 4 | 384 | Seoul | 20.375 | 20,538,000 | PCIe bottleneck during tensor parallel processing of large models; verification required |
|  |  | p4de.24xlarge | A100 80GB × 8 | 640 | Tokyo (not available in Seoul) | 37.622 | 37,923,000 | Previous-generation Ampere; does not support FP8 |
|  |  | p5.4xlarge | H100 × 1 | 80 | Tokyo (Not available in Seoul) | 8.600 | 8,669,000 | Single H100 GPU |
|  |  | p5.48xlarge | H100 × 8 | 640 | Seoul | 75.955 | 76,563,000 | NVLink·EFA, for training and large models |
| LLM | Azure | NC40ads_H100_v5 | H100 NVL × 1 | 94 | Seoul | 9.423 | 9,498,000 | 94 GB VRAM. About 10% more expensive than AWS p5.4xlarge (Tokyo $8.60) |
|  |  | NC80adis_H100_v5 | H100 NVL × 2 | 188 | Seoul | 18.846 | 18,997,000 | Two H100 NVLs connected via an NVLink bridge |
|  |  | ND96isr_H100_v5 | H100 × 8 | 640 | Seoul | 132.732 | 133,794,000 | InfiniBand. Approximately 1.75 times that of AWS p5.48xlarge (Seoul) |
| LLM | GCP | g2-standard-96 | L4 × 8 | 192 | Seoul | 10.278 | 10,360,000 | Not suitable for LLM due to 24 GB per GPU. Intended for deploying STT and detection workers |
|  |  | a3-highgpu-8g | H100 × 8 | 640 | Seoul | 112.794 | 113,697,000 | Approximately 1.49 times that of AWS p5.48xlarge (Seoul) |

#### 3.2 EBS Costs (Seoul, gp3)

| Item | Specifications | Unit Price (Seoul) | Monthly Fee for 100 GB |
| --- | --- | --- | --- |
| Capacity | 100 GiB | $0.0912/GB·month | $9.12 |
| IOPS | 3,000 | Free up to 3,000 | $0 |
| Throughput | 125 MB/s | Free up to 125 MB/s | $0 |
| **Total** |  |  | **$9.12 ≈ 13,000 KRW** |

The currently running GPU server volume (gp3 300 GiB, 3,000 IOPS, 125 MB/s throughput) costs $27.36 per month, or approximately 38,000 KRW.

---

### 4. Analysis

##### 4.1 Cost Efficiency

| Metric | Lowest | Highest | Notes |
| --- | --- | --- | --- |
| USD / GPU·h | GCP L4 $1.28 · AWS A100 $4.70 · AWS g7e $4.92 | Azure H100 (ND96isr) $16.59 | Caution: Direct comparisons are not recommended due to differences in GPU generation and VRAM |
| USD / VRAM GB·h | g7e.4xlarge $0.051 · g7e.12/24xlarge $0.053 · g2 $0.054 | Azure ND96isr $0.207 | This metric is more important for inference (model-resident) |

##### 4.2 Key Considerations

1. **Inference servers: AWS g7e series**
    A single 96GB GPU in Seoul costs $4.92 per hour, making it approximately 43% cheaper than a single H100 GPU (p5.4xlarge, 80GB, Tokyo: $8.60).  
   This is well-suited to the current architecture, which distributes Qwen-series text LLMs, Qwen3-VL, and embeddings across separate GPUs

2. **AWS offers the lowest prices for configurations with 8 H100 GPUs**
   With AWS reducing P5 pricing by approximately 44% in June 2025, the p5.48xlarge instance in Seoul now costs 57% of Azure’s ND96isr and 67% of GCP’s a3-highgpu. Recommended for short-term use only when fine-tuning or training large models is required

3. **Check TP performance for g7e multi-GPU**
   Since the RTX PRO 6000 lacks NVLink, it communicates via PCIe during tensor parallel processing on the 12xlarge and 24xlarge instances. This approach involves deploying the model on a single GPU and horizontally scaling the instances

---

### 5. Cost-Saving Options (AWS)

| Option | g7e.4xlarge | p5.48xlarge | Conditions |
| --- | --- | --- | --- |
| On-Demand | $3.998/h | $55.04/h | No commitment |
| EC2 Instance Savings Plan (1 year) | $2.519/h (−37%) | Approx. $38.53/h (−30%) | 1-year commitment, automatic payment |
| EC2 Instance Savings Plan (3 years) | $1.727/h (−57%) | Approx. $24.77/h (−55%, 3-year RI) | 3-year commitment |
| Capacity Block | — | $34.608/h | Term reservation, prepaid, guaranteed capacity |
| Spot | Approx. $1.7/h | Unstable availability | Only for batch jobs that tolerate interruptions |

The amounts above are **based on the us-east-1 region** and are provided for reference regarding discount rates. In the Seoul region, the g7e Spot discount is only about 10%, so the benefits of Spot are limited. 

The committed unit price for the Seoul region must be verified separately using the AWS Pricing Calculator.

For inference servers confirmed to run continuously, consider a Savings Plan; for occasional training, consider Capacity Block; and for analytical batch jobs that can be retried, consider Spot.

---

### 6. Important Notes

- For high-performance GPUs (P5, ND, A3), capacity is often unavailable even on-demand, so you must apply for a quota in advance.
- Prices are based on the published price list and may vary depending on provider pricing changes and exchange rates. You must verify the exact budget using each provider’s Pricing Calculator.
- A conservative exchange rate of 1,400 KRW is applied.
- Since the p4de.24xlarge and p5.4xlarge instances, which use Tokyo region pricing, are not available in the Seoul region, you must consider cross-region data transfer costs and latency when integrating them with other resources in Seoul.

---

