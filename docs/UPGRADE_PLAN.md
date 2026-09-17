# SIH-188: Comprehensive Privacy, Security & Permissioned Audit Upgrade Plan

**Project**: BorderShield — AI-Driven Document Screening & E-Gate Identity Verification System  
**Hackathon Target**: Smart India Hackathon 2026 | Problem Statement: PS 26188 (Ministry of Home Affairs - MHA)  
**Plan Date**: September 17, 2026  
**Document Status**: Phase 0 Complete — Awaiting User Approval to Implement Phase 1  
**Execution Mode**: Strict Phased Execution with Pre/Post Regression Gates  

---

## 1. Executive Summary & Core Mandate

This implementation plan defines the architectural roadmap for upgrading the BorderShield system to meet sovereign government standards for data privacy, cryptographic security, authenticated encryption, role-based access control (RBAC), and append-only audit provenance.

### Core Non-Negotiable Directives:
1. **Preserve Existing Screening Pipeline**: PaddleOCR, MRZ parser, Haar cascade multi-angle face voting, Verhoeff D5, ICAO Doc 9303 checksums, ViT deepfake forgery detection, and MobileNetV3 biometrics must continue to function with zero degradation in accuracy ($92.31\%$) or timing (~$1.10\text{ s}$ mean latency).
2. **Backward-Compatible API & Frontend Contracts**: All 8 existing API endpoints (`/api/upload`, `/api/extract/{id}`, `/api/validate/{id}`, `/api/tamper-check/{id}`, `/api/analyze/{id}`, `/api/face-verify/{id}`, `/api/ledger/blocks`, `/api/ledger/verify`) must preserve their exact input parameters and response schemas.
3. **Database Abstraction (SQLite + PostgreSQL Ready)**: SQLite remains the default for zero-setup, offline hackathon evaluation. A clean repository abstraction layer (`BaseRepository`) introduces optional PostgreSQL support via `DATABASE_URL`.
4. **Honest Ledger Nomenclature & NBF Architecture**: The local SQLite ledger is accurately designated as a **"Cryptographically Chained Audit Ledger"** (not a decentralized blockchain). A formal `PermissionedLedgerAdapter` is introduced targeting India's **National Blockchain Framework (NBF / Vishvasya Stack)** with an explicit prototype status.
5. **Zero PII on Ledger**: Raw names, Aadhaar numbers, passport numbers, face portraits, and 576-dim biometric vectors will **never** be written to the ledger. Only canonical event hashes, risk scores, decisions, model versions, and digital signatures are recorded.
6. **Strict Phased Gating**: No code is modified until Phase 0 is approved. Each subsequent phase (Phase 1 through Phase 18) must pass unit and regression tests before progressing.

---

## 2. Inventory of Target Files

### A. Existing Files to Modify

| File Path | Component | Why Modification is Required | Compatibility Risks & Mitigation |
| :--- | :--- | :--- | :--- |
| [`backend/main.py`](file:///d:/SIH%20188/backend/main.py) | API Orchestrator & Lifecycle | 1. Replace wildcard CORS with configurable `CORS_ALLOWED_ORIGINS`.<br>2. Add HTTP security headers middleware (CSP, X-Content-Type-Options, etc.).<br>3. Enforce secure file upload validations (magic bytes, size check, safe UUID filename).<br>4. Route ledger operations through `AuditLedgerService`.<br>5. Register background ephemeral file retention task. | **Low Risk**:<br>• Request/response JSON schemas remain identical.<br>• CORS defaults to `localhost:3000` and `127.0.0.1:3000` to prevent frontend breakage.<br>• Allowed file types match existing allowed image formats. |
| [`backend/modules/blockchain.py`](file:///d:/SIH%20188/backend/modules/blockchain.py) | Cryptographic Audit Ledger | 1. Replace in-place database updates (`update_block_biometric_decision`) with append-only linked audit events.<br>2. Implement canonical deterministic JSON serialization (RFC 8785 style) for SHA-256 hashing.<br>3. Implement Ed25519 digital signature signing and verification.<br>4. Implement `AuditLedger` abstraction with `LocalCryptographicLedger` and `PermissionedLedgerAdapter`. | **Low Risk**:<br>• `commit_inspection_block`, `get_ledger_blocks`, and `verify_chain_integrity` signatures and return formats are strictly preserved for existing callers. |
| [`backend/modules/biometrics.py`](file:///d:/SIH%20188/backend/modules/biometrics.py) | Biometric Engine & Vault | 1. Encrypt 576-dim float32 embeddings at rest using AES-256-GCM.<br>2. Decouple traveler PII from biometric vectors using pseudonymized `subject_id`.<br>3. Ensure raw embeddings are never returned to frontend or logged in plain text. | **Low Risk**:<br>• `verify_face_against_document` and `search_identity_1_to_n` retain exact input/output contracts.<br>• In-memory cosine similarity math is unchanged. |
| [`backend/modules/validation.py`](file:///d:/SIH%20188/backend/modules/validation.py) | Sovereign Rules & Registry | 1. Access registry via database repository layer.<br>2. Query passport and blacklist records using HMAC-SHA-256 tokens while supporting plaintext fallback during migration.<br>3. Preserve all ICAO, Verhoeff, EPIC, Sarathi validation algorithms unchanged. | **Zero Risk**:<br>• Output dictionary schema (`overall_valid`, `checksum`, `registry`, `dates`, etc.) remains identical. |
| [`backend/requirements.txt`](file:///d:/SIH%20188/backend/requirements.txt) | Dependencies | Add `cryptography>=43.0.0` (for AES-256-GCM, HMAC-SHA256, Ed25519) and `pydantic-settings>=2.0.0`. | **Zero Risk**:<br>• Standard compiled wheels available on Windows. No conflict with OpenCV, Torch, or PaddleOCR. |
| [`frontend/components/ExtractedFieldsTable.tsx`](file:///d:/SIH%20188/frontend/components/ExtractedFieldsTable.tsx) | UI Field Presentation | 1. Implement Aadhaar Act 2016 compliant 8-digit masking (`XXXX-XXXX-1234`).<br>2. Implement Passport number masking (`P*******78`).<br>3. Provide an authorized role toggle/badge to unmask fields for verified officer profiles. | **Zero Risk**:<br>• Purely presentation-layer formatting. Raw extracted data in state is preserved for validation logic. |
| [`frontend/components/BlockchainLedger.tsx`](file:///d:/SIH%20188/frontend/components/BlockchainLedger.tsx) | UI Ledger Dashboard | 1. Update title/terminology to "Cryptographically Chained Audit Ledger".<br>2. Add status badge for local cryptographic anchor vs. permissioned ledger sync status (NBF/Vishvasya readiness).<br>3. Add verification view displaying Ed25519 signature status and immutable event sequence. | **Zero Risk**:<br>• Visual and informational enhancements consuming existing `/api/ledger/*` endpoints. |
| [`frontend/types/index.ts`](file:///d:/SIH%20188/frontend/types/index.ts) | UI TypeScript Types | Add optional fields (`canonical_hash`, `signature`, `anchor_status`, `is_masked`) to ledger and field schemas. | **Zero Risk**:<br>• All new fields are optional (`?`); existing code continues to compile cleanly. |
| [`.gitignore`](file:///d:/SIH%20188/.gitignore) | Git Policies | Ensure `.env`, `*.pem`, `*.key`, and test database files are explicitly excluded. | **Zero Risk** |

---

### B. New Files to Create

| File Path | Component | Architectural Purpose |
| :--- | :--- | :--- |
| `backend/core/config.py` | Configuration Foundation | Centralized Pydantic Settings class loading from `.env`. Manages keys, CORS origins, retention windows, model versions, and fails closed if production secrets are missing. |
| `backend/core/security.py` | Cryptographic Primitives | Production-grade AES-256-GCM authenticated encryption/decryption and HMAC-SHA-256 keyed tokenization routines using `cryptography.hazmat`. |
| `backend/core/signatures.py` | Digital Signatures | Ed25519 asymmetric signing and public key verification for canonical audit events. Generates ephemeral development keypair if none configured. |
| `backend/core/auth.py` | RBAC & Session Context | Defines sovereign roles (`SCREENING_OFFICER`, `SUPERVISOR`, `INVESTIGATOR`, `AUDITOR`, `SYSTEM_ADMIN`), role validation dependencies, and demo officer context. |
| `backend/database/repository.py` | Database Abstraction Layer | `BaseRepository` interface with complete `SQLiteRepository` implementation (offline demo mode) and `PostgresRepository` implementation. Manages safe migrations. |
| `backend/modules/ledger_adapter.py` | Ledger Abstraction Layer | `AuditLedger` base class with `LocalCryptographicLedger` (SQLite-backed) and `PermissionedLedgerAdapter` (NBF/Vishvasya integration interface with staging adapter). |
| `backend/modules/lifecycle.py` | Ephemeral Storage Scrubber | File retention policy engine tracking `created_at` and `retention_until` for `backend/uploads/` files with legal hold exemptions. |
| `backend/tests/test_security_upgrades.py` | Security Test Suite | 15+ new tests covering AES-256-GCM, HMAC tokenization, Ed25519 signatures, append-only immutability, chain verification, RBAC, and secure file uploads. |
| `.env.example` | Configuration Template | Comprehensive documentation of all environment variables with safe development defaults and production instructions. |
| `docs/PRIVACY_SECURITY_ARCHITECTURE.md` | Architecture Specification | Detailed documentation of data flows, encryption envelopes, pseudonymization, and zero-PII ledger invariants. |
| `docs/SECURITY_THREAT_MODEL.md` | Threat Model Specification | Formal analysis of 14 threats (T1-T14) with impact, mitigations, and residual risks. |
| `docs/GOVERNMENT_DEPLOYMENT_ARCHITECTURE.md` | Government Deployment Guide | Architecture for NBF/Vishvasya onboarding, KMS/HSM key management, and air-gapped border deployment. |
| `docs/UPGRADE_REPORT.md` | Final Verification Report | Before/after comparison table, test results, benchmark comparisons, and deployment readiness summary. |

---

## 3. Detailed Phase-by-Phase Implementation Strategy

The upgrade will be executed in the exact order specified in `Security .md`. Each phase must pass all unit and regression tests before advancing.

```
Phase 0: Baseline & Audit (CURRENT - COMPLETE)
   │
   ▼ [User Approval Gate]
Phase 1: Configuration & Security Foundation (.env.example, config.py, CORS)
   │
   ▼
Phase 2: Database Abstraction Layer (repository.py, SQLite + Postgres ready)
   │
   ▼
Phase 3: Authenticated PII Encryption (AES-256-GCM, fail-closed)
   │
   ▼
Phase 4: Keyed Identifier Tokenization (HMAC-SHA-256 for registry lookups)
   │
   ▼
Phase 5: Biometric Vault Protection (Encrypted 576-dim blobs, pseudonymized subjects)
   │
   ▼
Phase 6: Secure File Upload & Retention Scrubber (Magic bytes, ephemeral cleanup)
   │
   ▼
Phase 7: Role-Based Access Control (RBAC, 5 roles, audit-safe)
   │
   ▼
Phase 8: Append-Only Audit Event Architecture (Canonical JSON, hash chaining)
   │
   ▼
Phase 9: Digital Signatures for Audit Events (Ed25519 asymmetric signing)
   │
   ▼
Phase 10: Local Cryptographic Ledger Adapter (LocalCryptographicLedger)
   │
   ▼
Phase 11: Permissioned Blockchain Adapter (PermissionedLedgerAdapter)
   │
   ▼
Phase 12: National Blockchain Framework (NBF/Vishvasya) Interface Alignment
   │
   ▼
Phase 13: Privacy-Aware Frontend Presentation (Aadhaar & Passport masking)
   │
   ▼
Phase 14: Audit Verification UI Dashboard (Status, signatures, explainability)
   │
   ▼
Phase 15: Comprehensive Security Test Suite (15+ security unit tests)
   │
   ▼
Phase 16: Full Regression Verification (31 backend tests + 6 crypto tests)
   │
   ▼
Phase 17: Performance & Latency Benchmark (104-document synthetic dataset)
   │
   ▼
Phase 18: Sovereign Documentation Suite (Threat model, Gov deployment guide, Report)
```

---

### Phase 1: Configuration & Security Foundation
- **Objectives**: Establish typed configuration, eliminate hardcoded values, secure CORS.
- **Actions**:
  1. Add `cryptography>=43.0.0` and `pydantic-settings>=2.0.0` to `backend/requirements.txt`.
  2. Create `backend/core/config.py` with `Settings` class (AES key, HMAC key, CORS origins, model versions: `OCR_v6`, `MobileNetV3_v1`, `ViT_Forgery_v1`).
  3. Create `.env.example` with documented variables and secure defaults for local development.
  4. Update `backend/main.py` to load `Settings` and replace `allow_origins=["*"]` with `settings.cors_allowed_origins`.
- **Validation**:
  - Verify FastAPI server imports without errors.
  - Test CORS rejection on unauthorized origin and acceptance on `localhost:3000`.

### Phase 2: Database Abstraction & Safe Migrations
- **Objectives**: Decouple modules from direct SQLite calls; provide repository pattern for SQLite (demo) and PostgreSQL (production).
- **Actions**:
  1. Create `backend/database/repository.py` defining `BaseRepository` with methods for documents, visas, blacklist, screenings, biometrics, and audit events.
  2. Implement `SQLiteRepository` preserving exact table schemas in `registry.db`, `biometrics.db`, and `blockchain.db`.
  3. Ensure all table initialization and migration scripts are safe, idempotent (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ADD COLUMN`), and non-destructive.
  4. Wire `backend/modules/validation.py` to use `get_repository()`.
- **Validation**:
  - Run `python backend/test_validation.py` to confirm all 12 validation tests pass without regression.

### Phase 3: Authenticated PII Encryption
- **Objectives**: Protect sensitive fields at rest using AES-256-GCM.
- **Actions**:
  1. Create `backend/core/security.py` implementing `encrypt_field(plaintext: str) -> str` (returning `version$iv$ciphertext$tag` in URL-safe base64) and `decrypt_field(token: str) -> str`.
  2. In local development mode, derive a deterministic local key if `ENCRYPTION_MASTER_KEY` is not set; in production mode (`ENVIRONMENT=production`), fail closed on missing key.
  3. Provide transparent decrypt-on-read in repository layer so upstream callers continue receiving expected plaintext fields.
- **Validation**:
  - Unit test encrypt/decrypt roundtrip, authentication tag tampering detection, and wrong-key rejection.

### Phase 4: Keyed Identifier Tokenization
- **Objectives**: Enable fast database index lookups on passport/Aadhaar numbers without storing or searching plaintext identifiers.
- **Actions**:
  1. Implement `tokenize_identifier(identifier: str) -> str` using HMAC-SHA-256 in `backend/core/security.py`.
  2. Add `document_token` column to `documents` and `blacklist` tables in `registry.db`.
  3. Update repository lookup to query by `document_token` with fallback to normalized plaintext for legacy records.
- **Validation**:
  - Verify blacklist lookups succeed for both new tokenized entries and legacy seeded entries (`X1234567`).

### Phase 5: Biometric Vault Protection
- **Objectives**: Encrypt 576-dim facial embeddings at rest; isolate identity metadata.
- **Actions**:
  1. Update `backend/modules/biometrics.py` to encrypt the 2304-byte float32 embedding buffer using AES-256-GCM prior to database insertion.
  2. Replace plaintext traveler names with encrypted fields or pseudonymized subject identifiers.
  3. Decrypt embeddings in memory during 1:N candidate search.
  4. Verify that raw embeddings and raw face portraits are excluded from all logging and API output dictionaries.
- **Validation**:
  - Run `python backend/tests/test_biometrics_and_blockchain.py` (all tests must pass).

### Phase 6: Secure File Upload & Storage Lifecycle
- **Objectives**: Prevent malicious file uploads; enforce ephemeral retention to comply with DPDP Act 2023.
- **Actions**:
  1. Harden `/api/upload` in `backend/main.py`:
     - Inspect magic bytes (JPEG: `\xFF\xD8\xFF`, PNG: `\x89PNG\r\n\x1a\n`, PDF: `%PDF`).
     - Reject files larger than `MAX_UPLOAD_SIZE_BYTES` (default: 15MB).
     - Generate server-side UUIDv4 filenames; never use client-supplied paths.
     - Prevent zip bombs / decompression attacks.
  2. Create `backend/modules/lifecycle.py` with `cleanup_expired_uploads()` that purges images exceeding `DOCUMENT_RETENTION_HOURS` (default: 24h) unless flagged for legal hold (`legal_hold=True`).
- **Validation**:
  - Test upload of valid JPEG/PNG (passes) and fake executable renamed to `.jpg` (rejected with 400 Bad Request).
  - Test retention scrubber on synthetic expired file.

### Phase 7: Role-Based Access Control (RBAC) & Authentication
- **Objectives**: Enforce principle of least privilege across E-Gate operational roles.
- **Actions**:
  1. Create `backend/core/auth.py` with 5 roles: `SCREENING_OFFICER`, `SUPERVISOR`, `INVESTIGATOR`, `AUDITOR`, `SYSTEM_ADMIN`.
  2. Define role permissions (e.g., screening officers cannot alter blacklist; supervisors can perform decision overrides; auditors can verify ledger).
  3. Add non-breaking FastAPI dependency `get_current_officer` that checks `X-Officer-Role` header, defaulting to `SCREENING_OFFICER` for seamless hackathon demo operation.
- **Validation**:
  - Verify supervisor override permission and screening officer restriction.

### Phase 8: Append-Only Audit Event Architecture
- **Objectives**: Eliminate in-place database mutations; guarantee append-only ledger integrity.
- **Actions**:
  1. Refactor `backend/modules/blockchain.py`:
     - Discontinue `UPDATE blockchain_ledger SET ...`.
     - Implement chained events: `SCREENING_EVENT` $\to$ `BIOMETRIC_EVENT` $\to$ `OFFICER_OVERRIDE_EVENT`.
  2. Implement deterministic canonical JSON serialization (RFC 8785: sorted keys, compact separators, UTF-8).
  3. Compute `event_hash = SHA-256(previous_event_hash + canonical_event_bytes)`.
- **Validation**:
  - Verify that appending a biometric decision creates a new linked event rather than modifying the screening event.
  - Verify that altering any historical record causes `verify_chain_integrity()` to flag the exact corrupted index.

### Phase 9: Digital Signatures for Audit Events
- **Objectives**: Cryptographically bind inspection decisions to the acting officer/workstation.
- **Actions**:
  1. Create `backend/core/signatures.py` using `Ed25519PrivateKey` and `Ed25519PublicKey` from `cryptography.hazmat`.
  2. Sign canonical event hashes upon commitment.
  3. Verify signatures in `verify_chain_integrity()`.
- **Validation**:
  - Test valid signature verification passes.
  - Test altered event payload causes signature verification to fail.

### Phase 10: Local Cryptographic Ledger Adapter
- **Objectives**: Wrap local SQLite blockchain logic under a clean `AuditLedger` interface.
- **Actions**:
  1. Create `backend/modules/ledger_adapter.py` defining `AuditLedger` abstract base class.
  2. Implement `LocalCryptographicLedger` subclass encapsulating the SQLite append-only chain.
  3. Preserve all existing API responses for `/api/ledger/blocks` and `/api/ledger/verify`.
- **Validation**:
  - Verify `/api/ledger/blocks` returns expected blocks for frontend consumption.

### Phase 11: Permissioned Blockchain Adapter Architecture
- **Objectives**: Decouple border screening from any specific blockchain vendor.
- **Actions**:
  1. Implement `PermissionedLedgerAdapter(AuditLedger)` in `backend/modules/ledger_adapter.py`.
  2. Include methods: `submit_event(event)`, `verify_event(event_id)`, `get_anchor_status(event_id)`.
  3. Support asynchronous queueing: if the permissioned ledger is unreachable or in prototype mode, store event locally with status `ANCHOR_PENDING` without halting screening.
- **Validation**:
  - Test simulated ledger outage: screening pipeline completes normally and records `ANCHOR_PENDING`.

### Phase 12: National Blockchain Framework (NBF / Vishvasya) Alignment
- **Objectives**: Architect integration-readiness for India's sovereign blockchain ecosystem.
- **Actions**:
  1. Implement `NBFPermissionedLedgerAdapter` targeting Vishvasya Stack architecture standards (MeitY NBF Guidelines).
  2. Explicitly label status as `"Prototype adapter — Integration-ready (Not connected to production government network)"`.
  3. DO NOT fabricate mock government endpoints or claim unverified certifications.
- **Validation**:
  - Review documentation and adapter strings to ensure zero deceptive claims.

### Phase 13: Privacy-Aware Frontend Presentation
- **Objectives**: Prevent shoulder-surfing and meet Section 29 Aadhaar Act masking mandates.
- **Actions**:
  1. In `frontend/components/ExtractedFieldsTable.tsx`:
     - Mask Aadhaar numbers to show only the last 4 digits (`XXXX-XXXX-1234`).
     - Mask Passport numbers (`P*******78`).
     - Add visual privacy shield badge and an authorized toggle ("Officer View") to reveal full values when permitted.
- **Validation**:
  - Verify frontend renders masked values by default. Run `npx tsc --noEmit` (must report 0 errors).

### Phase 14: Audit Verification UI Dashboard
- **Objectives**: Provide an honest, auditable dashboard for screening history and chain integrity.
- **Actions**:
  1. In `frontend/components/BlockchainLedger.tsx`:
     - Rename interface header to "Cryptographically Chained Audit Ledger".
     - Display dual anchor indicators: "Local Ledger: Anchored" and "Permissioned DLT (NBF): Integration-Ready".
     - Show cryptographic integrity badge (Ed25519 signature verified, SHA-256 chain valid).
     - Display explainability reason codes alongside risk scores.
- **Validation**:
  - Run frontend static type check (`npx tsc --noEmit`).

### Phase 15: Comprehensive Security Test Suite
- **Objectives**: Automated regression tests for all newly added security features.
- **Actions**:
  1. Create `backend/tests/test_security_upgrades.py` with 15+ comprehensive test cases:
     - `test_aes_gcm_encryption_roundtrip`
     - `test_aes_gcm_tampered_ciphertext_fails`
     - `test_aes_gcm_wrong_key_fails`
     - `test_hmac_tokenization_deterministic`
     - `test_ed25519_signature_verification`
     - `test_ed25519_tampered_payload_fails`
     - `test_append_only_audit_chain_integrity`
     - `test_audit_chain_tamper_detection`
     - `test_upload_magic_byte_validation`
     - `test_upload_path_traversal_prevention`
     - `test_rbac_supervisor_override`
     - `test_retention_scrubber_preserves_legal_hold`
- **Validation**:
  - Run `python -m unittest backend/tests/test_security_upgrades.py` (all tests pass).

### Phase 16: Full Regression Verification
- **Objectives**: Prove zero regressions across all pre-existing system components.
- **Actions**:
  1. Run existing backend unit test suite: `python -m unittest discover -s backend`.
  2. Run existing biometrics and blockchain tests: `python backend/tests/test_biometrics_and_blockchain.py`.
  3. Run frontend TypeScript type check: `npx tsc --noEmit`.
- **Validation**:
  - Exactly 31 / 31 existing unit tests pass.
  - Exactly 6 / 6 crypto/biometric tests pass.
  - Frontend type checks report 0 errors.

### Phase 17: Performance & Latency Benchmark Verification
- **Objectives**: Prove that security upgrades did not degrade system screening speed.
- **Actions**:
  1. Run `python backend/tools/benchmark_suite.py` on the 104-document synthetic dataset.
  2. Compare metrics against Phase 0 baseline:
     - Accuracy ($\ge 92\%$)
     - Mean latency ($\le 1.25\text{ s}$ synthetic)
     - P50 latency ($\le 800\text{ ms}$)
- **Validation**:
  - Verify benchmark report generates cleanly and metrics remain within the target envelope.

### Phase 18: Sovereign Documentation Suite & Final Report
- **Objectives**: Provide complete, honest, publication-quality documentation for SIH evaluators.
- **Actions**:
  1. Create `docs/PRIVACY_SECURITY_ARCHITECTURE.md`.
  2. Create `docs/SECURITY_THREAT_MODEL.md` (Threats T1-T14).
  3. Create `docs/GOVERNMENT_DEPLOYMENT_ARCHITECTURE.md`.
  4. Create `docs/UPGRADE_REPORT.md` with before/after comparison table.
  5. Update `README.md` to reflect upgraded security capabilities.

---

## 4. Database Migration & Backward Compatibility Strategy

### Schema Evolution Strategy:
- **Zero Destruction Policy**: No tables or columns will be dropped. Existing demo databases (`registry.db`, `blockchain.db`, `biometrics.db`) will remain fully readable.
- **Additive Migrations**: New columns (`document_token`, `retention_until`, `signature`, `canonical_hash`, `event_type`) will be added via safe `ALTER TABLE ... ADD COLUMN` statements or new auxiliary tables.
- **Transparent Dual-Read Fallback**:
  ```python
  # Conceptual lookup in SQLiteRepository
  token = tokenize_identifier(doc_number)
  cursor.execute("SELECT * FROM documents WHERE document_token = ?", (token,))
  row = cursor.fetchone()
  if not row:
      # Backward-compatible fallback for unmigrated seed records
      cursor.execute("SELECT * FROM documents WHERE document_number = ?", (doc_number,))
      row = cursor.fetchone()
  ```

---

## 5. Risk Assessment & Mitigation Matrix

| Risk Category | Identified Risk | Preventative Mitigation |
| :--- | :--- | :--- |
| **API Contract Breakage** | Frontend fails to parse analysis results if response structure changes. | Keep `/api/analyze/{file_id}` and `/api/upload` response schemas strictly unchanged. Security metadata is added additively under optional keys. |
| **OCR / Forensics Degradation** | Security wrappers add latency or alter image bytes before OCR/tampering. | File upload security validation occurs only on the initial raw buffer. Preprocessing and OCR pipelines receive unmodified image files. |
| **Offline Execution Failure** | Missing cloud or blockchain network halts screening at border checkpoint. | System is offline-first by design. Local SQLite and local Ed25519 signing work with zero network connectivity. |
| **Key Management Lockout** | Corrupted or missing encryption keys prevent application boot. | In development/demo mode, a deterministic local development key is safely derived if environment variables are absent. In production mode, the system fails closed. |
| **Ledger Inconsistency** | Migrating from tip-update to append-only breaks existing ledger viewer. | Adapter maps legacy block schema fields (`block_index`, `doc_hash`, `risk_score`, etc.) from append-only events, ensuring existing UI functions seamlessly. |

---

## 6. Stop Conditions & Human Approval Triggers

In strict accordance with Section 55 of `Security .md`, execution will **IMMEDIATELY STOP** and request explicit user direction if:
1. Any existing API endpoint contract would need to be modified.
2. Any database migration would require altering or deleting existing test documents.
3. Any existing AI model (PaddleOCR, Haar cascade, ViT, MobileNetV3) would need replacement.
4. Any sovereign risk threshold (e.g., risk $\ge 60$ FLAGGED) would be altered.
5. An external dependency fails to build or introduces a licensing incompatibility.

---

## 7. Next Step: Approval Gate for Phase 1

Phase 0 inspection and planning are 100% complete.  
**Execution is paused.**  
No application code has been modified.

**Awaiting user approval**:
> *"Approved. Implement Phase 1 only. Preserve all existing functionality. Run regression tests before and after. Do not proceed to Phase 2 until Phase 1 passes."*

