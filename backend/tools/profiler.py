import os
import sys
import time
import json
import psutil
import numpy as np

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from modules.preprocessing import detect_and_correct_document
from modules.ocr import extract_document_face, extract_passport, extract_document_fields, ensure_optimal_ocr_image
from modules.tampering import run_ela, check_metadata, analyze_stamp_region, check_ai_manipulation
from modules.validation import run_validation
from modules.blockchain import commit_inspection_block


def get_process_metrics():
    """Returns current process CPU percent and RSS memory in MB."""
    p = psutil.Process(os.getpid())
    mem_mb = p.memory_info().rss / (1024 * 1024)
    cpu_pct = p.cpu_percent(interval=None)
    return mem_mb, cpu_pct


def run_profiling(image_path: str, iterations: int = 5) -> dict:
    """
    Profiles each pipeline stage, measuring cold/warm latency,
    CPU/RAM usage, and computing P50, P95, P99 percentiles.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Test image not found at {image_path}")

    print(f"=== INITIATING PHASE 1 PIPELINE PROFILING ===")
    print(f"Target Image: {image_path}")
    print(f"Iterations: {iterations}\n")

    stages = [
        "1. Image Optimization",
        "2. Deskew & CLAHE",
        "3. Face Auto-Crop",
        "4. PassportEye MRZ",
        "5. ELA Analysis",
        "6. Metadata Check",
        "7. Stamp Forensics",
        "8. AI Forgery / Noise",
        "9. Validation Rules",
        "10. Blockchain Commit"
    ]

    timings = {s: [] for s in stages}
    ram_usage = []
    cpu_usage = []
    cold_latencies = {}
    warm_latencies = {}

    opt_img = ensure_optimal_ocr_image(image_path, max_dim=1200)

    for i in range(iterations):
        mem_before, _ = get_process_metrics()
        iter_start = time.perf_counter()

        # Stage 1: Image optimization
        t0 = time.perf_counter()
        opt = ensure_optimal_ocr_image(image_path, max_dim=1200)
        timings["1. Image Optimization"].append((time.perf_counter() - t0) * 1000)

        # Stage 2: Deskew
        t0 = time.perf_counter()
        prep = detect_and_correct_document(opt)
        timings["2. Deskew & CLAHE"].append((time.perf_counter() - t0) * 1000)

        # Stage 3: Face crop
        t0 = time.perf_counter()
        face = extract_document_face(opt)
        timings["3. Face Auto-Crop"].append((time.perf_counter() - t0) * 1000)

        # Stage 4: MRZ
        t0 = time.perf_counter()
        mrz = extract_passport(opt)
        timings["4. PassportEye MRZ"].append((time.perf_counter() - t0) * 1000)

        # Stage 5: ELA
        t0 = time.perf_counter()
        ela = run_ela(opt)
        timings["5. ELA Analysis"].append((time.perf_counter() - t0) * 1000)

        # Stage 6: Metadata
        t0 = time.perf_counter()
        meta = check_metadata(opt)
        timings["6. Metadata Check"].append((time.perf_counter() - t0) * 1000)

        # Stage 7: Stamp
        t0 = time.perf_counter()
        stamp = analyze_stamp_region(opt)
        timings["7. Stamp Forensics"].append((time.perf_counter() - t0) * 1000)

        # Stage 8: AI Forgery / Noise
        t0 = time.perf_counter()
        ai = check_ai_manipulation(opt)
        timings["8. AI Forgery / Noise"].append((time.perf_counter() - t0) * 1000)

        # Stage 9: Validation
        t0 = time.perf_counter()
        val = run_validation({"fields": mrz, "document_type": "passport"})
        timings["9. Validation Rules"].append((time.perf_counter() - t0) * 1000)

        # Stage 10: Blockchain
        t0 = time.perf_counter()
        blk = commit_inspection_block(opt, f"prof-{i}", "passport", 15.0, "LOW")
        timings["10. Blockchain Commit"].append((time.perf_counter() - t0) * 1000)

        iter_total = (time.perf_counter() - iter_start) * 1000
        mem_after, cpu_curr = get_process_metrics()
        ram_usage.append(mem_after)
        cpu_usage.append(cpu_curr)

        if i == 0:
            cold_latencies = {s: timings[s][0] for s in stages}
            cold_latencies["TOTAL"] = iter_total
        else:
            if "TOTAL" not in warm_latencies:
                warm_latencies = {s: [] for s in stages}
                warm_latencies["TOTAL"] = []
            for s in stages:
                warm_latencies[s].append(timings[s][-1])
            warm_latencies["TOTAL"].append(iter_total)

        print(f"Iteration {i+1}/{iterations} completed in {iter_total:.1f}ms | RAM: {mem_after:.1f} MB")

    # Compute percentiles
    summary = {}
    print("\n" + "="*70)
    print(f"{'STAGE':<30} | {'P50 (ms)':<10} | {'P95 (ms)':<10} | {'P99 (ms)':<10} | {'MEAN (ms)':<10}")
    print("="*70)

    total_p50 = 0
    total_p95 = 0
    total_p99 = 0

    for s in stages:
        arr = np.array(timings[s])
        p50 = float(np.percentile(arr, 50))
        p95 = float(np.percentile(arr, 95))
        p99 = float(np.percentile(arr, 99))
        mean = float(np.mean(arr))
        total_p50 += p50
        total_p95 += p95
        total_p99 += p99

        summary[s] = {
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
            "mean_ms": round(mean, 2)
        }
        print(f"{s:<30} | {p50:<10.1f} | {p95:<10.1f} | {p99:<10.1f} | {mean:<10.1f}")

    print("="*70)
    print(f"{'PIPELINE TOTAL':<30} | {total_p50:<10.1f} | {total_p95:<10.1f} | {total_p99:<10.1f} | {sum(s['mean_ms'] for s in summary.values()):<10.1f}")
    print("="*70)

    report = {
        "stages": summary,
        "total_p50_ms": round(total_p50, 2),
        "total_p95_ms": round(total_p95, 2),
        "total_p99_ms": round(total_p99, 2),
        "cold_start_total_ms": round(cold_latencies.get("TOTAL", 0), 2),
        "warm_start_mean_total_ms": round(float(np.mean(warm_latencies.get("TOTAL", [0]))), 2),
        "peak_ram_mb": round(max(ram_usage), 2),
        "mean_ram_mb": round(float(np.mean(ram_usage)), 2)
    }

    out_file = os.path.join(BACKEND_DIR, "data", "profiler_report.json")
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nReport written to: {out_file}\n")
    return report


if __name__ == "__main__":
    sample_img = os.path.join(BACKEND_DIR, "uploads", "befdbff0-3fd5-4214-b231-064e2fa68ab7.jpg")
    run_profiling(sample_img, iterations=3)

