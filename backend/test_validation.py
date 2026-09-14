import unittest
from fastapi.testclient import TestClient
from main import app, DB_FILES
from modules.validation import (
    calc_mrz_check_digit,
    validate_mrz_checksum,
    validate_dates,
    verhoeff_validate,
    validate_national_id,
    validate_viz_to_mrz,
    check_registry,
    run_validation
)


class TestValidationModule(unittest.TestCase):

    def test_mrz_checksum_valid(self):
        line2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
        res = validate_mrz_checksum(
            passport_number="L898902C3",
            date_of_birth="740812",
            date_of_expiry="120415",
            mrz_line2=line2
        )
        self.assertTrue(res["overall_checksum_valid"])
        self.assertTrue(res["passport_number_check"]["valid"])
        self.assertEqual(res["passport_number_check"]["expected_digit"], "6")
        self.assertEqual(res["passport_number_check"]["computed_digit"], "6")
        self.assertTrue(res["date_of_birth_check"]["valid"])
        self.assertTrue(res["date_of_expiry_check"]["valid"])
        self.assertTrue(res["composite_check"]["valid"])
        self.assertEqual(len(res["failed_fields"]), 0)

    def test_mrz_checksum_tampered(self):
        line2 = "L898902C35UTO7408122F1204159ZE184226B<<<<<10"
        res = validate_mrz_checksum(mrz_line2=line2)
        self.assertFalse(res["overall_checksum_valid"])
        self.assertFalse(res["passport_number_check"]["valid"])
        self.assertEqual(res["passport_number_check"]["expected_digit"], "5")
        self.assertEqual(res["passport_number_check"]["computed_digit"], "6")
        self.assertIn("passport_number_check", res["failed_fields"])

    def test_verhoeff_algorithm(self):
        # Known valid Verhoeff numbers
        self.assertTrue(verhoeff_validate("2363"))
        self.assertTrue(verhoeff_validate("1428570"))
        # Invalid numbers
        self.assertFalse(verhoeff_validate("12345"))
        self.assertFalse(verhoeff_validate("1428571"))
        self.assertFalse(verhoeff_validate(""))

    def test_national_id_validation_aadhaar(self):
        # Invalid length
        res_short = validate_national_id("aadhaar", {"aadhaar_number": "123456"})
        self.assertFalse(res_short["valid"])
        self.assertTrue(any("12 digits" in iss for iss in res_short["issues"]))

        # Invalid Verhoeff checksum
        res_bad_check = validate_national_id("aadhaar", {"aadhaar_number": "123456789012"})
        self.assertFalse(res_bad_check["valid"])
        self.assertTrue(any("Verhoeff" in iss for iss in res_bad_check["issues"]))

    def test_national_id_validation_voter_id(self):
        # Valid EPIC
        res_valid = validate_national_id("voter_id", {"voter_id": "ABC1234567"})
        self.assertTrue(res_valid["valid"])

        # Invalid EPIC format
        res_invalid = validate_national_id("voter_id", {"voter_id": "12345"})
        self.assertFalse(res_valid == False)
        self.assertFalse(res_invalid["valid"])
        self.assertTrue(any("format" in iss for iss in res_invalid["issues"]))

    def test_national_id_validation_driving_license(self):
        # Valid Sarathi DL format
        res_valid = validate_national_id("driving_license", {"dl_number": "DL0420110012345"})
        self.assertTrue(res_valid["valid"])

        # Invalid DL format
        res_invalid = validate_national_id("driving_license", {"dl_number": "123"})
        self.assertFalse(res_invalid["valid"])

    def test_viz_to_mrz_consistency(self):
        # Consistent names
        res_consistent = validate_viz_to_mrz(
            {"name": "ERIKSSON ANNA MARIA"},
            {"name": "ANNA MARIA ERIKSSON"}
        )
        self.assertTrue(res_consistent["consistent"])

        # Conflicting names
        res_conflict = validate_viz_to_mrz(
            {"name": "ERIKSSON ANNA MARIA"},
            {"name": "JOHN SMITH"}
        )
        self.assertFalse(res_conflict["consistent"])
        self.assertTrue(any("conflicts" in m for m in res_conflict["mismatches"]))

    def test_registry_lookups(self):
        # 1. Stolen passport
        res_stolen = check_registry("X1234567")
        self.assertTrue(res_stolen["blacklisted"])
        self.assertEqual(res_stolen["status"], "STOLEN")

        # 2. Revoked passport
        res_revoked = check_registry("REVOKED01")
        self.assertTrue(res_revoked["blacklisted"])
        self.assertEqual(res_revoked["status"], "REVOKED")

        # 3. Clean passport
        res_clean = check_registry("L898902C3")
        self.assertFalse(res_clean["blacklisted"])
        self.assertEqual(res_clean["status"], "VALID")

    def test_dates_valid(self):
        res = validate_dates(
            date_of_birth="1995-05-20",
            date_of_expiry="2032-12-31"
        )
        self.assertTrue(res["expiry_valid"])
        self.assertTrue(res["dob_plausible"])
        self.assertEqual(len(res["issues"]), 0)

    def test_dates_expired(self):
        res = validate_dates(
            date_of_birth="1990-01-01",
            date_of_expiry="2020-01-01"
        )
        self.assertFalse(res["expiry_valid"])
        self.assertTrue(any("expired" in issue.lower() for issue in res["issues"]))

    def test_run_validation_consolidated(self):
        sample_ocr = {
            "document_type": "passport",
            "method_used": "mrz",
            "fields": {
                "name": "ANNA MARIA ERIKSSON",
                "passport_number": "L898902C3",
                "date_of_birth": "740812",
                "date_of_expiry": "2030-04-15",
                "mrz_line2": "L898902C36UTO7408122F3004157ZE184226B<<<<<16"
            },
            "viz_fields": {
                "name": "ANNA MARIA ERIKSSON"
            }
        }
        res = run_validation(sample_ocr)
        self.assertIn("checksum", res)
        self.assertIn("national_id", res)
        self.assertIn("viz_consistency", res)
        self.assertIn("dates", res)
        self.assertIn("registry", res)
        self.assertTrue(res["overall_valid"])

    def test_fastapi_endpoints(self):
        client = TestClient(app)

        # 404 test
        resp_404 = client.post("/api/validate/non-existent-id")
        self.assertEqual(resp_404.status_code, 404)

        # Cached upload test
        DB_FILES["test-id-123"] = {
            "file_path": "dummy.jpg",
            "filename": "dummy.jpg",
            "document_type": "passport",
            "ocr_result": {
                "document_type": "passport",
                "method_used": "mrz",
                "fields": {
                    "passport_number": "X1234567",
                    "date_of_birth": "1990-01-01",
                    "date_of_expiry": "2030-01-01",
                    "mrz_line2": None
                },
                "viz_fields": {}
            }
        }

        resp_val = client.post("/api/validate/test-id-123")
        self.assertEqual(resp_val.status_code, 200)
        data = resp_val.json()
        self.assertTrue(data["blacklist"]["blacklisted"])
        self.assertFalse(data["overall_valid"])

    def test_mrz_line1_misrouting_safeguard(self):
        # When Line 1 (Holder Name) is passed as line 2 by mistake
        line1_as_line2 = "P<BRACOSTA<CARLOS<<<<<<<<<<<<<<<<<<S<SK<<K"
        res = validate_mrz_checksum(mrz_line2=line1_as_line2)
        self.assertIsNone(res["overall_checksum_valid"])
        self.assertIn("Holder Name", res.get("note", ""))

    def test_mrz_line_disambiguation(self):
        from modules.ocr import disambiguate_mrz_lines
        # 3 lines with a header above MRZ (e.g. from camera/scan of passport)
        raw_lines = [
            "VALIDO ATE / DATE OF EXPIRY",
            "P<BRACOSTA<CARLOS<<<<<<<<<<<<<<<<<<<<<<<<<<",
            "HAA000681<7BRA0103162M220753<<<<<<<<<<<<<<00"
        ]
        l1, l2, l3 = disambiguate_mrz_lines(raw_lines)
        self.assertTrue(l1.startswith("P<BRA"))
        self.assertTrue(l2.startswith("HAA000681"))

    def test_domain_specific_verifications(self):
        from modules.validation import (
            validate_aadhaar_card,
            validate_voter_id,
            validate_driving_license,
            validate_visa_document,
            verhoeff_compute_check_digit
        )

        # 1. Aadhaar Verification
        self.assertEqual(verhoeff_compute_check_digit("39005130720"), 6)
        aadhaar_res = validate_aadhaar_card(
            {"aadhaar_number": "3900 5130 7206", "date_of_birth": "23/03/1981"},
            raw_text=["Government of India", "Mehboob Rajput", "DOB: 23/03/1981", "3900 5130 7206"]
        )
        self.assertTrue(aadhaar_res["valid"])
        self.assertTrue(aadhaar_res["verhoeff_valid"])
        self.assertTrue(aadhaar_res["sovereign_header_detected"])

        # 2. Voter ID Verification
        voter_res = validate_voter_id(
            {"voter_id": "ABC1234567", "name": "Aditya Sen"},
            raw_text=["Election Commission of India", "ABC1234567", "Aditya Sen"]
        )
        self.assertTrue(voter_res["valid"])
        self.assertTrue(voter_res["epic_format_valid"])

        # 3. Driving License Verification
        dl_res = validate_driving_license(
            {"dl_number": "DL0420110012345"},
            raw_text=["Driving Licence", "DL0420110012345"]
        )
        self.assertTrue(dl_res["valid"])
        self.assertTrue(dl_res["jurisdiction_verified"])

        # 4. Visa Verification
        visa_res = validate_visa_document(
            {"visa_number": "VISA123456", "date_of_issue": "2023-01-01", "date_of_expiry": "2025-01-01"},
            raw_text=["Visa Type: Tourist", "VISA123456"]
        )
        self.assertTrue(visa_res["valid"])
        self.assertTrue(visa_res["visa_number_valid"])

    def test_date_plausibility_statuses(self):
        # Missing expiry
        res_missing = validate_dates(date_of_birth="1995-05-15", date_of_expiry=None, doc_type="passport")
        self.assertEqual(res_missing["expiry_status"], "NOT_DETECTED")
        self.assertFalse(res_missing["expiry_valid"])

        # Non-expiring ID (Aadhaar)
        res_aadhaar = validate_dates(date_of_birth="1995-05-15", date_of_expiry=None, doc_type="aadhaar")
        self.assertEqual(res_aadhaar["expiry_status"], "NOT_APPLICABLE")
        self.assertTrue(res_aadhaar["expiry_valid"])

        # Expired passport
        res_expired = validate_dates(date_of_birth="1995-05-15", date_of_expiry="2010-01-01", doc_type="passport")
        self.assertEqual(res_expired["expiry_status"], "EXPIRED")
        self.assertFalse(res_expired["expiry_valid"])

        # Active passport
        res_active = validate_dates(date_of_birth="1995-05-15", date_of_expiry="2035-01-01", doc_type="passport")
        self.assertEqual(res_active["expiry_status"], "ACTIVE")
        self.assertTrue(res_active["expiry_valid"])


if __name__ == "__main__":
    unittest.main()
