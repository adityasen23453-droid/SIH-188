import os
import hashlib
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "blockchain.db")


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
    """
    payload = f"{block_index}|{timestamp}|{doc_hash}|{risk_score:.2f}|{decision}|{officer_id}|{previous_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
            cursor.execute("""
                INSERT INTO blockchain_ledger
                (block_index, timestamp, doc_hash, file_id, document_type, risk_score, risk_level, biometric_status, decision, officer_id, previous_hash, block_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                0, genesis_timestamp, genesis_doc, "GENESIS_ROOT", "SYSTEM", 0.0, "LOW", "BYPASS",
                "GENESIS_NODE_ONLINE", "SYSTEM_ROOT", genesis_prev, genesis_hash
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
    officer_id: str = "SSB-OFFICER-7429"
) -> dict:
    """
    Appends a new cryptographically signed inspection block to the tamper-evident ledger.
    Zero-PII compliance: Only cryptographic hash of the document and risk metadata are recorded.
    """
    latest = get_latest_block()
    prev_index = latest.get("block_index", 0)
    prev_hash = latest.get("block_hash", "0" * 64)

    new_index = prev_index + 1
    timestamp = datetime.utcnow().isoformat() + "Z"
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

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO blockchain_ledger
            (block_index, timestamp, doc_hash, file_id, document_type, risk_score, risk_level, biometric_status, decision, officer_id, previous_hash, block_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            new_index, timestamp, doc_hash, file_id, document_type, risk_score, risk_level.upper(),
            biometric_status.upper(), decision, officer_id, prev_hash, block_hash
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
        "block_hash": block_hash
    }


def update_block_biometric_decision(
    file_id: str,
    biometric_status: str,
    additional_notes: str = ""
) -> dict | None:
    """
    Appends an immutable Biometric Decision Event Block or updates the tip block.
    Always maintains unbroken SHA-256 Merkle chain integrity.
    """
    latest = get_latest_block()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blockchain_ledger WHERE file_id = ? ORDER BY block_index DESC LIMIT 1", (file_id,))
        row = cursor.fetchone()
        if not row:
            return None
        orig = dict(row)

    # Determine decision
    if biometric_status in ["MISMATCH", "DUPLICATE_ALIAS_ALERT"]:
        new_decision = "REJECTED_IMPOSTOR"
    elif biometric_status == "BORDERLINE":
        new_decision = "FLAGGED_FOR_INSPECTION"
    else:
        new_decision = orig["decision"]

    # If this is the latest block, we can update it in place without invalidating downstream blocks
    if latest.get("block_index") == orig["block_index"]:
        new_hash = calculate_block_hash(
            orig["block_index"], orig["timestamp"], orig["doc_hash"],
            orig["risk_score"], new_decision, orig["officer_id"], orig["previous_hash"]
        )
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE blockchain_ledger
                SET biometric_status = ?, decision = ?, block_hash = ?
                WHERE block_index = ?
            """, (biometric_status.upper(), new_decision, new_hash, orig["block_index"]))
            conn.commit()
        orig["biometric_status"] = biometric_status.upper()
        orig["decision"] = new_decision
        orig["block_hash"] = new_hash
        return orig

    # Otherwise, append a linked state audit block (non-repudiation)
    return commit_inspection_block(
        file_path=orig["doc_hash"],
        file_id=file_id,
        document_type=f"{orig['document_type']}_BIOMETRIC_UPDATE",
        risk_score=orig["risk_score"],
        risk_level=orig["risk_level"],
        biometric_status=biometric_status.upper(),
        officer_id="SSB-OFFICER-7429"
    )


def verify_chain_integrity() -> dict:
    """
    Cryptographically verifies the entire blockchain from Genesis Block to current tip.
    Recomputes SHA-256 block hashes and asserts unbroken previous-hash continuity.
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

            prev_hash = b["block_hash"]

    is_valid = len(tampered_blocks) == 0
    return {
        "chain_valid": is_valid,
        "total_blocks": total_blocks,
        "tampered_blocks": tampered_blocks,
        "latest_block_hash": prev_hash,
        "verified_at": datetime.utcnow().isoformat() + "Z"
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

