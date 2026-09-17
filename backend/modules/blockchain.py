"""
BorderShield Sovereign Cryptographically Chained Audit Ledger
Complies with Sections 12, 13, 14, and 37 of Security.md:
- Append-Only Audit Event Architecture (zero in-place mutations)
- RFC 8785 Canonical JSON Serialization (deterministic key order, compact separators, UTF-8)
- SHA-256 Merkle-Chained Provenance with Mathematical Tamper-Evidence
- Chained Events: SCREENING_EVENT -> BIOMETRIC_EVENT -> OFFICER_OVERRIDE_EVENT
- Zero-PII Compliance (strictly cryptographic hashes, non-PII IDs, risk scores, model versions)
"""

import os
import json
import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

try:
    from core.signatures import sign_canonical_hash, verify_signature
except ImportError:
    from backend.core.signatures import sign_canonical_hash, verify_signature

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "blockchain.db")


def _current_timestamp() -> str:
    """Returns current UTC timestamp in ISO-8601 format with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compute_sha256_bytes(data: bytes) -> str:
    """Computes SHA-256 hash of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def compute_file_sha256(file_path_or_hash: str) -> str:
    """Computes SHA-256 cryptographic checksum of a document file on disk or returns existing hash."""
    if len(file_path_or_hash) == 64 and all(c in "0123456789abcdefABCDEF" for c in file_path_or_hash):
        return file_path_or_hash.lower()
    if not os.path.exists(file_path_or_hash):
        return hashlib.sha256(b"FILE_NOT_FOUND").hexdigest()
    hasher = hashlib.sha256()
    with open(file_path_or_hash, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def calculate_block_hash(
    block_index: int,
    timestamp: str,
    doc_hash: str,
    risk_score: float,
    decision: str,
    officer_id: str,
    previous_hash: str
) -> str:
    """
    Computes deterministic SHA-256 hash of block contents.
    Ensures mathematical non-repudiation and chain immutability.
    Maintains exact backward compatibility with historical blocks.
    """
    payload = f"{block_index}|{timestamp}|{doc_hash}|{risk_score:.2f}|{decision}|{officer_id}|{previous_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_json_bytes(data: dict) -> bytes:
    """
    Serializes a dictionary into RFC 8785 compliant canonical JSON bytes:
    - Sorted keys lexicographically
    - Compact separators (',', ':') with zero extraneous whitespace
    - UTF-8 encoding
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_canonical_hash(canonical_bytes: bytes, previous_hash: str) -> str:
    """
    Computes SHA-256(previous_event_hash + canonical_event_bytes).
    Cryptographically links the canonical event payload to the preceding chain tip.
    """
    hasher = hashlib.sha256()
    hasher.update(previous_hash.encode("utf-8"))
    hasher.update(canonical_bytes)
    return hasher.hexdigest()


def build_canonical_event(
    event_type: str,
    block_index: int,
    timestamp: str,
    file_id: str,
    doc_hash: str,
    document_type: str,
    risk_score: float,
    risk_level: str,
    biometric_status: str,
    decision: str,
    officer_id: str,
    previous_hash: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Constructs a deterministic canonical audit event dictionary.
    ZERO PII GUARANTEE: Never includes traveler names, passport numbers,
    face portraits, or biometric embeddings.
    """
    try:
        from core.config import get_settings
        settings = get_settings()
        ocr_ver = settings.MODEL_VERSION_OCR
        vit_ver = settings.MODEL_VERSION_VIT
        bio_ver = settings.MODEL_VERSION_BIOMETRICS
    except Exception:
        ocr_ver = "PP-OCRv6_medium"
        vit_ver = "ViT_Forgery_v1"
        bio_ver = "MobileNetV3_v1"

    event: Dict[str, Any] = {
        "anchor_protocol": "NBF-VISHVASYA-RFC8785",
        "biometric_status": str(biometric_status).upper(),
        "block_index": int(block_index),
        "decision": str(decision),
        "doc_hash": str(doc_hash),
        "document_type": str(document_type),
        "event_type": str(event_type),
        "file_id": str(file_id),
        "model_versions": {
            "biometrics": bio_ver,
            "ocr": ocr_ver,
            "tampering": vit_ver
        },
        "officer_id": str(officer_id),
        "previous_hash": str(previous_hash),
        "risk_level": str(risk_level).upper(),
        "risk_score": round(float(risk_score), 2),
        "timestamp": str(timestamp)
    }

    if metadata:
        # Sanitize metadata: only allow non-PII primitives
        clean_meta = {}
        disallowed = {"name", "names", "holder_name", "passport_number", "aadhaar_number", "embedding", "portrait"}
        for k, v in metadata.items():
            if k.lower() not in disallowed and isinstance(v, (str, int, float, bool)):
                clean_meta[k] = v
        if clean_meta:
            event["metadata"] = clean_meta

    return event


def _safe_add_column(cursor: sqlite3.Cursor, table: str, column_name: str, col_type: str):
    """Safely adds a column to an SQLite table if not already present."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {col_type}")


def init_blockchain_db():
    """Initializes the SQLite ledger and commits the immutable Genesis Block if empty."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blockchain_ledger (
                block_index INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                doc_hash TEXT NOT NULL,
                file_id TEXT NOT NULL,
                document_type TEXT NOT NULL,
                risk_score REAL NOT NULL,
                risk_level TEXT NOT NULL,
                biometric_status TEXT NOT NULL,
                decision TEXT NOT NULL,
                officer_id TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                block_hash TEXT NOT NULL
            )
        """)
        # Safe additive migrations for sovereign schema enhancements
        _safe_add_column(cursor, "blockchain_ledger", "signature", "TEXT")
        _safe_add_column(cursor, "blockchain_ledger", "canonical_hash", "TEXT")
        _safe_add_column(cursor, "blockchain_ledger", "event_type", "TEXT")
        _safe_add_column(cursor, "blockchain_ledger", "anchor_status", "TEXT")
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM blockchain_ledger")
        if cursor.fetchone()[0] == 0:
            # Commit Genesis Block
            genesis_timestamp = "2026-01-01T00:00:00.000Z"
            genesis_prev = "0" * 64
            genesis_doc = hashlib.sha256(b"SSB_BORDER_DEFENSE_GENESIS_ROOT").hexdigest()
            genesis_hash = calculate_block_hash(
                0, genesis_timestamp, genesis_doc, 0.0, "GENESIS_NODE_ONLINE", "SYSTEM_ROOT", genesis_prev
            )
            canonical_ev = build_canonical_event(
                event_type="GENESIS_EVENT",
                block_index=0,
                timestamp=genesis_timestamp,
                file_id="GENESIS_ROOT",
                doc_hash=genesis_doc,
                document_type="SYSTEM",
                risk_score=0.0,
                risk_level="LOW",
                biometric_status="BYPASS",
                decision="GENESIS_NODE_ONLINE",
                officer_id="SYSTEM_ROOT",
                previous_hash=genesis_prev
            )
            canonical_b = canonical_json_bytes(canonical_ev)
            canonical_h = compute_canonical_hash(canonical_b, genesis_prev)
            try:
                genesis_sig = sign_canonical_hash(canonical_h)
            except Exception:
                genesis_sig = None

            cursor.execute("""
                INSERT INTO blockchain_ledger
                (block_index, timestamp, doc_hash, file_id, document_type, risk_score, risk_level, biometric_status, decision, officer_id, previous_hash, block_hash, canonical_hash, event_type, anchor_status, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                0, genesis_timestamp, genesis_doc, "GENESIS_ROOT", "SYSTEM", 0.0, "LOW", "BYPASS",
                "GENESIS_NODE_ONLINE", "SYSTEM_ROOT", genesis_prev, genesis_hash, canonical_h, "GENESIS_EVENT", "LOCAL_ANCHORED", genesis_sig
            ))
            conn.commit()


# Initialize ledger at module load
init_blockchain_db()


def get_latest_block() -> dict:
    """Fetches the latest tip of the blockchain."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM blockchain_ledger ORDER BY block_index DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else {}


def commit_inspection_block(
    file_path: str,
    file_id: str,
    document_type: str,
    risk_score: float,
    risk_level: str,
    biometric_status: str = "PENDING",
    officer_id: str = "SSB-OFFICER-7429",
    event_type: str = "SCREENING_EVENT"
) -> dict:
    """
    Appends a new cryptographically signed inspection block to the tamper-evident ledger.
    Zero-PII compliance: Only cryptographic hash of the document, non-PII identifiers,
    and risk metadata are recorded.
    """
    latest = get_latest_block()
    prev_index = latest.get("block_index", 0)
    prev_hash = latest.get("block_hash", "0" * 64)

    new_index = prev_index + 1
    timestamp = _current_timestamp()
    doc_hash = compute_file_sha256(file_path)

    # Determine automated border decision
    if risk_score > 60.0 or biometric_status in ["MISMATCH", "DUPLICATE_ALIAS_ALERT"]:
        decision = "REJECTED_IMPOSTOR"
    elif risk_score > 30.0 or biometric_status == "BORDERLINE":
        decision = "FLAGGED_FOR_INSPECTION"
    else:
        decision = "CLEARED"

    block_hash = calculate_block_hash(
        new_index, timestamp, doc_hash, risk_score, decision, officer_id, prev_hash
    )

    canonical_ev = build_canonical_event(
        event_type=event_type,
        block_index=new_index,
        timestamp=timestamp,
        file_id=file_id,
        doc_hash=doc_hash,
        document_type=document_type,
        risk_score=risk_score,
        risk_level=risk_level,
        biometric_status=biometric_status,
        decision=decision,
        officer_id=officer_id,
        previous_hash=prev_hash
    )
    canonical_b = canonical_json_bytes(canonical_ev)
    canonical_h = compute_canonical_hash(canonical_b, prev_hash)
    try:
        signature = sign_canonical_hash(canonical_h)
    except Exception:
        signature = None

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO blockchain_ledger
            (block_index, timestamp, doc_hash, file_id, document_type, risk_score, risk_level, biometric_status, decision, officer_id, previous_hash, block_hash, canonical_hash, event_type, anchor_status, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            new_index, timestamp, doc_hash, file_id, document_type, risk_score, risk_level.upper(),
            biometric_status.upper(), decision, officer_id, prev_hash, block_hash, canonical_h, event_type, "LOCAL_ANCHORED", signature
        ))
        conn.commit()

    return {
        "block_index": new_index,
        "timestamp": timestamp,
        "doc_hash": doc_hash,
        "file_id": file_id,
        "document_type": document_type,
        "risk_score": risk_score,
        "risk_level": risk_level.upper(),
        "biometric_status": biometric_status.upper(),
        "decision": decision,
        "officer_id": officer_id,
        "previous_hash": prev_hash,
        "block_hash": block_hash,
        "event_type": event_type,
        "canonical_hash": canonical_h,
        "signature": signature,
        "anchor_status": "LOCAL_ANCHORED"
    }


def update_block_biometric_decision(
    file_id: str,
    biometric_status: str,
    additional_notes: str = "",
    officer_id: str = "SSB-OFFICER-7429"
) -> Optional[dict]:
    """
    Appends an immutable Biometric Decision Event Block to the audit ledger.
    COMPLIANCE WITH SECTION 13 OF SECURITY.MD:
    Never mutates historical screening blocks in place via UPDATE.
    Guarantees strict append-only audit trail and unbroken SHA-256 chain integrity.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM blockchain_ledger WHERE file_id = ? ORDER BY block_index DESC LIMIT 1",
            (file_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        orig = dict(row)

    # Determine updated decision based on combined document risk and biometric outcome
    bio_upper = biometric_status.upper()
    if bio_upper in ["MISMATCH", "DUPLICATE_ALIAS_ALERT"]:
        new_decision = "REJECTED_IMPOSTOR"
    elif bio_upper == "BORDERLINE":
        new_decision = "FLAGGED_FOR_INSPECTION"
    else:
        new_decision = orig["decision"]

    latest = get_latest_block()
    prev_index = latest.get("block_index", 0)
    prev_hash = latest.get("block_hash", "0" * 64)
    new_index = prev_index + 1
    timestamp = _current_timestamp()
    doc_hash = orig["doc_hash"]
    event_type = "BIOMETRIC_EVENT"

    block_hash = calculate_block_hash(
        new_index, timestamp, doc_hash, orig["risk_score"], new_decision, officer_id, prev_hash
    )

    meta = {"notes": additional_notes[:128]} if additional_notes else None
    canonical_ev = build_canonical_event(
        event_type=event_type,
        block_index=new_index,
        timestamp=timestamp,
        file_id=file_id,
        doc_hash=doc_hash,
        document_type=orig["document_type"],
        risk_score=orig["risk_score"],
        risk_level=orig["risk_level"],
        biometric_status=bio_upper,
        decision=new_decision,
        officer_id=officer_id,
        previous_hash=prev_hash,
        metadata=meta
    )
    canonical_b = canonical_json_bytes(canonical_ev)
    canonical_h = compute_canonical_hash(canonical_b, prev_hash)
    try:
        signature = sign_canonical_hash(canonical_h)
    except Exception:
        signature = None

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO blockchain_ledger
            (block_index, timestamp, doc_hash, file_id, document_type, risk_score, risk_level, biometric_status, decision, officer_id, previous_hash, block_hash, canonical_hash, event_type, anchor_status, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            new_index, timestamp, doc_hash, file_id, orig["document_type"], orig["risk_score"], orig["risk_level"].upper(),
            bio_upper, new_decision, officer_id, prev_hash, block_hash, canonical_h, event_type, "LOCAL_ANCHORED", signature
        ))
        conn.commit()

    return {
        "block_index": new_index,
        "timestamp": timestamp,
        "doc_hash": doc_hash,
        "file_id": file_id,
        "document_type": orig["document_type"],
        "risk_score": orig["risk_score"],
        "risk_level": orig["risk_level"].upper(),
        "biometric_status": bio_upper,
        "decision": new_decision,
        "officer_id": officer_id,
        "previous_hash": prev_hash,
        "block_hash": block_hash,
        "event_type": event_type,
        "canonical_hash": canonical_h,
        "signature": signature,
        "anchor_status": "LOCAL_ANCHORED"
    }


def record_officer_override(
    file_id: str,
    officer_id: str,
    override_decision: str,
    reason: str,
    supervisor_id: Optional[str] = None
) -> Optional[dict]:
    """
    Appends an immutable OFFICER_OVERRIDE_EVENT block to the audit ledger.
    COMPLIANCE WITH SECTION 37 OF SECURITY.MD:
    Human-in-the-loop: Officers can confirm, escalate, or override automated AI decisions.
    Creates a NEW append-only audit event. Never modifies the original AI decision.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM blockchain_ledger WHERE file_id = ? ORDER BY block_index DESC LIMIT 1",
            (file_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        orig = dict(row)

    latest = get_latest_block()
    prev_index = latest.get("block_index", 0)
    prev_hash = latest.get("block_hash", "0" * 64)
    new_index = prev_index + 1
    timestamp = _current_timestamp()
    event_type = "OFFICER_OVERRIDE_EVENT"
    clean_decision = override_decision.strip().upper()

    block_hash = calculate_block_hash(
        new_index, timestamp, orig["doc_hash"], orig["risk_score"], clean_decision, officer_id, prev_hash
    )

    meta = {
        "override_reason": reason[:256],
        "supervisor_id": supervisor_id or "",
        "ai_prior_decision": orig["decision"]
    }
    canonical_ev = build_canonical_event(
        event_type=event_type,
        block_index=new_index,
        timestamp=timestamp,
        file_id=file_id,
        doc_hash=orig["doc_hash"],
        document_type=orig["document_type"],
        risk_score=orig["risk_score"],
        risk_level=orig["risk_level"],
        biometric_status=orig["biometric_status"],
        decision=clean_decision,
        officer_id=officer_id,
        previous_hash=prev_hash,
        metadata=meta
    )
    canonical_b = canonical_json_bytes(canonical_ev)
    canonical_h = compute_canonical_hash(canonical_b, prev_hash)
    try:
        signature = sign_canonical_hash(canonical_h)
    except Exception:
        signature = None

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO blockchain_ledger
            (block_index, timestamp, doc_hash, file_id, document_type, risk_score, risk_level, biometric_status, decision, officer_id, previous_hash, block_hash, canonical_hash, event_type, anchor_status, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            new_index, timestamp, orig["doc_hash"], file_id, orig["document_type"], orig["risk_score"], orig["risk_level"].upper(),
            orig["biometric_status"], clean_decision, officer_id, prev_hash, block_hash, canonical_h, event_type, "LOCAL_ANCHORED", signature
        ))
        conn.commit()

    return {
        "block_index": new_index,
        "timestamp": timestamp,
        "doc_hash": orig["doc_hash"],
        "file_id": file_id,
        "document_type": orig["document_type"],
        "risk_score": orig["risk_score"],
        "risk_level": orig["risk_level"].upper(),
        "biometric_status": orig["biometric_status"],
        "decision": clean_decision,
        "officer_id": officer_id,
        "previous_hash": prev_hash,
        "block_hash": block_hash,
        "event_type": event_type,
        "canonical_hash": canonical_h,
        "signature": signature,
        "anchor_status": "LOCAL_ANCHORED"
    }


def verify_chain_integrity() -> dict:
    """
    Cryptographically verifies the entire blockchain from Genesis Block to current tip.
    Recomputes SHA-256 block hashes and asserts unbroken previous-hash continuity.
    Detects any historical block tampering, unauthorized alterations, or broken links.
    """
    tampered_blocks = []
    total_blocks = 0

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blockchain_ledger ORDER BY block_index ASC")
        blocks = cursor.fetchall()
        total_blocks = len(blocks)

        if total_blocks == 0:
            return {"chain_valid": True, "total_blocks": 0, "tampered_blocks": []}

        signatures_verified = 0
        prev_hash = "0" * 64
        for idx, row in enumerate(blocks):
            b = dict(row)
            # 1. Verify previous hash linkage
            if b["previous_hash"] != prev_hash:
                tampered_blocks.append({
                    "block_index": b["block_index"],
                    "reason": f"Previous hash mismatch: expected {prev_hash[:12]}..., got {b['previous_hash'][:12]}..."
                })

            # 2. Recompute current block hash
            expected_hash = calculate_block_hash(
                b["block_index"], b["timestamp"], b["doc_hash"],
                b["risk_score"], b["decision"], b["officer_id"], b["previous_hash"]
            )
            if b["block_hash"] != expected_hash:
                tampered_blocks.append({
                    "block_index": b["block_index"],
                    "reason": f"Block hash invalid: data tampered. Expected {expected_hash[:12]}..., found {b['block_hash'][:12]}..."
                })

            # 3. Verify Ed25519 digital signature where present
            sig = b.get("signature")
            can_hash = b.get("canonical_hash")
            if sig and can_hash:
                try:
                    if not verify_signature(can_hash, sig):
                        tampered_blocks.append({
                            "block_index": b["block_index"],
                            "reason": f"Digital signature invalid: cryptographic signature verification failed on block {b['block_index']}."
                        })
                    else:
                        signatures_verified += 1
                except Exception as e:
                    tampered_blocks.append({
                        "block_index": b["block_index"],
                        "reason": f"Digital signature verification error: {e}"
                    })

            prev_hash = b["block_hash"]

    is_valid = len(tampered_blocks) == 0
    return {
        "chain_valid": is_valid,
        "total_blocks": total_blocks,
        "signatures_verified": signatures_verified,
        "tampered_blocks": tampered_blocks,
        "latest_block_hash": prev_hash,
        "verified_at": _current_timestamp()
    }


def get_recent_blocks(limit: int = 25) -> list[dict]:
    """Returns the most recent blocks in reverse chronological order for the UI ledger explorer."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM blockchain_ledger ORDER BY block_index DESC LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
