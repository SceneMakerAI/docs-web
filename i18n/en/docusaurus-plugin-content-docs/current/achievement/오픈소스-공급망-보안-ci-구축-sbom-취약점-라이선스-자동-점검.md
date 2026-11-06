---
title: "Implementing CI for Open-Source Supply Chain Security (Automated SBOM, Vulnerability, and License Checks)"
sidebar_position: 5
slug: "5"
last_update:
  date: 2026-11-05
---

> 💡 **Applied to 9 repositories (2 public, 7 private) · Generate SBOMs for every PR and release · Automatic vulnerability and license checks · Release signature verification · 0 GPL or AGPL licenses out of 508 integrated assets**
We’ve integrated software supply chain checks into the CI pipeline for all SceneMakerAI service repositories. Every time the code changes, we generate a list (SBOM) of the open-source components it contains, and if any high-risk vulnerabilities or prohibited licenses are detected, we automatically mark the release for distribution as “disabled.”

---

### 1. Why We Built It

SceneMakerAI runs on top of hundreds of open-source components, including vLLM, FFmpeg, PyTorch, Whisper-based STT, and Pillow. To install and deliver this product to broadcasters’ equipment, we must be able to demonstrate the following three points:

| Question | Verification Method |
| --- | --- |
| Which open-source components (and their versions) are included in this release? | SBOM (SPDX · CycloneDX format) |
| Does it contain any known critical vulnerabilities? | Vulnerability Gate |
| Are there any licenses that would prevent redistribution? | License Gate · Open-Source Disclaimer |

If a person were to verify this manually with every release, it would be easy to overlook something, and no record would be kept. Therefore, we integrated these checks into the repository’s CI so that they run automatically with every change and release, leaving the results as evidence.

#### Terminology

**SBOM (Software Bill of Materials)**  
This is a list of open-source components included in the software. Similar to the ingredient list on food packaging, it records which packages are included and in which versions, along with their respective licenses and sources, in a machine-readable format. SPDX and CycloneDX are international standard formats.

With an SBOM, when a new vulnerability is disclosed, you can immediately verify “which parts of our deployment are affected.” During the 2021 Log4j vulnerability incident, many organizations were unable to even determine whether the library was present in their systems, leading to delayed responses. Subsequently, the U.S. and other countries began requiring the submission of SBOMs for software supplied to the public sector.

| Term | Meaning |
| --- | --- |
| CVE · GHSA | Unique identifiers assigned to disclosed vulnerabilities. CVE is an international standard identifier, while GHSA refers to the identifier used in the GitHub vulnerability database. |
| Vulnerability Severity | Critical · High · Medium · Low. “Critical” indicates a vulnerability that can be easily exploited remotely. |
| purl | A standard identifier that refers to a package (e.g., `pkg:pypi/pillow@13.0.0`). |
| Gate | An automated check that prevents progression to the next step if the risk exceeds a certain threshold. |
| Release · Pre-release | “Release” refers to a version finalized for distribution. “Pre-release” indicates a test version and should not be used for distribution. |
| attestation (signature) | A signature that cryptographically verifies who created this file and the process used to create it. If the file is altered even slightly, verification will fail. |
| Open Source Notice (NOTICE) | A document listing the open-source software used and their license terms. Most licenses require that this notice be included when redistributing the software. |

---

### 2. Inspection Structure

Inspections are conducted at three stages. A preliminary check is performed on the PR, and the final determination is made at the time of release.

| Stage | Action | On Failure |
| --- | --- | --- |
| **PR** | Review of governance documents; check for critical vulnerabilities in newly added or modified dependencies and prohibited licenses; preview of the SBOM after merge; update the PR with one comment containing the review results | Public repositories block PRs that introduce prohibited items; for all others, a warning is issued |
| **Snapshot** (when “main” changes · 1st of every month) | Retain the SBOM and vulnerability/license reports based on “main” for 90 days | Not a failure condition as it is for observation purposes. Serves as input for monthly checks |
| **Release Publication** | Generate SBOM and open-source disclosure statement → Check compliance, license identification rate, and malicious packages → Vulnerability gate → License gate → Sign(attestation) → Attach 6 types of deliverables | Change the Release to **Pre-release and add a "Do Not Use" warning** at the very beginning of the body |

#### Determined to be ready for distribution

Only Releases that meet all of the following conditions may be used for equipment installation and delivery.

| Condition | Where to Check |
| --- | --- |
| Official Release (not Pre-release) | Releases screen |
| 6 Attachments:    • Source bundle (.tar.gz)    • 2 SBOMs (CycloneDX · SPDX)    • Notice (NOTICE)   • Open-source notice package   • Checksums (SHA256SUMS) | Release attachments |
| Release Verification Workflow Success | Actions Execution Log |

Failed releases are not deleted but retained for record-keeping. After resolving the issue or obtaining approval for an exception, the release is republished as a new version.

#### Release Signature Verification (Public Repository)

Release files in public repositories are signed with a GitHub attestation. Before delivery or during evaluation, use the command below to verify that the file is **the original created by our repository’s official release workflow** and that **the SBOM belongs to that file**.

```bash
gh attestation verify <file>.tar.gz --repo SceneMakerAI/<repository>
gh attestation verify <file>.tar.gz --repo SceneMakerAI/<repository> --predicate-type https://spdx.dev/Document/v2.3
```

If even a single byte of the file changes, verification will fail. While the checksum can be swapped out along with the file, the signature cannot be generated without the workflow’s identity.

---

### 3. Evaluation Criteria

#### 3-1. Vulnerabilities

| Severity | Handling | Action Deadline |
| --- | --- | --- |
| Critical | Block release, PR warning · comment | 10 days |
| High | Log and address during monthly review (scheduled to be elevated to a block target after operational stabilization) | 30 days |
| Medium or lower | Verify via report · Dependabot | — |

#### 3-2. Licenses

| Category | License | Handling |
| --- | --- | --- |
| Prohibited | GPL-2.0, GPL-3.0, AGPL-3.0 | Block release (blocked at the PR stage for public repositories) |
| Allowed | MIT, Apache, BSD, LGPL, MPL, etc. | Pass |
| Verification Required | Dual licensing where one license is prohibited and the other is allowed | Warning |
| Redistribution Conditions to Verify | Proprietary licenses (e.g., NVIDIA components) | Warning |

The prohibited list is managed in a single configuration file, ensuring the same criteria apply to all repositories.

#### 3-3. Exception Approval

Vulnerabilities or licenses that cannot be upgraded may be approved as exceptions and allowed to pass. The gate only recognizes exceptions that meet all four of the following conditions.

| Item | Condition |
| --- | --- |
| Identifier | CVE · GHSA number or package identifier (purl) |
| Status | "Valid" |
| Approver | Record of approval by the project lead |
| Expiration Date | A date on or after today |

When an exception expires, the PR will trigger a warning again, and the release will be blocked once more. This mechanism treats exceptions not as permanent exemptions but as **time-limited grace periods** to enforce periodic review.

---

### 4. Implementation Results

#### 4-1. Implementation Status (as of October 26, 2026)

| Category | Repository | Status |
| --- | --- | --- |
| Public | [worker-render](https://github.com/SceneMakerAI/worker-render), [api-external](https://github.com/SceneMakerAI/api-external) | Implementation Complete |
| Private | 7 service repositories (STT, Vision, Scheduling Agent, Preprocessing Worker, etc.) | Implementation complete. PR review and SBOM auto-generation both successful |
| Remaining Targets | 1 private repository | Scheduled for implementation |

We have added governance documents (GOVERNANCE.md, MAINTAINERS.md, SECURITY.md, CODE_OF_CONDUCT.md) and records of the decision to adopt CI to all repositories.

#### 4-2. Validation Examples

| Validation Details | Results |
| --- | --- |
| Flow in pilot repository: Blocked → Exception Approved → Passed | Verified the entire process: gate blocked the release, an exception was registered, and the release was approved |
| Release gate in demo repository | Detected 2 critical vulnerabilities, automatically switched the release to “Pre-release” status, and displayed a usage warning |
| worker-render Release signing | Generated 6 attachments and 2 signatures (build source · SBOM); both passed the verification command on 2026-10-23 |
| Licenses | Based on 508 items in the consolidated asset list, 0 GPL or AGPL licenses found across 8 repositories |

Pillow 13.0.0, which was required by the supply chain audit to resolve critical vulnerabilities, includes three fixes contributed and merged by SceneMakerAI (see [Open Source Contributions](https://doc.scenemaker.solbox.com/docs/achievement/3)).

---

### 5. Differences Between Public and Private Repositories

GitHub offers many security features for free only on public repositories. While adhering to the same standards, we used alternative methods for private repositories.

| Feature | Public | Private (GitHub Free) | Alternative for Private |
| --- | --- | --- | --- |
| PR dependency review (dependency-review) | Y | N (Paid) | Detailed warnings in PR review comments |
| Release attestation | Y | N (Paid) | Checksums · Execution logs |
| Blocking direct pushes to `main` (Ruleset) | Y | N | Operational policies + monthly reviews |
| Monitoring and blocking secret key exposure | Y | N (Paid) | Policy against committing `.env` files |
| License gate | Replaced by `dependency-review` | Y | — |
| Dependabot Vulnerability Alerts | Y | Y | — |

---

### 6. Challenges

**The Release gate could not prevent the creation of a Release itself.**  
Since GitHub’s Release workflow runs after a Release is published, the Release is already created even if the check fails. To address this, we configured the workflow to change the Release to a “Pre-release” and add a “Do Not Use” warning to its description if the gate fails. We also established a separate criterion stipulating that only official Releases with all six required attachments may be used for deployment. Releases where the workflow was canceled and no warning was added are identified and addressed during the monthly review.

**Results varied depending on the vulnerability database.**  
SBOM-based inspection tools and GitHub Dependabot use different vulnerability databases, so there were cases where the same dependency was detected by only one of them (e.g., GHSA vulnerabilities related to certifi were detected only by Dependabot). We have divided their roles: SBOM checks serve as a gate and official evidence, while Dependabot acts as a supplementary tool for continuous monitoring and suggesting fix PRs; we cross-check the results of both during the monthly review.

**PR checks only examine newly added dependencies.**  
Since `dependency-review` only checks dependencies newly added or changed in a PR, it cannot detect vulnerabilities that were already present. Existing vulnerabilities are tracked separately via SBOM preview notifications, monthly snapshots, and Dependabot.

**Private repositories had limited protection features available on the free plan.**  
Since main branch protection rules, signing, and secret key monitoring are paid features, we maintain the same level of security in private repositories through operational guidelines and monthly reviews.

**There are components that the SBOM does not cover.**  
Since the SBOM is generated based on dependencies at the Python package level, components installed on the system—such as NVENC-built FFmpeg or GPU drivers—and the licenses for AI model weights are not included in the list. We are preparing to either scan images at the time of delivery or list these components separately in a disclosure package.

**We needed to strike a balance between development speed and the level of control.**  
Requiring approval from designated personnel, tag protection, and release execution approval during the development phase significantly slows down work. Therefore, we decided to enforce only “no direct pushes to ‘main’ + PRs required + passing mandatory checks” at the system level, and to adhere to operational principles for review approvals based on the severity of changes (routine, important, critical), documenting these decisions. We will review this again once operations stabilize.

---

### 7. Remaining Tasks

| Task | Details |
| --- | --- |
| Final Implementation | Implement changes to the remaining private repository; replace the signing certificate for the worker-render production release |
| Raising Thresholds | Block releases containing high-severity vulnerabilities once operations stabilize |
| Full Scope of Distributions | Scan images at the FFmpeg and GPU driver layers; verify AI model licenses |
| Operational Records | Accumulate records of Dependabot configuration screens, monthly metrics, and quarterly spot checks |
| CI Maintenance | Automatically suggest GitHub Actions version updates; lock runner versions |

---

### 8. References

| Resource | Description |
| --- | --- |
| [SPDX](https://spdx.dev/) | SBOM standard format (ISO/IEC 5962) |
| [CycloneDX](https://cyclonedx.org/) | SBOM standard format (OWASP) |
| [SLSA](https://slsa.dev/) | Build provenance security level framework |
| [dependency-review-action](https://github.com/actions/dependency-review-action) | PR dependency review |
| [attest-build-provenance](https://github.com/actions/attest-build-provenance) | Release file signing |
| [worker-render Releases](https://github.com/SceneMakerAI/worker-render/releases) | 6 Types of Attachments · Example of a Signed Release |

---

**Related Documents**

- [Open Source Contributions](https://doc.scenemaker.solbox.com/docs/achievement/3)

