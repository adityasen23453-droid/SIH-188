import os
import uuid
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from modules.ocr import run_ocr
from modules.validation import run_validation
from modules.tampering import run_tampering_detection
from modules.preprocessing import detect_and_correct_document

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
UPLOAD_ELA_DIR = os.path.join(UPLOAD_DIR, "ela")
os.makedirs(UPLOAD_ELA_DIR, exist_ok=True)
app.mount("/ela-images", StaticFiles(directory=UPLOAD_ELA_DIR), name="ela_images")

DB_FILES = {}


def get_preprocessed_data(file_info: dict) -> tuple[str, dict]:
    if not file_info.get("preprocessed_result"):
        file_info["preprocessed_result"] = detect_and_correct_document(file_info["file_path"])
    prep_res = file_info["preprocessed_result"]
    proc_path = prep_res.get("processed_image_path") or file_info["file_path"]
    return proc_path, prep_res


@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(...)
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    filename = f"{file_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    DB_FILES[file_id] = {
        "file_path": file_path,
        "filename": filename,
        "document_type": document_type,
        "preprocessed_result": None,
        "ocr_result": None
    }

    return {
        "file_id": file_id,
        "document_type": document_type,
        "status": "uploaded"
    }


@app.post("/api/extract/{file_id}")
async def extract_document(file_id: str):
    file_info = DB_FILES.get(file_id)
    if not file_info:
        return JSONResponse(status_code=404, content={"error": "File not found"})

    _, prep_res = get_preprocessed_data(file_info)

    if not file_info.get("ocr_result"):
        ocr_res = run_ocr(file_info["file_path"], file_info["document_type"])
        ocr_res["preprocessing"] = prep_res
        file_info["ocr_result"] = ocr_res

    return file_info["ocr_result"]


@app.post("/api/validate/{file_id}")
async def validate_document(file_id: str):
    file_info = DB_FILES.get(file_id)
    if not file_info:
        return JSONResponse(status_code=404, content={"error": "File not found"})

    _, prep_res = get_preprocessed_data(file_info)

    if not file_info.get("ocr_result"):
        ocr_res = run_ocr(file_info["file_path"], file_info["document_type"])
        ocr_res["preprocessing"] = prep_res
        file_info["ocr_result"] = ocr_res

    validation_result = run_validation(file_info["ocr_result"])
    if "preprocessing" not in validation_result:
        validation_result["preprocessing"] = prep_res
    return validation_result


@app.post("/api/tamper-check/{file_id}")
async def tamper_check_document(file_id: str):
    file_info = DB_FILES.get(file_id)
    if not file_info:
        return JSONResponse(status_code=404, content={"error": "File not found"})

    proc_path, prep_res = get_preprocessed_data(file_info)

    if not file_info.get("tampering_result"):
        tampering_res = run_tampering_detection(proc_path)
        tampering_res["preprocessing"] = prep_res
        file_info["tampering_result"] = tampering_res

    return file_info["tampering_result"]


@app.post("/api/analyze/{file_id}")
async def analyze_document(file_id: str):
    file_info = DB_FILES.get(file_id)
    if not file_info:
        return JSONResponse(status_code=404, content={"error": "File not found"})

    proc_path, prep_res = get_preprocessed_data(file_info)

    # 1. OCR Extraction (run on original raw image for MRZ accuracy)
    if not file_info.get("ocr_result"):
        ocr_res = run_ocr(file_info["file_path"], file_info["document_type"])
        ocr_res["preprocessing"] = prep_res
        file_info["ocr_result"] = ocr_res
    else:
        ocr_res = file_info["ocr_result"]

    # 2. Validation
    validation_res = run_validation(ocr_res)
    if "preprocessing" not in validation_res:
        validation_res["preprocessing"] = prep_res

    # 3. Tampering Detection (run on preprocessed deskewed image)
    if not file_info.get("tampering_result"):
        tampering_res = run_tampering_detection(proc_path)
        tampering_res["preprocessing"] = prep_res
        file_info["tampering_result"] = tampering_res
    else:
        tampering_res = file_info["tampering_result"]

    # 4. Calculate Risk Score & Summary Flags
    base_score = float(tampering_res.get("tampering_likelihood", 0.0))
    penalties = 0.0
    summary_flags = []

    checksum_info = validation_res.get("checksum", {})
    if checksum_info.get("overall_checksum_valid") is False:
        penalties += 20.0
        failed_fields = checksum_info.get("failed_fields", [])
        if failed_fields:
            summary_flags.append(f"MRZ checksum mismatch on field(s): {', '.join(failed_fields)}")
        else:
            summary_flags.append("MRZ checksum mismatch")

    dates_info = validation_res.get("dates", {})
    if dates_info.get("expiry_valid") is False:
        penalties += 15.0
        date_issues = [issue for issue in dates_info.get("issues", []) if "expired" in issue.lower()]
        if date_issues:
            summary_flags.append(date_issues[0])
        else:
            summary_flags.append("Document is expired")

    blacklist_info = validation_res.get("blacklist", {})
    if blacklist_info.get("blacklisted") is True:
        penalties += 30.0
        reason = blacklist_info.get("reason")
        summary_flags.append(f"Passport blacklisted: {reason}" if reason else "Passport is blacklisted")

    tamper_likelihood = float(tampering_res.get("tampering_likelihood", 0.0))
    tamper_level = tampering_res.get("risk_level", "low")
    if tamper_likelihood >= 30.0 or tamper_level in ["medium", "high"]:
        summary_flags.append(f"Tampering likelihood: {tamper_level} ({tamper_likelihood:.2f})")

    overall_score = max(0.0, min(100.0, base_score + penalties))
    overall_score = round(overall_score, 2)

    if overall_score < 30.0:
        overall_level = "low"
    elif overall_score <= 60.0:
        overall_level = "medium"
    else:
        overall_level = "high"

    if not summary_flags:
        summary_flags = ["No issues detected."]

    extracted_fields = ocr_res.get("fields") or {}

    return {
        "file_id": file_id,
        "document_type": file_info["document_type"],
        "extracted_fields": extracted_fields,
        "validation": validation_res,
        "tampering": tampering_res,
        "overall_risk_score": overall_score,
        "overall_risk_level": overall_level,
        "summary_flags": summary_flags
    }




