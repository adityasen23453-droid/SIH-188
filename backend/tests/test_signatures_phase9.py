"""
Unit tests for Phase 9: Sovereign Ed25519 Digital Signatures for Audit Events.
Tests:
- Key derivation and public key export (RFC 8032)
- Canonical hash signing and signature verification
- Tamper detection on payload and signature bytes
- End-to-end block commitment with valid Ed25519 signatures
- Biometric and Officer Override event signature verification
- Chain integrity verification of Ed25519 signatures
- Tamper detection when a signature is corrupted in SQLite
"""

import os
import sys
import sqlite3
import unittest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.signatures import (
    sign_canonical_hash,
    verify_signature,
    get_station_public_key_hex,
    generate_station_keypair,
    SIGNATURE_PREFIX
)
from modules.blockchain import (
    commit_inspection_block,
    update_block_biometric_decision,
    record_officer_override,
    verify_chain_integrity,
    DB_PATH
)


class TestDigitalSignaturesPhase9(unittest.TestCase):

    def test_station_public_key_derivation(self):
        """Verify station public key is derived deterministically and has 64-char hex format."""
        pub_hex = get_station_public_key_hex()
        self.assertEqual(len(pub_hex), 64)
        self.assertTrue(all(c in "0123456789abcdefABCDEF" for c in pub_hex))

    def test_canonical_hash_signing_and_verification(self):
        """Verify signing a 64-char canonical hash produces valid Ed25519 signature."""
        test_hash = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
        sig = sign_canonical_hash(test_hash)

        self.assertTrue(sig.startswith(SIGNATURE_PREFIX))
        raw_hex = sig[len(SIGNATURE_PREFIX):]
        self.assertEqual(len(raw_hex), 128)  # 64 bytes = 128 hex chars

        # Verification with station public key must pass
        self.assertTrue(verify_signature(test_hash, sig))

    def test_tampered_payload_fails_verification(self):
        """Verify that altering even a single character in the canonical hash causes verification failure."""
        test_hash = "1111111111111111111111111111111111111111111111111111111111111111"
        sig = sign_canonical_hash(test_hash)

        # Alter hash
        tampered_hash = "1111111111111111111111111111111111111111111111111111111111111112"
        self.assertFalse(verify_signature(tampered_hash, sig))

    def test_tampered_signature_bytes_fails(self):
        """Verify that modifying signature bytes fails verification."""
        test_hash = "2222222222222222222222222222222222222222222222222222222222222222"
        sig = sign_canonical_hash(test_hash)

        # Invert last two hex digits of signature
        prefix = SIGNATURE_PREFIX
        raw_hex = sig[len(prefix):]
        corrupted_hex = raw_hex[:-2] + ("00" if raw_hex[-2:] != "00" else "ff")
        corrupted_sig = prefix + corrupted_hex

        self.assertFalse(verify_signature(test_hash, corrupted_sig))

    def test_generate_station_keypair(self):
        """Verify keypair generator creates valid 64-char hex key representations."""
        priv_hex, pub_hex = generate_station_keypair()
        self.assertEqual(len(priv_hex), 64)
        self.assertEqual(len(pub_hex), 64)
        self.assertNotEqual(priv_hex, pub_hex)

    def test_block_commit_carries_valid_signature(self):
        """Verify commit_inspection_block signs the canonical hash and stores it in SQLite."""
        session_id = f"test-p9-session-{os.urandom(4).hex()}"
        block = commit_inspection_block(
            file_path=os.path.abspath(__file__),
            file_id=session_id,
            document_type="PASSPORT",
            risk_score=14.0,
            risk_level="LOW",
            biometric_status="PENDING",
            officer_id="SSB-OFFICER-7429"
        )

        self.assertIn("signature", block)
        self.assertIsNotNone(block["signature"])
        self.assertTrue(block["signature"].startswith(SIGNATURE_PREFIX))

        # Verify signature against the block's canonical hash
        self.assertTrue(verify_signature(block["canonical_hash"], block["signature"]))

        # Verify stored in SQLite
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT signature, canonical_hash FROM blockchain_ledger WHERE block_index = ?", (block["block_index"],))
            row = c.fetchone()
            self.assertEqual(row[0], block["signature"])
            self.assertEqual(row[1], block["canonical_hash"])

    def test_biometric_and_override_signatures(self):
        """Verify chained BIOMETRIC_EVENT and OFFICER_OVERRIDE_EVENT blocks carry valid signatures."""
        session_id = f"test-p9-chain-{os.urandom(4).hex()}"

        # 1. Screening
        b1 = commit_inspection_block(
            file_path=os.path.abspath(__file__),
            file_id=session_id,
            document_type="PASSPORT",
            risk_score=20.0,
            risk_level="LOW",
            biometric_status="PENDING",
            officer_id="SSB-OFFICER-7429"
        )
        self.assertTrue(verify_signature(b1["canonical_hash"], b1["signature"]))

        # 2. Biometric
        b2 = update_block_biometric_decision(
            file_id=session_id,
            biometric_status="MATCH",
            additional_notes="Biometric verification confirmed",
            officer_id="SSB-OFFICER-7429"
        )
        self.assertIsNotNone(b2)
        self.assertTrue(verify_signature(b2["canonical_hash"], b2["signature"]))

        # 3. Override
        b3 = record_officer_override(
            file_id=session_id,
            officer_id="SSB-SUPERVISOR-001",
            override_decision="CLEARED",
            reason="Senior review cleared secondary check",
            supervisor_id="SSB-SUPERVISOR-001"
        )
        self.assertIsNotNone(b3)
        self.assertTrue(verify_signature(b3["canonical_hash"], b3["signature"]))

    def test_chain_integrity_verifies_signatures(self):
        """Verify that verify_chain_integrity counts and validates Ed25519 signatures."""
        report = verify_chain_integrity()
        self.assertTrue(report["chain_valid"])
        self.assertIn("signatures_verified", report)
        self.assertGreater(report["signatures_verified"], 0)

    def test_signature_tamper_detection_in_db(self):
        """Verify that altering a block's signature directly in SQLite causes chain verification failure."""
        session_id = f"test-p9-tamper-{os.urandom(4).hex()}"
        block = commit_inspection_block(
            file_path=os.path.abspath(__file__),
            file_id=session_id,
            document_type="PASSPORT",
            risk_score=10.0,
            risk_level="LOW",
            biometric_status="PENDING",
            officer_id="SSB-OFFICER-7429"
        )
        block_idx = block["block_index"]
        original_sig = block["signature"]

        # Corrupt the signature in DB
        corrupted_sig = SIGNATURE_PREFIX + "0" * 128
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("UPDATE blockchain_ledger SET signature = ? WHERE block_index = ?", (corrupted_sig, block_idx))
            conn.commit()

        try:
            tamper_report = verify_chain_integrity()
            self.assertFalse(tamper_report["chain_valid"])
            tampered_indices = [t["block_index"] for t in tamper_report["tampered_blocks"]]
            self.assertIn(block_idx, tampered_indices)
        finally:
            # Restore original signature
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute("UPDATE blockchain_ledger SET signature = ? WHERE block_index = ?", (original_sig, block_idx))
                conn.commit()

        # Confirm restored state
        restored = verify_chain_integrity()
        self.assertTrue(restored["chain_valid"])


if __name__ == "__main__":
    unittest.main()

