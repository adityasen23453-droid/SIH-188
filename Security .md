
MASTER IMPLEMENTATION PROMPT — SIH-188 Privacy + Security + Permissioned Audit Upgrade
You are working on my existing GitHub repository:

https://github.com/adityasen23453-droid/SIH-188.git

Project:
AI-Driven Document Screening & E-Gate Identity Verification System

Target:
Smart India Hackathon 2026 — Problem Statement SIH26188

IMPORTANT:
This is an EXISTING working SIH project.

Your job is NOT to rewrite, restructure unnecessarily, replace, or simplify the existing system.

Your job is to perform a SAFE, INCREMENTAL SECURITY, PRIVACY, DATABASE, AUDIT-LEDGER AND GOVERNMENT-DEPLOYMENT-READINESS UPGRADE.

============================================================

# 0. ABSOLUTE NON-BREAKING REQUIREMENT

============================================================

The existing functionality is more important than the upgrade.

DO NOT break, remove, replace, rename, or silently change any existing:

- API endpoint
- API request schema
- API response schema
- frontend page
- frontend component
- backend module
- OCR pipeline
- OCR fallback logic
- MRZ processing
- document validation
- tampering detection
- ELA analysis
- metadata analysis
- stamp analysis
- ViT forgery detection
- biometric verification
- 1:N identity/alias search
- blacklist/revocation checking
- risk engine
- screening decision logic
- benchmark functionality
- test functionality
- audit functionality
- existing database functionality
- upload workflow
- UI behavior
- error handling
- model loading/warmup
- performance optimizations
- concurrency
- existing configuration variables

Do not remove a feature simply because you think another implementation is cleaner.

If an existing implementation must change internally, preserve its external behavior and compatibility.

Existing functionality has PRIORITY over architectural elegance.

============================================================

# 1. FIRST STEP — FULL REPOSITORY AUDIT

============================================================

Before modifying ANY file:

1. Inspect the complete repository.
2. Identify:
   - frontend
   - backend
   - database
   - OCR modules
   - validation modules
   - tampering modules
   - biometric modules
   - risk engine
   - audit/blockchain module
   - configuration
   - environment variables
   - tests
   - benchmark scripts
   - upload/storage directories
   - dependencies
   - startup commands
   - Docker configuration if present
   - documentation
3. Trace the complete existing screening flow.
4. Identify all database schemas/tables.
5. Identify every API endpoint.
6. Identify frontend → backend dependencies.
7. Identify all places where PII, documents, biometric data or logs are stored.
8. Identify current cryptographic operations.
9. Identify current blockchain/audit-ledger implementation.
10. Identify hardcoded secrets, keys, credentials, CORS values, thresholds or environment-specific settings.
11. Run the existing test suite BEFORE changing anything.
12. Run the existing application if possible.
13. Record the baseline:
    - test count
    - passing tests
    - failing tests
    - API behavior
    - benchmark results
    - startup behavior
    - frontend behavior

Create a file:

docs/UPGRADE_BASELINE.md

containing the discovered baseline.

DO NOT start refactoring before this audit is complete.

============================================================

# 2. CREATE A SAFE UPGRADE STRATEGY

============================================================

Before implementing:

Create:

docs/PRIVACY_SECURITY_ARCHITECTURE.md

and explain:

CURRENT SYSTEM
      ↓
existing screening pipeline
      ↓
new security/privacy layer
      ↓
new audit/event layer
      ↓
permissioned-ledger adapter

The existing screening pipeline must remain intact.

The upgrade should be additive wherever possible.

Preferred strategy:

Existing code
     ↓
Security/privacy wrappers
     ↓
Secure storage
     ↓
Audit events
     ↓
Ledger adapter

Do NOT rewrite the entire backend.

============================================================

# 3. DATABASE UPGRADE

============================================================

The existing database must continue working.

Do NOT blindly replace SQLite if that would break the current project.

Instead introduce a database abstraction/repository layer.

Example conceptual architecture:

database/
    repository.py
    models.py
    migrations/
    connection.py

Existing SQLite:
    continue supporting it for local/demo mode.

PostgreSQL:
    support as the preferred production-style database.

Configuration must determine which database is used.

Example:

DATABASE_URL=<configured value></configured>

NEVER hardcode:

- localhost database credentials
- username
- password
- database URL
- production hostname

Use environment configuration.

The system must remain runnable without requiring PostgreSQL if the current SIH demo depends on SQLite.

============================================================

# 4. DATABASE SCHEMA

============================================================

Introduce normalized entities where appropriate.

At minimum support concepts equivalent to:

screenings
documents
document_fields
biometric_events
risk_assessments
audit_events
officers
blacklist_records
retention_metadata

Do NOT duplicate information unnecessarily.

Every database migration must be:

- versioned
- reversible where practical
- safe
- idempotent
- documented

Existing databases must not be destroyed.

NEVER execute destructive operations such as:

DROP DATABASE
DROP TABLE
DELETE existing production/demo records

unless explicitly required and safely migrated.

============================================================

# 5. PII PROTECTION

============================================================

Identify all personally identifiable information.

Potential examples:

- name
- date of birth
- passport number
- Aadhaar number
- voter ID
- driving licence number
- address
- nationality
- document images
- face images
- biometric templates
- officer identity information

Create a clear classification.

Example:

PUBLIC
INTERNAL
SENSITIVE
HIGHLY_SENSITIVE

Do not expose raw sensitive information unnecessarily.

============================================================

# 6. ENCRYPTION

============================================================

Implement authenticated encryption for sensitive data.

Preferred algorithm:

AES-256-GCM

Use a mature, maintained cryptographic library.

DO NOT implement cryptography manually.

DO NOT create custom encryption algorithms.

DO NOT hardcode encryption keys.

DO NOT store encryption keys inside:

- Python source
- JavaScript source
- Git
- database
- README
- Dockerfile

Configuration should come from environment/configuration or an appropriate secret/key provider.

For the SIH prototype, environment-based key configuration is acceptable.

For production architecture document:

HSM/KMS/government key-management infrastructure

as the intended deployment path.

Document:

- key generation
- key loading
- key rotation
- key versioning
- encryption/decryption
- failure behavior

If a required encryption key is missing in production mode:

FAIL CLOSED.

Do not silently generate a predictable/default key.

============================================================

# 7. DO NOT PUT PII ON THE BLOCKCHAIN

============================================================

THIS IS A HARD REQUIREMENT.

NEVER store these directly on the ledger:

- passport image
- Aadhaar number
- name
- DOB
- address
- face image
- raw face embedding
- document scan
- complete OCR output
- biometric template
- secret encryption key

The blockchain/audit ledger should contain only the minimum necessary audit/proof information.

Examples:

- event ID
- event type
- document hash
- screening ID/token
- risk score
- decision
- model versions
- validation summary
- timestamp
- officer role or pseudonymous officer ID
- previous event hash
- event hash
- digital signature

Even then, minimize metadata.

============================================================

# 8. TOKENIZATION / PSEUDONYMIZATION

============================================================

For identifiers that must be searchable without repeatedly exposing raw PII:

Implement keyed tokenization using a cryptographically secure construction such as:

HMAC-SHA-256

Concept:

token = HMAC(secret_key, normalized_identifier)

Examples:

passport lookup
Aadhaar lookup
internal subject lookup

DO NOT use:

SHA256(identifier)

alone for sensitive identifiers because predictable identifiers can be brute-forced.

Use a secret HMAC key.

Never expose the HMAC key.

Do not display the raw token as if it were the real identity.

Maintain the ability for authorized backend services to resolve the underlying record where legally/operationally appropriate.

============================================================

# 9. BIOMETRIC DATA PROTECTION

============================================================

Treat biometric information as highly sensitive.

Do NOT place biometric embeddings on the blockchain.

Store biometric templates only in controlled storage.

Protect them with encryption at rest.

Separate:

identity metadata

from:

biometric template

where practical.

Use an internal subject identifier.

Example:

subject_id
encrypted_embedding
model_version
created_at
retention_until

The frontend should not unnecessarily receive raw biometric embeddings.

Do not send embeddings to the browser.

Do not log embeddings.

Do not log raw face images.

Do not put biometric data into normal application logs.

============================================================

# 10. DOCUMENT IMAGE LIFECYCLE

============================================================

Audit every place where uploaded files are stored.

Current uploads/processed images must not remain indefinitely without purpose.

Introduce configurable retention.

Example configuration:

DOCUMENT_RETENTION_HOURS
BIOMETRIC_RETENTION_HOURS
FORENSIC_ARTIFACT_RETENTION_HOURS

DO NOT hardcode retention periods.

Use configuration.

The system should track:

created_at
purpose
retention_until
deletion_status

Implement automatic cleanup.

Important:

Do not delete evidence that is explicitly marked as required for an active investigation/case.

Use a retention policy abstraction rather than hardcoded deletion logic.

============================================================

# 11. SECURE FILE UPLOAD

============================================================

Harden document uploads without breaking the current upload flow.

Validate:

- MIME type
- file extension
- file signature/magic bytes
- file size
- image dimensions
- malformed files
- decompression bombs where applicable

Do not trust:

filename
Content-Type header
client-provided extension

Generate server-side random filenames.

Never use user-supplied filenames as filesystem paths.

Prevent:

- path traversal
- arbitrary file overwrite
- executable uploads
- unexpected archive extraction

Do not change the frontend upload contract unless absolutely necessary.

============================================================

# 12. CURRENT BLOCKCHAIN / AUDIT LEDGER

============================================================

The existing SQLite SHA-256 chained ledger must NOT simply be deleted.

Rename the conceptual terminology where necessary.

Use:

"Cryptographically Chained Audit Ledger"

instead of falsely claiming that the SQLite implementation is a decentralized blockchain.

The current ledger can remain as:

LOCAL_DEMO_LEDGER

Create an abstraction:

AuditLedger
    |
    +-- LocalCryptographicLedger
    |
    +-- PermissionedLedgerAdapter

The rest of the application must depend on the abstraction, not directly on SQLite blockchain implementation.

============================================================

# 13. MAKE THE AUDIT LEDGER APPEND-ONLY

============================================================

IMPORTANT.

Existing audit records must never be modified in-place.

Do NOT use:

UPDATE previous audit event

to change a historical event.

Instead create a new event.

Example:

EVENT 001
SCREENING_CREATED

↓

EVENT 002
OCR_COMPLETED

↓

EVENT 003
VALIDATION_COMPLETED

↓

EVENT 004
TAMPERING_ANALYSIS_COMPLETED

↓

EVENT 005
BIOMETRIC_COMPLETED

↓

EVENT 006
RISK_ASSESSMENT_COMPLETED

↓

EVENT 007
FINAL_DECISION

↓

EVENT 008
OFFICER_OVERRIDE

Each event should reference the previous event.

Each event should contain:

previous_event_hash
current_event_hash

The historical event itself must remain immutable.

============================================================

# 14. CANONICAL AUDIT EVENTS

============================================================

Create a deterministic canonical representation for audit events.

Do NOT hash arbitrary JSON serialization if field ordering can vary.

Use deterministic canonical serialization.

Concept:

canonical_event
    ↓
SHA-256
    ↓
event_hash

The hash should include the security-relevant event fields.

Example conceptual event:

{
    "event_id": "...",
    "event_type": "FINAL_SCREENING_DECISION",
    "screening_id": "...",
    "document_hash": "...",
    "decision": "FLAGGED_FOR_INSPECTION",
    "risk_score": 82.4,
    "model_versions": {...},
    "timestamp": "...",
    "previous_event_hash": "..."
}

Do not include sensitive raw PII.

============================================================

# 15. DIGITAL SIGNATURES

============================================================

Where practical, digitally sign important audit events.

Use a mature standard implementation.

Acceptable algorithm choices may include:

Ed25519
ECDSA
RSA-PSS

Choose ONE appropriate implementation.

Do not implement signing mathematics yourself.

The choice must be documented.

The signature must cover the canonical event/hash.

Verify signatures during audit verification.

Never hardcode private signing keys.

Private keys must be loaded securely through configuration/secret infrastructure.

============================================================

# 16. PERMISSIONED BLOCKCHAIN ARCHITECTURE

============================================================

DO NOT connect SIH-188 directly to Ethereum, Polygon, Solana or Bitcoin as the production architecture.

DO NOT claim that SIH/MHA officially mandates one specific blockchain platform unless verified from an official source.

The architecture should instead target:

India's National Blockchain Framework (NBF)
and Vishvasya ecosystem

where appropriate.

The repository should implement an abstraction:

PermissionedLedgerAdapter

The application should not depend directly on a particular blockchain vendor.

Concept:

AuditEvent
    ↓
AuditLedgerService
    ↓
BlockchainAdapter
    ↓
LocalLedger
or
NBF/Vishvasya-compatible permissioned ledger

The prototype can continue running using the local ledger.

============================================================

# 17. NBF / VISHVASYA INTEGRATION

============================================================

IMPORTANT:

Do NOT invent APIs.

Do NOT create fake Vishvasya endpoints.

Do NOT pretend that a local Hyperledger deployment is NBF.

Do NOT claim official integration unless actual official APIs/access are available.

First investigate the currently available official NBF/Vishvasya documentation and determine:

- official platform information
- available developer resources
- API/interface availability
- sandbox availability
- deployment requirements
- authentication requirements
- supported blockchain platforms

If direct integration is not publicly available or requires government access:

implement a clean adapter interface and a documented integration-ready connector.

Example:

NBFPermissionedLedgerAdapter

with clearly documented configuration requirements.

The local demo must continue working without NBF access.

============================================================

# 18. DO NOT USE HYPERLEDGER AS "THE OFFICIAL MHA BLOCKCHAIN"

============================================================

Hyperledger Fabric may be considered as a permissioned DLT technology for a development/prototype implementation if technically appropriate.

But NEVER write:

"Hyperledger Fabric is the official MHA blockchain."

That claim is not allowed unless official documentation proves it.

If using Fabric for a local prototype:

call it:

"Permissioned DLT prototype"

and document:

"Production deployment target: NBF/Vishvasya-compatible government permissioned infrastructure."

============================================================

# 19. DATABASE VS BLOCKCHAIN RESPONSIBILITIES

============================================================

Do not use blockchain as the primary operational database.

DATABASE:

- screening records
- encrypted PII
- biometric metadata
- case data
- risk details
- operational queries
- retention metadata

AUDIT LEDGER:

- event integrity
- screening event hashes
- decision proof
- audit sequence
- timestamps
- model/version evidence
- signatures

BLOCKCHAIN:

- trusted multi-party audit anchoring
- tamper-evident event verification
- inter-organization integrity

Do not duplicate entire database records on-chain.

============================================================

# 20. OFFICER RBAC

============================================================

Implement configurable Role-Based Access Control.

Suggested roles:

SCREENING_OFFICER
SUPERVISOR
INVESTIGATOR
AUDITOR
SYSTEM_ADMIN

Do not hardcode authorization throughout random files.

Create a centralized authorization layer.

Example conceptual permissions:

SCREENING_OFFICER:
    run screening
    view minimum required result

SUPERVISOR:
    review flagged cases
    approve/escalate

INVESTIGATOR:
    access authorized investigation evidence

AUDITOR:
    inspect audit records

SYSTEM_ADMIN:
    system configuration
    infrastructure management

IMPORTANT:

System administrators must not automatically gain unrestricted permission to alter screening decisions.

Final decisions should be append-only audit events.

============================================================

# 21. AUTHENTICATION

============================================================

Inspect the existing authentication system first.

If authentication is missing or incomplete, add a minimal secure authentication layer without breaking current demo operation.

Do not introduce unnecessary external SaaS authentication.

For the SIH demo:

support a local configurable authentication mechanism.

For production architecture:

document integration with government identity/SSO infrastructure where appropriate.

Never hardcode:

admin/admin
password123
JWT secrets
API keys
database credentials

============================================================

# 22. FIX CORS

============================================================

The current project may contain permissive CORS such as:

allow_origins=["*"]

Do NOT leave wildcard CORS for a security-sensitive deployment.

Make allowed origins configurable:

CORS_ALLOWED_ORIGINS

The default development configuration may allow localhost.

Production must require an explicit allowlist.

Do not break the current frontend.

Verify frontend requests after changing this.

============================================================

# 23. SECURITY HEADERS

============================================================

Add appropriate security headers where compatible with the existing frontend/backend architecture.

Examples:

Content-Security-Policy
X-Content-Type-Options
Referrer-Policy
Permissions-Policy
Strict-Transport-Security in HTTPS deployment

Do not blindly apply a CSP that breaks the existing application.

Test it.

============================================================

# 24. LOGGING PRIVACY

============================================================

Audit all logging statements.

NEVER log:

- passport numbers
- Aadhaar numbers
- full names unnecessarily
- DOB
- addresses
- raw OCR text unnecessarily
- face embeddings
- raw document contents
- encryption keys
- access tokens
- passwords

Use:

request_id
screening_id
event_id
safe status
reason codes

for diagnostics.

If sensitive debugging information is required:

make it explicitly configurable and disabled by default.

============================================================

# 25. ERROR HANDLING

============================================================

Never leak:

- stack traces
- database credentials
- filesystem paths
- cryptographic secrets
- model internals unnecessarily

to the frontend.

Maintain detailed internal logs while returning safe API errors.

Do not change existing successful response formats unnecessarily.

============================================================

# 26. RISK ENGINE PRESERVATION

============================================================

DO NOT rewrite the current risk engine just because security work is being added.

Existing signals such as:

- checksum failure
- MRZ/VIZ mismatch
- expiry
- blacklist
- tampering
- biometric mismatch
- missing fields

must continue working.

Security/audit changes must observe the decision, not accidentally change the decision.

If risk logic must change:

1. document why
2. add tests
3. compare before/after outputs
4. verify benchmark results
5. do not silently change thresholds

============================================================

# 27. AI MODEL VERSIONING

============================================================

Every important AI decision should be traceable to:

model name
model version
configuration version

Examples:

OCR_MODEL_VERSION
FACE_MODEL_VERSION
TAMPERING_MODEL_VERSION

Do not hardcode model versions throughout application logic.

Centralize configuration.

Store model version in audit events.

This allows an auditor to determine:

"Which model produced this decision?"

============================================================

# 28. CONFIGURATION — NO HARD CODING

============================================================

ABSOLUTELY NO hardcoded:

- secrets
- passwords
- API keys
- database credentials
- encryption keys
- signing keys
- blockchain endpoints
- production URLs
- CORS origins
- retention periods
- security thresholds
- environment-specific paths

Use:

.env
environment variables
configuration objects
typed settings

Do not commit .env containing real secrets.

Update .env.example with placeholders.

============================================================

# 29. OFFLINE-FIRST DESIGN

============================================================

SIH-188 is a border-screening prototype.

The core screening pipeline must continue to work offline/local.

Do NOT make the system dependent on:

- internet
- public blockchain
- cloud OCR
- cloud biometric APIs
- cryptocurrency
- external SaaS services

for the core demonstration.

Blockchain/network integration must be an additional trust/audit layer.

If unavailable:

screening must still function.

============================================================

# 30. FAILURE / DEGRADATION BEHAVIOR

============================================================

Design explicit behavior when components fail.

Example:

OCR unavailable:
    do not fabricate identity data

Tampering model unavailable:
    return "ANALYSIS_UNAVAILABLE"
    do not pretend PASS

Blockchain unavailable:
    screening can continue
    audit event enters a secure pending queue
    retry later

Database unavailable:
    fail safely

Encryption key unavailable:
    fail closed

Biometric service unavailable:
    return "BIOMETRIC_UNAVAILABLE"

NEVER generate fake/default identity values to make the UI appear successful.

============================================================

# 31. IMPORTANT: NO FABRICATED OCR VALUES

============================================================

If the existing code contains fallback values such as:

"NAGRIK CITIZEN"
"01/01/1995"
"AA00000000"

or similar fake identity values:

DO NOT introduce anything like this into SIH-188.

If OCR fails:

return a clearly typed state such as:

OCR_FAILED
LOW_CONFIDENCE
MANUAL_REVIEW_REQUIRED

Do not invent names, dates, document numbers or countries.

============================================================

# 32. AUDIT EVENT QUEUE

============================================================

Implement reliable audit submission.

Concept:

Screening completed
      ↓
Create canonical audit event
      ↓
Store locally
      ↓
Sign/hash
      ↓
Submit to configured ledger
      ↓
ACK
      ↓
mark anchored

If blockchain/permissioned ledger is unavailable:

ANCHOR_PENDING

must be stored.

Do not lose audit events.

Do not block the entire screening pipeline unnecessarily because an external ledger is temporarily unavailable.

============================================================

# 33. AUDIT VERIFICATION

============================================================

Create a verification function/API that can answer:

"Has this audit chain been modified?"

It should verify:

- event hash
- previous hash
- sequence
- signature
- ledger anchor where available

Return something like:

CHAIN_VALID
CHAIN_INVALID
ANCHOR_PENDING

Do not simply return True without actually verifying.

============================================================

# 34. PRIVACY-AWARE FRONTEND

============================================================

Do not expose more PII than necessary.

Mask sensitive values.

Example:

Passport:

P*******78

Aadhaar:

XXXX-XXXX-1234

Only authorized roles should see complete values.

Do not show:

raw embeddings
encryption keys
internal tokens
database IDs unnecessarily

Do not redesign the complete UI.

Add privacy indicators where useful.

============================================================

# 35. OFFICER AUDIT VIEW

============================================================

Add an audit section to the existing UI without destroying the current dashboard.

Show:

Screening ID
Decision
Risk score
Reason codes
Timestamp
Model versions
Audit status
Chain verification status

Example:

AUDIT STATUS:
✓ Cryptographic integrity verified

LEDGER:
✓ Local audit anchored

or:

LEDGER:
Pending permissioned-ledger synchronization

Do not claim "blockchain verified" when only local SQLite verification has occurred.

============================================================

# 36. EXPLAINABILITY

============================================================

The final decision must remain explainable.

Do not show only:

RISK = 82

Instead show reason codes:

- MRZ checksum mismatch
- suspected photo manipulation
- biometric mismatch
- blacklist match

or:

- MRZ valid
- document not expired
- no tampering evidence
- biometric match
- no blacklist match

This is particularly important for government decision-support systems.

============================================================

# 37. HUMAN-IN-THE-LOOP

============================================================

Do not turn the AI into an unquestionable autonomous border authority.

Support:

AI decision
    ↓
Officer review
    ↓
Confirm / Escalate / Override

If officer overrides the AI:

create a NEW append-only audit event.

Never modify the original AI decision.

Example:

AI:
FLAGGED_FOR_INSPECTION

Officer:
ESCALATED

This entire history must remain auditable.

============================================================

# 38. BENCHMARK PRESERVATION

============================================================

The existing performance benchmark is extremely important.

DO NOT break it.

After every major upgrade run:

existing benchmark

and compare:

P50
P95
P99
mean latency
throughput
accuracy
precision
recall
F1
FPR
FNR

Security features must not unnecessarily destroy the current performance advantage.

If performance changes:

document it.

============================================================

# 39. TESTING

============================================================

Before changes:

run all existing tests.

After each logical phase:

run tests.

At the end:

run all tests again.

Add tests for:

1. encryption/decryption
2. wrong encryption key
3. token generation
4. token mismatch
5. audit hash verification
6. chain tampering
7. signature verification
8. signature failure
9. append-only behavior
10. retention cleanup
11. unauthorized access
12. RBAC
13. CORS
14. malicious upload
15. path traversal
16. missing OCR
17. blockchain unavailable
18. database unavailable
19. model unavailable
20. existing screening workflow

Existing tests must continue passing.

============================================================

# 40. REGRESSION TESTING

============================================================

Create a regression test suite that confirms:

Same valid document
    →
same existing screening result

Same fake document
    →
same expected fraud result

Existing API clients
    →
continue working

Existing frontend
    →
continues working

Existing benchmark
    →
continues running

Existing demo startup
    →
continues working

============================================================

# 41. MIGRATION SAFETY

============================================================

If changing database schemas:

DO NOT destroy existing data.

Provide migrations.

Example:

migration_001_add_audit_events
migration_002_add_retention
migration_003_add_encrypted_fields

Use safe migration patterns.

Existing database should remain readable.

============================================================

# 42. DEPENDENCY DISCIPLINE

============================================================

Do not install large numbers of unnecessary packages.

Before adding a dependency:

1. check whether an existing dependency already provides the functionality
2. determine package maintenance/security status
3. justify the dependency
4. add only what is necessary

Do not replace working libraries without reason.

Avoid unnecessary blockchain frameworks if an adapter interface is sufficient.

============================================================

# 43. NO DEAD CODE

============================================================

Do not create:

- unused modules
- unused imports
- placeholder classes
- fake blockchain implementations
- empty methods
- TODO-only security modules
- duplicate encryption implementations

Every new file must have a real purpose.

============================================================

# 44. NO FAKE FEATURES

============================================================

DO NOT create UI buttons that claim functionality that does not actually exist.

Examples:

"Verify on NBF"
"Blockchain verified"
"Government database verified"

must only appear if the underlying functionality genuinely exists.

For unavailable production infrastructure, explicitly display:

"Prototype adapter"
"Integration-ready"
"Not connected to production government infrastructure"

============================================================

# 45. GOVERNMENT / NBF DOCUMENTATION

============================================================

Add:

docs/GOVERNMENT_DEPLOYMENT_ARCHITECTURE.md

Explain:

Prototype:
    local encrypted DB
    local cryptographic audit ledger

Production target:
    controlled government infrastructure
    permissioned blockchain
    NBF/Vishvasya-compatible architecture
    government-controlled key management
    RBAC
    secure network
    audit logging

Do NOT claim:

"SIH requires Hyperledger."

Do NOT claim:

"MHA officially mandates Hyperledger."

Do NOT claim:

"Polygon is prohibited by MHA."

Do NOT claim:

"System is DPDP compliant."

Instead use accurate wording:

"Designed according to applicable privacy/security principles."

"Architecture is intended to support migration to India's permissioned National Blockchain Framework ecosystem."

============================================================

# 46. OFFICIAL SOURCES

============================================================

Use official sources when documenting government standards.

Prioritize:

MeitY
PIB
India Code
ICAO
official SIH problem statement

Do not base government compliance claims on random blogs.

If you include links/references in documentation, make sure they are real and verified.

============================================================

# 47. ICAO ALIGNMENT

============================================================

Preserve and improve the existing ICAO/MRZ work.

Document:

ICAO Doc 9303
MRZ validation
VIZ/MRZ consistency
eMRTD concepts where actually implemented

Do NOT claim complete ePassport chip authentication unless the project actually implements it.

Clearly separate:

implemented
prototype
future production integration

============================================================

# 48. ARCHITECTURE DOCUMENTATION

============================================================

Create:

docs/SECURITY_THREAT_MODEL.md

Include threats:

T1 document theft
T2 database compromise
T3 biometric leakage
T4 audit tampering
T5 insider modification
T6 unauthorized officer access
T7 malicious upload
T8 credential theft
T9 blockchain unavailability
T10 model failure
T11 OCR failure
T12 replay/tampering
T13 log leakage
T14 key compromise

For each:

Threat
Impact
Mitigation
Residual risk

============================================================

# 49. PRIVACY DATA FLOW

============================================================

Create a privacy data-flow diagram.

Show:

Document
 ↓
Local OCR
 ↓
Sensitive extracted fields
 ↓
Encrypted database

Face
 ↓
Biometric processing
 ↓
Encrypted biometric vault

Screening event
 ↓
Hash
 ↓
Digital signature
 ↓
Permissioned ledger

Clearly show:

RAW PII NEVER ENTERS BLOCKCHAIN.

============================================================

# 50. FINAL TARGET ARCHITECTURE

============================================================

The final architecture should conceptually become:

                    BORDER WORKSTATION
                           |
                           v
                 Existing SIH-188 Pipeline
                           |
          +----------------+----------------+
          |                |                |
         OCR          Forensics         Biometrics
          |                |                |
          +----------------+----------------+
                           |
                      Risk Engine
                           |
                     Officer Review
                           |
                 +---------+---------+
                 |                   |
                 v                   v
          Secure Data Vault      Audit Event
                 |                   |
          PostgreSQL/SQLite      Canonical JSON
          encrypted PII              |
          encrypted biometric       SHA-256
          tokenized identifiers      |
                                    Signature
                                      |
                                      v
                             AuditLedgerService
                                      |
                          +-----------+-----------+
                          |                       |
                          v                       v
                  Local Demo Ledger      Permissioned Ledger
                     (SQLite)             NBF/Vishvasya path

============================================================

51. IMPLEMENTATION ORDER

============================================================

Implement in this EXACT order:

PHASE 0
Repository audit + baseline

PHASE 1
Configuration/security foundation

PHASE 2
Database abstraction + safe migrations

PHASE 3
PII encryption

PHASE 4
Identifier tokenization

PHASE 5
Biometric protection

PHASE 6
Secure upload + storage lifecycle

PHASE 7
RBAC/authentication

PHASE 8
Append-only audit-event architecture

PHASE 9
Digital signatures

PHASE 10
Local cryptographic ledger adapter

PHASE 11
Permissioned blockchain adapter architecture

PHASE 12
NBF/Vishvasya integration only if an actual supported interface is available

PHASE 13
Privacy-aware frontend

PHASE 14
Audit verification UI

PHASE 15
Security tests

PHASE 16
Full regression tests

PHASE 17
Performance benchmark

PHASE 18
Documentation

Do NOT implement everything in one giant uncontrolled refactor.

After each phase:

run tests
check startup
check existing API
check frontend
check benchmark where relevant

============================================================

52. GIT / CHECKPOINT STRATEGY

============================================================

Before starting:

create a clean checkpoint/branch.

Suggested commits:

security: add configuration foundation
security: add encrypted data layer
security: add identifier tokenization
security: protect biometric storage
security: harden file uploads
security: add RBAC
audit: introduce append-only events
audit: add event signatures
audit: add local ledger adapter
blockchain: add permissioned ledger abstraction
frontend: add privacy controls
testing: add security regression tests
docs: add security architecture

Do not make one massive commit containing everything.

============================================================

53. FINAL ACCEPTANCE CRITERIA

============================================================

The upgrade is NOT complete until all of the following are true:

[ ] Existing application starts successfully.

[ ] Existing frontend works.

[ ] Existing backend works.

[ ] Existing API contracts are preserved.

[ ] Existing OCR works.

[ ] Existing MRZ validation works.

[ ] Existing document validation works.

[ ] Existing tampering analysis works.

[ ] Existing biometrics work.

[ ] Existing 1:N identity matching works.

[ ] Existing blacklist logic works.

[ ] Existing risk engine works.

[ ] Existing benchmark works.

[ ] Existing tests still pass.

[ ] Sensitive database data is encrypted.

[ ] Encryption keys are not hardcoded.

[ ] Sensitive identifiers are tokenized where appropriate.

[ ] Biometric embeddings are protected.

[ ] Raw PII is not stored on blockchain.

[ ] Raw images are not stored indefinitely.

[ ] Retention is configurable.

[ ] Upload security is hardened.

[ ] CORS is configurable and restrictive.

[ ] RBAC is implemented.

[ ] Sensitive data is absent from normal logs.

[ ] Audit events are append-only.

[ ] Historical events cannot be silently modified.

[ ] Audit chain can be independently verified.

[ ] Important audit events can be digitally signed.

[ ] Local ledger still works offline.

[ ] Permissioned blockchain adapter exists.

[ ] NBF/Vishvasya integration is NOT falsely claimed.

[ ] Public cryptocurrency blockchain is NOT required.

[ ] No fake government APIs are implemented.

[ ] No fake OCR identity values are generated.

[ ] AI model versions are auditable.

[ ] Officer overrides are auditable.

[ ] Blockchain/network failure does not destroy screening.

[ ] Security changes do not significantly degrade existing performance.

[ ] Documentation accurately distinguishes:
implemented
prototype
production target
future integration

============================================================

54. FINAL REPORT

============================================================

When finished, create:

docs/UPGRADE_REPORT.md

Include:

Existing architecture
Changes made
Files changed
Database changes
Security improvements
Privacy improvements
Encryption approach
Tokenization approach
Biometric protection
Audit architecture
Digital signature approach
Local ledger architecture
Permissioned blockchain architecture
NBF/Vishvasya integration status
RBAC
Retention
Upload security
Threat model
Tests added
Regression test results
Performance before/after
Known limitations
Future production migration plan

Include a table:

Feature | Before | After | Status

============================================================

55. VERY IMPORTANT — STOP CONDITIONS

============================================================

STOP and ask for human approval rather than guessing if:

an existing API must be broken
a database migration could destroy data
an existing model must be replaced
an existing risk threshold must be changed
a production government API requires credentials
NBF/Vishvasya access is unavailable
a cryptographic algorithm must be changed for compatibility
an existing feature cannot be preserved
a dependency introduces a major compatibility issue

Do NOT make assumptions simply to finish the task.

============================================================

56. DEFINITION OF SUCCESS

============================================================

The goal is NOT:

"Add more technologies."

The goal is:

Make SIH-188 a technically credible, privacy-conscious, security-focused, government-deployment-oriented prototype while preserving its existing strengths.

The final system should communicate this architecture:


AI detects
+
Rules validate
+
Biometrics verify
+
Risk engine prioritizes
+
Officer decides
+
Encrypted storage protects PII
+
Cryptographic audit proves history
+
Permissioned blockchain provides future multi-agency trust

The project must remain:

FAST
OFFLINE-CAPABLE
SECURE
PRIVACY-AWARE
AUDITABLE
EXPLAINABLE
NON-BREAKING
CONFIGURABLE
HONEST ABOUT PROTOTYPE LIMITATIONS

Do not over-engineer.
Do not rewrite working code unnecessarily.
Do not add technologies just for presentation.
Do not hardcode anything sensitive.
Do not claim government certification/compliance/integration that has not actually been implemented.

FIRST perform the repository audit and baseline.
THEN provide the proposed file-by-file implementation plan.
ONLY AFTER validating that plan should implementation begin.
