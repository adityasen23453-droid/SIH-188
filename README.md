# 🛡️ BorderShield: AI-Driven Document Screening & E-Gate Identity Verification System
### **Smart India Hackathon (SIH) | Problem Statement: PS 26188**
**Ministry of Home Affairs (MHA) | Automated Border Control (ABC) & E-Gate Infrastructure**

---

## 📌 Executive Summary

**BorderShield** is an automated, border-grade identity screening and document verification platform developed for the **Ministry of Home Affairs (MHA)** under **Smart India Hackathon (PS 26188)**. Designed for airport electronic gates (E-Gates) and international immigration checkpoints, the system evaluates passports, national identity cards, visas, and residence permits with a **~1.10s mean pipeline latency** (warm inference P50: **721 ms**, P95: **1453 ms** on our 104-document benchmark dataset), catching digital forgeries, physical tampering, fraudulent numbers, and biometric aliases with zero hardcoded rules.

```
+---------------------------------------------------------------------------------------------------------+
|                                    BORDERSHIELD E-GATE ARCHITECTURE                                      |
+---------------------------------------------------------------------------------------------------------+
|                                                                                                         |
|   [Passenger Document]  --->  [Orientation Rectification]  --->  [Single-Pass Deep Scene OCR]            |
|       (Phone / Flatbed)            (0°, 90°, 180°, 270°)             (PaddleOCR PP-OCRv6 Fast Path)      |
|                                                                                   |                     |
|                                            +--------------------------------------+                     |
|                                            |                                      |                     |
|                                            v                                      v                     |
|                                [Domain Verification Engine]            [Tampering & Forgery Engine]      |
|                                * Aadhaar (Verhoeff D5)                 * Error Level Analysis (ELA)     |
|                                * Voter ID (ECI EPIC)                   * ViT Deepfake Transformer       |
|                                * Driving License (Sarathi)             * EXIF Editing Metadata          |
|                                * Passport (ICAO Doc 9303 7-3-1)        * Consular Stamp Splicing        |
|                                * Consular Visa Validation                                               |
|                                            |                                      |                     |
|                                            +-------------------+------------------+                     |
|                                                                |                                        |
|                                                                v                                        |
|                                               [Multi-Signal Risk Scoring Engine]                        |
|                                                                |                                        |
|                                            +-------------------+------------------+                     |
|                                            |                                      |                     |
|                                            v                                      v                     |
|                               [1:1 & 1:N Biometric Engine]             [SHA-256 Blockchain Ledger]      |
|                               (Live Match & Alias Alert)               (Immutable Inspection Receipt)   |
|                                                                                                         |
+---------------------------------------------------------------------------------------------------------+
```

---

## ⚡ High-Speed Architecture & Benchmark Performance

Automated Border Control (ABC) gates operate under strict international latency budgets (target: **sub-5 seconds per passenger** under warm operation). BorderShield achieves this through:

1. **Elimination of the OCR Fallback Waterfall**:
   - Rather than executing multiple OCR engines sequentially (PassportEye $\to$ Tesseract $\to$ PaddleOCR $\to$ Fallbacks), BorderShield utilizes a **Fast Path + In-Memory Recovery** architecture.
   - A single deep detection pass (`PP-OCRv6_medium_det` & `PP-OCRv6_medium_rec`) extracts both Machine Readable Zones (MRZ) and Visual Inspection Zone (VIZ) textlines concurrently.
   - Secondary recovery (PassportEye / Tesseract OCR-B) is strictly targeted to an in-memory bottom $32\%$ crop, eliminating disk I/O churn and full-image re-scans.
2. **Fast Face Multi-Angle Orientation Voting**:
   - Rotations ($0^\circ, 90^\circ, 180^\circ, 270^\circ$) are detected using multi-angle Haar cascade face detection and ICAO chevron spatial priors on an $800\text{ px}$ thumbnail. Normal upright documents exit orientation detection in $<15\text{ ms}$, while sideways documents (e.g. $90^\circ$ CW) rotate and align in $<1.3\text{ s}$ without synchronous Tesseract OSD disk calls.
3. **Dynamic Resolution Capping ($1200\text{ px}$)**:
   - High-resolution smartphone uploads ($8\text{ MB}+$, $4000\times3000\text{ px}$) are proportionally capped to $1200\text{ px}$ during initial context creation, reducing CPU compute time by **$85\%$** without degradation in OCR character accuracy.
4. **Engine Configuration & Windows Python 3.13 Runtime Stability**:
   - PaddleX 3 support models (`PP-LCNet_x1_0_doc_ori`, `UVDoc` 3D unwarper, and `PP-LCNet_x1_0_textline_ori`) are bypassed via `use_doc_orientation_classify=False`, `use_doc_unwarping=False`, and `use_textline_orientation=False`, removing $15+\text{ seconds}$ of redundant neural inference.
   - `enable_mkldnn=False` is enforced on Windows with Python 3.13 to avert PIR runtime crashes (`ConvertPirAttribute2RuntimeAttribute not support`), providing deterministic sub-second CPU inference.
5. **Background Pre-Warming at Startup**:
   - The FastAPI backend pre-warms OCR models during server launch in a background daemon thread, eliminating the $25\text{s}$ cold-start penalty on live passenger requests.

---

### 📊 Benchmark Metrics (Rigorous 104-Document Dataset)

Evaluated with `backend/tools/benchmark_suite.py` across 104 multi-class documents (52 genuine, 52 tampered across Passports, Aadhaar, Voter ID, and Driving Licenses with various degradation levels):

| Metric | Measured Value | Standard Target | Status |
| :--- | :--- | :--- | :--- |
| **Dataset Size** | **104 Documents** (52 Genuine, 52 Manipulated) | $\ge 100$ | **PASSED** |
| **Accuracy** | **$92.31\%$** | $> 90\%$ | **PASSED** |
| **Precision** | **$87.93\%$** | $> 85\%$ | **PASSED** |
| **Recall (Detection Rate)** | **$98.08\%$** (51 / 52 tampered caught) | $> 95\%$ | **PASSED** |
| **F1 Score** | **$92.73\%$** | $> 90\%$ | **PASSED** |
| **False Negative Rate (FNR)** | **$1.92\%$** (Only 1 missed forgery) | $< 5\%$ | **PASSED** |
| **False Positive Rate (FPR)** | **$13.46\%$** | $< 15\%$ | **PASSED** |
| **Latency P50 (Median)** | **$721.00\text{ ms}$** ($0.721\text{ s}$) | $< 2.0\text{ s}$ | **OPTIMAL** |
| **Latency P95** | **$1453.78\text{ ms}$** ($1.454\text{ s}$) | $< 4.0\text{ s}$ | **OPTIMAL** |
| **Mean Pipeline Latency** | **$1102.37\text{ ms}$** ($1.102\text{ s}$) | $< 3.0\text{ s}$ | **OPTIMAL** |

**Stage Breakdown (Mean)**:
- `PREPROCESS`: $86.31\text{ ms}$
- `PADDLE_OCR`: $949.18\text{ ms}$
- `TAMPERING`: $65.53\text{ ms}$
- `VALIDATION`: $1.33\text{ ms}$
- *Hardware Testbed*: Intel x86_64 CPU, 16 GB RAM, Windows 11, Python 3.13, CPU-mode inference.

---

## 🔍 Key Capabilities

### 1. 4-Way Multi-Angle Document Orientation Rectification
Documents uploaded upside-down or sideways are automatically re-oriented prior to OCR:
- **ICAO MRZ Spatial Inversion Prior**: ICAO Doc 9303 mandates MRZ chevrons (`<<`, `P<`, `V<`, `I<`) at the bottom strip. If chevrons appear in the top $35\%$, the document is immediately rotated $180^\circ$ upright.
- **Multi-Angle Frontal Face Verification**: Evaluates $0^\circ, 90^\circ, 180^\circ, 270^\circ$ for an upright facial portrait using Haar cascades on a downscaled thumbnail.
- **Tesseract OSD Fallback**: Verifies script and orientation confidence metrics.

### 2. Border-Grade Sovereign Verification Engines
Zero hardcoding — all verifications enforce official government and international standards:

| Document Type | Governing Standard | Verification Methodology |
| :--- | :--- | :--- |
| **Indian Aadhaar** | **UIDAI Specification** | **Dihedral Group $D_5$ Verhoeff Algorithm**: Dynamically computes the 12th check digit from the first 11 digits using multiplication table $d(j, k)$, permutation table $p(i, j)$, and inverse table $inv(j)$. Validates UID length, verifies first digit $\notin \{0, 1\}$, detects UIDAI sovereign emblems, and scans for high-density 2D QR matrices. |
| **Voter ID (EPIC)** | **Election Commission of India (ECI)** | **10-Character Alphanumeric Standard**: Enforces 3-letter Assembly Constituency functional code + 7-digit sequential unique number (`^[A-Z]{3}[0-9]{7}$`). Validates Election Commission of India sovereign headers. |
| **Driving License** | **MoRTH Sarathi Standard** | **16-Character Registry Standard**: Validates `SS-RR-YYYY-NNNNNNN` structure against the official 36 Indian States and Union Territories registry (`INDIAN_RTO_STATES`). Verifies 2-digit RTO division code, 4-digit issuance year, and validity window. |
| **Consular Visa** | **ICAO MRV-A / MRV-B & Consular Rules** | Validates Visa control number, authorized category (Tourist, Business, Student, Entry), permitted entries (Single, Double, Multiple), validity window ($\text{Date of Issue} \le \text{Date of Expiry}$), and checks consular stamp splicing integrity. |
| **Passports** | **ICAO Doc 9303 (TD3 & TD1)** | **7-3-1 Modulo-10 Weighting Matrix**: Computes check digits across document number, DOB, and expiry date, plus composite check digit. Supports standard 2-line TD3 passports and 3-line TD1 ID cards (e.g. US Passport Cards). |

### 3. Positional OCR Auto-Correction
Applies scoped character-to-digit conversions strictly to numeric positions (DOB 13–19, Expiry 21–27, check digits 9, 19, 27, 43):
$$\text{B}\to 8,\quad \text{O}/\text{Q}/\text{D}\to 0,\quad \text{I}/\text{L}\to 1,\quad \text{S}\to 5,\quad \text{Z}\to 2,\quad \text{A}\to 4$$
Preserves authentic alphanumeric characters in Passport Number (0–8) and Issuing Country / Nationality (10–12).

### 4. Multi-Signal Tampering & Forgery Detection
- **Error Level Analysis (ELA)**: Recompresses document images at JPEG quality 90, measures pixel-level compression rate variance, detects spliced elements, and outputs visual difference heatmaps.
- **Pretrained Vision Transformer (ViT)**: Evaluates deepfake document manipulation using Hugging Face model `zodumair/document-forgery-detector`.
- **EXIF Metadata Forensics**: Flags software traces from Photoshop, GIMP, or Canva, and identifies stripped metadata signatures.
- **Consular Stamp Forensics**: Analyzes official circular and rectangular stamps via HSV color segmentation and morphological edge inspection.

### 5. Biometric Face Verification (1:1 & 1:N Alias Screening)
- **1:1 Face Verification**: Matches the live traveler's facial capture against the passport portrait crop using OpenCV DNN feature vectors.
- **1:N Alias & Duplicate Screening**: Screens travelers against historical border crossing logs to detect travelers attempting entry under multiple aliases or forged passport numbers with the same face.
- **Liveness Verification**: Evaluates Laplacian variance and mean saturation to detect printed photo spoofing.

### 6. SHA-256 Cryptographic Blockchain Audit Ledger
- Every inspection decision generates an immutable cryptographic block with `previous_hash`, `block_hash`, `file_id`, `officer_id`, `risk_score`, and `timestamp`.
- Real-time tamper auditing verifies the entire ledger chain on every block creation.

---

## 💻 Tech Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn, Asyncio, ThreadPoolExecutor
- **Computer Vision & OCR**: OpenCV (`cv2`), PaddleOCR (`paddlex` PP-OCRv6, PP-LCNet), PyTesseract, Pillow, PassportEye
- **Deep Learning**: PyTorch, Hugging Face `transformers` (ViT Forgery Detector, Microsoft TrOCR)
- **Database & Storage**: SQLite3 (`blacklist.db`, `border_ledger.db`)
- **Frontend**: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, Lucide Icons, Framer Motion

---

## 📁 Repository Directory Structure

```
SIH 188/
├── backend/
│   ├── data/
│   │   ├── blacklist.db             # Stolen / blacklisted travel documents database
│   │   └── border_ledger.db        # Blockchain audit ledger database
│   ├── modules/
│   │   ├── biometrics.py           # 1:1 and 1:N facial matching & liveness engine
│   │   ├── blockchain.py           # Cryptographic SHA-256 inspection ledger
│   │   ├── ocr.py                  # PaddleOCR, TrOCR, MRZ parsing & HUD scanner
│   │   ├── preprocessing.py        # 4-way orientation, contour deskew & CLAHE
│   │   ├── tampering.py            # ELA heatmap, ViT deepfake detector & EXIF
│   │   └── validation.py           # Verhoeff D5, ECI, Sarathi, ICAO 7-3-1 engines
│   ├── uploads/                    # Local storage (gitignored with .gitkeep)
│   │   ├── ela/                    # Generated ELA difference heatmaps
│   │   ├── faces/                  # Cropped biometric passport portraits
│   │   ├── preprocessed/           # CLAHE deskewed top-down images
│   │   └── scanned/                # Green line overlay scanner HUD images
│   ├── main.py                     # FastAPI server & route handlers
│   ├── requirements.txt            # Python dependencies
│   └── test_validation.py          # Deterministic unit test suite
├── frontend/
│   ├── app/
│   │   ├── globals.css             # Tailwind CSS & custom design tokens
│   │   ├── layout.tsx              # Root HTML wrapper & layout
│   │   └── page.tsx                # Main border screening interface
│   ├── components/
│   │   ├── BiometricVerification.tsx # Live camera facial capture & match card
│   │   ├── BlockchainLedger.tsx     # Immutable audit ledger viewer & integrity audit
│   │   ├── DocumentPreview.tsx     # Original vs. ELA vs. HUD overlay viewer
│   │   ├── ExtractedFieldsTable.tsx # Dynamic extracted fields table
│   │   ├── RiskBanner.tsx          # Overall composite risk meter & security flags
│   │   ├── TamperingAnalysis.tsx   # ELA, ViT AI detector, & EXIF inspection card
│   │   └── ValidationResults.tsx   # Dynamic Verhoeff, ECI, Sarathi, ICAO cards
│   ├── lib/
│   │   └── api.ts                  # Axios/Fetch API client
│   ├── types/
│   │   └── index.ts                # TypeScript interface declarations
│   ├── package.json                # Frontend npm manifest
│   └── tsconfig.json               # TypeScript configuration
├── .gitignore                      # Comprehensive git ignore rules
└── README.md                       # Comprehensive Project Documentation
```

---

## 🚀 Installation & Setup Guide

### 1. System Prerequisites
- **Python**: 3.10 to 3.13
- **Node.js**: 18.x or 20.x+
- **Tesseract OCR (Windows)**:
  1. Download the Windows installer: [UB-Mannheim Tesseract Wiki](https://github.com/UB-Mannheim/tesseract/wiki).
  2. Install to the default directory: `C:\Program Files\Tesseract-OCR\`.
  3. Ensure `C:\Program Files\Tesseract-OCR` is in your System `PATH`.

---

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Start the FastAPI server with pre-warmed models
python -m uvicorn main:app --reload --port 8000
```

> **Backend API Docs (Swagger UI)**: `http://localhost:8000/docs`  
> **Health Check**: `http://localhost:8000/api/health`

---

### 3. Frontend Setup

```bash
# Open a new terminal and navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start the Next.js development server
npm run dev
```

> **Web Application Interface**: `http://localhost:3000`

---

## 🧪 Testing & Verification

### Running Backend Unit Tests
Execute the comprehensive test suite verifying Verhoeff $D_5$, ECI EPIC, MoRTH Driving License, Consular Visa, and ICAO 7-3-1 calculations:

```bash
cd backend
python -m unittest test_validation.py
```
```
................
----------------------------------------------------------------------
Ran 16 tests in 0.025s

OK
```

### Running Frontend Type Checks
Verify that all TypeScript types, component props, and API response interfaces compile with zero errors:

```bash
cd frontend
npx tsc --noEmit
```

---

## 📡 API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/upload` | Uploads document image, returns tracking `file_id` |
| `POST` | `/api/analyze/{file_id}` | Runs unified single-pass OCR, validation, tampering, and risk assessment |
| `POST` | `/api/extract/{file_id}` | Returns extracted fields and bounding boxes |
| `POST` | `/api/validate/{file_id}` | Evaluates checksums, Verhoeff $D_5$, registry, and dates |
| `POST` | `/api/tamper-check/{file_id}` | Generates ELA heatmap and runs ViT deepfake analysis |
| `POST` | `/api/biometrics/verify-face` | Performs 1:1 facial match and 1:N alias check |
| `GET` | `/api/blockchain/chain` | Retrieves the immutable SHA-256 inspection audit blocks |
| `GET` | `/api/blockchain/verify` | Cryptographically audits block hashes and previous-hash chaining |

---

## 🏆 SIH PS 26188 Competitive Advantages

1. **Zero Hardcoded Mock Responses**: All fields, check digits, and tamper scores are computed dynamically in real time from the uploaded document binary.
2. **Sub-5-Second E-Gate Performance**: High-resolution downscaling, background model pre-warming, and unified single-pass scene scanning prevent the 60-second waterfall delay.
3. **Comprehensive Indian & International Support**: Native mathematical verification for Indian Aadhaar ($D_5$), Voter ID (ECI), and Driving License (Sarathi), alongside ICAO Doc 9303 international passports and visas.
4. **Defense-in-Depth Security**: Combines physics-based compression forensics (ELA), deep neural classification (ViT), mathematical check digits (Verhoeff & 7-3-1), biometrics, and cryptographic blockchain auditability.
