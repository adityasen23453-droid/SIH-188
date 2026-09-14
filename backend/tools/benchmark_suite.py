import os
import sys
import time
import json
import random
import cv2
import numpy as np

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from modules.preprocessing import create_document_context
from modules.ocr import run_ocr
from modules.validation import run_validation, verhoeff_validate, _VERHOEFF_D, _VERHOEFF_P, calc_mrz_check_digit
from modules.tampering import run_tampering_detection

_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]

def generate_valid_verhoeff(base_11_str: str) -> str:
    c = 0
    rev = list(map(int, reversed(base_11_str)))
    for i, digit in enumerate(rev):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][digit]]
    check_digit = _VERHOEFF_INV[c]
    return f"{base_11_str}{check_digit}"


# =====================================================================
# DATASET GENERATOR (50+ GENUINE, 50+ MANIPULATED)
# =====================================================================

def generate_synthetic_dataset(output_dir: str, n_genuine: int = 52, n_tampered: int = 52) -> list[dict]:
    """
    Generates a rigorous benchmark dataset containing 50+ genuine and 50+ manipulated documents
    across multiple degradation levels and document types (Passport, Aadhaar, Voter ID, DL).
    """
    os.makedirs(output_dir, exist_ok=True)
    dataset = []

    # Helper: Create base document canvas
    def make_doc_canvas(doc_type: str, title: str, bg_color=(240, 245, 250)):
        canvas = np.full((700, 1000, 3), bg_color, dtype=np.uint8)
        # Guilloche border simulation
        cv2.rectangle(canvas, (20, 20), (980, 680), (180, 190, 200), 2)
        cv2.rectangle(canvas, (30, 30), (970, 670), (210, 220, 230), 1)
        # Header
        cv2.putText(canvas, title, (50, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 40, 80), 2)
        return canvas

    # Helper: Add synthetic portrait face
    def add_face_box(img, x=60, y=120, w=180, h=220, seed=42):
        np.random.seed(seed)
        face_img = np.full((h, w, 3), (200, 215, 230), dtype=np.uint8)
        # Simple face geometry
        cv2.ellipse(face_img, (w//2, h//2), (w//3, h//2 - 10), 0, 0, 360, (140, 160, 190), -1)
        cv2.circle(face_img, (w//2 - 25, h//2 - 20), 10, (50, 60, 80), -1) # left eye
        cv2.circle(face_img, (w//2 + 25, h//2 - 20), 10, (50, 60, 80), -1) # right eye
        cv2.line(face_img, (w//2, h//2), (w//2, h//2 + 25), (100, 120, 150), 3) # nose
        cv2.ellipse(face_img, (w//2, h//2 + 45), (25, 12), 0, 0, 180, (80, 90, 110), 3) # mouth
        img[y:y+h, x:x+w] = face_img
        return (x, y, w, h)

    # 1. Generate 52 Genuine Documents
    print(f"Generating {n_genuine} genuine documents across multiple types & degradations...")
    first_names = ["AARAV", "VIKRAM", "PRIYA", "ROHIT", "ANANYA", "DEEPAK", "SUNITA", "AMIT", "NEHA", "SANJAY"]
    last_names = ["SHARMA", "VERMA", "SINGH", "PATEL", "KUMAR", "GUPTA", "REDDY", "DESHMUKH", "MEHTA", "JOSHI"]

    for i in range(n_genuine):
        fname = random.choice(first_names)
        lname = random.choice(last_names)
        doc_type_idx = i % 4

        if doc_type_idx == 0:  # Genuine Passport
            canvas = make_doc_canvas("passport", "REPUBLIC OF INDIA - PASSPORT", (245, 248, 252))
            add_face_box(canvas, seed=i)
            pass_num = f"Z{1000000 + i}"
            cv2.putText(canvas, f"SURNAME: {lname}", (280, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 20, 30), 2)
            cv2.putText(canvas, f"GIVEN NAMES: {fname}", (280, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 20, 30), 2)
            cv2.putText(canvas, f"PASSPORT NO: {pass_num}", (280, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 20, 30), 2)
            cv2.putText(canvas, "NATIONALITY: IND", (280, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 20, 30), 2)
            cv2.putText(canvas, "DOB: 15/08/1992", (280, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 20, 30), 2)
            cv2.putText(canvas, "EXPIRY: 20/12/2032", (280, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 20, 30), 2)

            # Valid ICAO MRZ Line 1 & Line 2
            mrz_l1 = f"P<IND{lname}<<{fname}"
            mrz_l1 = (mrz_l1 + "<" * 44)[:44]

            p_slice = f"{pass_num}<"
            p_cd = str(calc_mrz_check_digit(p_slice))
            dob_str = "920815"
            dob_cd = str(calc_mrz_check_digit(dob_str))
            exp_str = "321220"
            exp_cd = str(calc_mrz_check_digit(exp_str))
            comp_body = f"{p_slice}{p_cd}IND{dob_str}{dob_cd}M{exp_str}{exp_cd}" + "<" * 14 + "0"
            comp_cd = str(calc_mrz_check_digit(comp_body))
            mrz_l2 = f"{comp_body}{comp_cd}"

            cv2.putText(canvas, mrz_l1, (50, 580), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            cv2.putText(canvas, mrz_l2, (50, 630), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            meta_type = "passport"

        elif doc_type_idx == 1:  # Genuine Aadhaar
            canvas = make_doc_canvas("aadhaar", "UNIQUE IDENTIFICATION AUTHORITY OF INDIA", (255, 255, 255))
            add_face_box(canvas, x=80, y=140, w=160, h=200, seed=i)
            # Generate valid Verhoeff Aadhaar UID
            base_11 = f"{20000000000 + i}"
            aadhaar_uid = generate_valid_verhoeff(base_11)
            formatted_uid = f"{aadhaar_uid[:4]} {aadhaar_uid[4:8]} {aadhaar_uid[8:12]}"
            cv2.putText(canvas, f"{fname} {lname}", (280, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
            cv2.putText(canvas, "DOB: 10/05/1988", (280, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (40, 40, 40), 2)
            cv2.putText(canvas, "GENDER: MALE", (280, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (40, 40, 40), 2)
            cv2.putText(canvas, formatted_uid, (280, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 20, 20), 3)
            meta_type = "aadhaar"

        elif doc_type_idx == 2:  # Genuine Voter ID (EPIC)
            canvas = make_doc_canvas("voter_id", "ELECTION COMMISSION OF INDIA - IDENTITY CARD", (250, 250, 245))
            add_face_box(canvas, seed=i)
            epic_num = f"ABC{1000000 + i}"
            cv2.putText(canvas, f"NAME: {fname} {lname}", (280, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 2)
            cv2.putText(canvas, f"EPIC NO: {epic_num}", (280, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 30, 100), 2)
            cv2.putText(canvas, "DOB: 22/01/1995", (280, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (40, 40, 40), 2)
            meta_type = "voter_id"

        else:  # Genuine Driving License
            canvas = make_doc_canvas("driving_license", "UNION OF INDIA - DRIVING LICENCE", (248, 252, 250))
            add_face_box(canvas, seed=i)
            dl_num = f"DL042021{1000000 + i}"
            cv2.putText(canvas, f"NAME: {fname} {lname}", (280, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 2)
            cv2.putText(canvas, f"DL NO: {dl_num}", (280, 215), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (10, 50, 20), 2)
            cv2.putText(canvas, "DOB: 12/04/1990", (280, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (40, 40, 40), 2)
            cv2.putText(canvas, "VALID TILL: 15/09/2035", (280, 305), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (40, 40, 40), 2)
            meta_type = "driving_license"

        # Apply realistic physical degradation
        deg_type = i % 3
        if deg_type == 1:
            canvas = cv2.GaussianBlur(canvas, (3, 3), 0.3)  # slight lens softness
        elif deg_type == 2:
            noise = np.random.normal(0, 2.0, canvas.shape).astype(np.int16)
            canvas = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)  # sensor noise

        img_path = os.path.join(output_dir, f"genuine_{i:03d}_{meta_type}.jpg")
        cv2.imwrite(img_path, canvas, [cv2.IMWRITE_JPEG_QUALITY, 95])
        dataset.append({
            "id": f"gen_{i}",
            "path": img_path,
            "document_type": meta_type,
            "is_tampered": False,
            "expected_decision": "CLEARED"
        })

    # 2. Generate 52 Manipulated / Fraudulent Documents
    print(f"Generating {n_tampered} manipulated documents across diverse attack vectors...")
    attack_types = [
        "checksum_mismatch",
        "invalid_verhoeff",
        "expired_document",
        "spliced_photo_ela",
        "tampered_stamp",
        "revoked_blacklist",
        "viz_mrz_inconsistency"
    ]

    for i in range(n_tampered):
        attack = attack_types[i % len(attack_types)]
        fname = random.choice(first_names)
        lname = random.choice(last_names)

        if attack == "checksum_mismatch":
            canvas = make_doc_canvas("passport", "REPUBLIC OF INDIA - PASSPORT", (245, 248, 252))
            add_face_box(canvas, seed=100+i)
            pass_num = f"Z{9000000 + i}"
            cv2.putText(canvas, f"PASSPORT NO: {pass_num}", (280, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 20, 30), 2)
            # Deliberate check digit error in Line 2
            mrz_l1 = f"P<IND{lname}<<{fname}" + "<" * 20
            mrz_l2 = f"{pass_num}<9IND9208154M3212202<<<<<<<<<<<<<<06" # Bad checkdigit 9 vs expected
            cv2.putText(canvas, mrz_l1[:44], (50, 580), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            cv2.putText(canvas, mrz_l2[:44], (50, 630), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            meta_type = "passport"

        elif attack == "invalid_verhoeff":
            canvas = make_doc_canvas("aadhaar", "UNIQUE IDENTIFICATION AUTHORITY OF INDIA", (255, 255, 255))
            add_face_box(canvas, seed=100+i)
            # Invalidate Aadhaar checksum by flipping check digit
            bad_aadhaar = f"29384756102{((i % 9) + 1)}"
            fmt = f"{bad_aadhaar[:4]} {bad_aadhaar[4:8]} {bad_aadhaar[8:12]}"
            cv2.putText(canvas, f"{fname} {lname}", (280, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
            cv2.putText(canvas, fmt, (280, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 20, 20), 3)
            meta_type = "aadhaar"

        elif attack == "expired_document":
            canvas = make_doc_canvas("passport", "REPUBLIC OF INDIA - PASSPORT", (245, 248, 252))
            add_face_box(canvas, seed=100+i)
            pass_num = f"Z{8000000 + i}"
            cv2.putText(canvas, "EXPIRY: 10/01/2018", (280, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 20, 30), 2) # EXPIRED
            mrz_l1 = f"P<IND{lname}<<{fname}" + "<" * 20
            mrz_l2 = f"{pass_num}<8IND9208154M1801102<<<<<<<<<<<<<<06"
            cv2.putText(canvas, mrz_l1[:44], (50, 580), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            cv2.putText(canvas, mrz_l2[:44], (50, 630), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            meta_type = "passport"

        elif attack == "spliced_photo_ela":
            canvas = make_doc_canvas("passport", "REPUBLIC OF INDIA - PASSPORT", (245, 248, 252))
            add_face_box(canvas, seed=999+i)
            # Create a spliced photo block with distinct noise
            spliced_box = np.full((120, 120, 3), (240, 200, 150), dtype=np.uint8)
            cv2.rectangle(spliced_box, (5, 5), (115, 115), (0, 0, 255), 2)
            noise_patch = np.random.normal(0, 12.0, spliced_box.shape).astype(np.int16)
            spliced_box = np.clip(spliced_box.astype(np.int16) + noise_patch, 0, 255).astype(np.uint8)
            canvas[150:270, 70:190] = spliced_box  # Spliced overlay

            mrz_l1 = f"P<IND{lname}<<{fname}"
            mrz_l1 = (mrz_l1 + "<" * 44)[:44]
            p_slice = f"Z{1000000 + i}<"
            p_cd = str(calc_mrz_check_digit(p_slice))
            comp_body = f"{p_slice}{p_cd}IND9208153M3212208" + "<" * 14 + "0"
            comp_cd = str(calc_mrz_check_digit(comp_body))
            mrz_l2 = f"{comp_body}{comp_cd}"
            cv2.putText(canvas, mrz_l1, (50, 580), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            cv2.putText(canvas, mrz_l2, (50, 630), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            meta_type = "passport"

        elif attack == "tampered_stamp":
            canvas = make_doc_canvas("passport", "REPUBLIC OF INDIA - PASSPORT", (245, 248, 252))
            add_face_box(canvas, seed=100+i)
            # Add synthetic spliced stamp with extreme Laplacian sharpness
            stamp = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.circle(stamp, (50, 50), 45, (180, 20, 160), 3)
            cv2.putText(stamp, "SSB ENTRY", (15, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 20, 160), 1)
            canvas[400:500, 750:850] = stamp

            mrz_l1 = f"P<IND{lname}<<{fname}"
            mrz_l1 = (mrz_l1 + "<" * 44)[:44]
            p_slice = f"Z{1000000 + i}<"
            p_cd = str(calc_mrz_check_digit(p_slice))
            comp_body = f"{p_slice}{p_cd}IND9208153M3212208" + "<" * 14 + "0"
            comp_cd = str(calc_mrz_check_digit(comp_body))
            mrz_l2 = f"{comp_body}{comp_cd}"
            cv2.putText(canvas, mrz_l1, (50, 580), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            cv2.putText(canvas, mrz_l2, (50, 630), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            meta_type = "passport"

        elif attack == "revoked_blacklist":
            canvas = make_doc_canvas("passport", "REPUBLIC OF INDIA - PASSPORT", (245, 248, 252))
            add_face_box(canvas, seed=100+i)
            pass_num = "K9876543"  # Blacklisted in SQLite registry.db
            mrz_l1 = "P<INDCRIMINAL<<WANTED<<<<<<<<<<<<<<<<<<<<"
            mrz_l2 = "K9876543<8IND9208154M3212202<<<<<<<<<<<<<<06"
            cv2.putText(canvas, mrz_l1[:44], (50, 580), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            cv2.putText(canvas, mrz_l2[:44], (50, 630), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            meta_type = "passport"

        else:  # viz_mrz_inconsistency
            canvas = make_doc_canvas("passport", "REPUBLIC OF INDIA - PASSPORT", (245, 248, 252))
            add_face_box(canvas, seed=100+i)
            cv2.putText(canvas, "NAME: RAJESH KHANNA", (280, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 20, 30), 2)
            mrz_l1 = "P<INDSURNAME<<DIFFERENTNAME<<<<<<<<<<<<<"
            mrz_l2 = "M1234567<8IND9208154M3212202<<<<<<<<<<<<<<06"
            cv2.putText(canvas, mrz_l1[:44], (50, 580), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            cv2.putText(canvas, mrz_l2[:44], (50, 630), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            meta_type = "passport"

        img_path = os.path.join(output_dir, f"tampered_{i:03d}_{attack}.jpg")
        cv2.imwrite(img_path, canvas, [cv2.IMWRITE_JPEG_QUALITY, 90])
        dataset.append({
            "id": f"tamp_{i}",
            "path": img_path,
            "document_type": meta_type,
            "is_tampered": True,
            "attack_type": attack,
            "expected_decision": "FLAGGED_OR_REJECTED"
        })

    print(f"Total benchmark dataset generated: {len(dataset)} documents ({n_genuine} genuine, {n_tampered} manipulated).\n")
    return dataset


# =====================================================================
# BENCHMARK EVALUATOR & METRICS COMPILER
# =====================================================================

def evaluate_dataset(dataset: list[dict]) -> dict:
    """Runs complete end-to-end verification pipeline over all 100+ documents and computes metrics."""
    tp, fp, tn, fn = 0, 0, 0, 0
    latencies = []
    stage_latencies = {"preprocessing": [], "ocr": [], "tampering": [], "validation": []}

    print(f"=== EXECUTING PHASE 10 BENCHMARK EVALUATION ({len(dataset)} DOCUMENTS) ===")

    for idx, item in enumerate(dataset):
        path = item["path"]
        doc_type = item["document_type"]
        is_tampered_ground_truth = item["is_tampered"]

        t_start = time.perf_counter()

        # 1. Preprocessing (Phase 3 context)
        t0 = time.perf_counter()
        ctx = create_document_context(path, max_dim=1200)
        stage_latencies["preprocessing"].append((time.perf_counter() - t0) * 1000)

        # 2. Fast Cascaded OCR (Phase 2)
        t0 = time.perf_counter()
        ocr_res = run_ocr(ctx.processed_image_path, doc_type)
        stage_latencies["ocr"].append((time.perf_counter() - t0) * 1000)

        # 3. Offline Tampering Forensics (Phase 4)
        t0 = time.perf_counter()
        tamp_res = run_tampering_detection(ctx.processed_image_path)
        stage_latencies["tampering"].append((time.perf_counter() - t0) * 1000)

        # 4. Validation (Phase 6)
        t0 = time.perf_counter()
        val_res = run_validation(ocr_res)
        stage_latencies["validation"].append((time.perf_counter() - t0) * 1000)

        # Risk Orchestration (Phase 8)
        base_score = float(tamp_res.get("tampering_likelihood", 0.0))
        penalties = 0.0

        if val_res.get("checksum", {}).get("overall_checksum_valid") is False:
            penalties += 35.0
        if val_res.get("national_id", {}).get("valid") is False:
            penalties += 35.0
        if val_res.get("dates", {}).get("expiry_valid") is False:
            penalties += 30.0
        if val_res.get("dates", {}).get("dob_plausible") is False:
            penalties += 30.0
        if val_res.get("viz_consistency", {}).get("consistent") is False:
            penalties += 35.0
        if val_res.get("registry", {}).get("blacklisted") is True:
            penalties += 45.0
        if tamp_res.get("stamp_forensics", {}).get("suspicious_stamp_splicing"):
            penalties += 30.0
        if len(tamp_res.get("ela", {}).get("tamper_boxes", [])) > 0:
            penalties += 30.0

        total_risk = round(min(100.0, base_score + penalties), 2)
        total_time_ms = (time.perf_counter() - t_start) * 1000
        latencies.append(total_time_ms)

        # System decision: Flagged if risk > 30.0 or any fatal validation failure
        system_flagged = total_risk > 30.0 or val_res.get("overall_valid") is False

        if is_tampered_ground_truth and system_flagged:
            tp += 1
        elif not is_tampered_ground_truth and system_flagged:
            fp += 1
        elif not is_tampered_ground_truth and not system_flagged:
            tn += 1
        else: # is_tampered_ground_truth and not system_flagged
            fn += 1

        if (idx + 1) % 20 == 0 or (idx + 1) == len(dataset):
            print(f"Processed {idx + 1}/{len(dataset)} | Current Avg Latency: {np.mean(latencies):.1f}ms")

    # Metrics computation
    total = tp + fp + tn + fn
    accuracy = (tp + tn) / float(total) if total > 0 else 0.0
    precision = tp / float(tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / float(tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2.0 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / float(fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / float(fn + tp) if (fn + tp) > 0 else 0.0

    p50_lat = float(np.percentile(latencies, 50))
    p95_lat = float(np.percentile(latencies, 95))
    p99_lat = float(np.percentile(latencies, 99))
    mean_lat = float(np.mean(latencies))

    # Print Formatted Executive Table
    print("\n" + "="*70)
    print("           PROJECT GUARDIAN (SIH PS 26188) BENCHMARK REPORT         ")
    print("="*70)
    print(f"{'Metric':<35} | {'Value':<25}")
    print("-"*70)
    print(f"{'Total Evaluated Documents':<35} | {total} (Genuine: {tn+fp}, Manipulated: {tp+fn})")
    print(f"{'Accuracy':<35} | {accuracy * 100:.2f}%")
    print(f"{'Precision (Positive Predictive Val)':<35} | {precision * 100:.2f}%")
    print(f"{'Recall (Sensitivity / Detection Rate)':<35} | {recall * 100:.2f}%")
    print(f"{'F1 Score':<35} | {f1 * 100:.2f}%")
    print(f"{'False Positive Rate (FPR)':<35} | {fpr * 100:.2f}%")
    print(f"{'False Negative Rate (FNR)':<35} | {fnr * 100:.2f}%")
    print("-"*70)
    print(f"{'Latency P50 (Median)':<35} | {p50_lat:.2f} ms ({p50_lat/1000:.3f} s)")
    print(f"{'Latency P95':<35} | {p95_lat:.2f} ms ({p95_lat/1000:.3f} s)")
    print(f"{'Latency P99':<35} | {p99_lat:.2f} ms ({p99_lat/1000:.3f} s)")
    print(f"{'Mean End-to-End Latency':<35} | {mean_lat:.2f} ms ({mean_lat/1000:.3f} s)")
    print("="*70)

    report_dict = {
        "dataset_size": total,
        "genuine_count": tn + fp,
        "manipulated_count": tp + fn,
        "confusion_matrix": {"TP": tp, "FP": fp, "TN": tn, "FN": fn},
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "false_negative_rate": round(fnr, 4),
        "latency_ms": {
            "p50": round(p50_lat, 2),
            "p95": round(p95_lat, 2),
            "p99": round(p99_lat, 2),
            "mean": round(mean_lat, 2)
        },
        "stage_mean_ms": {
            k: round(float(np.mean(v)), 2) for k, v in stage_latencies.items()
        }
    }

    out_file = os.path.join(BACKEND_DIR, "data", "benchmark_report.json")
    with open(out_file, "w") as f:
        json.dump(report_dict, f, indent=2)

    print(f"Full benchmark JSON saved to: {out_file}\n")
    return report_dict


if __name__ == "__main__":
    benchmark_dir = os.path.join(BACKEND_DIR, "data", "benchmark_dataset")
    ds = generate_synthetic_dataset(benchmark_dir, n_genuine=52, n_tampered=52)
    evaluate_dataset(ds)
