# SIH-188: System Baseline & Security Audit (Phase 0)

**Project**: BorderShield — AI-Driven Document Screening & E-Gate Identity Verification System  
**Hackathon Target**: Smart India Hackathon 2026 | Problem Statement: PS 26188 (Ministry of Home Affairs - MHA)  
**Audit Date**: September 17, 2026  
**Status**: Baseline Completed | Application Code Unmodified  

---

## 1. Executive Summary & Audit Scope

This document establishes the verified technical baseline for the BorderShield repository prior to executing the security, privacy, and permissioned audit upgrades specified in `Security .md`.

### Core Mandate:
- Zero breaking changes to the existing screening pipeline (OCR, forensics, biometrics, risk scoring, and sovereign document rules).
- Retain local offline execution capabilities and full SQLite compatibility for SIH hackathon evaluation.
- Identify all sensitive data, data flows, storage locations, cryptographic mechanisms, and operational vulnerabilities.

---

## 2. Verified Baseline Metrics (Pre-Upgrade)

| Evaluation Category | Measured Baseline Result | Status |
| :--- | :--- | :--- |
| **Backend Unit Test Suite** (`python -m unittest discover -s backend`) | **31 Tests Run, 31 Passed, 0 Failed** (Duration: 18.86s) | **PASS** |
| **Biometric & Cryptographic Tests** (`test_biometrics_and_blockchain.py`) | **6 Tests Run, 6 Passed, 0 Failed** | **PASS** |
| **Frontend Static Type Checks** (`npx tsc --noEmit`) | **0 Errors** (TypeScript strict mode) | **PASS** |
| **Benchmark Suite Accuracy** (104 Documents: 52 Genuine, 52 Tampered) | **92.31% Accuracy**, **87.93% Precision**, **98.08% Recall**, **92.73% F1** | **PASS** |
| **Benchmark Latencies (Synthetic Testbed)** | **P50: 721.0 ms**, **P95: 1453.8 ms**, **Mean: 1102.4 ms** | **OPTIMAL** |
| **Real Document Latency** (Full Pipeline with Neural Tampering & MRZ Rescue) | **~3.2s to 4.5s** warm latency | **OPTIMAL** |

---

## 3. Architecture & Repository Inventory

```
SIH 188/
├── backend/
│   ├── data/
│   │   ├── registry.db              # Document registry, visa allowances, and blacklist records
│   │   ├── blockchain.db            # Cryptographically chained SHA-256 inspection blocks
│   │   ├── biometrics.db            # 1:N facial biometric vector database & crossing logs
│   │   └── benchmark_report.json    # 104-document benchmark verification statistics
│   ├── modules/
│   │   ├── ocr.py                   # PaddleOCR PP-OCRv6, TrOCR fallback, MRZ parser, HUD scanner
│   │   ├── preprocessing.py         # Multi-angle face voting, contour deskew, CLAHE contrast
│   │   ├── validation.py            # Verhoeff D5, ECI EPIC, MoRTH Sarathi, ICAO Doc 9303 7-3-1
│   │   ├── tampering.py             # ELA compression variance, ViT deepfake detector, EXIF, stamps
│   │   ├── biometrics.py            # MobileNetV3 576-dim L2 embeddings, cosine match, liveness, 1:N search
│   │   ├── blockchain.py            # SHA-256 Merkle chain, block hashing, chain verification
│   │   └── timing.py                # High-resolution StageTimer (zero PII logging)
│   ├── tests/
│   │   └── test_biometrics_and_blockchain.py # Unit tests for biometrics and blockchain logic
│   ├── tools/
│   │   ├── benchmark_suite.py       # 104-document synthetic & degraded testbed evaluator
│   │   ├── profiler.py              # Component-level latency profiling script
│   │   └── verify_user_image.py     # Offline single-document verification CLI
│   ├── uploads/                     # File storage for active passenger sessions
│   │   ├── ela/                     # JPEG Q90 difference heatmaps
│   │   ├── faces/                   # Extracted biometric facial portraits
│   │   ├── preprocessed/            # Deskewed & contrast-enhanced images
│   │   └── scanned/                 # HUD green-line overlay images
│   ├── main.py                      # FastAPI application, routing, orchestration & lifecycle
│   └── requirements.txt             # Python runtime dependencies
├── frontend/
│   ├── app/                         # Next.js 16 App Router (layout.tsx, page.tsx, globals.css)
│   ├── components/                  # UI widgets (BiometricVerification, BlockchainLedger, etc.)
│   ├── lib/api.ts                   # Fetch client for backend API communication
│   ├── types/index.ts               # Shared TypeScript schemas
│   └── package.json                 # Frontend dependencies (React 19, Tailwind v4, Lucide)
├── docs/                            # Technical documentation and architecture reports
├── Security .md                     # Master implementation prompt & requirements
├── README.md                        # Root system documentation and benchmark report
└── .gitignore                       # Git ignore policies
```

---

## 4. API Endpoints & Request/Response Contracts

All 8 existing API endpoints must remain strictly backward-compatible:

| Endpoint | Method | Input Parameters | Output Schema Summary | Consumer |
| :--- | :--- | :--- | :--- | :--- |
| `/api/upload` | `POST` | `file: UploadFile`, `document_type: str = "auto"` | `{"file_id", "document_type", "status": "uploaded"}` | `frontend/lib/api.ts` |
| `/api/extract/{file_id}` | `POST` | `file_id: str` | `{"document_type", "fields", "viz_fields", "raw_text", "confidence", "detected_regions"}` | Internal / Modular test |
| `/api/validate/{file_id}` | `POST` | `file_id: str` | `{"checksum", "national_id", "dates", "registry", "viz_consistency", "overall_valid"}` | Internal / Modular test |
| `/api/tamper-check/{file_id}`| `POST` | `file_id: str` | `{"tampering_likelihood", "risk_level", "ela", "metadata", "stamp_forensics"}` | Internal / Modular test |
| `/api/analyze/{file_id}` | `POST` | `file_id: str` | Consolidated dictionary containing extracted fields, validation, tampering, risk score, decision, blockchain receipt, HUD image URL, and pipeline timings | `frontend/lib/api.ts` |
| `/api/face-verify/{file_id}` | `POST` | `file_id: str`, `file: UploadFile (optional)`, `live_image_base64: str (optional)` | `{"file_id", "verification": {...}, "blockchain_receipt": {...}}` | `BiometricVerification.tsx` |
| `/api/ledger/blocks` | `GET` | `limit: int = 25` | `{"total_returned", "blocks": [...]}` | `BlockchainLedger.tsx` |
| `/api/ledger/verify` | `GET` | *None* | `{"chain_valid": bool, "total_blocks": int, "tampered_blocks": list}` | `BlockchainLedger.tsx` |

---

## 5. Existing Database Schemas & Storage Analysis

### A. `backend/data/registry.db`
1. **`documents` Table**:
   - `document_number TEXT PRIMARY KEY`
   - `document_type TEXT NOT NULL`
   - `holder_name TEXT`
   - `status TEXT NOT NULL CHECK(status IN ('VALID', 'EXPIRED', 'REVOKED', 'STOLEN'))`
   - `revocation_reason TEXT`
   - *Current Content*: Seeded with 3 test identities (`ANNA MARIA ERIKSSON`, `JOHN DOE`, `UNKNOWN HOLDER`).
2. **`visas` Table**:
   - `visa_number TEXT PRIMARY KEY`
   - `passport_number TEXT NOT NULL`
   - `visa_type TEXT`
   - `status TEXT NOT NULL CHECK(status IN ('VALID', 'EXPIRED', 'REVOKED'))`
3. **`blacklist` Table**:
   - `passport_number TEXT PRIMARY KEY`
   - `reason TEXT`
   - *Current Content*: Seeded with 3 test watchlist documents (`X1234567`, `A9876543`, `P0000000`).

### B. `backend/data/blockchain.db`
- **`blockchain_ledger` Table**:
  - `block_index INTEGER PRIMARY KEY`
  - `timestamp TEXT NOT NULL`
  - `doc_hash TEXT NOT NULL`
  - `file_id TEXT NOT NULL`
  - `document_type TEXT NOT NULL`
  - `risk_score REAL NOT NULL`
  - `risk_level TEXT NOT NULL`
  - `biometric_status TEXT NOT NULL`
  - `decision TEXT NOT NULL`
  - `officer_id TEXT NOT NULL`
  - `previous_hash TEXT NOT NULL`
  - `block_hash TEXT NOT NULL`

### C. `backend/data/biometrics.db`
- **`biometric_records` Table**:
  - `id INTEGER PRIMARY KEY AUTOINCREMENT`
  - `traveler_name TEXT NOT NULL`
  - `document_number TEXT NOT NULL`
  - `document_type TEXT NOT NULL`
  - `nationality TEXT`
  - `crossing_point TEXT`
  - `crossing_timestamp TEXT`
  - `embedding_blob BLOB NOT NULL` (576 raw float32 floats = 2304 bytes)
  - *Current Content*: Seeded with 2 mock historical crossings (`RAMESH SHARMA`, `TASHI DORJEE`).

---

## 6. Security, Privacy & Compliance Findings (Gap Analysis)

### Finding 1: Permissive Wildcard CORS
- **Current State**: [`backend/main.py`](file:///d:/SIH%20188/backend/main.py#L27) uses `allow_origins=["*"]`.
- **Risk**: Any arbitrary third-party web origin can make cross-origin API calls to the E-Gate screening endpoints.
- **Requirement**: Must be configurable via `CORS_ALLOWED_ORIGINS`, defaulting to `http://localhost:3000` and `http://127.0.0.1:3000`.

### Finding 2: Plaintext Personally Identifiable Information (PII) at Rest
- **Current State**: `traveler_name`, `document_number`, and `holder_name` are stored unencrypted in `biometrics.db` and `registry.db`.
- **Risk**: A physical disk extraction or backup leak directly exposes traveler identities.
- **Requirement**: Implement authenticated symmetric encryption (AES-256-GCM) with environment-managed keys for sensitive fields.

### Finding 3: Biometric Template Protection (ISO/IEC 19794-5)
- **Current State**: Raw 576-dimensional MobileNetV3 feature vectors are stored as unencrypted byte blobs in `biometrics.db`.
- **Risk**: Allows biometric reconstruction attacks if the database is read.
- **Requirement**: Encrypt embedding blobs at rest and tokenize traveler identifiers.

### Finding 4: In-Place Ledger Mutation
- **Current State**: In [`blockchain.py`](file:///d:/SIH%20188/backend/modules/blockchain.py#L200), `update_block_biometric_decision` updates the tip block in place via `UPDATE blockchain_ledger SET ...`.
- **Risk**: Violates the core principle of append-only audit logs.
- **Requirement**: Audit events must be strictly append-only. A biometric update or officer override must append a new event referencing the prior event hash.

### Finding 5: Ledger Nomenclature & NBF Positioning
- **Current State**: The UI and code refer to the local SQLite SHA-256 table as a "Blockchain".
- **Risk**: Technical evaluators will correctly point out that an SQLite table with SHA-256 hashes is a *cryptographic audit log*, not a decentralized blockchain.
- **Requirement**: Formally designate this component as a **"Cryptographically Chained Audit Ledger"** for local demo execution, and introduce an abstraction layer (`PermissionedLedgerAdapter`) modeling integration with India's **National Blockchain Framework (NBF / Vishvasya Stack)**.

### Finding 6: Unmasked Sovereign Identity Numbers in UI
- **Current State**: Full 12-digit Indian Aadhaar numbers are displayed in the frontend extracted fields table.
- **Risk**: Section 29 of the Aadhaar Act 2016 and UIDAI regulations prohibit displaying or publishing unmasked 12-digit numbers.
- **Requirement**: Mask the first 8 digits in presentation layers (`XXXX-XXXX-1234`).

### Finding 7: Indefinite Image Lifecycle in `backend/uploads/`
- **Current State**: Uploaded documents, preprocessed images, cropped faces, ELA heatmaps, and HUD overlays remain indefinitely on disk.
- **Risk**: Violates the storage limitation principle of India's Digital Personal Data Protection (DPDP) Act 2023.
- **Requirement**: Implement configurable retention tracking (`retention_until`) and automatic ephemeral scrubbing for completed screening sessions.

### Finding 8: Hardcoded Operator Identity
- **Current State**: `commit_inspection_block` hardcodes `officer_id="SSB-OFFICER-7429"`.
- **Requirement**: Support configurable officer sessions and Role-Based Access Control (RBAC).

---

## 7. Baseline Conclusion

The baseline audit confirms that the core AI screening engines (PaddleOCR, Haar multi-angle orientation, Verhoeff D5, ICAO 7-3-1, ViT deepfake forensics, MobileNetV3 biometrics) are highly optimized, accurate ($92.31\%$), fast ($1.10\text{s}$ mean), and passing all 37 tests.

All proposed upgrades in `Security .md` can and must be implemented **additively via wrappers and abstraction layers**, ensuring zero breaking changes to existing APIs, databases, or frontend components.

