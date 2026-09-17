"""
Unit tests for Phase 11: Permissioned Blockchain Adapter Architecture.
Tests:
- PermissionedLedgerAdapter initialization and metadata
- Offline-first resilience: local cryptographic commit and spooling under network outage
- Graceful degradation: marks records as ANCHOR_PENDING without halting screening
- Asynchronous spool flushing to NBF_ANCHORED
- API endpoint integration: GET /api/ledger/anchor-status/{id}, POST /api/ledger/sync
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from modules.ledger_adapter import (
    PermissionedLedgerAdapter,
    LocalCryptographicLedger,
    AuditLedger
)
from main import app


class TestPermissionedAdapterPhase11(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.adapter = PermissionedLedgerAdapter(endpoint=None)

    def test_permissioned_adapter_hierarchy_and_metadata(self):
        """Verify PermissionedLedgerAdapter implements AuditLedger ABC and honest metadata."""
        self.assertIsInstance(self.adapter, AuditLedger)
        info = self.adapter.get_adapter_info()
        self.assertEqual(info["adapter_name"], "PermissionedLedgerAdapter")
        self.assertEqual(info["ledger_type"], "PERMISSIONED_DLT_STAGING")
        self.assertEqual(info["offline_resilience"], "LOCAL_SPOOL_FALLBACK_ACTIVE")
        self.assertTrue(info["zero_pii_enforced"])
        self.assertTrue(info["nbf_vishvasya_aligned"])

    def test_offline_resilience_and_anchor_pending_status(self):
        """
        Verify Section 30 & 32:
        Under remote network absence, screening completes without error,
        cryptographic hashes and signatures are recorded, and status is ANCHOR_PENDING.
        """
        session_id = f"test-p11-offline-{os.urandom(4).hex()}"
        block = self.adapter.commit_inspection_block(
            file_path=os.path.abspath(__file__),
            file_id=session_id,
            document_type="PASSPORT",
            risk_score=22.0,
            risk_level="LOW",
            biometric_status="PENDING",
            officer_id="SSB-OFFICER-7429"
        )

        self.assertIsNotNone(block)
        self.assertEqual(block["file_id"], session_id)
        self.assertEqual(block["anchor_status"], "ANCHOR_PENDING")
        self.assertIn("signature", block)
        self.assertIn("canonical_hash", block)
        self.assertGreater(len(self.adapter.pending_spool), 0)

        # Confirm chain integrity is intact locally
        report = self.adapter.verify_integrity()
        self.assertTrue(report["chain_valid"])

    def test_simulated_ledger_outage_graceful_degradation(self):
        """Verify that an unreachable endpoint fails gracefully to ANCHOR_PENDING without crashing."""
        outage_adapter = PermissionedLedgerAdapter(endpoint="mock://unreachable.border.gov.in:8545")
        session_id = f"test-p11-outage-{os.urandom(4).hex()}"

        block = outage_adapter.commit_inspection_block(
            file_path=os.path.abspath(__file__),
            file_id=session_id,
            document_type="PASSPORT",
            risk_score=35.0,
            risk_level="MEDIUM",
            biometric_status="PENDING",
            officer_id="SSB-OFFICER-7429"
        )
        self.assertEqual(block["anchor_status"], "ANCHOR_PENDING")
        self.assertFalse(outage_adapter.is_connected)

    def test_flush_pending_anchors(self):
        """Verify flushing the pending spool transitions blocks to NBF_ANCHORED."""
        session_id = f"test-p11-sync-{os.urandom(4).hex()}"
        self.adapter.commit_inspection_block(
            file_path=os.path.abspath(__file__),
            file_id=session_id,
            document_type="PASSPORT",
            risk_score=15.0,
            risk_level="LOW",
            biometric_status="PENDING",
            officer_id="SSB-OFFICER-7429"
        )
        initial_spool_len = len(self.adapter.pending_spool)
        self.assertGreaterEqual(initial_spool_len, 1)

        sync_result = self.adapter.flush_pending_anchors()
        self.assertEqual(sync_result["status"], "SYNCED")
        self.assertEqual(sync_result["synced_count"], initial_spool_len)
        self.assertEqual(len(self.adapter.pending_spool), 0)

        # Status in DB should now be NBF_ANCHORED
        status_info = self.adapter.get_anchor_status(session_id)
        self.assertEqual(status_info["anchor_status"], "NBF_ANCHORED")

    def test_api_anchor_status_endpoint(self):
        """Verify GET /api/ledger/anchor-status/{file_id} endpoint."""
        session_id = f"test-p11-api-{os.urandom(4).hex()}"
        # Commit a block
        self.adapter.commit_inspection_block(
            file_path=os.path.abspath(__file__),
            file_id=session_id,
            document_type="PASSPORT",
            risk_score=10.0,
            risk_level="LOW",
            biometric_status="PENDING",
            officer_id="SSB-OFFICER-7429"
        )

        resp = self.client.get(f"/api/ledger/anchor-status/{session_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["file_id"], session_id)
        self.assertIn("anchor_status", data)

    def test_api_sync_endpoint(self):
        """Verify POST /api/ledger/sync endpoint."""
        resp = self.client.post("/api/ledger/sync")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("status", data)


if __name__ == "__main__":
    unittest.main()

