import os
import sys
import math
import numpy as np

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from modules.biometrics import (
    compute_cosine_similarity,
    estimate_liveness_score,
    search_alias_identities,
    register_biometric_profile,
    extract_face_embedding
)
from modules.blockchain import (
    calculate_block_hash,
    commit_inspection_block,
    verify_chain_integrity,
    get_recent_blocks,
    update_block_biometric_decision,
    get_latest_block
)


def test_cosine_similarity_properties():
    # Identical unit vector gives 1.0
    v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    assert math.isclose(compute_cosine_similarity(v1, v1), 1.0, abs_tol=1e-4)

    # Orthogonal vectors give 0.0
    v2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    assert math.isclose(compute_cosine_similarity(v1, v2), 0.0, abs_tol=1e-4)

    # 45-degree angle
    v3 = np.array([1.0, 1.0, 0.0], dtype=np.float32)
    v3 /= np.linalg.norm(v3)
    assert math.isclose(compute_cosine_similarity(v1, v3), 0.7071, abs_tol=1e-3)



def test_liveness_heuristics():
    # Blank/None image
    res_none = estimate_liveness_score(None)
    assert res_none["is_live"] is False

    # Synthetic sharp colored image
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[20:80, 20:80] = [0, 180, 255] # orange/skin tone
    cv2_res = estimate_liveness_score(img)
    assert "liveness_score" in cv2_res
    assert isinstance(cv2_res["liveness_score"], float)


def test_alias_detection_with_synthetic_embedding():
    # Register a known test traveler
    np.random.seed(999)
    emb = np.random.randn(576).astype(np.float32)
    emb /= np.linalg.norm(emb)

    rec_id = register_biometric_profile(
        name="VIKRAM SINGH",
        doc_number="K9876543",
        doc_type="PASSPORT",
        nationality="IND",
        crossing_point="Attari Border",
        embedding=emb
    )
    assert rec_id > 0

    # Case 1: Same person, same name -> No alias alert
    match_same = search_alias_identities(emb, current_name="VIKRAM SINGH", current_doc_num="K9876543")
    assert match_same["match_count"] >= 1
    assert match_same["alias_detected"] is False

    # Case 2: Same face, DIFFERENT name ("ANAND VERMA") -> Triggers duplicate alias alert!
    match_diff = search_alias_identities(emb, current_name="ANAND VERMA", current_doc_num="P1122334")
    assert match_diff["alias_detected"] is True
    assert match_diff["top_match"]["previous_name"] == "VIKRAM SINGH"
    assert match_diff["top_match"]["similarity"] >= 0.99


def test_blockchain_genesis_and_chain_integrity():
    # Ledger should have at least genesis block
    report = verify_chain_integrity()
    assert report["chain_valid"] is True
    assert report["total_blocks"] >= 1
    assert len(report["tampered_blocks"]) == 0


def test_blockchain_block_commit_and_linkage():
    # Commit a test inspection block
    test_file_id = "test-session-uuid-1234"
    block = commit_inspection_block(
        file_path=os.path.abspath(__file__), # use existing file for SHA-256
        file_id=test_file_id,
        document_type="PASSPORT",
        risk_score=15.5,
        risk_level="LOW",
        biometric_status="MATCH",
        officer_id="SSB-OFFICER-7429"
    )

    assert block["block_index"] > 0
    assert block["decision"] == "CLEARED"
    assert len(block["block_hash"]) == 64
    assert len(block["previous_hash"]) == 64

    # Verify chain integrity remains intact
    report = verify_chain_integrity()
    assert report["chain_valid"] is True
    assert report["total_blocks"] >= block["block_index"] + 1

    # Update biometric decision for this block
    updated = update_block_biometric_decision(test_file_id, "MISMATCH")
    assert updated is not None
    assert updated["biometric_status"] == "MISMATCH"
    assert updated["decision"] == "REJECTED_IMPOSTOR"

    # Verify chain integrity after update
    report2 = verify_chain_integrity()
    assert report2["chain_valid"] is True


def test_blockchain_recent_blocks():
    blocks = get_recent_blocks(limit=10)
    assert len(blocks) >= 1
    assert "block_hash" in blocks[0]
    assert "doc_hash" in blocks[0]
    assert "timestamp" in blocks[0]


if __name__ == "__main__":
    print("Running biometric and blockchain tests...")
    test_cosine_similarity_properties()
    print("[PASS] test_cosine_similarity_properties")
    test_liveness_heuristics()
    print("[PASS] test_liveness_heuristics")
    test_alias_detection_with_synthetic_embedding()
    print("[PASS] test_alias_detection_with_synthetic_embedding")
    test_blockchain_genesis_and_chain_integrity()
    print("[PASS] test_blockchain_genesis_and_chain_integrity")
    test_blockchain_block_commit_and_linkage()
    print("[PASS] test_blockchain_block_commit_and_linkage")
    test_blockchain_recent_blocks()
    print("[PASS] test_blockchain_recent_blocks")
    print("\nALL 6 BIOMETRIC & BLOCKCHAIN TESTS PASSED SUCCESSFULLY!")


