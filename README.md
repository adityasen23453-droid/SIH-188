# AI-Based Fake Identity & Document Screening System (SIH PS 26188)

An automated AI-driven document screening and identity verification platform designed for the **Ministry of Home Affairs (MHA)** under **Smart India Hackathon (SIH)**. The system detects fraudulent passports, visas, and national identity cards using ICAO Doc 9303 checksum verification, Error Level Analysis (ELA), EXIF metadata inspection, and a pretrained Vision Transformer (ViT) deepfake forgery model.

---

## 📌 Problem Statement Details
* **ID / Problem Statement**: PS 26188
* **Organization / Ministry**: Ministry of Home Affairs (MHA)
* **Objective**: Develop an AI-based system to screen documents (passports, visas, national IDs) for identity fraud, forgery, structural tampering, and data mismatches.

---

## 🚀 Key Features & System Architecture

The project consists of a high-performance **FastAPI Python Backend** and a modern **Next.js 16 (App Router) TypeScript Frontend**:

### 1. Next.js 16 Frontend (`frontend/`)
* **SIH Executive UI Theme**: Clean, professional light theme palette with dark navy header (`bg-slate-900`), glowing status badges, dot grid pattern canvas, and responsive glassmorphism cards.
* **Framer Motion 60fps Animations**: Smooth page transitions, circular SVG score gauges, staggered list cascades, and spring tab switchers.
* **Document Inspection Viewer**: Side-by-side toggle comparing original binary upload scans with generated ELA compression heatmaps.
* **Extracted Fields & Confidence Ratings**: Visually highlights low-confidence text extractions and unverified gender reads (`M`/`F`/`<`).
* **MRZ 7-3-1 Checksum Table**: Interactive breakdown of passport check digits with pass/fail/skipped indicators and 1-click MRZ raw line copy.
* **Multi-Signal Tampering Dashboard**: Real-time visual progress bars for Error Level Analysis, AI ViT Deepfake model predictions, and EXIF editing software detection.

### 2. FastAPI Python Backend (`backend/`)
* **Pre-OCR Document Preprocessing (`modules/preprocessing.py`)**: OpenCV perspective transform matrix generation, contour border approximation, and CLAHE contrast enhancement for angled phone camera uploads.
* **Passport MRZ & OCR Extraction (`modules/ocr.py`)**: High-accuracy Machine Readable Zone (MRZ) parser powered by `PassportEye` with positional confidence scoring (`name_confidence`, `passport_number_confidence`, `nationality_confidence`).
* **Scoped Positional OCR Auto-Corrector (`modules/validation.py`)**: Applies ICAO 9303 letter-to-digit auto-correction strictly to numeric positions (DOB 13–19, Expiry 21–27, check digits 9, 19, 27, 43): `B`→`8`, `O`/`Q`/`D`→`0`, `I`/`L`→`1`, `S`→`5`, `Z`→`2`, `A`→`4`.
* **Multi-Signal Forgery Detection Engine (`modules/tampering.py`)**:
  * **Error Level Analysis (ELA)**: JPEG quality 90 compression variance calculation and visual heatmap generation.
  * **Pretrained ViT AI Forgery Detector**: Runs Hugging Face Vision Transformer `"zodumair/document-forgery-detector"` over alpha-blended ELA composite maps.
  * **EXIF Metadata Inspection**: Scans EXIF tags for Photoshop, GIMP, or Canva signatures.
* **Aggregated Dashboard Risk Endpoint (`POST /api/analyze/{file_id}`)**: Consolidates OCR, validation, and tampering into a single payload with `overall_risk_score` (0-100 weighted formula), `overall_risk_level` (`low`, `medium`, `high`), and human-readable `summary_flags`.

---

## 📁 Repository Structure

```
SIH-188/
├── backend/
│   ├── data/
│   │   └── blacklist.db         # SQLite database of stolen/blacklisted document numbers
│   ├── modules/
│   │   ├── ocr.py               # PassportEye MRZ parser & OCR text extractor
│   │   ├── preprocessing.py     # OpenCV contour detection & top-down deskewing
│   │   ├── tampering.py         # ELA analysis, EXIF parser & Hugging Face ViT model
│   │   └── validation.py        # ICAO 7-3-1 check digit rules & date plausibility
│   ├── uploads/                 # Storage for uploaded files, preprocessed images, & ELA heatmaps
│   ├── main.py                  # FastAPI REST endpoints & CORS configuration
│   ├── requirements.txt         # Python dependency manifest
│   └── test_validation.py       # Unit test suite
├── frontend/
│   ├── app/
│   │   ├── globals.css          # Tailwind CSS v4 & light grid background styles
│   │   └── page.tsx             # Main SIH Document Screening App Page
│   ├── components/
│   │   ├── DocumentPreview.tsx  # Dual-mode image & ELA heatmap toggle inspector
│   │   ├── ExtractedFieldsTable.tsx # Field metadata grid with confidence badges
│   │   ├── RiskBanner.tsx       # Animated overall risk meter & summary flags
│   │   ├── TamperingAnalysis.tsx# Multi-signal ELA & AI ViT forgery breakdown
│   │   └── ValidationResults.tsx# MRZ checkdigit verification table & dates
│   ├── lib/
│   │   └── api.ts               # API fetch helper for FastAPI endpoints
│   ├── types/
│   │   └── index.ts             # TypeScript interfaces for API response shapes
│   └── package.json             # Next.js & Framer Motion dependency manifest
├── .gitignore
└── README.md                    # Main Project Documentation
```

---

## ⚙️ Installation & Local Setup

### Prerequisites
* **Python**: 3.10+
* **Node.js**: 18.x or 20.x+
* **Tesseract OCR System Binary (Windows)**:
  1. Install Tesseract OCR from [UB-Mannheim Wiki](https://github.com/UB-Mannheim/tesseract/wiki).
  2. Default path: `C:\Program Files\Tesseract-OCR\`. Add to system `PATH`.

---

### 1. Running the FastAPI Backend Server

```bash
# Navigate to backend folder
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Start FastAPI application
python -m uvicorn main:app --reload --port 8000
```
👉 Interactive API documentation (Swagger UI): `http://localhost:8000/docs`

---

### 2. Running the Next.js Frontend Client

```bash
# Navigate to frontend folder (in a separate terminal)
cd frontend

# Install Node dependencies
npm install

# Start Next.js development server
npm run dev
```
👉 Interactive SIH Screening App: `http://localhost:3000`

---

## 📡 API Endpoint Overview

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/upload` | `POST` | Uploads document binary file and returns a tracking `file_id`. |
| `/api/extract/{file_id}` | `POST` | Runs PassportEye MRZ parser on native raw file and returns fields with confidence flags. |
| `/api/validate/{file_id}` | `POST` | Performs field-level MRZ 7-3-1 check digit validation, date expiration checks, and blacklist screening. |
| `/api/tamper-check/{file_id}` | `POST` | Executes ELA analysis, EXIF metadata scanning, and ViT AI forgery classification on deskewed preprocessed image. |
| `/api/analyze/{file_id}` | `POST` | Aggregated dashboard endpoint returning combined risk scores, risk levels, and summary flags. |

---

## 🧪 Verification & Testing

To run the backend unit test suite:
```bash
cd backend
python -m unittest test_validation.py test_tampering.py test_preprocessing.py
```
To run the frontend production build verification:
```bash
cd frontend
npm run build
```
