# 🛡️ BorderShield Backend: E-Gate Document Verification Engine
### **Smart India Hackathon (SIH) | Problem Statement: PS 26188**
**Ministry of Home Affairs (MHA) | Automated Border Control (ABC) Engine**

---

## 📌 Overview

The **BorderShield Backend** is a high-throughput, asynchronous FastAPI service designed for electronic border control gates (E-Gates). It orchestrates unified deep scene text OCR, sovereign mathematical checkdigit verification (ICAO Doc 9303, UIDAI Verhoeff $D_5$, ECI EPIC, MoRTH Sarathi), multi-signal digital tampering detection, live biometric facial verification, and an immutable SHA-256 cryptographic audit ledger.

---

## ⚡ High-Speed Performance Optimizations & Architecture

1. **Fast Path + In-Memory Recovery Architecture**:
   - PaddleOCR executes **once** on the preprocessed document to detect word boxes, bounding polygons, and text lines concurrently.
   - Extracts both MRZ and VIZ text in a single pass without triggering cascading full-image OCR waterfalls.
   - Secondary recovery (PassportEye / Tesseract OCR-B) is targeted to an in-memory bottom $32\%$ crop, avoiding duplicate disk roundtrips.
2. **Fast Face Multi-Angle Orientation Voting**:
   - Rotations ($0^\circ, 90^\circ, 180^\circ, 270^\circ$) are detected using multi-angle Haar cascade face detection and ICAO chevron spatial priors on an $800\text{ px}$ thumbnail. Normal upright documents exit in $<15\text{ ms}$, while sideways documents align in $<1.3\text{ s}$ without synchronous Tesseract disk calls.
3. **Resolution Capping ($1200\text{ px}$)**:
   - High-resolution camera uploads are capped to $1200\text{ px}$ max dimension, cutting CPU processing latency by **$85\%$**.
4. **Engine Tuning & Python 3.13 Windows Stability**:
   - PaddleX 3 doc orientation, 3D unwarping, and textline orientation sub-models are disabled (`use_doc_orientation_classify=False`, `use_doc_unwarping=False`, `use_textline_orientation=False`), eliminating $15+\text{ s}$ of auxiliary neural overhead.
   - `enable_mkldnn=False` is enforced to prevent PIR runtime crashes on Windows with Python 3.13.
5. **Background Pre-Warming at Startup**:
   - Pre-warms deep detection (`PP-OCRv6_medium_det`) and recognition (`PP-OCRv6_medium_rec`) models during server launch in a background daemon thread, eliminating the cold-start penalty for users.
6. **Centralized Timing & Privacy Guard**:
   - Microsecond precision `StageTimer` measures each stage (`PREPROCESS`, `PADDLE_OCR`, `TAMPERING`, `VALIDATION`) with zero PII logging.

### 📊 Benchmark Metrics (104 Documents: 52 Genuine, 52 Manipulated)
- **Accuracy**: **$92.31\%$** | **Precision**: **$87.93\%$** | **Recall**: **$98.08\%$** | **F1 Score**: **$92.73\%$**
- **False Negative Rate**: **$1.92\%$** (1 / 52 missed) | **False Positive Rate**: **$13.46\%$**
- **Latency P50**: **$721\text{ ms}$** | **Latency P95**: **$1454\text{ ms}$** | **Mean Latency**: **$1102\text{ ms}$** ($1.10\text{ s}$)
- *Stage Mean Latencies*: Preprocess: $86.3\text{ ms}$ | OCR: $949.2\text{ ms}$ | Tampering: $65.5\text{ ms}$ | Validation: $1.3\text{ ms}$
- *Hardware Environment*: Intel x86_64 CPU, 16 GB RAM, Windows 11, Python 3.13.

---

## 🔬 Core Modules Architecture

- **`modules/preprocessing.py`**:
  - 4-Way Multi-Angle Orientation ($0^\circ, 90^\circ, 180^\circ, 270^\circ$) via ICAO MRZ spatial inversion prior, multi-angle Haar cascade face detection, and Tesseract OSD.
  - 4-point convex contour border detection, perspective transform deskewing, and LAB CLAHE contrast enhancement.
- **`modules/ocr.py`**:
  - Unified scene text detection via PaddleOCR 3.7 with textline orientation classification.
  - ICAO Doc 9303 TD3 (2-line $\times$ 44 chars) and TD1 (3-line $\times$ 30 chars) Machine Readable Zone disambiguation and token parsing.
  - Multilingual Visual Inspection Zone (VIZ) extraction for English, French, Spanish, Portuguese, and Hindi document layouts.
  - Dynamic Border Scanner HUD overlay with real-time green bounding boxes.
- **`modules/validation.py`**:
  - **Indian Aadhaar**: Dihedral Group $D_5$ Verhoeff algorithm ($d(j, k)$, $p(i, j)$, $inv(j)$) verifying the 12th check digit from the first 11 digits, UIDAI sovereign emblem check, and QR matrix detection.
  - **Voter ID (EPIC)**: 10-character alphanumeric standard (`^[A-Z]{3}[0-9]{7}$`) and Election Commission of India sovereign headers.
  - **Driving License**: MoRTH Sarathi 16-character format, 36 Indian States/UTs RTO registry lookup, and validity period check.
  - **Consular Visas**: Machine-readable visa parsing, visa control number validation, authorized category & entry allowances, validity window, and consular stamp splicing checks.
  - **Passports**: ICAO 7-3-1 modulo-10 check digits over document number, DOB, date of expiry, and composite check digit, plus scoped OCR auto-corrector.
- **`modules/tampering.py`**:
  - Error Level Analysis (ELA) with JPEG quality 90 compression variance calculation and visual heatmap generation.
  - Hugging Face Vision Transformer model `zodumair/document-forgery-detector` detecting digital splicing and generative alterations.
  - EXIF metadata forensics detecting editing software traces (Photoshop, GIMP, Canva) and stripped metadata.
  - Consular stamp morphology and splicing detection via HSV color masking and contour edge analysis.
- **`modules/biometrics.py`**:
  - 1:1 Live camera portrait to passport biometric portrait matching.
  - 1:N Facial alias and duplicate identity screening against historical crossing points.
  - Liveness verification detecting printed spoofing attacks.
- **`modules/blockchain.py`**:
  - Cryptographic SHA-256 inspection blocks recording document hash, officer ID, risk score, biometric status, and decision.
  - Previous-hash validation ensuring tamper detection across all audit blocks.

---

## 🛠️ Setup & Execution

### Prerequisites
- Python 3.10+
- Tesseract OCR installed to `C:\Program Files\Tesseract-OCR\` (or on system `PATH`).

```bash
# Navigate to backend directory
cd backend

# Install dependencies
pip install -r requirements.txt

# Run server with live reload
python -m uvicorn main:app --reload --port 8000
```

### Running Unit Tests
```bash
python -m unittest test_validation.py
```
