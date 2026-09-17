import os
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import sys
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from core.config import get_settings
from core.auth import get_current_officer, OfficerSession, SovereignRole
from modules.ocr import run_ocr
from modules.validation import run_validation
from modules.tampering import run_tampering_detection
from modules.preprocessing import detect_and_correct_document, create_document_context
from modules.timing import StageTimer
from modules.biometrics import verify_face_1to1_and_1toN
from modules.blockchain import (
    commit_inspection_block,
    update_block_biometric_decision,
    record_officer_override,
    verify_chain_integrity,
    get_recent_blocks,
    get_latest_block
)
from modules.ledger_adapter import get_audit_ledger

settings = get_settings()

app = FastAPI(title="SIH 26188 Border Document Screening API")

# Configure CORS using strict allowlist from centralized settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Adds standard security headers to all HTTP responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


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


@app.get("/api/auth/me")
def get_active_officer_session(officer: OfficerSession = Depends(get_current_officer)):
    """Returns active sovereign border checkpoint officer profile and permissions."""
    return officer.to_dict()


@app.get("/api/auth/roles")
def get_available_sovereign_roles():
    """Returns available sovereign operational roles for UI role-switcher."""
    return [{"role": r.value, "description": r.name} for r in SovereignRole]


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
    try:
        content = await file.read()
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Failed to read upload payload: {str(e)}"})

    # Phase 6: Validate file size and authentic magic-byte signature
    from modules.lifecycle import validate_file_content
    is_valid, safe_ext, err_msg, status_code = validate_file_content(content, file.filename)
    if not is_valid:
        return JSONResponse(status_code=status_code, content={"error": err_msg})

    file_id = str(uuid.uuid4())
    filename = f"{file_id}{safe_ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    try:
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
async def analyze_document(
    file_id: str,
    background_tasks: BackgroundTasks,
    officer: OfficerSession = Depends(get_current_officer)
):
    timer = StageTimer(document_id=file_id[:8] if file_id else None)
    file_info = DB_FILES.get(file_id)
    if not file_info:
        return JSONResponse(status_code=404, content={"error": "File not found"})

    # Phase 3: Shared In-Memory Preprocessing (decode once, resize once, deskew once)
    timer.start_stage("PREPROCESS")
    ctx = create_document_context(file_info["file_path"], max_dim=1200)
    timer.end_stage("PREPROCESS")

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

    # Phase 5: Multi-Core Parallel Execution (reusing in-memory clahe_bgr matrix)
    timer.start_stage("OCR_&_TAMPERING")
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=2) as pool:
        ocr_task = loop.run_in_executor(
            pool, run_ocr, proc_path, file_info["document_type"], face_info, file_info["file_path"], ctx.document_quad, file_id, ctx.clahe_bgr
        )
        tamp_task = loop.run_in_executor(pool, run_tampering_detection, proc_path)
        ocr_res, tampering_res = await asyncio.gather(ocr_task, tamp_task)
    timer.end_stage("OCR_&_TAMPERING")

    ocr_res["preprocessing"] = prep_res
    tampering_res["preprocessing"] = prep_res
    if ocr_res.get("document_type"):
        file_info["document_type"] = ocr_res["document_type"]
    file_info["ocr_result"] = ocr_res
    file_info["tampering_result"] = tampering_res

    # Phase 6: Validation (MRZ, Verhoeff, VIZ-to-MRZ, Registry)
    timer.start_stage("VALIDATION")
    validation_res = run_validation(
        ocr_res,
        stamp_forensics=tampering_res.get("stamp_forensics"),
        image_path=file_info.get("file_path")
    )
    timer.end_stage("VALIDATION")
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
        next_index, now_iso, ctx.doc_hash, overall_score, decision, officer.officer_id, prev_hash
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
        "officer_id": officer.officer_id,
        "previous_hash": prev_hash,
        "block_hash": block_hash
    }
    background_tasks.add_task(
        get_audit_ledger().commit_inspection_block,
        file_path=file_info["file_path"],
        file_id=file_id,
        document_type=file_info["document_type"],
        risk_score=overall_score,
        risk_level=overall_level,
        biometric_status="PENDING",
        officer_id=officer.officer_id
    )

    timer.print_summary(
        fast_path=(ocr_res.get("method_used") != "generic_ocr_fallback"),
        recovery_used=ocr_res.get("method_used", "none")
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
        "detected_regions": ocr_res.get("detected_regions", []),
        "pipeline_timings": timer.to_dict()
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

    # Validate live capture signature and dimensions
    from modules.lifecycle import validate_file_content
    is_valid_live, _, live_err, live_code = validate_file_content(live_bytes, "live_capture.jpg")
    if not is_valid_live:
        return JSONResponse(status_code=live_code, content={"error": f"Invalid live face capture: {live_err}"})

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

    # 5. Update Audit Ledger with biometric audit verdict
    updated_block = get_audit_ledger().update_biometric_decision(
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
    """Fetches recent immutable blocks from the cryptographically chained audit ledger."""
    blocks = get_audit_ledger().get_recent_blocks(limit=limit)
    return {
        "total_returned": len(blocks),
        "blocks": blocks
    }


@app.get("/api/ledger/verify")
async def verify_ledger():
    """Cryptographically verifies continuous SHA-256 chain and Ed25519 signatures from Genesis to tip."""
    audit_report = get_audit_ledger().verify_integrity()
    return audit_report


@app.get("/api/ledger/info")
async def get_ledger_adapter_info():
    """Returns active sovereign audit ledger adapter designation, anchor status, and cryptographic parameters."""
    return get_audit_ledger().get_adapter_info()


@app.post("/api/ledger/override")
async def officer_override_endpoint(
    file_id: str = Form(...),
    decision: str = Form(...),
    reason: str = Form(...),
    officer: OfficerSession = Depends(get_current_officer)
):
    """
    Appends an immutable OFFICER_OVERRIDE_EVENT to the audit ledger.
    Requires 'decision:override' sovereign permission (Supervisor / Investigator).
    Preserves original screening decision in immutable historical block.
    """
    if not officer.can_override_decision():
        return JSONResponse(
            status_code=403,
            content={"error": f"Role '{officer.role.value}' is not authorized to override screening decisions."}
        )

    receipt = get_audit_ledger().record_officer_override(
        file_id=file_id,
        officer_id=officer.officer_id,
        override_decision=decision.strip().upper(),
        reason=reason.strip()
    )
    if not receipt:
        return JSONResponse(status_code=404, content={"error": "Document session not found in ledger."})

    return {
        "status": "override_recorded",
        "blockchain_receipt": receipt
    }


@app.get("/api/ledger/anchor-status/{file_id}")
async def get_anchor_status_endpoint(file_id: str):
    """Returns sovereign anchor status (LOCAL_ANCHORED, ANCHOR_PENDING, NBF_ANCHORED) for a session."""
    ledger = get_audit_ledger()
    if hasattr(ledger, "get_anchor_status"):
        return ledger.get_anchor_status(file_id)
    import sqlite3
    from modules.blockchain import DB_PATH
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT block_index, file_id, anchor_status, canonical_hash, signature FROM blockchain_ledger WHERE file_id = ? ORDER BY block_index DESC LIMIT 1",
            (file_id,)
        )
        row = cur.fetchone()
        if row:
            return dict(row)
    return JSONResponse(status_code=404, content={"error": "Session not found in audit ledger."})


@app.post("/api/ledger/sync")
async def sync_ledger_anchors_endpoint(officer: OfficerSession = Depends(get_current_officer)):
    """Flushes spooled ANCHOR_PENDING events to permissioned ledger when connectivity is restored."""
    ledger = get_audit_ledger()
    if hasattr(ledger, "flush_pending_anchors"):
        return ledger.flush_pending_anchors()
    return {"status": "LOCAL_ONLY", "message": "Active adapter operates strictly in local demo mode."}


@app.get("/api/ledger/nbf-specification")
async def get_nbf_specification_endpoint():
    """
    Returns architectural specification for integration with
    India's National Blockchain Framework (NBF / Vishvasya Stack - MeitY).
    Includes cryptographic parameters, zero-PII guarantees, and onboarding requirements.
    """
    ledger = get_audit_ledger()
    if hasattr(ledger, "get_nbf_specification"):
        return ledger.get_nbf_specification()
    from modules.ledger_adapter import NBFPermissionedLedgerAdapter
    return NBFPermissionedLedgerAdapter().get_nbf_specification()





