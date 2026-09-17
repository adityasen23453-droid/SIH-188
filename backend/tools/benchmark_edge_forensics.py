"""
BorderShield Comparative Benchmark: Existing SIH-188 vs SIH-188 + Edge Boundary Forensics.

Runs rigorous comparative benchmark across a 104-document dataset (52 genuine, 52 tampered):
- Attack vectors: Photo replacement, text alteration, stamp splicing, cut-and-paste patches,
  checksum tampering, invalid Verhoeff, expired documents, and revoked blacklist credentials.
- Degradations: Clean, Gaussian blur, sensor noise, aggressive JPEG compression (Q=50).

Measures and compares:
- Precision, Recall, F1 Score, False Positive Rate (FPR), False Negative Rate (FNR)
- Latency profile: P50 (median), P95, P99, Mean (in ms)
- Stage-by-stage runtime breakdown
- Side-by-side delta analysis
"""

import os
import sys
import time
import json
import random
import cv2
import numpy as np

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.config import get_settings
from modules.preprocessing import create_document_context
from modules.ocr import run_ocr
from modules.validation import run_validation
from modules.tampering import run_tampering_detection
from modules.edge_forensics import detect_boundary_discontinuities
from tools.benchmark_suite import generate_synthetic_dataset


def run_single_pass(dataset: list, mode: str = "shadow") -> dict:
    """
    Executes a benchmark pass over the dataset.
    mode: "shadow" (Existing baseline) vs "active" (SIH-188 + Edge Forensics)
    """
    settings = get_settings()
    orig_mode = settings.EDGE_FORENSICS_MODE
    settings.EDGE_FORENSICS_MODE = mode

    tp = 0
    fp = 0
    tn = 0
    fn = 0

    latencies = []
    stage_latencies = {
        "preprocessing": [],
        "ocr": [],
        "tampering": [],
        "validation": []
    }

    tamper_scores = []
    edge_scores = []

    try:
        for idx, item in enumerate(dataset):
            path = item["path"]
            doc_type = item["document_type"]
            is_tampered_ground_truth = item["is_tampered"]

            t_start = time.perf_counter()

            # 1. Preprocessing
            t0 = time.perf_counter()
            ctx = create_document_context(path, max_dim=1200)
            stage_latencies["preprocessing"].append((time.perf_counter() - t0) * 1000)

            # 2. Fast Cascaded OCR
            t0 = time.perf_counter()
            ocr_res = run_ocr(ctx.processed_image_path, doc_type, image_bgr=ctx.clahe_bgr)
            stage_latencies["ocr"].append((time.perf_counter() - t0) * 1000)

            # 3. Tampering Forensics (reuses ctx.clahe_bgr)
            t0 = time.perf_counter()
            tamp_res = run_tampering_detection(ctx.processed_image_path, context=ctx, image_bgr=ctx.clahe_bgr)
            stage_latencies["tampering"].append((time.perf_counter() - t0) * 1000)

            # 4. Validation
            t0 = time.perf_counter()
            val_res = run_validation(ocr_res)
            stage_latencies["validation"].append((time.perf_counter() - t0) * 1000)

            # Risk Orchestration
            base_score = float(tamp_res.get("tampering_likelihood", 0.0))
            tamper_scores.append(base_score)

            edge_forensics_data = tamp_res.get("edge_forensics", {})
            edge_scores.append(edge_forensics_data.get("edge_anomaly_score", 0.0))

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

            # In active mode, if edge forensics flags an anomaly, apply forensic penalty
            if mode == "active" and edge_forensics_data.get("status") == "ANOMALY_DETECTED":
                penalties += 25.0
            elif mode == "active" and edge_forensics_data.get("status") == "SUSPICIOUS":
                penalties += 10.0

            total_risk = round(min(100.0, base_score + penalties), 2)
            total_time_ms = (time.perf_counter() - t_start) * 1000
            latencies.append(total_time_ms)

            # Decision: Flagged if risk > 30.0 or any fatal validation failure
            system_flagged = total_risk > 30.0 or val_res.get("overall_valid") is False

            if is_tampered_ground_truth and system_flagged:
                tp += 1
            elif not is_tampered_ground_truth and system_flagged:
                fp += 1
            elif not is_tampered_ground_truth and not system_flagged:
                tn += 1
            else:
                fn += 1

    finally:
        settings.EDGE_FORENSICS_MODE = orig_mode

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

    return {
        "mode": mode,
        "total": total,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": round(accuracy * 100, 2),
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "f1": round(f1 * 100, 2),
        "fpr": round(fpr * 100, 2),
        "fnr": round(fnr * 100, 2),
        "lat_p50": round(p50_lat, 2),
        "lat_p95": round(p95_lat, 2),
        "lat_p99": round(p99_lat, 2),
        "lat_mean": round(mean_lat, 2),
        "stage_latencies": {
            k: round(float(np.mean(v)), 2) for k, v in stage_latencies.items()
        },
        "mean_tamper_score": round(float(np.mean(tamper_scores)), 2),
        "mean_edge_score": round(float(np.mean(edge_scores)), 2)
    }


def run_comparative_benchmark():
    print("=" * 80)
    print(" BORDERSHIELD COMPARATIVE BENCHMARK: EXISTING SIH-188 vs SIH-188 + EDGE FORENSICS ")
    print("=" * 80)

    # 1. Prepare benchmark dataset
    dataset_dir = os.path.join(BACKEND_DIR, "data", "benchmark_edge_docs")
    dataset = generate_synthetic_dataset(dataset_dir, n_genuine=52, n_tampered=52)
    print(f"\nGenerated benchmark dataset: {len(dataset)} documents ({dataset_dir})\n")

    # 2. Run Baseline Pass (Shadow Mode)
    print(">> [1/2] Executing Baseline Pass (Existing SIH-188 / Shadow Mode)...")
    baseline = run_single_pass(dataset, mode="shadow")

    # 3. Run Upgrade Pass (Active Mode)
    print(">> [2/2] Executing Upgrade Pass (SIH-188 + Active Edge Boundary Forensics)...")
    upgrade = run_single_pass(dataset, mode="active")

    # 4. Compute Deltas
    prec_delta = upgrade["precision"] - baseline["precision"]
    rec_delta = upgrade["recall"] - baseline["recall"]
    f1_delta = upgrade["f1"] - baseline["f1"]
    fpr_delta = upgrade["fpr"] - baseline["fpr"]
    fnr_delta = upgrade["fnr"] - baseline["fnr"]
    lat_delta = upgrade["lat_p50"] - baseline["lat_p50"]

    # 5. Print Comparative Table
    print("\n" + "=" * 80)
    print("                  COMPARATIVE BENCHMARK EVALUATION RESULTS                   ")
    print("=" * 80)
    print(f"{'Metric':<30} | {'Existing SIH-188':<18} | {'SIH-188 + Edge':<18} | {'Delta':<10}")
    print("-" * 80)
    print(f"{'Accuracy (%)':<30} | {baseline['accuracy']:<18.2f} | {upgrade['accuracy']:<18.2f} | {upgrade['accuracy'] - baseline['accuracy']:+.2f}%")
    print(f"{'Precision (%)':<30} | {baseline['precision']:<18.2f} | {upgrade['precision']:<18.2f} | {prec_delta:+.2f}%")
    print(f"{'Recall (Sensitivity %)':<30} | {baseline['recall']:<18.2f} | {upgrade['recall']:<18.2f} | {rec_delta:+.2f}%")
    print(f"{'F1 Score (%)':<30} | {baseline['f1']:<18.2f} | {upgrade['f1']:<18.2f} | {f1_delta:+.2f}%")
    print(f"{'False Positive Rate (%)':<30} | {baseline['fpr']:<18.2f} | {upgrade['fpr']:<18.2f} | {fpr_delta:+.2f}%")
    print(f"{'False Negative Rate (%)':<30} | {baseline['fnr']:<18.2f} | {upgrade['fnr']:<18.2f} | {fnr_delta:+.2f}%")
    print("-" * 80)
    print(f"{'P50 Latency (ms)':<30} | {baseline['lat_p50']:<18.2f} | {upgrade['lat_p50']:<18.2f} | {lat_delta:+.2f} ms")
    print(f"{'P95 Latency (ms)':<30} | {baseline['lat_p95']:<18.2f} | {upgrade['lat_p95']:<18.2f} | {upgrade['lat_p95'] - baseline['lat_p95']:+.2f} ms")
    print(f"{'P99 Latency (ms)':<30} | {baseline['lat_p99']:<18.2f} | {upgrade['lat_p99']:<18.2f} | {upgrade['lat_p99'] - baseline['lat_p99']:+.2f} ms")
    print(f"{'Mean Latency (ms)':<30} | {baseline['lat_mean']:<18.2f} | {upgrade['lat_mean']:<18.2f} | {upgrade['lat_mean'] - baseline['lat_mean']:+.2f} ms")
    print("-" * 80)
    print(f"{'Stage: Preprocessing (ms)':<30} | {baseline['stage_latencies']['preprocessing']:<18.2f} | {upgrade['stage_latencies']['preprocessing']:<18.2f} | {upgrade['stage_latencies']['preprocessing'] - baseline['stage_latencies']['preprocessing']:+.2f} ms")
    print(f"{'Stage: OCR (ms)':<30} | {baseline['stage_latencies']['ocr']:<18.2f} | {upgrade['stage_latencies']['ocr']:<18.2f} | {upgrade['stage_latencies']['ocr'] - baseline['stage_latencies']['ocr']:+.2f} ms")
    print(f"{'Stage: Tampering Forensics (ms)':<30} | {baseline['stage_latencies']['tampering']:<18.2f} | {upgrade['stage_latencies']['tampering']:<18.2f} | {upgrade['stage_latencies']['tampering'] - baseline['stage_latencies']['tampering']:+.2f} ms")
    print(f"{'Stage: Validation (ms)':<30} | {baseline['stage_latencies']['validation']:<18.2f} | {upgrade['stage_latencies']['validation']:<18.2f} | {upgrade['stage_latencies']['validation'] - baseline['stage_latencies']['validation']:+.2f} ms")
    print("=" * 80)

    # 6. Save JSON Report
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset_size": len(dataset),
        "baseline_existing": baseline,
        "upgrade_with_edge": upgrade,
        "delta": {
            "accuracy": round(upgrade["accuracy"] - baseline["accuracy"], 2),
            "precision": round(prec_delta, 2),
            "recall": round(rec_delta, 2),
            "f1": round(f1_delta, 2),
            "fpr": round(fpr_delta, 2),
            "fnr": round(fnr_delta, 2),
            "lat_p50_ms": round(lat_delta, 2),
            "lat_p95_ms": round(upgrade["lat_p95"] - baseline["lat_p95"], 2),
            "lat_p99_ms": round(upgrade["lat_p99"] - baseline["lat_p99"], 2)
        }
    }

    out_file = os.path.join(BACKEND_DIR, "data", "benchmark_edge_forensics.json")
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nComparative benchmark report written to: {out_file}\n")
    return report


if __name__ == "__main__":
    run_comparative_benchmark()

