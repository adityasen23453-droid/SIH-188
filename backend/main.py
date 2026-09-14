import os
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from modules.ocr import run_ocr
from modules.validation import run_validation
from modules.tampering import run_tampering_detection
from modules.preprocessing import detect_and_correct_document, create_document_context
from modules.biometrics import verify_face_1to1_and_1toN
from modules.blockchain import (
    commit_inspection_block,
    update_block_biometric_decision,
    verify_chain_integrity,
    get_recent_blocks,
    get_latest_block
)

app = FastAPI(title="SIH 26188 Border Document Screening API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def prewarm_models():
    """Pre-warms PaddleOCR and ViT Forgery Detector in background thread at server startup so uploads run with zero cold-start latency."""
    import threading

    def _warmup():
        try:
            import numpy as np
            from modules.ocr import get_ocr_engine
            engine = get_ocr_engine()
            dummy = np.zeros((64, 192, 3), dtype=np.uint8)
            engine.ocr(dummy)
            print("[INFO] PaddleOCR models pre-warmed into RAM successfully.")
        except Exception as e:
            print(f"[WARN] OCR prewarm notice: {e}")

        try:
            from modules.tampering import get_forgery_model_and_processor
            get_forgery_model_and_processor()
            print("[INFO] ViT Forgery Detector pre-warmed into RAM successfully.")
        except Exception as e:
            print(f"[WARN] ViT prewarm notice: {e}")

    threading.Thread(target=_warmup, daemon=True).start()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
UPLOAD_ELA_DIR = os.path.join(UPLOAD_DIR, "ela")
UPLOAD_FACES_DIR = os.path.join(UPLOAD_DIR, "faces")
UPLOAD_SCANNED_DIR = os.path.join(UPLOAD_DIR, "scanned")
os.makedirs(UPLOAD_ELA_DIR, exist_ok=True)
os.makedirs(UPLOAD_FACES_DIR, exist_ok=True)
os.makedirs(UPLOAD_SCANNED_DIR, exist_ok=True)

app.mount("/ela-images", StaticFiles(directory=UPLOAD_ELA_DIR), name="ela_images")
app.mount("/doc-faces", StaticFiles(directory=UPLOAD_FACES_DIR), name="doc_faces")
app.mount("/scanned-images", StaticFiles(directory=UPLOAD_SCANNED_DIR), name="scanned_images")

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
    document_type: str = Form("auto")
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
        "ocr_result": None,
        "tampering_result": None
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

    proc_path, prep_res = get_preprocessed_data(file_info)

    if not file_info.get("ocr_result"):
        ocr_res = run_ocr(proc_path, file_info["document_type"], fallback_image_path=file_info["file_path"], file_id=file_id)
        ocr_res["preprocessing"] = prep_res
        file_info["ocr_result"] = ocr_res

    return file_info["ocr_result"]


@app.post("/api/validate/{file_id}")
async def validate_document(file_id: str):
    file_info = DB_FILES.get(file_id)
    if not file_info:
        return JSONResponse(status_code=404, content={"error": "File not found"})

    proc_path, prep_res = get_preprocessed_data(file_info)

    if not file_info.get("ocr_result"):
        ocr_res = run_ocr(proc_path, file_info["document_type"], fallback_image_path=file_info["file_path"], file_id=file_id)
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
async def analyze_document(file_id: str, background_tasks: BackgroundTasks):
    file_info = DB_FILES.get(file_id)
    if not file_info:
        return JSONResponse(status_code=404, content={"error": "File not found"})

    # Phase 3: Shared In-Memory Preprocessing (decode once, resize once, deskew once)
    ctx = create_document_context(file_info["file_path"], max_dim=1200)
    proc_path = ctx.processed_image_path
    prep_res = {
        "processed_image_path": ctx.processed_image_path,
        "correction_applied": ctx.correction_applied,
        "note": ctx.note
    }
    face_info = {
        "face_detected": ctx.face_roi is not None,
        "face_image_path": ctx.face_image_path,
        "face_image_url": ctx.face_image_url,
        "bounding_box": ctx.face_bbox
    }

    # Phase 5: Multi-Core Parallel Execution (OCR and Tampering in ThreadPool)
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=2) as pool:
        ocr_task = loop.run_in_executor(pool, run_ocr, proc_path, file_info["document_type"], face_info, file_info["file_path"], ctx.document_quad, file_id)
        tamp_task = loop.run_in_executor(pool, run_tampering_detection, proc_path)
        ocr_res, tampering_res = await asyncio.gather(ocr_task, tamp_task)

    ocr_res["preprocessing"] = prep_res
    tampering_res["preprocessing"] = prep_res
    if ocr_res.get("document_type"):
        file_info["document_type"] = ocr_res["document_type"]
    file_info["ocr_result"] = ocr_res
    file_info["tampering_result"] = tampering_res

    # Phase 6: Validation (MRZ, Verhoeff, VIZ-to-MRZ, Registry)
    validation_res = run_validation(
        ocr_res,
        stamp_forensics=tampering_res.get("stamp_forensics"),
        image_path=file_info.get("file_path")
    )
    validation_res["preprocessing"] = prep_res

    # Phase 8: Multi-Signal Risk Orchestration Engine
    base_score = float(tampering_res.get("tampering_likelihood", 0.0))
    penalties = 0.0
    summary_flags = []

    # A. Checksum penalty
    checksum_info = validation_res.get("checksum", {})
    if checksum_info.get("overall_checksum_valid") is False:
        penalties += 20.0
        failed_fields = checksum_info.get("failed_fields", [])
        if failed_fields:
            summary_flags.append(f"MRZ checksum mismatch on field(s): {', '.join(failed_fields)}")
        else:
            summary_flags.append("MRZ checksum mismatch")

    # B. National ID rules penalty (Aadhaar Verhoeff / Voter ID / DL)
    national_id_info = validation_res.get("national_id", {})
    if national_id_info.get("valid") is False:
        penalties += 25.0
        for issue in national_id_info.get("issues", []):
            summary_flags.append(f"National ID Error: {issue}")

    # C. VIZ-to-MRZ consistency check
    viz_info = validation_res.get("viz_consistency", {})
    if viz_info.get("consistent") is False:
        penalties += 20.0
        for mismatch in viz_info.get("mismatches", []):
            summary_flags.append(f"Consistency Alert: {mismatch}")

    # D. Expiry penalty
    dates_info = validation_res.get("dates", {})
    if dates_info.get("expiry_status") == "EXPIRED":
        penalties += 20.0
        date_issues = [issue for issue in dates_info.get("issues", []) if "expired" in issue.lower()]
        if date_issues:
            summary_flags.append(date_issues[0])
        else:
            summary_flags.append("Document is expired")
    elif dates_info.get("expiry_status") == "UNPARSEABLE":
        penalties += 10.0
        summary_flags.append("Document expiry date is unparseable")

    # E. Registry & Blacklist penalty
    registry_info = validation_res.get("registry", {})
    if registry_info.get("blacklisted") is True or registry_info.get("status") in ["REVOKED", "STOLEN"]:
        penalties += 35.0
        reason = registry_info.get("reason")
        summary_flags.append(f"Registry alert: {reason}" if reason else "Document is blacklisted/revoked")

    # F. Stamp tampering penalty
    stamp_info = tampering_res.get("stamp_forensics", {})
    if stamp_info.get("suspicious_stamp_splicing"):
        penalties += 15.0
        summary_flags.append("Suspicious border stamp splicing detected")

    # G. Tampering likelihood alert
    tamper_likelihood = float(tampering_res.get("tampering_likelihood", 0.0))
    tamper_level = tampering_res.get("risk_level", "low")
    if tamper_likelihood >= 30.0 or tamper_level in ["medium", "high"]:
        summary_flags.append(f"Tampering likelihood: {tamper_level} ({tamper_likelihood:.2f})")

    # H. Critical Unread / Missing Identity Data Security Policy
    extracted_fields = ocr_res.get("fields") or {}
    has_critical_identity = bool(
        extracted_fields.get("name")
        or extracted_fields.get("passport_number")
        or extracted_fields.get("id_number")
        or extracted_fields.get("aadhaar_number")
        or extracted_fields.get("voter_id")
        or extracted_fields.get("dl_number")
    )
    ocr_confidence = str(ocr_res.get("confidence", "")).upper()

    if not has_critical_identity or ocr_confidence == "LOW":
        penalties += 45.0
        summary_flags.append("CRITICAL: Document identity data unreadable or unverified. Secondary physical inspection required.")

    # Strict Security Circuit Breaker: Collect any failed check
    has_any_failure = (
        checksum_info.get("overall_checksum_valid") is False
        or national_id_info.get("valid") is False
        or viz_info.get("consistent") is False
        or dates_info.get("expiry_status") in ["EXPIRED", "UNPARSEABLE"]
        or dates_info.get("dob_plausible") is False
        or registry_info.get("blacklisted") is True
        or registry_info.get("status") in ["REVOKED", "STOLEN"]
        or stamp_info.get("suspicious_stamp_splicing") is True
        or tamper_likelihood >= 30.0
        or not has_critical_identity
        or ocr_confidence == "LOW"
    )

    overall_score = max(0.0, min(100.0, base_score + penalties))
    overall_score = round(overall_score, 2)

    if has_any_failure:
        # Strict policy: If ANY check fails or identity is unverified, NEVER CLEAR
        if tamper_likelihood >= 60.0 or checksum_info.get("overall_checksum_valid") is False or registry_info.get("blacklisted") is True:
            overall_level = "high"
            decision = "REJECTED_IMPOSTOR"
        else:
            overall_level = "medium" if overall_score <= 60.0 else "high"
            decision = "FLAGGED_FOR_INSPECTION"
    else:
        overall_level = "low"
        decision = "CLEARED"

    if not summary_flags:
        summary_flags = ["No issues detected. Document passed all border verification checks."]

    extracted_fields = ocr_res.get("fields") or {}

    # Phase 9: Asynchronous Blockchain Ledger Mining
    latest = get_latest_block()
    next_index = latest.get("block_index", 0) + 1
    prev_hash = latest.get("block_hash", "0" * 64)
    from modules.blockchain import calculate_block_hash
    from datetime import datetime
    now_iso = datetime.utcnow().isoformat() + "Z"
    block_hash = calculate_block_hash(
        next_index, now_iso, ctx.doc_hash, overall_score, decision, "SSB-OFFICER-7429", prev_hash
    )
    blockchain_receipt = {
        "block_index": next_index,
        "timestamp": now_iso,
        "doc_hash": ctx.doc_hash,
        "file_id": file_id,
        "document_type": file_info["document_type"],
        "risk_score": overall_score,
        "risk_level": overall_level.upper(),
        "biometric_status": "PENDING",
        "decision": decision,
        "officer_id": "SSB-OFFICER-7429",
        "previous_hash": prev_hash,
        "block_hash": block_hash
    }
    background_tasks.add_task(
        commit_inspection_block,
        file_path=file_info["file_path"],
        file_id=file_id,
        document_type=file_info["document_type"],
        risk_score=overall_score,
        risk_level=overall_level,
        biometric_status="PENDING",
        officer_id="SSB-OFFICER-7429"
    )

    return {
        "file_id": file_id,
        "document_type": file_info["document_type"],
        "extracted_fields": extracted_fields,
        "viz_fields": ocr_res.get("viz_fields"),
        "portrait_face": ocr_res.get("portrait_face"),
        "validation": validation_res,
        "tampering": tampering_res,
        "overall_risk_score": overall_score,
        "overall_risk_level": overall_level,
        "decision": decision,
        "summary_flags": summary_flags,
        "blockchain_receipt": blockchain_receipt,
        "scanned_image_url": ocr_res.get("scanned_image_url"),
        "detected_regions": ocr_res.get("detected_regions", [])
    }


@app.post("/api/face-verify/{file_id}")
async def face_verify_endpoint(
    file_id: str,
    file: UploadFile = File(None),
    live_image_base64: str = Form(None)
):
    """
    Biometric Verification Engine (1:1 Match & 1:N Alias Search):
    Compares the document's extracted portrait against the live checkpoint webcam capture.
    """
    file_info = DB_FILES.get(file_id)
    if not file_info:
        return JSONResponse(status_code=404, content={"error": "Document session not found"})

    # 1. Locate document face
    doc_face_filename = f"{file_id}_face.jpg"
    doc_face_path = os.path.join(UPLOAD_FACES_DIR, doc_face_filename)
    if not os.path.exists(doc_face_path):
        # If not already cropped, try cropping from original document
        from modules.ocr import extract_document_face
        face_info = extract_document_face(file_info["file_path"], UPLOAD_FACES_DIR)
        if not face_info.get("face_detected"):
            return JSONResponse(
                status_code=400,
                content={"error": "No face detected on document portrait to compare against."}
            )

    # 2. Get live image bytes
    live_bytes = None
    if file:
        live_bytes = await file.read()
    elif live_image_base64:
        import base64
        data = live_image_base64
        if "," in data:
            data = data.split(",")[1]
        try:
            live_bytes = base64.b64decode(data)
        except Exception as e:
            return JSONResponse(status_code=400, content={"error": f"Invalid base64 image: {str(e)}"})
    else:
        return JSONResponse(status_code=400, content={"error": "No live webcam image provided."})

    # 3. Retrieve traveler metadata for 1:N alias cross-referencing
    traveler_name = ""
    doc_number = ""
    doc_type = file_info.get("document_type", "PASSPORT")
    nationality = ""

    ocr_res = file_info.get("ocr_result") or {}
    fields = ocr_res.get("fields") or {}
    traveler_name = fields.get("names", "") or fields.get("name", "")
    doc_number = fields.get("number", "") or fields.get("passport_number", "") or fields.get("aadhaar_number", "")
    nationality = fields.get("nationality", "")

    # 4. Perform 1:1 Cosine match and 1:N Alias search
    verification_result = verify_face_1to1_and_1toN(
        doc_face_path=doc_face_path,
        live_face_path_or_bytes=live_bytes,
        traveler_name=traveler_name,
        doc_number=doc_number,
        doc_type=doc_type,
        nationality=nationality
    )

    # 5. Update Blockchain Block with biometric audit verdict
    updated_block = update_block_biometric_decision(
        file_id=file_id,
        biometric_status=verification_result["status"]
    )

    return {
        "file_id": file_id,
        "verification": verification_result,
        "blockchain_receipt": updated_block
    }


@app.get("/api/ledger/blocks")
async def get_ledger_blocks(limit: int = 30):
    """Fetches recent immutable blocks from the SHA-256 Merkle blockchain ledger."""
    blocks = get_recent_blocks(limit=limit)
    return {
        "total_returned": len(blocks),
        "blocks": blocks
    }


@app.get("/api/ledger/verify")
async def verify_ledger():
    """Cryptographically verifies continuous SHA-256 chain integrity from Genesis to tip."""
    audit_report = verify_chain_integrity()
    return audit_report

