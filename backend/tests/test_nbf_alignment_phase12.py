"""
Unit tests for Phase 12: National Blockchain Framework (NBF / Vishvasya Stack) Interface Alignment.
Complies with Sections 16, 17, 18, 30, and 32 of Security.md:
- Honest nomenclature: "Prototype adapter — Integration-ready (Not connected to production government network)"
- Zero fake endpoints or simulated claims of official government clearance
- Formats canonical zero-PII Vishvasya BaaS transaction envelopes
- Enforces pre-flight cryptographic and zero-PII compliance checks
- Offline-first resilience with local cryptographic commit and spooling
- API endpoint integration: GET /api/ledger/nbf-specification
"""

import os
import sys
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from modules.ledger_adapter import (
    NBFPermissionedLedgerAdapter,
    PermissionedLedgerAdapter,
    AuditLedger,
    get_audit_ledger
)
from core.signatures import get_station_public_key_hex
from main import app


class TestNBFAlignmentPhase12(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.adapter = NBFPermissionedLedgerAdapter(endpoint=None)

    def test_nbf_adapter_class_hierarchy_and_inheritance(self):
        """Verify NBFPermissionedLedgerAdapter correctly subclasses PermissionedLedgerAdapter and AuditLedger."""
        self.assertIsInstance(self.adapter, PermissionedLedgerAdapter)
        self.assertIsInstance(self.adapter, AuditLedger)
        self.assertEqual(self.adapter.framework, "National Blockchain Framework (NBF) / Vishvasya Stack")
        self.assertEqual(self.adapter.authority, "Ministry of Electronics and Information Technology (MeitY) / C-DAC / NIC")

    def test_honest_designation_and_zero_fabrication(self):
        """
        Verify Section 17 & 18:
        Adapter explicitly labels prototype status and makes zero false claims
        of official production deployment or unverified certifications.
        """
        expected_status = "Prototype adapter — Integration-ready (Not connected to production government network)"
        self.assertEqual(self.adapter.status_label, expected_status)

        info = self.adapter.get_adapter_info()
        self.assertEqual(info["adapter_name"], "NBFPermissionedLedgerAdapter")
        self.assertEqual(info["ledger_type"], "NBF_VISHVASYA_STAGING")
        self.assertEqual(info["status_label"], expected_status)
        self.assertIn("nbf_specification", info)

        # Check specification fields
        spec = info["nbf_specification"]
        self.assertEqual(spec["guidelines_reference"], "MeitY National Blockchain Framework (NBF) - September 2024")
        self.assertEqual(spec["deployment_tier"], "PROTOTYPE_STAGING")
        self.assertIn("production_onboarding_requirements", spec)
        self.assertGreater(len(spec["production_onboarding_requirements"]), 0)

    def test_format_nbf_payload_canonical_envelope(self):
        """
        Verify formatting of canonical transaction envelope conforming to
        Vishvasya BaaS guidelines with zero PII.
        """
        dummy_block = {
            "block_index": 42,
            "timestamp": "2026-09-17T12:00:00Z",
            "file_id": "test-doc-uuid-42",
            "doc_hash": "a" * 64,
            "risk_score": 18.5,
            "decision": "CLEARED",
            "canonical_hash": "c" * 64,
            "signature": f"sig:ed25519:{'e' * 128}",
            "event_type": "SCREENING_EVENT"
        }

        envelope = self.adapter.format_nbf_payload(dummy_block)

        self.assertEqual(envelope["protocol_version"], "NBF-VISHVASYA-v1.0")
        self.assertEqual(envelope["channel_id"], "mha-border-screening-audit")
        self.assertEqual(envelope["chaincode_id"], "border_screening_audit_v1")
        self.assertEqual(envelope["transaction_id"], f"tx-nbf-42-{'c' * 16}")
        self.assertEqual(envelope["station_id"], "SSB-ICP-RXL-01")
        self.assertEqual(envelope["station_public_key"], get_station_public_key_hex())
        self.assertEqual(envelope["event_type"], "SCREENING_EVENT")
        self.assertTrue(envelope["zero_pii_assertion"])
        self.assertEqual(envelope["deployment_tier"], "PROTOTYPE_STAGING")

        # Zero-PII verification: ensure no sensitive keys are present
        forbidden_keys = {"name", "aadhaar", "passport_number", "face_vector", "embedding"}
        for k in forbidden_keys:
            self.assertNotIn(k, envelope)

    def test_verify_nbf_compliance_success_and_violations(self):
        """
        Verify that compliance checker passes compliant blocks and rejects
        forbidden PII or missing cryptographic signatures.
        """
        # 1. Compliant block
        valid_block = {
            "block_index": 1,
            "file_id": "session-1",
            "doc_hash": "b" * 64,
            "canonical_hash": "d" * 64,
            "signature": f"sig:ed25519:{'f' * 128}",
            "event_type": "SCREENING_EVENT"
        }
        res_valid = self.adapter.verify_nbf_compliance(valid_block)
        self.assertTrue(res_valid["is_compliant"])
        self.assertEqual(len(res_valid["violations"]), 0)
        self.assertTrue(res_valid["checks"]["zero_pii_verified"])
        self.assertTrue(res_valid["checks"]["ed25519_signature_present"])
        self.assertTrue(res_valid["checks"]["canonical_hash_valid"])

        # 2. Block with forbidden PII
        pii_block = dict(valid_block)
        pii_block["name"] = "Traveler Name"
        pii_block["aadhaar_number"] = "123456789012"
        pii_block["face_vector"] = [0.1, 0.2, 0.3]
        res_pii = self.adapter.verify_nbf_compliance(pii_block)
        self.assertFalse(res_pii["is_compliant"])
        self.assertFalse(res_pii["checks"]["zero_pii_verified"])
        self.assertGreaterEqual(len(res_pii["violations"]), 3)

        # 3. Block missing signature
        no_sig_block = dict(valid_block)
        no_sig_block["signature"] = None
        res_no_sig = self.adapter.verify_nbf_compliance(no_sig_block)
        self.assertFalse(res_no_sig["is_compliant"])
        self.assertFalse(res_no_sig["checks"]["ed25519_signature_present"])

        # 4. Block with invalid canonical hash
        bad_hash_block = dict(valid_block)
        bad_hash_block["canonical_hash"] = "short_hash"
        res_bad_hash = self.adapter.verify_nbf_compliance(bad_hash_block)
        self.assertFalse(res_bad_hash["is_compliant"])
        self.assertFalse(res_bad_hash["checks"]["canonical_hash_valid"])

    def test_nbf_offline_first_screening_and_spooling(self):
        """
        Verify that screening with NBF adapter completes locally,
        attaches NBF envelope and compliance assertion, and spools as ANCHOR_PENDING.
        """
        session_id = f"test-p12-nbf-offline-{os.urandom(4).hex()}"
        block = self.adapter.commit_inspection_block(
            file_path=os.path.abspath(__file__),
            file_id=session_id,
            document_type="PASSPORT",
            risk_score=19.0,
            risk_level="LOW",
            biometric_status="PENDING",
            officer_id="SSB-OFFICER-7429"
        )

        self.assertIsNotNone(block)
        self.assertEqual(block["file_id"], session_id)
        self.assertEqual(block["anchor_status"], "ANCHOR_PENDING")
        self.assertIn("nbf_payload", block)
        self.assertTrue(block["nbf_compliance"])
        self.assertEqual(block["nbf_payload"]["protocol_version"], "NBF-VISHVASYA-v1.0")

        # Verify chain integrity locally
        report = self.adapter.verify_integrity()
        self.assertTrue(report["chain_valid"])

        # Verify spool flush
        flush_res = self.adapter.flush_pending_anchors()
        self.assertEqual(flush_res["status"], "SYNCED")
        self.assertEqual(flush_res["remaining_pending"], 0)

    def test_api_nbf_specification_endpoint(self):
        """Verify GET /api/ledger/nbf-specification returns 200 with full specification."""
        resp = self.client.get("/api/ledger/nbf-specification")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["framework"], "National Blockchain Framework (NBF) / Vishvasya Stack")
        self.assertEqual(data["authority"], "Ministry of Electronics and Information Technology (MeitY) / C-DAC / NIC")
        self.assertEqual(data["deployment_tier"], "PROTOTYPE_STAGING")
        self.assertIn("cryptographic_profile", data)
        self.assertEqual(data["cryptographic_profile"]["digital_signatures"], "Ed25519 (RFC 8032)")
        self.assertEqual(data["cryptographic_profile"]["canonical_serialization"], "RFC 8785 (Canonical JSON / JCS)")
        self.assertIn("zero_pii_guarantee", data)
        self.assertIn("offline_resilience", data)
        self.assertIn("production_onboarding_requirements", data)

    def test_factory_instantiates_nbf_adapter_when_configured(self):
        """Verify get_audit_ledger() factory returns NBFPermissionedLedgerAdapter when LEDGER_MODE='NBF_PERMISSIONED'."""
        get_audit_ledger.cache_clear()
        with patch.dict(os.environ, {"LEDGER_MODE": "NBF_PERMISSIONED"}):
            from core.config import get_settings
            get_settings.cache_clear()
            ledger = get_audit_ledger()
            self.assertIsInstance(ledger, NBFPermissionedLedgerAdapter)
            get_settings.cache_clear()
        get_audit_ledger.cache_clear()


if __name__ == "__main__":
    unittest.main()

