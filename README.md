# AI-Based Fake Identity & Document Screening System (SIH Prototype)

An automated AI-driven document screening and identity verification platform designed to detect fraudulent passports, visas, and identity cards.

---

## 📌 Problem Statement
* **ID / Problem Statement**: PS 26188
* **Organization / Ministry**: Ministry of Home Affairs (MHA)
* **Objective**: Develop an AI-based system to screen documents (passports, visas, national IDs) for identity fraud, forgery, and data mismatches.

---

## 🚀 Current Status

The core backend pipeline, OCR extraction engine, and document validation module are implemented:

* **FastAPI Backend Server**: RESTful API endpoints for uploading, extracting, and validating documents.
* **Passport MRZ Extraction Engine**: High-accuracy Machine Readable Zone (MRZ) parser powered by `passporteye` (extracting name, passport number, nationality, date of birth, expiry date, gender, check digit validation score, and MRZ line 2).
* **Generic OCR Fallback Engine**: Unstructured text and field extractor powered by `PaddleOCR` and `pytesseract` for visas, residence permits, and non-MRZ identity documents.
* **Dual-Pipeline Execution**: Automatically attempts high-precision MRZ extraction first for passport documents; seamlessly falls back to generic OCR parsing if MRZ is absent or invalid.
* **Document Validation Engine (`modules/validation.py`)**:
  * **MRZ Checksum Verification**: Calculates 7-3-1 modulo 10 check digits over standard TD3 passport MRZ lines.
  * **Date Plausibility & Expiry Verification**: Verifies document expiration and evaluates DOB plausibility and issue date ordering.
  * **Blacklist Database Screening**: Queries local SQLite database (`data/blacklist.db`) seeded with blacklisted documents.
* **OCR Caching System**: Caches OCR extraction results per `file_id` in `DB_FILES` to eliminate redundant OCR operations during validation calls.

---

## 🛠️ Tech Stack

* **Backend Framework**: Python 3.10+, FastAPI, Uvicorn
* **Database**: SQLite3 (`data/blacklist.db`)
* **OCR Engines**: `PaddleOCR` (with `paddlepaddle`), `PassportEye`, `PyTesseract`
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
Uploads a document (JPEG/PNG/PDF) to the backend storage and assigns a tracking UUID.

**Request Body (`multipart/form-data`)**:
* `file`: Image or document binary file
* `document_type`: Document classification string (e.g., `passport`, `visa`, `id_card`)

**Sample Response (`200 OK`)**:
```json
{
  "file_id": "8e78c8fc-c009-4936-a654-f688187b4de2",
  "document_type": "passport",
  "status": "uploaded"
}
```

---

### 2. `POST /api/extract/{file_id}`
Triggers document extraction on the uploaded file, caches the result, and returns structured metadata.

**Sample Response - Passport (MRZ Extraction)**:
```json
{
  "document_type": "passport",
  "method_used": "mrz",
  "fields": {
    "name": "AKSHAY SHARMA",
    "passport_number": "A1234567",
    "nationality": "IND",
    "date_of_birth": "950101",
    "date_of_expiry": "350101",
    "gender": "M",
    "mrz_valid_score": 100,
    "mrz_line2": "A1234567<8IND9501015M3501019<<<<<<<<<<<<<<00"
  },
  "raw_text": null
}
```

---

### 3. `POST /api/validate/{file_id}`
Runs document validation logic using cached OCR results (or triggering OCR if not extracted yet).

**Sample Response (`200 OK`)**:
```json
{
  "checksum": {
    "checksum_valid": true,
    "details": "MRZ checksums valid"
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

## 🗺️ Next Steps

* [x] **Validation & Checksum Module**: Logical verification of DOB/expiry dates, MRZ checksum validation rules, and SQLite blacklist screening.
* [ ] **Tampering & Forgery Detection**: Error Level Analysis (ELA) and copy-move forgery detection algorithms.
* [ ] **Face Matching Module**: Cross-verifying facial biometrics against document photos.
* [ ] **Frontend Dashboard**: Interactive web client built with Next.js & Tailwind CSS.
