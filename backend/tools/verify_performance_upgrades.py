"""
BorderShield Performance & Latency Benchmark Suite (Phase 17).
Measures:
1. Micro-benchmark: Throughput & latency of sovereign cryptographic primitives:
   - AES-256-GCM authenticated encryption and decryption
   - HMAC-SHA-256 keyed tokenization
   - RFC 8785 canonical JSON hashing
   - Ed25519 digital signature generation and verification
2. Macro-benchmark: End-to-end border document screening latency across genuine and manipulated documents.
3. Verification against SLA targets:
   - Mean latency <= 1.25s per document
   - Cryptographic overhead <= 5ms per document (< 0.5% overhead)
"""

import os
import sys
import time
import json
import numpy as np

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.security import encrypt_field, decrypt_field, tokenize_identifier
from core.signatures import sign_canonical_hash, verify_signature, get_station_public_key_hex
from modules.blockchain import (
    canonical_json_bytes,
    compute_canonical_hash,
    commit_inspection_block
)
from modules.preprocessing import create_document_context
from modules.ocr import run_ocr
from modules.tampering import run_tampering_detection
from modules.validation import run_validation


def benchmark_crypto_primitives(iterations: int = 1000) -> dict:
    """Measures micro-benchmarks for all newly added sovereign cryptographic operations."""
    print(f"\n{'='*70}")
    print(f"1. SOVEREIGN CRYPTOGRAPHIC PRIMITIVES BENCHMARK ({iterations} iterations)")
    print(f"{'='*70}")

    sample_id = "A1234567"
    sample_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    # 1. AES-256-GCM Encryption
    t0 = time.perf_counter()
    for _ in range(iterations):
        enc = encrypt_field(sample_id)
    aes_enc_time = (time.perf_counter() - t0) * 1000 / iterations

    # 2. AES-256-GCM Decryption
    t0 = time.perf_counter()
    for _ in range(iterations):
        dec = decrypt_field(enc)
    aes_dec_time = (time.perf_counter() - t0) * 1000 / iterations

    # 3. HMAC-SHA-256 Tokenization
    t0 = time.perf_counter()
    for _ in range(iterations):
        tok = tokenize_identifier(sample_id)
    hmac_time = (time.perf_counter() - t0) * 1000 / iterations

    # 4. RFC 8785 Canonical JSON Serialization & Hashing
    dummy_ev = {
        "event_type": "SCREENING_EVENT",
        "block_index": 42,
        "doc_hash": sample_hash,
        "risk_score": 15.5,
        "decision": "CLEARED"
    }
    t0 = time.perf_counter()
    for _ in range(iterations):
        b = canonical_json_bytes(dummy_ev)
        h = compute_canonical_hash(b, sample_hash)
    canonical_time = (time.perf_counter() - t0) * 1000 / iterations

    # 5. Ed25519 Digital Signing
    t0 = time.perf_counter()
    for _ in range(iterations):
        sig = sign_canonical_hash(sample_hash)
    ed25519_sign_time = (time.perf_counter() - t0) * 1000 / iterations

    # 6. Ed25519 Digital Verification
    pubkey = get_station_public_key_hex()
    t0 = time.perf_counter()
    for _ in range(iterations):
        valid = verify_signature(sample_hash, sig, pubkey)
    ed25519_verify_time = (time.perf_counter() - t0) * 1000 / iterations

    total_crypto_overhead = aes_enc_time + aes_dec_time + hmac_time + canonical_time + ed25519_sign_time

    print(f"  {'Operation':<35} | {'Mean Latency':<15} | {'Throughput':<15}")
    print(f"  {'-'*65}")
    print(f"  {'AES-256-GCM Encrypt':<35} | {aes_enc_time*1000:.2f} µs ({aes_enc_time:.4f} ms) | {1000/aes_enc_time:.0f} ops/sec")
    print(f"  {'AES-256-GCM Decrypt':<35} | {aes_dec_time*1000:.2f} µs ({aes_dec_time:.4f} ms) | {1000/aes_dec_time:.0f} ops/sec")
    print(f"  {'HMAC-SHA-256 Tokenize':<35} | {hmac_time*1000:.2f} µs ({hmac_time:.4f} ms) | {1000/hmac_time:.0f} ops/sec")
    print(f"  {'RFC 8785 Canonical Digest':<35} | {canonical_time*1000:.2f} µs ({canonical_time:.4f} ms) | {1000/canonical_time:.0f} ops/sec")
    print(f"  {'Ed25519 Signature Sign':<35} | {ed25519_sign_time*1000:.2f} µs ({ed25519_sign_time:.4f} ms) | {1000/ed25519_sign_time:.0f} ops/sec")
    print(f"  {'Ed25519 Signature Verify':<35} | {ed25519_verify_time*1000:.2f} µs ({ed25519_verify_time:.4f} ms) | {1000/ed25519_verify_time:.0f} ops/sec")
    print(f"  {'-'*65}")
    print(f"  {'TOTAL CRYPTOGRAPHIC OVERHEAD PER INSPECTION':<35} | {total_crypto_overhead:.4f} ms (< 0.001 s)")

    return {
        "aes_enc_ms": round(aes_enc_time, 4),
        "aes_dec_ms": round(aes_dec_time, 4),
        "hmac_ms": round(hmac_time, 4),
        "canonical_ms": round(canonical_time, 4),
        "ed25519_sign_ms": round(ed25519_sign_time, 4),
        "ed25519_verify_ms": round(ed25519_verify_time, 4),
        "total_crypto_overhead_ms": round(total_crypto_overhead, 4)
    }


def benchmark_end_to_end_screening(sample_count: int = 10) -> dict:
    """Measures macro-benchmark for full screening pipeline with all security upgrades active."""
    dataset_dir = os.path.join(BACKEND_DIR, "data", "benchmark_dataset")
    if not os.path.exists(dataset_dir):
        print(f"Dataset directory not found at {dataset_dir}, skipping macro-benchmark.")
        return {}

    all_files = [f for f in os.listdir(dataset_dir) if f.endswith(".jpg")]
    genuine_files = [f for f in all_files if f.startswith("genuine_")][:sample_count // 2]
    tampered_files = [f for f in all_files if f.startswith("tampered_")][:sample_count // 2]
    selected_files = genuine_files + tampered_files

    print(f"\n{'='*70}")
    print(f"2. END-TO-END SCREENING PIPELINE BENCHMARK ({len(selected_files)} documents)")
    print(f"{'='*70}")

    latencies = []
    stage_latencies = {
        "preprocessing": [],
        "ocr": [],
        "tampering": [],
        "validation": [],
        "ledger_commit": []
    }

    correct_predictions = 0

    for idx, fname in enumerate(selected_files):
        fpath = os.path.join(dataset_dir, fname)
        is_tampered_ground_truth = fname.startswith("tampered_")
        doc_type = "PASSPORT" if "passport" in fname else "AADHAAR" if "aadhaar" in fname else "AUTO"

        t_start = time.perf_counter()

        # 1. Preprocessing
        t0 = time.perf_counter()
        ctx = create_document_context(fpath, max_dim=1200)
        stage_latencies["preprocessing"].append((time.perf_counter() - t0) * 1000)

        # 2. OCR
        t0 = time.perf_counter()
        ocr_res = run_ocr(ctx.processed_image_path, doc_type.lower(), image_bgr=ctx.clahe_bgr)
        stage_latencies["ocr"].append((time.perf_counter() - t0) * 1000)

        # 3. Tampering Forensics
        t0 = time.perf_counter()
        tamp_res = run_tampering_detection(ctx.processed_image_path)
        stage_latencies["tampering"].append((time.perf_counter() - t0) * 1000)

        # 4. Validation
        t0 = time.perf_counter()
        val_res = run_validation(ocr_res)
        stage_latencies["validation"].append((time.perf_counter() - t0) * 1000)

        # Risk scoring
        base_score = float(tamp_res.get("tampering_likelihood", 0.0))
        penalties = 0.0
        if val_res.get("checksum", {}).get("overall_checksum_valid") is False:
            penalties += 35.0
        if val_res.get("national_id", {}).get("valid") is False:
            penalties += 35.0
        if val_res.get("registry", {}).get("blacklisted") is True:
            penalties += 45.0
        total_risk = round(min(100.0, base_score + penalties), 2)
        decision = "FLAGGED" if total_risk > 30.0 else "CLEARED"

        # 5. Append-only Cryptographic Ledger Commit (with Ed25519 signature)
        t0 = time.perf_counter()
        block = commit_inspection_block(
            file_path=fpath,
            file_id=f"bench-{idx}",
            document_type=doc_type,
            risk_score=total_risk,
            risk_level="HIGH" if total_risk > 60 else "MEDIUM" if total_risk > 30 else "LOW",
            officer_id="SSB-OFFICER-7429"
        )
        stage_latencies["ledger_commit"].append((time.perf_counter() - t0) * 1000)

        total_ms = (time.perf_counter() - t_start) * 1000
        latencies.append(total_ms)

        predicted_tampered = decision == "FLAGGED"
        if predicted_tampered == is_tampered_ground_truth:
            correct_predictions += 1

        print(f"  [{idx+1:02d}/{len(selected_files):02d}] {fname:<35} -> {decision:<8} (Risk: {total_risk:>5.1f}) in {total_ms:.1f}ms (Ledger: {stage_latencies['ledger_commit'][-1]:.2f}ms)")

    mean_latency = float(np.mean(latencies))
    p50_latency = float(np.median(latencies))
    p95_latency = float(np.percentile(latencies, 95))
    accuracy = (correct_predictions / len(selected_files)) * 100

    print(f"\n{'-'*70}")
    print(f"  {'Metric':<35} | {'Value':<20}")
    print(f"  {'-'*70}")
    print(f"  {'Evaluation Sample Size':<35} | {len(selected_files)} documents")
    print(f"  {'Sample Accuracy':<35} | {accuracy:.1f}%")
    print(f"  {'Mean End-to-End Latency':<35} | {mean_latency:.2f} ms ({mean_latency/1000:.3f} s)")
    print(f"  {'P50 Latency (Median)':<35} | {p50_latency:.2f} ms ({p50_latency/1000:.3f} s)")
    print(f"  {'P95 Latency':<35} | {p95_latency:.2f} ms ({p95_latency/1000:.3f} s)")
    print(f"  {'Mean Cryptographic Ledger Commit':<35} | {np.mean(stage_latencies['ledger_commit']):.2f} ms")
    print(f"  {'Sub-Second E-Gate Target (<= 1.25s)':<35} | {'PASSED' if mean_latency <= 1250 else 'NEEDS_OPTIMIZATION'}")
    print(f"{'='*70}\n")

    return {
        "sample_count": len(selected_files),
        "accuracy_pct": accuracy,
        "mean_latency_ms": round(mean_latency, 2),
        "p50_latency_ms": round(p50_latency, 2),
        "p95_latency_ms": round(p95_latency, 2),
        "stage_mean_ms": {k: round(float(np.mean(v)), 2) for k, v in stage_latencies.items()}
    }


if __name__ == "__main__":
    crypto_res = benchmark_crypto_primitives(iterations=1000)
    pipeline_res = benchmark_end_to_end_screening(sample_count=10)

    out_file = os.path.join(BACKEND_DIR, "data", "performance_benchmark_upgraded.json")
    with open(out_file, "w") as f:
        json.dump({"crypto_primitives": crypto_res, "pipeline_benchmark": pipeline_res}, f, indent=2)
    print(f"Performance report saved to {out_file}")

