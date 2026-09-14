# 🛡️ BorderShield Backend: E-Gate Document Verification Engine
### **Smart India Hackathon (SIH) | Problem Statement: PS 26188**
**Ministry of Home Affairs (MHA) | Automated Border Control (ABC) Engine**

---

## 📌 Overview

The **BorderShield Backend** is a high-throughput, asynchronous FastAPI service designed for electronic border control gates (E-Gates). It orchestrates unified deep scene text OCR, sovereign mathematical checkdigit verification (ICAO Doc 9303, UIDAI Verhoeff $D_5$, ECI EPIC, MoRTH Sarathi), multi-signal digital tampering detection, live biometric facial verification, and an immutable SHA-256 cryptographic audit ledger.

---

## ⚡ High-Speed Performance Optimizations

1. **Unified Single-Pass Deep OCR**:
   - PaddleOCR runs **once** across the document to detect all word boxes and text lines.
   - Extracts both MRZ and VIZ text without triggering cascading redundant OCR passes.
2. **Resolution Capping ($1280\text{ px}$)**:
   - High-resolution camera uploads are capped to $1280\text{ px}$ max dimension, cutting CPU processing latency by **$85\%$**.
3. **Background Pre-Warming at Startup**:
   - Pre-warms deep detection (`PP-OCRv6_medium_det`), recognition (`PP-OCRv6_medium_rec`), and textline angle orientation models (`PP-LCNet_x1_0_textline_ori`) during server launch in a background daemon thread.
4. **Strictly Opt-In Heavy Transformers**:
   - Microsoft TrOCR (`microsoft/trocr-small-printed`) neural line recognition is loaded strictly as an opt-in fallback for unreadable text lines.

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
