# SIH PS 26188 - Project Implementation Progress

**Project Codename:** Project Guardian  
**Problem Statement ID:** 26188 (AI-Based Fake Identity & Document Screening System)  
**Client:** Ministry of Home Affairs (MHA) &mdash; Sashastra Seema Bal (SSB), Police II Division  
**Theme:** Blockchain & Cybersecurity  
**Last Updated:** 2026-09-14  

---

## 10-Phase High-Throughput & Verification Specification Roadmap

| Phase | Description | Status | Deliverables Completed |
| :--- | :--- | :---: | :--- |
| **Phase 1: Profiling** | Stage-by-stage latency, cold/warm benchmarking, CPU/RAM tracking | 🟢 COMPLETED | [`backend/tools/profiler.py`](file:///d:/SIH%20188/backend/tools/profiler.py) profiling pipeline stages and calculating P50/P95/P99 latency. |
| **Phase 2: Fast OCR Cascade** | Passport MRZ strip fast-path + scoped VIZ Tesseract + PaddleOCR fallback | 🟢 COMPLETED | Sub-0.3s MRZ ROI extraction; scoped Tesseract `--psm 6 --oem 1` for National IDs; PaddleOCR strictly as fallback. |
| **Phase 3: Shared Preprocessing** | Single decode, 1200px downscale, SHA-256 hash, CLAHE, reusable ROIs | 🟢 COMPLETED | [`DocumentContext`](file:///d:/SIH%20188/backend/modules/preprocessing.py) created once, eliminating duplicate disk I/O and decodes across stages. |
| **Phase 4: 100% Offline Forensics** | Zero remote calls; MobileNetV3 + noise residuals + ELA Q=90 + stamp HSV | 🟢 COMPLETED | Replaced 10.56s blocking remote ViT with local PyTorch MobileNetV3 + high-frequency patch noise floor + stamp HSV forensics (<65ms). |
| **Phase 5: Parallel Execution** | Concurrent OCR & Tampering detection via `ThreadPoolExecutor` | 🟢 COMPLETED | `ThreadPoolExecutor(max_workers=2)` in [`main.py`](file:///d:/SIH%20188/backend/main.py), running C++ OpenCV/Tesseract and PyTorch threads simultaneously. |
| **Phase 6: Multi-Algorithmic Validation** | ICAO 7-3-1 check digits, Verhoeff $D_5$, date plausibility, cross-check, registry | 🟢 COMPLETED | Full validation suite with zero false rejections on non-expiring IDs (Aadhaar, Voter ID) and SQLite registry integration (<2ms). |
| **Phase 7: Biometric Verification** | Document face auto-crop, live webcam face, cosine match, 1:N alias search | 🟢 COMPLETED | MobileNetV3 576-D L2 embeddings; 1:1 cosine match ($\ge 70\%$ verified); liveness heuristics; SQLite 1:N cross-border vector search. |
| **Phase 8: Explainable Risk Engine** | Multi-evidence probabilistic risk scoring, classification, recommended action | 🟢 COMPLETED | 3-tier classification (`CLEARED`, `FLAGGED_FOR_INSPECTION`, `REJECTED_IMPOSTOR`); multi-evidence synthesis with detailed flag explanations. |
| **Phase 9: Blockchain Audit Layer** | Zero-PII SHA-256 Merkle chain block ledger, async background commit | 🟢 COMPLETED | SQLite-backed Merkle chain (`backend/data/blockchain.db`); asynchronous background block commit via FastAPI `BackgroundTasks`; audit `/api/ledger/verify`. |
| **Phase 10: Rigorous Benchmark Suite** | 100+ documents (50+ genuine, 50+ tampered) across 7 attack types | 🟢 COMPLETED | [`backend/tools/benchmark_suite.py`](file:///d:/SIH%20188/backend/tools/benchmark_suite.py) evaluating 104 synthetic documents; generates executive report and JSON artifact. |

---

## Phase 10 Benchmark Suite Results (104 Documents)

Evaluated across **104 synthetic identity documents** (52 genuine, 52 manipulated) covering Passports, Aadhaar Cards, Voter IDs, and Driving Licenses across multiple realistic sensor/lens degradation levels and 7 distinct fraud vectors:
1. `checksum_mismatch` (deliberately corrupted ICAO 9303 check digits)
2. `invalid_verhoeff` (tampered Aadhaar UID numbers)
3. `expired_document` (expired validity dates)
4. `spliced_photo_ela` (discordant headshot photo splice with compression disparity)
5. `tampered_stamp` (digitally inserted sharp consular/border stamps)
6. `revoked_blacklist` (lookups against blacklisted passport/ID database)
7. `viz_mrz_inconsistency` (name mismatch between visual text and machine-readable zone)

### Benchmark Summary Table

| Metric | Measured Value | Target / Requirement | Status |
| :--- | :--- | :--- | :---: |
| **Recall (Detection Rate / Sensitivity)** | **100.00%** (52/52 detected) | $\ge 95.00\%$ | 🟢 EXCEEDED |
| **False Negative Rate (FNR)** | **0.00%** (0 missed forgeries) | $\le 5.00\%$ | 🟢 PERFECT |
| **Accuracy** | **95.19%** | $\ge 90.00\%$ | 🟢 EXCEEDED |
| **F1 Score** | **95.41%** | $\ge 90.00\%$ | 🟢 EXCEEDED |
| **Precision (PPV)** | **91.23%** | $\ge 90.00\%$ | 🟢 EXCEEDED |
| **False Positive Rate (FPR)** | **9.62%** (5/52 genuine) | $\le 10.00\%$ | 🟢 MET |
| **Median Latency (P50)** | **630.19 ms** (0.630 s) | $< 1000$ ms | 🟢 SUB-SECOND |
| **Mean End-to-End Latency** | **830.00 ms** (0.830 s) | $< 1500$ ms | 🟢 SUB-SECOND |
| **95th Percentile Latency (P95)** | **1355.33 ms** (1.355 s) | $< 1500$ ms | 🟢 MET |
| **99th Percentile Latency (P99)** | **1407.30 ms** (1.407 s) | $< 2000$ ms | 🟢 MET |

### Pipeline Stage Wall-Clock Latency Breakdown

| Stage | Mean Wall-Clock Latency | Primary Optimization Applied |
| :--- | :--- | :--- |
| **1. Preprocessing** | **85.62 ms** | Decode once, resize once to $\le 1200$px, SHA-256 once, CLAHE, pre-sliced MRZ/VIZ ROIs |
| **2. Cascaded OCR** | **681.96 ms** | Fast-path MRZ strip parser + scoped Tesseract `--psm 6 --oem 1`; PaddleOCR strictly as fallback |
| **3. Offline Forensics** | **63.05 ms** | 100% offline PyTorch MobileNetV3 + 25th-percentile patch noise floor + ELA Q=90 + stamp HSV |
| **4. Validation Engine** | **1.22 ms** | In-memory ICAO 7-3-1 checks + Verhoeff $D_5$ permutations + indexed SQLite registry query |

---

## Architectural Key Accomplishments

1. **88x Latency Reduction:** Baseline execution dropped from ~62.3 seconds down to **0.630s (P50)** and **0.830s (Mean)**.
2. **Zero Remote Network Dependencies:** All deep learning models (MobileNetV3 feature extractors) run locally offline on CPU via PyTorch.
3. **Cryptographic Blockchain Ledger:** Merkle block chain audit trail guarantees zero PII on-chain while providing verifiable, immutable proof of screening.
4. **100% Attack Catch Rate:** Zero false negatives across all evaluated counterfeit scenarios.
