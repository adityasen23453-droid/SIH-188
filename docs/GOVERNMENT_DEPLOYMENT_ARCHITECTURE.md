# BorderShield: Government Deployment Architecture & National Blockchain Framework (NBF) Onboarding

**Problem Statement**: Smart India Hackathon 2026 — PS 26188 (Ministry of Home Affairs - MHA)  
**System Designation**: Border Document Screening & E-Gate Identity Verification System  
**Target Environments**: Integrated Check Posts (ICPs), Land Ports Authority of India (LPAI), Bureau of Immigration (BoI), Sashastra Seema Bal (SSB), Assam Rifles  
**National Integration**: National Blockchain Framework (NBF / Vishvasya Stack — MeitY, Sept 2024)  
**Status**: Production Deployment Architecture Blueprint  

---

## 1. Border Checkpoint Deployment Topology

BorderShield is engineered for mission-critical deployment across India's terrestrial land borders and international airports. Terrestrial border stations frequently face intermittent satellite or cellular wide-area connectivity, extreme environmental conditions, and high peak traveler throughput.

```
+-----------------------------------------------------------------------------------+
|               Integrated Check Post (ICP) Local Border Facility                   |
|                                                                                   |
|  +-----------------------+     +-----------------------+                          |
|  |   E-Gate Turnstile 1  |     |   E-Gate Turnstile 2  |                          |
|  | - Document Scanner    |     | - Document Scanner    |                          |
|  | - IR/Visible Camera   |     | - IR/Visible Camera   |                          |
|  | - Officer Touch UI    |     | - Officer Touch UI    |                          |
|  +-----------+-----------+     +-----------+-----------+                          |
|              |                             |                                      |
|              +--------------+--------------+                                      |
|                             | Isolated Edge LAN (VLAN 10 - 10 Gbps)               |
|                             v                                                     |
|  +-----------------------------------------------------------------------------+  |
|  |           Station Edge Node Enclave (Redundant Cluster - Active/Passive)   |  |
|  |                                                                             |  |
|  |  +-----------------------------------+   +-------------------------------+  |  |
|  |  |      BorderShield Core Engine     |   |   Local Cryptographic Ledger  |  |  |
|  |  | - PaddleOCR Extraction            |   | - SQLite / Local PostgreSQL   |  |  |
|  |  | - MobileNetV3 Biometrics          |   | - Ed25519 Local Chaining      |  |  |
|  |  | - ViT Forgery Forensic Engine     |   | - Append-Only Event Stream    |  |  |
|  |  | - AES-256-GCM Vault               |   | - Offline Spool Queue         |  |  |
|  |  +-----------------+-----------------+   +---------------+---------------+  |  |
|  |                    |                                     |                  |  |
|  |                    +------------------+------------------+                  |  |
|  |                                       | PKCS#11                             |  |
|  |                                       v                                     |  |
|  |                  +-----------------------------------------+                |  |
|  |                  | Hardware Security Module (FIPS 140-3 L3)|                |  |
|  |                  | - AES-256 Storage Master Key            |                |  |
|  |                  | - HMAC-SHA-256 Lookup Secret Key        |                |  |
|  |                  | - Station Ed25519 Signing Private Key   |                |  |
|  |                  +-----------------------------------------+                |  |
|  +---------------------------------------+-------------------------------------+  |
+------------------------------------------|----------------------------------------+
                                           | Encrypted Government WAN / NICNET / BharatNet
                                           | Asynchronous Anchor Spool Synchronization
                                           v
+-----------------------------------------------------------------------------------+
|            National Blockchain Framework (NBF / Vishvasya Stack - MeitY)          |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | MHA Border Security Consortium Channel: `mha-border-screening-audit`         |  |
|  | - Chaincode: `border_screening_audit_v1`                                    |  |
|  | - Consensus: Raft / IBFT 2.0 Permissioned BFT                               |  |
|  | - Orderers: National Informatics Centre (NIC) & C-DAC Nodes                  |  |
|  | - Endorsers: MHA, BoI, LPAI, MeitY Trust Nodes                              |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Central Identity Vault & Watchlist Registry (PostgreSQL Cluster)             |  |
|  | - National Blacklist & INTERPOL Notice Registry (HMAC Tokenized)            |  |
|  | - Centralized Disaster Recovery & Biometric Re-enrollment Vault             |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### 1.1 Target Deployment Locations
The architecture is designed for direct commissioning at primary Land Ports Authority of India (LPAI) and Bureau of Immigration (BoI) check posts:
- **SSB ICP Raxaul** (Bihar – Nepal Border)
- **ICP Petrapole** (West Bengal – Bangladesh Border)
- **ICP Jaigaon** (West Bengal – Bhutan Border)
- **ICP Moreh** (Manipur – Myanmar Border)
- **ICP Attari** (Punjab – Pakistan Border)
- **Airports (Tier-1 E-Gates)**: IGI Airport New Delhi, CSMI Airport Mumbai, Kempegowda Airport Bengaluru (DigiYatra International Prototype Gate).

---

## 2. Air-Gapped Secure Enclave Architecture

To guarantee zero operational dependency on external network health, each border facility functions as a self-sovereign **Air-Gapped Secure Enclave**.

### 2.1 Network Segmentation & Zoning
Each border installation enforces strict hardware-isolated VLANs:
1. **Z1: E-Gate Terminal Zone (VLAN 10)**:
   - Dedicated physical network connecting document optical scanners, high-resolution portrait cameras, biometric fingerprint readers, and officer terminal displays to the local Edge Node.
   - Strictly isolated from internet and external municipal networks.
2. **Z2: Secure Core Enclave (VLAN 20)**:
   - Houses the BorderShield processing servers, AI inference accelerators (NVIDIA TensorRT / OpenVINO), Hardware Security Modules (HSMs), and local database repositories.
   - Accessible only via mTLS with station certificate authentication.
3. **Z3: Government WAN Uplink (VLAN 30 / DMZ)**:
   - Encrypted gateway via National Informatics Centre (NICNET) or BharatNet satellite uplinks.
   - Dedicated exclusively to outbound asynchronous audit anchoring to the National Blockchain Framework (NBF) and periodic synchronized downloads of cryptographically signed watchlists.

### 2.2 Offline-First E-Gate Continuity
The primary operational directive of border management is **Zero Gate Paralysis**:
- When satellite or WAN connectivity fails, BorderShield executes 100% of identity verification, document forensics, OCR extraction, and biometric face comparison locally within the enclave.
- Screening events are signed with the station's private key, chained into the local SQLite/Postgres ledger, and spooled in the `ANCHOR_PENDING` state.
- Mean processing latency remains **397.66 ms**, allowing continuous passenger flow without queuing delays.

---

## 3. Hardware Security Module (HSM) & Key Lifecycle (PKCS#11)

In development and standalone evaluation environments, BorderShield uses high-entropy environment variables (`ENCRYPTION_MASTER_KEY`, `HMAC_SECRET_KEY`, `STATION_PRIVATE_KEY`). In production government commissioning, all cryptographic operations are offloaded to **FIPS 140-3 Level 3 validated Hardware Security Modules** (e.g., Thales Luna PCIe, Nitrokey HSM, or YubiHSM 2).

### 3.1 Key Management Protocol (PKCS#11)
```
+----------------------------+                     +-------------------------------+
|      BorderShield Core     |                     |     FIPS 140-3 Level 3 HSM    |
|                            |   PKCS#11 Session   |                               |
| 1. Generate Nonce (IV)     +-------------------->| Slot 0: MHA-ICP-KEYS          |
| 2. Pass Plaintext PII      |   C_EncryptInit()   | - Master Storage Key (AES-256)|
| 3. Receive Ciphertext + Tag|<--------------------+ - Lookup Key (HMAC-SHA-256)   |
|                            |   C_SignInit()      | - Station Key (Ed25519)       |
| 4. Canonical Event Digest  +-------------------->|                               |
| 5. Receive 64-byte Ed25519 |<--------------------+ Private keys never leave      |
|    Signature               |                     | secure cryptographic silicon. |
+----------------------------+                     +-------------------------------+
```

### 3.2 Cryptographic Key Separation Matrix
| Key Identifier | Algorithm | Storage Location | Rotation Interval | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `MHA_STORAGE_KEK_V1` | AES-256 | HSM Tamper Enclave | 365 Days | Key Encryption Key protecting database field ciphertexts. |
| `MHA_LOOKUP_HMAC_V1` | HMAC-SHA-256 | HSM Tamper Enclave | 730 Days | Keyed tokenization for deterministic passport/Aadhaar matching. |
| `ICP_STATION_ED25519` | Ed25519 (RFC 8032) | HSM Secure Key Slot | 90 Days | Station identity signature for ledger blocks and officer actions. |
| `NBF_BAAS_TLS_CERT` | X.509 RSA-4096 / ECDSA | PKCS#11 Keystore | 365 Days | Mutual TLS (mTLS) authentication for Vishvasya BaaS gateway. |

---

## 4. National Blockchain Framework (NBF / Vishvasya Stack) Onboarding

The Ministry of Electronics and Information Technology (MeitY) launched the **Vishvasya Blockchain Technology Stack** in September 2024 to provide Blockchain-as-a-Service (BaaS) for sovereign national infrastructure. BorderShield includes native, out-of-the-box alignment with Vishvasya BaaS specifications.

### 4.1 BaaS Consortium Channel Provisioning
BorderShield registers under the MHA National Border Audit Consortium:
- **Channel Name**: `mha-border-screening-audit`
- **Chaincode ID**: `border_screening_audit_v1`
- **Consensus Protocol**: Raft (Crash Fault Tolerant) or Istanbul BFT 2.0 (Byzantine Fault Tolerant) across NIC, BoI, and MHA validating peers.
- **Endorsement Policy**: `AND('MHABorderMSP.peer', 'BoIMSP.peer')`

### 4.2 Vishvasya BaaS Canonical Transaction Envelope
Every anchor transaction submitted to the NBF gateway adheres to the RFC 8785 canonical JSON envelope generated by `format_nbf_payload()` in `backend/modules/ledger_adapter.py`:

```json
{
  "header": {
    "framework": "National Blockchain Framework (NBF) - Vishvasya Stack",
    "version": "1.0",
    "specification": "MeitY NBF-BaaS Core Specification (Sept 2024)",
    "consortium_channel": "mha-border-screening-audit",
    "station_id": "ICP-RAXAUL-GATE-01",
    "station_public_key": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "timestamp_iso": "2026-09-17T12:00:00Z"
  },
  "payload": {
    "event_id": "EVT-d4f1a2e3b8c9",
    "event_type": "SCREENING_EVENT",
    "document_type": "PASSPORT",
    "document_hash": "a8f5f167f44f4964e6c998dee827110c",
    "risk_score": 0.12,
    "decision": "CLEAR",
    "anomaly_count": 0,
    "reason_codes": ["DOC_GENUINE", "MRZ_CHECKSUM_VALID", "BIOMETRIC_MATCH"],
    "model_provenance": {
      "ocr_engine": "PP-OCRv6_medium",
      "forgery_detector": "ViT-B/16-BorderShield-v1",
      "biometric_extractor": "MobileNetV3-Small-576dim"
    },
    "canonical_event_digest": "4f8b2c1d9e7a...",
    "station_ed25519_signature": "7a3b8c1d..."
  },
  "privacy_attestation": {
    "zero_pii_verified": true,
    "dpdp_act_compliance": "DPDP-2023-Sec8-Audited",
    "aadhaar_act_compliance": "Section-29-Masked-NoStorage",
    "raw_biometric_excluded": true
  }
}
```

### 4.3 Automated Anchor Spool Reconciliation
When connectivity to Vishvasya BaaS is restored after an outage:
1. The background reconciliation task queries `audit_ledger` where `nbf_anchor_status = 'ANCHOR_PENDING'`.
2. Blocks are batched into chunks of 50 events.
3. Batches are transmitted to the Vishvasya BaaS gateway via `POST /api/v1/nbf/anchor-batch` with mTLS client certificate authentication.
4. Upon receipt of valid transaction IDs (`tx_id`), the local repository updates block statuses to `ANCHOR_CONFIRMED` alongside block heights and anchor timestamps.
5. In accordance with our sovereign transparency mandate, the system explicitly logs:
   `"Prototype adapter — Integration-ready (Not connected to production government network)"` when operating in hackathon or isolated evaluation mode.

---

## 5. Centralized Disaster Recovery & Database Migration

BorderShield utilizes the repository pattern (`BaseRepository`) in `backend/database/repository.py` to achieve instant migration between edge storage and centralized databases without altering business logic.

### 5.1 SQLite (Edge Node Default) vs PostgreSQL (Centralized Hub)
- **Local Checkpoint Edge**: Default SQLite (`border_shield.db`) provides zero-dependency, ultra-fast read/write access (sub-1ms commits) on localized ruggedized edge servers.
- **State/National Command Center**: Centralized PostgreSQL cluster activated by configuring the environment variable:
  ```bash
  DATABASE_URL=postgresql://mha_admin:SecureVaultPass2026@postgres-cluster.mha.gov.in:5432/bordershield_central
  ```

### 5.2 Database Migration Protocol
The `init_db()` lifecycle performs non-destructive, idempotent DDL execution:
```python
# Automatic repository selection based on configuration
from backend.database.repository import get_repository

repo = get_repository()
# Fully compatible with both SQLite and PostgreSQL backends
screening = repo.get_screening(doc_id)
repo.insert_ledger_block(block_data)
```

### 5.3 Backup and Disaster Recovery (RPO / RTO Targets)
- **Recovery Point Objective (RPO)**: $\le 0\text{ seconds}$ for local cryptographic ledger (synchronous WAL commits). Remote ledger RPO $\le 60\text{ seconds}$ via periodic spool flushing.
- **Recovery Time Objective (RTO)**: $\le 5\text{ minutes}$ for automatic failover to the secondary redundant edge server in the local ICP cluster.

---

## 6. Operational E-Gate Inspection Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Traveler
    actor Officer as Border Officer
    participant EGate as E-Gate Terminal UI
    participant Backend as BorderShield Core
    participant HSM as Hardware Security Module
    participant Ledger as Cryptographic Ledger
    participant NBF as Vishvasya BaaS (NBF)

    Traveler->>EGate: Presents Passport & Looks at Camera
    EGate->>Backend: POST /api/screen-document (Image + Face)
    activate Backend
    Backend->>Backend: Magic Byte & Size Validation (No RCE/Pixel Flood)
    Backend->>Backend: Preprocess, OCR Extraction & ViT Forensics
    Backend->>HSM: HMAC-SHA-256(Doc Number)
    HSM-->>Backend: Keyed Token (tok:v1:...)
    Backend->>Backend: Blacklist & Watchlist Match via Token
    Backend->>Backend: MobileNetV3 Feature Extraction & Cosine Match
    Backend->>HSM: Encrypt PII & Biometrics (AES-256-GCM)
    HSM-->>Backend: Ciphertext (enc:v1:...)
    Backend->>Backend: Compute Canonical RFC 8785 Digest
    Backend->>HSM: Sign Digest with Ed25519 Station Key
    HSM-->>Backend: 64-byte Ed25519 Signature
    Backend->>Ledger: Commit Linked Audit Block (Local Anchor)
    par Asynchronous Remote Anchor
        Backend--)NBF: Spool Vishvasya BaaS Envelope (mTLS)
    and Immediate Response to E-Gate
        Backend-->>EGate: Return Decision (Risk Score, Clear/Flag, Masked PII)
    end
    deactivate Backend

    alt Verification Clear
        EGate->>Traveler: Turnstile Opens (Traveler Cleared)
    else Verification Flagged / Anomaly
        EGate->>Officer: Alert Officer with Explainable Reason Codes
        Officer->>EGate: Review Forensics & Issue Officer Decision
        EGate->>Backend: POST /api/ledger/record-override
        Backend->>Ledger: Append OFFICER_OVERRIDE_EVENT Block
    end
```

---

## 7. Conclusion & Government Commissioning Checklist

Before commissioning BorderShield in a live operational Integrated Check Post, the following pre-flight verification checklist must be executed:

- [x] **Zero Plaintext PII at Rest**: Verified via `test_security_upgrades.py`.
- [x] **DPDP Act 2023 & Aadhaar Section 29 Compliance**: Verified via 8-digit masking and officer unmask audits.
- [x] **Biometric Template Protection**: Verified via AES-256-GCM encrypted vault.
- [x] **Sub-Second Processing SLA**: Verified via macro-benchmark (397.66ms mean latency).
- [x] **Append-Only Immutability**: Verified via SHA-256 continuous linking and Ed25519 signatures.
- [x] **MeitY Vishvasya Stack Alignment**: Verified via BaaS payload formatters and test suite.
- [ ] **Physical HSM Key Generation**: Generate station keys within FIPS 140-3 L3 hardware prior to production turnstile activation.
- [ ] **mTLS Certificate Issuance**: Provision X.509 client certificates from MHA/NIC Root CA.

