"""
Unit tests for Phase 8: Append-Only Audit Event Architecture.
Tests:
- Deterministic RFC 8785 canonical JSON serialization
- Append-only event chaining: SCREENING_EVENT -> BIOMETRIC_EVENT -> OFFICER_OVERRIDE_EVENT
- Immutability preservation (screening block not mutated in-place)
- Full cryptographic chain verification
- Accurate tamper detection when records are manipulated
- Zero PII inclusion in canonical audit event dictionaries
"""

import os
import sys
import json
import sqlite3
import unittest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from modules.blockchain import (
    commit_inspection_block,
    update_block_biometric_decision,
    record_officer_override,
    verify_chain_integrity,
    canonical_json_bytes,
    build_canonical_event,
    calculate_block_hash,
    DB_PATH
)


class TestAuditLedgerPhase8(unittest.TestCase):

    def test_canonical_json_serialization_rfc8785(self):
        """Verify canonical serialization sorts keys deterministically and uses compact separators."""
        data = {
            "zebra": 1,
            "alpha": "hello",
            "middle": {"charlie": True, "bravo": 12.34}
        }
        b = canonical_json_bytes(data)
        s = b.decode("utf-8")

        # Compact: no spaces after colons or commas
        self.assertNotIn(": ", s)
        self.assertNotIn(", ", s)

        # Keys ordered lexicographically
        expected = '{"alpha":"hello","middle":{"bravo":12.34,"charlie":true},"zebra":1}'
        self.assertEqual(s, expected)

    def test_zero_pii_in_canonical_event(self):
        """Verify canonical audit event strictly excludes traveler PII."""
        event = build_canonical_event(
            event_type="SCREENING_EVENT",
            block_index=1,
            timestamp="2026-09-17T12:00:00Z",
            file_id="session-uuid-1234",
            doc_hash="a" * 64,
            document_type="PASSPORT",
            risk_score=22.5,
            risk_level="LOW",
            biometric_status="PENDING",
            decision="CLEARED",
            officer_id="SSB-OFFICER-7429",
            previous_hash="0" * 64,
            metadata={
                "name": "VIKRAM SINGH",  # Must be stripped!
                "passport_number": "P1234567",  # Must be stripped!
                "station": "ICP-RAXAUL"  # Safe primitive allowed
            }
        )
        canonical_str = json.dumps(event)
        self.assertNotIn("VIKRAM SINGH", canonical_str)
        self.assertNotIn("P1234567", canonical_str)
        self.assertEqual(event["event_type"], "SCREENING_EVENT")
        self.assertEqual(event["block_index"], 1)

    def test_append_only_event_chaining_and_immutability(self):
        """
        Verify:
        1. SCREENING_EVENT commits block N
        2. BIOMETRIC_EVENT appends block N+1 (does NOT mutate block N)
        3. OFFICER_OVERRIDE_EVENT appends block N+2
        4. Previous block hashes form unbroken cryptographic chain
        """
        session_id = f"test-p8-session-{os.urandom(4).hex()}"

        # 1. Commit screening block
        b_screen = commit_inspection_block(
            file_path=os.path.abspath(__file__),
            file_id=session_id,
            document_type="PASSPORT",
            risk_score=18.0,
            risk_level="LOW",
            biometric_status="PENDING",
            officer_id="SSB-OFFICER-7429"
        )
        idx_screen = b_screen["block_index"]
        hash_screen = b_screen["block_hash"]
        self.assertEqual(b_screen["event_type"], "SCREENING_EVENT")
        self.assertEqual(b_screen["decision"], "CLEARED")

        # 2. Append biometric decision block
        b_bio = update_block_biometric_decision(
            file_id=session_id,
            biometric_status="MISMATCH",
            additional_notes="Face does not match document photo",
            officer_id="SSB-OFFICER-7429"
        )
        self.assertIsNotNone(b_bio)
        idx_bio = b_bio["block_index"]
        hash_bio = b_bio["block_hash"]
        self.assertEqual(idx_bio, idx_screen + 1)
        self.assertEqual(b_bio["event_type"], "BIOMETRIC_EVENT")
        self.assertEqual(b_bio["previous_hash"], hash_screen)
        self.assertEqual(b_bio["decision"], "REJECTED_IMPOSTOR")

        # Verify block N (screening) remains UNCHANGED in SQLite
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT decision, biometric_status FROM blockchain_ledger WHERE block_index = ?", (idx_screen,))
            row = c.fetchone()
            self.assertEqual(row[0], "CLEARED")
            self.assertEqual(row[1], "PENDING")

        # 3. Append officer override event
        b_override = record_officer_override(
            file_id=session_id,
            officer_id="SSB-SUPERVISOR-1001",
            override_decision="FLAGGED_FOR_INSPECTION",
            reason="Subject requested secondary manual passport interview",
            supervisor_id="SSB-SUPERVISOR-1001"
        )
        self.assertIsNotNone(b_override)
        idx_override = b_override["block_index"]
        self.assertEqual(idx_override, idx_bio + 1)
        self.assertEqual(b_override["event_type"], "OFFICER_OVERRIDE_EVENT")
        self.assertEqual(b_override["previous_hash"], hash_bio)
        self.assertEqual(b_override["decision"], "FLAGGED_FOR_INSPECTION")

        # 4. Verify full chain validity
        report = verify_chain_integrity()
        self.assertTrue(report["chain_valid"])
        self.assertEqual(len(report["tampered_blocks"]), 0)

    def test_tamper_detection(self):
        """Verify that any database mutation breaks chain integrity and flags the exact index."""
        # Find the latest block
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT block_index, decision FROM blockchain_ledger ORDER BY block_index DESC LIMIT 1")
            row = c.fetchone()
            target_idx, original_decision = row

            # Tamper the decision field
            tampered_val = "UNAUTHORIZED_CHANGE"
            c.execute("UPDATE blockchain_ledger SET decision = ? WHERE block_index = ?", (tampered_val, target_idx))
            conn.commit()

        try:
            # Verification must detect the tampering
            tamper_report = verify_chain_integrity()
            self.assertFalse(tamper_report["chain_valid"])
            tampered_indices = [t["block_index"] for t in tamper_report["tampered_blocks"]]
            self.assertIn(target_idx, tampered_indices)
        finally:
            # Revert the change so subsequent test runs pass
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute("UPDATE blockchain_ledger SET decision = ? WHERE block_index = ?", (original_decision, target_idx))
                conn.commit()

        # Confirm restored state
        restored = verify_chain_integrity()
        self.assertTrue(restored["chain_valid"])

    def test_officer_override_endpoint_rbac(self):
        """Verify /api/ledger/override endpoint enforces RBAC permissions."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        session_id = f"test-rbac-override-{os.urandom(4).hex()}"

        # First commit a screening block
        commit_inspection_block(
            file_path=os.path.abspath(__file__),
            file_id=session_id,
            document_type="PASSPORT",
            risk_score=75.0,
            risk_level="HIGH",
            biometric_status="PENDING",
            officer_id="SSB-OFFICER-7429"
        )

        # 1. SCREENING_OFFICER attempt must fail with 403
        resp_officer = client.post(
            "/api/ledger/override",
            data={"file_id": session_id, "decision": "CLEARED", "reason": "Officer override attempt"},
            headers={"X-Officer-Role": "SCREENING_OFFICER", "X-Officer-Id": "SSB-OFFICER-7429"}
        )
        self.assertEqual(resp_officer.status_code, 403)

        # 2. SUPERVISOR attempt must succeed with 200 and return blockchain receipt
        resp_sup = client.post(
            "/api/ledger/override",
            data={"file_id": session_id, "decision": "CLEARED", "reason": "Valid diplomatic pass presented"},
            headers={"X-Officer-Role": "SUPERVISOR", "X-Officer-Id": "SSB-SUPERVISOR-001"}
        )
        self.assertEqual(resp_sup.status_code, 200)
        data = resp_sup.json()
        self.assertEqual(data["status"], "override_recorded")
        self.assertEqual(data["blockchain_receipt"]["decision"], "CLEARED")
        self.assertEqual(data["blockchain_receipt"]["event_type"], "OFFICER_OVERRIDE_EVENT")


if __name__ == "__main__":
    unittest.main()
