# BorderShield: Sovereign Security Threat Model (STRIDE)

**Problem Statement**: Smart India Hackathon 2026 — PS 26188 (Ministry of Home Affairs - MHA)  
**System Designation**: Border Document Screening & E-Gate Identity Verification System  
**Threat Analysis Framework**: Microsoft STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)  
**Document Status**: Fully Implemented & Formally Verified  

---

## 1. Threat Matrix Overview (T1 – T14)

| Threat ID | STRIDE Category | Threat Description | Attack Vector | BorderShield Sovereign Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| **T1** | Information Disclosure | Plaintext PII Leakage from Database at Rest | Compromised DB file or offline backup extraction | AES-256-GCM authenticated encryption (`enc:v1:`) with 96-bit unique IVs. Zero plaintext PII in database columns. |
| **T2** | Information Disclosure | Query Leakage & Inversion Attacks on Indexed IDs | Frequency analysis or dictionary attacks on hashed passport/Aadhaar IDs | Keyed HMAC-SHA-256 tokenization (`tok:v1:`) with normalized inputs and isolated secret key. |
| **T3** | Information Disclosure | Biometric Template Inversion & Face Reconstruction | Reconstructing facial portrait from stored float32 feature embeddings | AES-256-GCM encrypted embedding vault at rest, pseudonymized `subject_id` binding, and in-memory matching. |
| **T4** | Information Disclosure | Indefinite Data Retention & Exposure Window | Retaining passenger scans indefinitely on checkpoint disks | Automated ephemeral retention scrubber purging files after 24h unless flagged for judicial `legal_hold`. |
| **T5** | Tampering / EoP | Malicious File Upload & Remote Code Execution | Polyglot PHP/ELF payloads disguised as JPEG images | Strict magic-byte inspection (`\xff\xd8\xff`), file extension validation, and server-side UUID renaming. |
| **T6** | Denial of Service | Decompression Bomb (Pixel Flood Attack) | 10,000x10,000 pixel images crashing OpenCV memory | 50 Megapixel decode guard (`MAX_IMAGE_PIXELS = 50,000,000`) and 15MB file size boundary (`HTTP 413`). |
| **T7** | Elevation of Privilege | Unauthorized Screening Decision Override | Malicious or colluding officer clearing blacklisted traveler | Sovereign RBAC enforcing `decision:override` permission (Supervisors/Investigators only); immutable audit event. |
| **T8** | Tampering | In-Place Ledger Mutation & Record Alteration | Attacker or DBA running `UPDATE` query to alter risk score or decision | Append-only event architecture; SHA-256 Merkle continuous chaining; in-memory tamper detection in `verify_chain_integrity()`. |
| **T9** | Repudiation | Audit Record Repudiation by Station or Officer | Checkpoint officer denying having cleared a fraudulent document | Ed25519 asymmetric digital signatures (RFC 8032) signing canonical digests with station keypair. |
| **T10** | Denial of Service | Network Outage Halting Checkpoint Border Operations | Central DLT or WAN disruption causing e-gate paralysis | Offline-First architecture: immediate local SQLite commit with asynchronous `ANCHOR_PENDING` spooling. Zero gate delay. |
| **T11** | System Integrity | Vendor Lock-in & Incompatible Distributed Ledger | Proprietary blockchain SDK deprecation or licensing lock-in | Abstract `AuditLedger` interface; local cryptographic ledger default; Vishvasya BaaS transaction envelope alignment. |
| **T12** | Information Disclosure | Shoulder-Surfing of Aadhaar / Passport Numbers | Public onlookers viewing terminal screens at physical booths | Section 29 Aadhaar Act 8-digit masking (`XXXX-XXXX-1234`), passport masking (`P*******78`), and Officer Reveal Toggle. |
| **T13** | Repudiation / Trust | False Government Certification Claims / Fake Endpoints | Deceptive marketing claiming live government integration | Explicit prototype labeling: *"Prototype adapter — Integration-ready (Not connected to production network)"*. Zero mock endpoints. |
| **T14** | Tampering / Info Leak | Cross-Origin Request Forgery & Wildcard CORS | Malicious browser extension stealing session tokens via `*` CORS | Strict CORS allowlist (`localhost:3000`, `127.0.0.1:3000`) and standard HTTP security headers (`nosniff`, `DENY`). |

---

## 2. Detailed Threat Analysis & Mitigation Proofs

### T1: Plaintext PII Leakage from Database at Rest
- **Risk Assessment**: **CRITICAL**. A physical disk seizure or unauthorized database dump at a remote border checkpoint could expose thousands of traveler identity records.
- **Vulnerability**: Legacy systems storing raw names, Aadhaar numbers, and passport numbers in plaintext SQL tables.
- **BorderShield Mitigation**:
  - All sensitive fields are encrypted prior to insertion using AES-256-GCM.
  - Ciphertexts take the authenticated format `enc:v1:<nonce>:<ciphertext>`.
  - Keys are loaded from `ENCRYPTION_MASTER_KEY` and never hardcoded in repository files.
- **Verification**: Verified in `test_aes_gcm_encryption_roundtrip`, `test_aes_gcm_tampered_ciphertext_fails`, and `test_aes_gcm_wrong_key_fails` in `backend/tests/test_security_upgrades.py`.

### T2: Indexable Query Leakage & Inversion Attacks
- **Risk Assessment**: **HIGH**. Unsalted or static SHA-256 hashes of standard 8-character passport numbers can be inverted using precomputed rainbow tables in seconds.
- **Vulnerability**: Querying blacklist tables using raw hashes of document numbers.
- **BorderShield Mitigation**:
  - Uses HMAC-SHA-256 with a dedicated `HMAC_SECRET_KEY`.
  - Normalizes numbers by removing spaces, hyphens, and casing before hashing.
  - Outputs `tok:v1:<digest>`, ensuring lookups are fast (`O(1)` index lookup) while computationally irreversible without the secret key.
- **Verification**: Verified in `test_hmac_tokenization_deterministic_and_prefixed` in `backend/tests/test_security_upgrades.py`.

### T3: Biometric Template Inversion & Face Reconstruction
- **Risk Assessment**: **HIGH**. Advanced generative models can reconstruct recognizable facial images from unencrypted 576-dimensional embedding vectors.
- **Vulnerability**: Storing raw float32 byte arrays in database blobs.
- **BorderShield Mitigation**:
  - Float32 embedding vectors are encrypted using `encrypt_bytes()` (AES-256-GCM).
  - Templates are linked exclusively to isolated `subject_id` UUIDs (`SUBJ-<UUID12>`).
  - Raw embedding vectors are never returned over HTTP or printed in application logs.
- **Verification**: Verified in `test_biometric_vault_embedding_encryption` in `backend/tests/test_security_upgrades.py`.

### T4: Indefinite Data Retention & Exposure Window
- **Risk Assessment**: **HIGH**. Accumulating years of traveler document scans creates an expanding attack surface violating DPDP Act 2023 storage limitation mandates.
- **Vulnerability**: Document uploads accumulating on local SSD without an automated deletion lifecycle.
- **BorderShield Mitigation**:
  - Background `cleanup_expired_uploads()` sweeps upload directories on startup and on schedule.
  - Files exceeding `DOCUMENT_RETENTION_HOURS` (24h) are permanently deleted.
  - Files marked with `legal_hold = True` for active investigations are preserved.
- **Verification**: Verified in `test_retention_scrubber_preserves_legal_hold` in `backend/tests/test_security_upgrades.py`.

### T5: Malicious File Upload & Remote Code Execution
- **Risk Assessment**: **CRITICAL**. An attacker uploading a webshell or polyglot executable disguised as `passport.jpg` could compromise the border inspection server.
- **Vulnerability**: Relying on client-supplied `Content-Type: image/jpeg` headers or `.jpg` file extensions.
- **BorderShield Mitigation**:
  - Deep magic-byte inspection: checks leading bytes (`\xff\xd8\xff` for JPEG, `\x89PNG` for PNG, `RIFF...WEBP` for WebP).
  - Rejects unknown binaries (ELF, PE, Mach-O) and script tags (`<?php`, `<script`) with HTTP 400.
  - Strips user-supplied filenames via `sanitize_filename()` and writes files with random UUIDs.
- **Verification**: Verified in `test_magic_byte_file_validation_valid_and_invalid` and `test_upload_path_traversal_prevention` in `backend/tests/test_security_upgrades.py`.

### T6: Decompression Bomb Denial-of-Service
- **Risk Assessment**: **HIGH**. A tiny compressed image (e.g. 50KB ZIP bomb) expanding into a 50,000x50,000 pixel raster can exhaust system RAM and crash OpenCV.
- **Vulnerability**: Unchecked decompression of valid image formats.
- **BorderShield Mitigation**:
  - Enforces `MAX_IMAGE_PIXELS = 50,000,000` (50 Megapixels).
  - Rejects images whose dimension product exceeds threshold prior to downstream AI pipeline execution.
- **Verification**: Verified in `test_upload_size_limit_and_bomb_protection` in `backend/tests/test_security_upgrades.py`.

### T7: Unauthorized Screening Decision Override
- **Risk Assessment**: **CRITICAL**. A rogue booth operator accepting a bribe could unilaterally clear an impostor or blacklisted fugitive.
- **Vulnerability**: Allowing arbitrary officer clients to update screening decisions without role enforcement.
- **BorderShield Mitigation**:
  - Enforces strict sovereign RBAC. Only `SUPERVISOR` and `INVESTIGATOR` roles possess `decision:override`.
  - Screening officers attempting to call `/api/ledger/override` receive HTTP 403 Forbidden.
  - Overrides append a new `OFFICER_OVERRIDE_EVENT` to the ledger, recording the original automated decision, the new decision, supervisor ID, and audit justification.
- **Verification**: Verified in `test_rbac_sovereign_roles_and_permissions` and `test_rbac_override_endpoint_enforcement` in `backend/tests/test_security_upgrades.py`.

### T8: In-Place Ledger Mutation & Record Alteration
- **Risk Assessment**: **CRITICAL**. An attacker gaining database access could alter historical records (`UPDATE blockchain_ledger SET decision = 'CLEARED'`) to erase audit trails.
- **Vulnerability**: Mutable relational schemas updating existing rows.
- **BorderShield Mitigation**:
  - Transitioned from `UPDATE` mutations to append-only linked events.
  - Each block links to its predecessor via `previous_hash`.
  - `verify_chain_integrity()` verifies SHA-256 hash continuity from Genesis to tip. If a single historical block is modified, the entire downstream chain breaks, and the tampered block index is flagged.
- **Verification**: Verified in `test_append_only_audit_chain_integrity` and `test_audit_chain_tamper_detection` in `backend/tests/test_security_upgrades.py`.

### T9: Audit Record Repudiation by Station or Officer
- **Risk Assessment**: **HIGH**. In a judicial dispute or inquiry, an agency could claim that audit ledger records were fabricated or modified after the fact.
- **Vulnerability**: Unsigned ledger records that could be authored by any process with write access to SQLite.
- **BorderShield Mitigation**:
  - Station private key signs each block's RFC 8785 canonical hash using Ed25519 (RFC 8032).
  - Signature `sig:ed25519:<hex>` is stored alongside the block and verified by external auditors using the station's public key.
- **Verification**: Verified in `test_ed25519_signature_verification` and `test_ed25519_tampered_payload_fails` in `backend/tests/test_security_upgrades.py`.

### T10: Network Outage Halting Checkpoint Border Operations
- **Risk Assessment**: **CRITICAL**. Wide-area network outages at remote borders (e.g. Indo-Nepal or Indo-Bhutan border checkposts) must never paralyze e-gate throughput.
- **Vulnerability**: Synchronous blocking calls to remote cloud or blockchain nodes.
- **BorderShield Mitigation**:
  - `PermissionedLedgerAdapter` commits to local SQLite immediately.
  - Unreachable remote endpoints spool records as `ANCHOR_PENDING`.
  - When connectivity is restored, `POST /api/ledger/sync` flushes spooled records to `NBF_ANCHORED`.
- **Verification**: Verified in `test_offline_resilience_and_anchor_pending_status` in `backend/tests/test_permissioned_adapter_phase11.py`.

### T11: Proprietary Vendor Lock-in
- **Risk Assessment**: **MEDIUM**. Tight coupling to proprietary enterprise blockchain APIs prevents adoption of sovereign national standards.
- **Vulnerability**: Hardcoded SDK calls to third-party vendor blockchains.
- **BorderShield Mitigation**:
  - Abstract base class `AuditLedger` decouples border screening logic from storage backends.
  - Native support for `LocalCryptographicLedger`, `PermissionedLedgerAdapter`, and `NBFPermissionedLedgerAdapter` aligned with MeitY's Vishvasya Stack.
- **Verification**: Verified in `backend/tests/test_ledger_adapter_phase10.py` and `backend/tests/test_nbf_alignment_phase12.py`.

### T12: Shoulder-Surfing of Aadhaar / Passport Numbers
- **Risk Assessment**: **MEDIUM**. Terminal screens visible in public checkpoint queues can leak traveler identity numbers to onlookers.
- **Vulnerability**: Plaintext display of 12-digit Aadhaar UID numbers and passport numbers on frontend UI.
- **BorderShield Mitigation**:
  - Section 29 Aadhaar Act 8-digit masking (`XXXX-XXXX-1234`) and passport masking (`P*******78`).
  - Privacy Shield badge in frontend UI.
  - Authorized "Officer View" toggle requiring explicit action to reveal PII.
- **Verification**: Verified in `frontend/components/ExtractedFieldsTable.tsx` and tested via Node test runner.

### T13: False Government Certification Claims
- **Risk Assessment**: **HIGH (Compliance & Integrity)**. Misleading claims of official government production deployment destroy solution credibility.
- **Vulnerability**: Mocking fake government REST endpoints or claiming unverified clearances.
- **BorderShield Mitigation**:
  - Strict zero-fabrication policy.
  - Transparent labeling: *"Prototype adapter — Integration-ready (Not connected to production government network)"*.
  - Documents exact technical requirements for government onboarding in `docs/GOVERNMENT_DEPLOYMENT_ARCHITECTURE.md`.
- **Verification**: Verified in `test_honest_designation_and_zero_fabrication` in `backend/tests/test_nbf_alignment_phase12.py`.

### T14: Insecure Cross-Origin Request Forgery & Wildcard CORS
- **Risk Assessment**: **HIGH**. Wildcard `allow_origins=["*"]` allows malicious web pages visited on checkpoint browsers to execute unauthenticated screening requests.
- **Vulnerability**: Permissive CORS policy across border API endpoints.
- **BorderShield Mitigation**:
  - Configurable strict CORS allowlist in `core/config.py` (`localhost:3000`, `127.0.0.1:3000`).
  - Standard HTTP security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`).
- **Verification**: Verified in `backend/main.py` middleware and tested in baseline test discovery.

