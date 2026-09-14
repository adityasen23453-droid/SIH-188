# SIH 26188 - AI-Based Fake Identity & Document Screening System

## Executive conclusion

SIH 26188 is asking for an AI-assisted border-document screening platform. The core workflow is not simply “detect a fake passport.” It is a layered verification system:

1. Capture a passport/visa/ID/permit.
2. Detect and rectify the document.
3. OCR all relevant fields and MRZ.
4. Validate document structure, dates, codes, checksums and cross-field consistency.
5. Detect visual/physical/digital tampering.
6. Verify that the presented person matches the document portrait.
7. Check a document/identity registry for expiry, revocation, blacklist/watchlist and duplicate identity signals.
8. Fuse the evidence into an explainable risk score.
9. Store a privacy-preserving, tamper-evident audit trail on a permissioned blockchain.
10. Route high-risk cases to a human officer; do not make an unconditional automated “admit/deny” decision.

The supplied SIH statement explicitly requires OCR extraction, document validation, tampering detection and face verification, with tampering detection identified as the core AI innovation. It also calls for validation against rules/databases, risk scoring and a digital trail for investigations. (Source: supplied PS 26188.)

## What the system should look like

```text
Camera / Upload
      |
      v
Document Detection + Perspective Correction
      |
      +--------------------+
      |                    |
      v                    v
OCR + MRZ parser      Visual/Forensic Engine
      |                    |
      v                    +--> tamper localization mask
Rule / Template Engine    +--> photo replacement score
      |                    +--> metadata/provenance score
      |
      +----------+---------+
                 |
                 v
       Issuer / Registry Check
                 |
                 +--> status: valid / expired / revoked / unknown
                 +--> visa validity / blacklist / watchlist
                 |
                 v
      Face Match + (optional) Liveness
                 |
                 v
       Evidence Fusion / Risk Engine
                 |
          +------+------+
          |             |
       LOW/MEDIUM      HIGH
          |             |
       clear with     manual review
       reasons        + evidence
                 |
                 v
      Audit event + document fingerprint
                 |
                 v
      Hyperledger Fabric ledger
```

## 1. OCR and document understanding

### Recommended stack

- Python + FastAPI for the backend.
- OpenCV for image processing and perspective correction.
- PaddleOCR or an equivalent OCR stack for the visual information zone.
- PassportEye/Tesseract-style MRZ extraction as a deterministic fallback.
- A small document-type classifier or detector for passport/visa/ID/permit.
- PostgreSQL for document/verification metadata; object storage such as MinIO for encrypted originals.

PassportEye exposes MRZ extraction and requires Tesseract. MIDV-500 is a useful research dataset for identity-document analysis; it contains 500 video clips covering 50 document types, including passports, IDs and driving licences, with ground truth.

### Pipeline

1. Detect the document boundaries.
2. Apply a four-point perspective transform.
3. Estimate document type and country/template.
4. OCR the visible information zone.
5. Detect the MRZ region.
6. OCR the MRZ separately with a tightly constrained OCR configuration.
7. Parse fields into a canonical JSON structure.
8. Retain OCR confidence for each field.

Example normalized output:

```json
{
  "document_type": "passport",
  "issuing_country": "IND",
  "name": "EXAMPLE HOLDER",
  "document_number": "X1234567",
  "date_of_birth": "1999-08-12",
  "date_of_expiry": "2034-08-11",
  "nationality": "IND",
  "sex": "M",
  "mrz_valid": true
}
```

## 2. Document validation

This layer should be mostly deterministic, not AI.

### Checks for passports

- Correct MRZ structure.
- Correct number of characters per MRZ line.
- Valid issuing-state / nationality code.
- Valid document type code.
- Date parsing.
- Expiry check.
- Passport-number check digit.
- Date-of-birth check digit.
- Date-of-expiry check digit.
- Optional/personal-number check digit where applicable.
- Composite check digit.
- VIZ-to-MRZ consistency.
- Template/layout consistency.
- Issuer registry status.

ICAO documentation specifically discusses incorrect check digits, country codes, MRZ structure and inconsistencies between the visual zone and MRZ as useful inspection signals. ICAO also warns that check digits cannot by themselves authenticate a travel document because the algorithm is public. Therefore checksum validation should be one evidence source, not the whole fraud detector.

### MRZ algorithm

For a field, map characters to values, apply the repeating 7-3-1 weights, sum the products and take the result modulo 10. Use ICAO Doc 9303 as the implementation authority rather than copying a random online implementation.

## 3. Issuer / rules / blacklist database

The PS says the system should validate information against “rules and databases.” For a college prototype you will not have access to operational SSB, immigration, passport or blacklist databases.

Build a clearly labelled simulated issuer/immigration registry instead.

Example tables:

```text
documents
- document_id
- document_number_hash
- issuing_country
- holder_reference_hash
- issue_date
- expiry_date
- status
- document_type
- version

visas
- visa_number_hash
- passport_reference_hash
- valid_from
- valid_until
- entries_allowed
- status

watchlist
- reference_hash
- category
- active
- reason_code

screening_events
- event_id
- document_hash
- result
- risk_score
- model_version
- officer_id
- timestamp
```

Important: do not put raw names, passport numbers, photos or Aadhaar numbers on a public blockchain. Keep sensitive data off-chain and encrypted.

## 4. Tampering detection - the real centerpiece

Treat tampering as several different attack classes rather than one binary classifier.

### A. Text alteration

Examples:

- DOB changed.
- Expiry date changed.
- Passport number edited.
- Name edited.
- Visa duration edited.

Use a document tamper segmentation model and compare local image features around text regions. The DocTamper research dataset has 170,000 tampered document images with copy-move, splicing and generation tampering, plus pixel-level annotations. It is valuable as pretraining/benchmark data, but it is not a passport-only dataset, so you should fine-tune on your own identity-document attack set.

### B. Photo replacement

Detect the portrait region from the document template and compute:

- face embedding consistency with expected portrait characteristics;
- edge/blending artifacts around the inserted face;
- JPEG/compression inconsistencies;
- local noise mismatch;
- texture/resampling artifacts;
- alignment with the surrounding printed frame.

A dedicated crop classifier can output a “photo replacement suspicion” score.

### C. Copy-move / splicing

Useful forensic features:

- frequency-domain inconsistency;
- resampling artifacts;
- local noise residuals;
- duplicated local descriptors;
- edge discontinuities;
- inconsistent compression blocks.

Do not rely on Error Level Analysis alone; use it only as an auxiliary visualization.

### D. Stamp / seal forgery

For visas and permits, detect the stamp/mark region first and then compare it with expected geometry, color/ink distribution and template characteristics. For the SIH demo, you can create several synthetic stamp manipulations and train/evaluate on those while honestly presenting the scope.

### E. Metadata

Inspect:

- EXIF creation software;
- editing software tags;
- modification time;
- image dimensions;
- JPEG quantization tables;
- PDF creator/producer metadata when the input is a PDF.

Metadata is supporting evidence only because it is easily removed or rewritten.

## 5. “How do I verify that the document is AI-generated?”

This is the most important conceptual correction: you should NOT promise a detector that can prove “AI-generated” with certainty.

A robust system instead computes an AI/synthetic-content suspicion signal and combines it with provenance, cryptography, tamper forensics and document rules.

### Recommended AI-generated screening pipeline

```text
Uploaded document
      |
      +--> C2PA / Content Credentials check
      |
      +--> issuer digital signature / ePassport chip check when available
      |
      +--> metadata analysis
      |
      +--> image-generation detector
      |
      +--> document forensic/tamper detector
      |
      +--> template/layout consistency
      |
      +--> OCR semantic consistency
      |
      v
AI/Synthetic suspicion score
```

### Provenance first

C2PA provides a standard way to verify signed provenance information about content. A provenance signal can say where an image came from and how it was handled, but absence of a credential does NOT prove that content is fake. This makes provenance a strong positive signal when present, but not a reliable negative test when absent.

### AI detector

Use a vision classifier trained on real vs generated images. GenImage is a million-scale benchmark for AI-generated image detection and includes testing across generators and degraded images.

For your prototype, do not classify the entire passport page only. Run the model on:

- portrait crop;
- background/design crop;
- stamp crop;
- full page.

The final AI suspicion score should aggregate these crops.

### Why an ensemble matters

An attacker can strip metadata, recompress an image, crop watermarks and move a fake into a new file. Therefore:

```text
AI suspicion
+ forensic tamper evidence
+ document-template evidence
+ cryptographic/provenance evidence
+ issuer lookup
+ biometric match
```

is much more defensible than “our CNN says fake.”

## 6. ePassport / cryptographic verification

For real ePassports, this can be stronger than image AI. ICAO says ePassport validation verifies the digital signature on the chip to confirm authenticity and integrity. The ICAO PKD distributes trusted certificates, including the Master List of Country Signing Certificate Authority certificates.

A production-capable architecture should therefore support:

```text
NFC/ePassport chip
       |
       v
Read LDS data
       |
       v
Passive authentication
       |
       +--> issuer signature valid?
       +--> chip data altered?
       |
       v
Compare chip data with printed data
```

For a hackathon, a real NFC passport implementation is optional and risky in terms of time. Build the interface and demonstrate the same trust model with a simulated signed document record if needed.

## 7. Face verification

The PS's “face detection” module is more useful if implemented as face verification:

```text
Document portrait ---> face detector ---> embedding A
                                             |
Live camera --------> face detector ---> embedding B
                                             |
                                             v
                                      similarity score
```

Recommended stack:

- SCRFD or RetinaFace for face detection.
- ArcFace/InsightFace for embeddings.
- Cosine similarity for matching.
- Optional passive liveness / presentation-attack detector.

There is no universal threshold. Calibrate a threshold using your validation set and report false-match/false-non-match performance. NIST's current FRTE 1:1 program explicitly evaluates false match and false non-match rates and also documents demographic performance differences.

For the demo, show:

- document face;
- live face;
- similarity score;
- quality flag;
- result: match / uncertain / mismatch.

## 8. Multiple identities by the same person

This background requirement can be addressed with a 1:N biometric search.

Store face embeddings in an encrypted vector database or FAISS index. On a new person:

```text
live face -> embedding -> 1:N search -> nearest identities
```

Flag “possible duplicate identity” for human investigation instead of saying “this person definitely has multiple identities.”

## 9. Risk-scoring engine

The final decision should be explainable.

Example evidence vector:

```text
MRZ checksum                 0.00 risk
Document expired             +0.30
Issuer lookup failed         +0.35
Text tamper score             +0.40
Photo replacement score      +0.45
AI-generation suspicion      +0.15
Face mismatch                +0.45
Blacklisted/revoked          +1.00
```

Do not hard-code these weights as the final scientific solution. Use them as an initial demo policy, then calibrate them using a validation dataset.

A better output is:

```json
{
  "risk_score": 87,
  "risk_band": "HIGH",
  "reasons": [
    "MRZ expiry mismatch",
    "High probability of text manipulation",
    "Issuer registry status: REVOKED",
    "Face similarity below threshold"
  ],
  "recommended_action": "MANUAL_REVIEW"
}
```

## 10. Blockchain - exactly where it belongs

Blockchain should NOT be used as the AI engine and should NOT store passport images.

Use a permissioned blockchain as the trust/audit layer.

### Best choice

Hyperledger Fabric is a strong architectural fit because it is permissioned and supports channels and private data collections for organizations that need confidentiality.

### Blockchain records

#### A. Issuance registry

```text
Document UUID
SHA-256(document canonical representation)
Issuer organization ID
Document type
Issue timestamp
Expiry timestamp
Revocation status
Public-key / certificate fingerprint
```

#### B. Screening event

```text
event_id
Document hash
Checkpoint ID
Model version
Risk score
Decision band
Timestamp
Officer/service ID
```

#### C. Revocation

Issuer writes:

```text
DOCUMENT_REVOKED(document_uuid, timestamp, reason_code)
```

#### D. Investigation trail

The ledger provides a tamper-evident sequence of who screened what, with which model/version, and what evidence/risk result was produced.

### What stays off-chain

- passport images;
- face embeddings;
- names;
- dates of birth;
- passport numbers;
- visa details;
- raw OCR output;
- biometric templates;
- large model outputs.

Store these in an encrypted database/object store and place only hashes/references or tightly controlled private data on Fabric.

## 11. Smart contracts / chaincode

Implement four simple functions:

```text
registerDocument(docHash, issuer, issueDate, expiryDate)
getDocumentStatus(docHash)
revokeDocument(docHash, reason)
recordScreeningEvent(docHash, riskBand, modelVersion, timestamp)
```

For a prototype, create two organizations:

```text
Org1 = Issuing Authority
Org2 = Border Screening Authority
```

A private collection can contain restricted document state while public/common ledger data contains the auditable event metadata.

## 12. Recommended technology stack

### Frontend

- React + Vite or Next.js.
- Tailwind CSS.
- Recharts/ECharts for risk and evidence charts.
- Browser camera access for live face verification.

### Backend

- Python 3.11+.
- FastAPI.
- Pydantic.
- PostgreSQL.
- Redis optional.
- MinIO/S3-compatible object storage.

### Computer vision / OCR

- OpenCV.
- PaddleOCR and/or Tesseract.
- PassportEye for MRZ support.
- PyTorch.
- scikit-image.

### Face

- InsightFace / ArcFace.
- SCRFD or RetinaFace.
- Optional anti-spoof model.
- FAISS for 1:N nearest-neighbour search.

### ML tamper detector

- Start with a pretrained segmentation/classification model.
- Fine-tune on DocTamper plus a small custom identity-document attack set.
- Keep a second “classical forensic feature” path as a fallback.

### Blockchain

- Hyperledger Fabric.
- Fabric Gateway SDK from the backend.
- Chaincode in Go or Node.js.
- Docker Compose for local development.

### Deployment

- Docker.
- Nginx reverse proxy.
- TLS.
- GPU optional; CPU prototype is possible with slower inference.

## 13. Dataset strategy

Do not train only on random internet passports.

Use three layers of data:

### Layer 1 - public research datasets

- MIDV-500 for identity-document detection/recognition.
- MIDV-2019 / related identity-document captures for difficult imaging conditions.
- DocTamper for document tampering pretraining/benchmarking.
- GenImage for generic AI-generated image detector development.
- FaceForensics++ only for understanding general facial manipulation detection; it is not a passport dataset.

### Layer 2 - synthetic identity-document dataset

Create your own fake documents from clean templates.

For each genuine document generate:

- DOB edit;
- expiry edit;
- name edit;
- passport-number edit;
- photo replacement;
- pasted stamp;
- copy-move;
- splicing;
- AI-repainted portrait;
- diffusion-generated portrait;
- full synthetic document;
- recompressed version;
- print-scan version;
- low-light capture;
- blur;
- perspective distortion.

Save exact ground truth masks for the manipulated regions.

### Layer 3 - adversarial test set

Never use only the same manipulations used to train the model. Create a holdout set with different fonts, generators, compression levels and document layouts.

## 14. How to generate the demo data safely

Use fictional identities and synthetic documents. Do not build the prototype by collecting or publishing real people's passports/Aadhaar/IDs.

For the demo, create 8-15 document scenarios:

1. Genuine passport -> PASS.
2. Expired passport -> HIGH/expired.
3. Wrong MRZ checksum -> MEDIUM/HIGH.
4. DOB altered -> HIGH.
5. Photo swapped -> HIGH.
6. Visa stamp copied -> HIGH.
7. AI-generated portrait inserted -> HIGH.
8. Registry says revoked -> HIGH.
9. Face mismatch -> HIGH.
10. Multiple-identity candidate -> MANUAL REVIEW.

Each demo case should have a known ground-truth label.

## 15. UI the judge should see

The best screen is not a generic admin dashboard.

Show one document case in an “investigation view”:

### Left
- Original document.
- Zoomed MRZ.
- Document portrait.

### Centre
- OCR extracted fields.
- Validation status per field.
- Tamper heatmap.
- Face similarity.

### Right
- Overall risk score.
- Reasons for risk.
- Issuer status.
- Blockchain audit status.
- Recommended action.

Example:

```text
RISK: 92 / HIGH

[!] Passport expired
[!] MRZ composite checksum failed
[!] Text tamper detected near Date of Birth
[!] Issuer status = REVOKED
[!] Face mismatch

Blockchain audit: VERIFIED
Model versions: OCR-1.2 | TAMPER-0.8 | FACE-2.1
Recommended action: MANUAL SECURITY REVIEW
```

## 16. Explainable evidence is your competitive advantage

When the system says “FAKE,” never show only a number.

Show:

```text
Why flagged?

1. Issuer registry: document not found
2. MRZ: checksum mismatch
3. OCR vs MRZ: date of expiry conflict
4. Tamper model: altered text region at (x,y,w,h)
5. Face match: 0.31, below calibrated threshold
6. Provenance: no trusted credential found
```

This turns a black-box AI demo into a security decision-support system.

## 17. Recommended development order

### Phase 1 - deterministic core

Build document upload, perspective correction, OCR, MRZ parsing and checksum validation.

### Phase 2 - registry

Build PostgreSQL fake issuer, expiry, revocation and watchlist tables.

### Phase 3 - face verification

Add document-face extraction, webcam capture, embeddings and threshold calibration.

### Phase 4 - tamper detector

Start with synthetic edits. Add localization heatmaps.

### Phase 5 - AI-generation signal

Add provenance checks + AI-image classifier + forensic signals. Report this as “synthetic-content suspicion,” not proof.

### Phase 6 - risk engine

Fuse all signals into explainable risk score and reason codes.

### Phase 7 - blockchain

Record document hashes, issuer status and screening events on Fabric.

### Phase 8 - polish

Add investigation UI, performance measurements, model-version display and offline demo mode.

## 18. Evaluation metrics

Do not show only model accuracy.

### OCR

- Character error rate.
- Field extraction exact-match rate.

### Validation

- Rule-validation precision/recall.
- Number of false alerts.

### Tampering

- Precision.
- Recall.
- F1.
- IoU/Dice for tamper-region localization.
- Cross-domain performance.

### Face verification

- FMR.
- FNMR.
- ROC.
- TAR at a chosen FAR.

### Risk engine

- AUROC.
- AUPRC.
- Recall at low false-positive rate.
- Calibration error.

### System

- Average screening latency.
- P95 latency.
- Throughput.
- Percentage of cases sent to manual review.

## 19. Security and privacy requirements

At minimum:

- TLS everywhere.
- AES-256 or equivalent encryption at rest.
- Hash document IDs instead of storing raw identifiers in logs.
- RBAC for officer/admin roles.
- Signed model/version metadata.
- Audit logging.
- Automatic deletion policy for temporary images.
- No raw biometric data on the blockchain.
- Model and dependency version pinning.
- Rate limits and upload validation.
- Malware scanning for PDFs/files.
- Model inference sandboxing where possible.

## 20. Biggest technical risks

### Risk 1 - claiming perfect AI detection

Avoid this. Current provenance and AI-generation tools are signals, not universal proof.

### Risk 2 - training only on your own fake edits

A detector can memorize your attack style. Use cross-domain evaluation and independent test manipulations.

### Risk 3 - blockchain becomes decorative

Avoid a “blockchain” badge. Demonstrate a real transaction: register -> verify -> revoke -> verify again and show the changed result while preserving the audit trail.

### Risk 4 - face verification becomes a single threshold

Calibrate the threshold and show uncertainty.

### Risk 5 - operational databases are unavailable

Clearly label your prototype registry as simulated. Explain what production would connect to: trusted issuer APIs, immigration databases, ePassport PKD infrastructure and authorised watchlists.

## Recommended hackathon MVP

For an SIH team with limited time, implement this exact slice:

```text
Passport image
   -> document detection
   -> OCR + MRZ
   -> ICAO validation
   -> simulated issuer DB
   -> tamper localization
   -> document-face vs webcam-face match
   -> AI/synthetic suspicion
   -> explainable risk score
   -> Hyperledger Fabric audit event
```

Then demonstrate four cases side by side:

```text
REAL          -> LOW -> PASS
EXPIRED       -> HIGH -> MANUAL REVIEW
TAMPERED      -> HIGH -> MANUAL REVIEW
FACE MISMATCH -> HIGH -> MANUAL REVIEW
```

That is enough to satisfy the PS while leaving a credible path to a production architecture.

## Sources to consult

1. ICAO, Doc 9303 / Machine Readable Travel Documents.
2. ICAO PKD - ePassport Validation and Master List.
3. NIST Face Recognition Technology Evaluation (FRTE) 1:1.
4. Qu et al., CVPR 2023, DocTamper.
5. MIDV-500 identity-document dataset paper.
6. GenImage AI-generated image detection benchmark.
7. C2PA Specifications / Content Credentials.
8. Hyperledger Fabric documentation on permissioned networks and private data collections.
9. UIDAI Offline Aadhaar e-KYC documentation as an example of digitally signed offline document verification.
10. DigiLocker architecture/API documentation as an example of issuer-controlled digital document verification.
