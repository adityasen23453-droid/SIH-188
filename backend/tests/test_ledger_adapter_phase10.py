"""
Unit tests for Phase 10: Local Cryptographic Ledger Adapter.
Tests:
- AuditLedger abstract interface and LocalCryptographicLedger implementation
- Honest terminology metadata (Section 12: Cryptographically Chained Audit Ledger)
- End-to-end ledger lifecycle via adapter interface
- Chain integrity verification via adapter
- API endpoint integration: /api/ledger/blocks, /api/ledger/verify, /api/ledger/info
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from modules.ledger_adapter import get_audit_ledger, AuditLedger, LocalCryptographicLedger
from main import app


class TestLedgerAdapterPhase10(unittest.TestCase):

    def setUp(self):
        self.ledger = get_audit_ledger()
        self.client = TestClient(app)

    def test_audit_ledger_factory_instance(self):
        """Verify factory provides AuditLedger and LocalCryptographicLedger singleton."""
        self.assertIsInstance(self.ledger, AuditLedger)
        self.assertIsInstance(self.ledger, LocalCryptographicLedger)

    def test_adapter_info_metadata(self):
        """Verify get_adapter_info returns honest sovereign nomenclature compliant with Section 12."""
        info = self.ledger.get_adapter_info()
        self.assertEqual(info["adapter_name"], "LocalCryptographicLedger")
        self.assertEqual(info["ledger_type"], "LOCAL_DEMO_LEDGER")
        self.assertEqual(info["designation"], "Cryptographically Chained Audit Ledger")
        self.assertEqual(info["anchor_status"], "LOCAL_ANCHORED")
        self.assertEqual(info["hash_algorithm"], "SHA-256 Merkle-Chained")
        self.assertEqual(info["signature_algorithm"], "Ed25519 (RFC 8032)")
        self.assertEqual(info["canonical_serialization"], "RFC 8785 (JCS)")
        self.assertTrue(info["zero_pii_enforced"])

    def test_adapter_block_lifecycle(self):
        """Verify full screening -> biometric -> override lifecycle through adapter."""
        session_id = f"test-p10-session-{os.urandom(4).hex()}"

        # 1. Commit inspection block
        b1 = self.ledger.commit_inspection_block(
            file_path=os.path.abspath(__file__),
            file_id=session_id,
            document_type="PASSPORT",
            risk_score=15.0,
            risk_level="LOW",
            biometric_status="PENDING",
            officer_id="SSB-OFFICER-7429"
        )
        self.assertEqual(b1["file_id"], session_id)
        self.assertEqual(b1["decision"], "CLEARED")
        self.assertEqual(b1["event_type"], "SCREENING_EVENT")
        self.assertIsNotNone(b1.get("signature"))

        # 2. Update biometric decision
        b2 = self.ledger.update_biometric_decision(
            file_id=session_id,
            biometric_status="BORDERLINE",
            additional_notes="Low lighting capture",
            officer_id="SSB-OFFICER-7429"
        )
        self.assertIsNotNone(b2)
        self.assertEqual(b2["event_type"], "BIOMETRIC_EVENT")
        self.assertEqual(b2["decision"], "FLAGGED_FOR_INSPECTION")
        self.assertEqual(b2["previous_hash"], b1["block_hash"])

        # 3. Override decision
        b3 = self.ledger.record_officer_override(
            file_id=session_id,
            officer_id="SSB-SUPERVISOR-001",
            override_decision="CLEARED",
            reason="Secondary physical passport inspected and verified"
        )
        self.assertIsNotNone(b3)
        self.assertEqual(b3["event_type"], "OFFICER_OVERRIDE_EVENT")
        self.assertEqual(b3["decision"], "CLEARED")
        self.assertEqual(b3["previous_hash"], b2["block_hash"])

    def test_adapter_verify_integrity(self):
        """Verify verify_integrity through adapter returns valid chain and signature counts."""
        report = self.ledger.verify_integrity()
        self.assertTrue(report["chain_valid"])
        self.assertGreaterEqual(report["total_blocks"], 1)
        self.assertIn("signatures_verified", report)
        self.assertEqual(len(report["tampered_blocks"]), 0)

    def test_api_ledger_blocks_endpoint(self):
        """Verify /api/ledger/blocks preserves schema for frontend consumption."""
        resp = self.client.get("/api/ledger/blocks?limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_returned", data)
        self.assertIn("blocks", data)
        self.assertIsInstance(data["blocks"], list)
        self.assertGreaterEqual(len(data["blocks"]), 1)

        tip = data["blocks"][0]
        self.assertIn("block_index", tip)
        self.assertIn("block_hash", tip)
        self.assertIn("doc_hash", tip)
        self.assertIn("timestamp", tip)
        self.assertIn("decision", tip)

    def test_api_ledger_verify_endpoint(self):
        """Verify /api/ledger/verify returns cryptographic audit report."""
        resp = self.client.get("/api/ledger/verify")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("chain_valid", data)
        self.assertTrue(data["chain_valid"])
        self.assertIn("total_blocks", data)
        self.assertIn("tampered_blocks", data)

    def test_api_ledger_info_endpoint(self):
        """Verify /api/ledger/info exposes adapter designation to frontend/auditors."""
        resp = self.client.get("/api/ledger/info")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["designation"], "Cryptographically Chained Audit Ledger")
        self.assertEqual(data["adapter_name"], "LocalCryptographicLedger")
        self.assertEqual(data["anchor_status"], "LOCAL_ANCHORED")


if __name__ == "__main__":
    unittest.main()

