import os
import sys
import json
import time

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from modules.timing import StageTimer
from modules.preprocessing import create_document_context
from modules.ocr import run_ocr
from modules.tampering import run_tampering_detection
from modules.validation import run_validation

def test_user_image():
    img_path = r"C:\Users\adity\.gemini\antigravity\brain\ce50fe27-a044-4610-83cb-c0ce0c206a8d\.user_uploaded\media_1789442827174.webp"
    if not os.path.exists(img_path):
        print(f"Error: Image not found at {img_path}")
        return

    timer = StageTimer("USER_VISA_END_TO_END")
    print("\n=======================================================")
    print(" EXECUTING END-TO-END VERIFICATION ON USER UPLOADED VISA")
    print("=======================================================")

    # 1. Preprocessing
    timer.start_stage("PREPROCESS")
    ctx = create_document_context(img_path, max_dim=1200)
    timer.end_stage("PREPROCESS")
    print(f"1. Preprocessing Note : {ctx.note}")
    print(f"   Face Detected      : {ctx.face_roi is not None}")
    print(f"   Processed Path     : {ctx.processed_image_path}")

    face_info = {
        "face_detected": ctx.face_roi is not None,
        "face_image_path": ctx.face_image_path,
        "face_image_url": ctx.face_image_url,
        "bounding_box": ctx.face_bbox
    }

    # 2. OCR
    timer.start_stage("PADDLE_OCR")
    ocr_res = run_ocr(
        ctx.processed_image_path,
        "auto",
        face_info,
        img_path,
        ctx.document_quad,
        "user_visa_test",
        image_bgr=ctx.clahe_bgr
    )
    timer.end_stage("PADDLE_OCR")
    print(f"2. Detected Doc Type  : {ocr_res.get('document_type')}")
    print(f"   OCR Method Used    : {ocr_res.get('method_used')}")
    print(f"   OCR Confidence     : {ocr_res.get('confidence')}")

    # 3. Tampering
    timer.start_stage("TAMPERING")
    tamp_res = run_tampering_detection(ctx.processed_image_path)
    timer.end_stage("TAMPERING")
    print(f"3. Tampering Score    : {tamp_res.get('tampering_likelihood')}% (Risk: {tamp_res.get('risk_level')})")

    # 4. Validation
    timer.start_stage("VALIDATION")
    val_res = run_validation(ocr_res, stamp_forensics=tamp_res.get("stamp_forensics"), image_path=img_path)
    timer.end_stage("VALIDATION")
    print(f"4. Date Expiry Status : {val_res.get('dates', {}).get('expiry_status')}")

    # Print centralized timing breakdown
    timer.print_summary(fast_path=True, recovery_used=ocr_res.get("method_used", "none"))

    print("\n--- EXTRACTED IDENTITY FIELDS ---")
    fields = ocr_res.get("fields", {})
    for k, v in fields.items():
        if v:
            print(f"  {k:<20} : {v}")

    print("\n--- VALIDATION ANALYSIS ---")
    dates_info = val_res.get("dates", {})
    print(f"  Expiry Status        : {dates_info.get('expiry_status')}")
    print(f"  Days Remaining       : {dates_info.get('days_to_expiry')}")
    print(f"  Date Issues Found    : {dates_info.get('issues')}")
    print(f"  Overall Valid        : {val_res.get('overall_valid')}")
    print("=======================================================\n")

if __name__ == "__main__":
    test_user_image()

