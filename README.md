# AI-Based Fake Identity & Document Screening System (SIH Prototype)

An automated AI-driven document screening and identity verification platform designed to detect fraudulent passports, visas, and identity cards.

---

## 📌 Problem Statement
* **ID / Problem Statement**: PS 26188
* **Organization / Ministry**: Ministry of Home Affairs (MHA)
* **Objective**: Develop an AI-based system to screen documents (passports, visas, national IDs) for identity fraud, forgery, and data mismatches.

---

## 🚀 Current Status & Features

The core backend pipeline, OCR extraction engine, document validation module, AI document forgery model, document deskewing preprocessor, and aggregated risk scoring engine are fully implemented:

* **FastAPI Backend Server**: RESTful API endpoints for uploading, extracting, validating, tamper checking, and analyzing documents.
* **Pre-OCR Document Preprocessing (`modules/preprocessing.py`)**:
  * **Boundary Detection & Perspective Warping**: Uses OpenCV contour approximation and morphological closing to detect document borders on angled camera photos.
  * **Contrast Enhancement**: Applies LAB color space CLAHE (Contrast Limited Adaptive Histogram Equalization) for top-down deskewing.
* **Dual-Path Execution Pipeline**:
  * **OCR Extraction Path**: Executes `run_ocr()` on original raw image uploads to maintain native MRZ font geometry and character contrast ratios.
  * **Tampering Detection Path**: Executes `run_tampering_detection()` on deskewed preprocessed image bounding ROIs for optimal forgery detection.
* **Passport MRZ Extraction & Sanity Validation Engine (`modules/ocr.py`)**:
  * High-accuracy Machine Readable Zone (MRZ) parser powered by `passporteye`.
  * **Gender Validation**: Strictly validates gender against ICAO values (`M`, `F`, `<`). Converts invalid OCR reads to `null` with `gender_note`.
  * **Field Confidence Scoring**: Flags fields with 3+ repeated characters or unreasonable length as `"name_confidence"`, `"passport_number_confidence"`, and `"nationality_confidence"` (`high` / `low`).
* **Generic OCR Fallback Engine**: Unstructured text and field extractor powered by `PaddleOCR` and `PyTesseract` for non-MRZ identity documents.
* **Document Validation Engine (`modules/validation.py`)**:
  * **Field-Level MRZ Checksum Verification**: Calculates 7-3-1 modulo 10 check digits over standard TD3 passport MRZ lines with granular per-field check objects (`passport_number_check`, `date_of_birth_check`, `date_of_expiry_check`, `composite_check`).
  * **Scoped OCR Positional Auto-Corrector**: Applies ICAO 9303 letter-to-digit auto-correction strictly to numeric positions (DOB 13–19, Expiry 21–27, check digits 9, 19, 27, 43): `B`→`8`, `O`/`Q`/`D`→`0`, `I`/`L`→`1`, `S`→`5`, `Z`→`2`, `A`→`4`. Transparently returns `ocr_corrections_applied`. Excludes Passport Number (0–8) and Nationality (10–12) to preserve authentic alphanumeric strings.
  * **Date Plausibility & Century Parsing**: Verifies document expiration and parses YYMMDD dates (e.g. `200221` → `2020-02-21`).
  * **Blacklist Database Screening**: Queries local SQLite database (`data/blacklist.db`) seeded with blacklisted documents.
* **Tampering & AI Forgery Detection Engine (`modules/tampering.py`)**:
  * **Error Level Analysis (ELA)**: Measures pixel compression differences at JPEG quality 90, generates visual difference heatmaps in `uploads/ela/`, and calculates 0-100 `ela_score`.
  * **Pretrained ViT AI Forgery Detector**: Runs Hugging Face Vision Transformer model `"zodumair/document-forgery-detector"` over alpha-blended ELA composite maps.
  * **EXIF Metadata Inspection**: Scans EXIF tags for editing software signatures ("Photoshop", "GIMP", "Canva") and flags stripped metadata.
  * **Multi-Signal Risk Rating**: Combines AI detector (50%), ELA score (30%), and EXIF metadata (20%) into a 0-100 `tampering_likelihood` score.
* **Aggregated Dashboard Risk Assessment Endpoint (`POST /api/analyze/{file_id}`)**:
  * Combines OCR, validation, and tampering into a single judge-friendly dashboard response.
  * Calculates `overall_risk_score` (0-100 weighted formula) and `overall_risk_level` (`low`, `medium`, `high`).
  * Generates human-readable `summary_flags` highlighting key findings.

---

## 🛠️ Tech Stack

* **Backend Framework**: Python 3.10+, FastAPI, Uvicorn
* **AI & Deep Learning**: PyTorch, Hugging Face `transformers` (`zodumair/document-forgery-detector` ViT model)
* **Database**: SQLite3 (`data/blacklist.db`)
* **OCR & Computer Vision**: OpenCV (`cv2`), `Pillow` (PIL), `PassportEye`, `PaddleOCR`, `PyTesseract`
* **System Engine**: Tesseract OCR (Binary Engine)

---

## ⚙️ Installation & Setup

### 1. System Dependency: Tesseract OCR Engine (Windows)
`passporteye` and `pytesseract` require the Tesseract OCR system binary.

1. Download the Windows installer from the official build repository: [UB-Mannheim Tesseract Wiki](https://github.com/UB-Mannheim/tesseract/wiki).
2. Install Tesseract to the standard directory:
   `C:\Program Files\Tesseract-OCR\`
3. Add `C:\Program Files\Tesseract-OCR` to your System `PATH` environment variable.

### 2. Python Environment Setup
Navigate to the `backend` directory and install required Python packages:

```bash
cd backend
pip install -r requirements.txt
```

### 3. Running the Backend Server
Start the FastAPI application with live-reloading enabled:

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

Access the interactive API documentation (Swagger UI) at:
👉 `http://localhost:8000/docs`

---

## 📡 API Endpoints & Usage

### 1. `POST /api/upload`
Uploads a document image/PDF to backend storage and assigns a tracking UUID.

**Sample Response (`200 OK`)**:
```json
{
  "file_id": "8d45c2df-123f-4d90-8e91-3d570a51ce98",
  "document_type": "passport",
  "status": "uploaded"
}
```

---

### 2. `POST /api/extract/{file_id}`
Triggers document OCR extraction on the original raw file and returns extracted fields with confidence ratings.

**Sample Response**:
```json
{
  "document_type": "passport",
  "method_used": "mrz",
  "fields": {
    "name": "CARLOS COSTA",
    "name_confidence": "high",
    "passport_number": "AA000681",
    "passport_number_confidence": "high",
    "nationality": "BRA",
    "nationality_confidence": "high",
    "date_of_birth": "010316",
    "date_of_expiry": "220706",
    "gender": "M",
    "gender_note": null,
    "mrz_valid_score": 100,
    "mrz_line2": "AA000681<7BRA0103162M2207063<<<<<<<<<<<<<<00"
  }
}
```

---

### 3. `POST /api/validate/{file_id}`
Runs field-level MRZ 7-3-1 checksum validation, date expiration/plausibility checks, and blacklist screening.

**Sample Response (`200 OK`)**:
```json
{
  "checksum": {
    "passport_number_check": {
      "value": "AA000681",
      "expected_digit": "7",
      "computed_digit": "7",
      "valid": true,
      "field_slice": "0:9",
      "check_digit_pos": 9
    },
    "date_of_birth_check": {
      "value": "010316",
      "expected_digit": "2",
      "computed_digit": "2",
      "valid": true,
      "field_slice": "13:19",
      "check_digit_pos": 19
    },
    "date_of_expiry_check": {
      "value": "220706",
      "expected_digit": "3",
      "computed_digit": "3",
      "valid": true,
      "field_slice": "21:27",
      "check_digit_pos": 27
    },
    "composite_check": {
      "expected_digit": "0",
      "computed_digit": "0",
      "valid": true,
      "field_slice": "0:10 + 13:20 + 21:43",
      "check_digit_pos": 43
    },
    "overall_checksum_valid": true,
    "failed_fields": [],
    "ocr_corrections_applied": []
  },
  "dates": {
    "expiry_valid": true,
    "dob_plausible": true,
    "issues": []
  },
  "blacklist": {
    "blacklisted": false,
    "reason": null
  },
  "overall_valid": true,
  "issues": []
}
```

---

### 4. `POST /api/tamper-check/{file_id}`
Executes ELA compression analysis, EXIF metadata inspection, and Hugging Face ViT AI document forgery classification on the deskewed preprocessed image.

**Sample Response (`200 OK`)**:
```json
{
  "ela": {
    "ela_score": 9.2,
    "ela_image_path": "uploads\\ela\\8d45c2df_processed_ela.png",
    "ela_image_url": "/ela-images/8d45c2df_processed_ela.png"
  },
  "metadata": {
    "editing_software_detected": false,
    "software_name": null,
    "metadata_stripped": true
  },
  "ai_detection": {
    "label": "real",
    "confidence": 0.5343,
    "ai_generated_likelihood": 46.57
  },
  "tampering_likelihood": 46.57,
  "risk_level": "medium"
}
```

---

### 5. `POST /api/analyze/{file_id}`
Consolidates OCR extraction, validation, and tampering into a single aggregated dashboard payload with calculated risk scores and human-readable summary flags.

**Sample Response (`200 OK`)**:
```json
{
  "file_id": "8d45c2df-123f-4d90-8e91-3d570a51ce98",
  "document_type": "passport",
  "extracted_fields": { ... },
  "validation": { ... },
  "tampering": { ... },
  "overall_risk_score": 81.57,
  "overall_risk_level": "high",
  "summary_flags": [
    "MRZ checksum mismatch on field(s): date_of_birth_check",
    "Document is expired",
    "Tampering likelihood: medium (46.57)"
  ]
}
```

---

## 🗺️ Next Steps

* [x] **Validation & Checksum Module**: Positional MRZ checksum validation, date expiration/plausibility checks, SQLite blacklist screening, and scoped OCR auto-correction.
* [x] **Tampering & Forgery Detection**: Error Level Analysis (ELA), EXIF metadata inspection, and Hugging Face ViT Document Forgery classifier.
* [x] **Document Preprocessing**: OpenCV perspective warping and deskewing for camera uploads.
* [x] **Aggregated Risk API**: Single-call `/api/analyze/{file_id}` endpoint.
* [ ] **Face Matching Module**: Cross-verifying facial biometrics against document photos.
* [ ] **Frontend Dashboard**: Interactive web client built with Next.js & Tailwind CSS.
