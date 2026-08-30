import unittest
import os
import sqlite3
from fastapi.testclient import TestClient
from main import app, DB_FILES
from modules.validation import (
    validate_mrz_checksum,
    validate_dates,
    check_blacklist,
    run_validation,
    get_blacklist_db_path
)


class TestValidationModule(unittest.TestCase):

    def test_mrz_checksum_valid(self):
        # Standard TD3 line 2 example with valid check digits
        # Passport L898902C3 (6), DOB 740812 (2), EXP 120415 (9), Composite 0
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
        # Tampered check digit for passport number (changed 6 to 5)
        line2 = "L898902C35UTO7408122F1204159ZE184226B<<<<<10"
        res = validate_mrz_checksum(mrz_line2=line2)
        self.assertFalse(res["overall_checksum_valid"])
        self.assertFalse(res["passport_number_check"]["valid"])
        self.assertEqual(res["passport_number_check"]["expected_digit"], "5")
        self.assertEqual(res["passport_number_check"]["computed_digit"], "6")
        self.assertIn("passport_number_check", res["failed_fields"])

    def test_mrz_checksum_none(self):
        res = validate_mrz_checksum(mrz_line2=None)
        self.assertIsNone(res["overall_checksum_valid"])
        self.assertIn("note", res)
        self.assertIn("MRZ line 2 not available", res["note"])

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
        self.assertTrue(res["dob_plausible"])
        self.assertTrue(any("expired" in issue.lower() for issue in res["issues"]))

    def test_dates_future_dob(self):
        res = validate_dates(
            date_of_birth="2050-01-01",
            date_of_expiry="2035-01-01"
        )
        self.assertFalse(res["dob_plausible"])
        self.assertTrue(any("future" in issue.lower() for issue in res["issues"]))

    def test_dates_missing(self):
        res = validate_dates(date_of_birth=None, date_of_expiry=None)
        self.assertFalse(res["expiry_valid"])
        self.assertFalse(res["dob_plausible"])
        self.assertEqual(len(res["issues"]), 2)

    def test_dates_issue_after_expiry(self):
        res = validate_dates(
            date_of_birth="1990-01-01",
            date_of_issue="2035-01-01",
            date_of_expiry="2030-01-01"
        )
        self.assertTrue(any("not before date of expiry" in issue for issue in res["issues"]))

    def test_blacklist_check(self):
        db_path = get_blacklist_db_path()
        res_blacklisted = check_blacklist("X1234567")
        self.assertTrue(res_blacklisted["blacklisted"])
        self.assertEqual(res_blacklisted["reason"], "Reported stolen")

        # Case insensitive test
        res_case = check_blacklist("x1234567")
        self.assertTrue(res_case["blacklisted"])

        # Clean passport test
        res_clean = check_blacklist("Z9999999")
        self.assertFalse(res_clean["blacklisted"])
        self.assertIsNone(res_clean["reason"])

    def test_run_validation_consolidated(self):
        sample_ocr_result = {
            "document_type": "passport",
            "method_used": "mrz",
            "fields": {
                "name": "ANNA MARIA ERIKSSON",
                "passport_number": "L898902C3",
                "nationality": "UTO",
                "date_of_birth": "740812",
                "date_of_expiry": "2030-04-15",
                "gender": "F",
                "mrz_line2": "L898902C36UTO7408122F3004159ZE184226B<<<<<10"
            }
        }
        res = run_validation(sample_ocr_result)
        self.assertIn("checksum", res)
        self.assertIn("dates", res)
        self.assertIn("blacklist", res)
        self.assertIn("overall_valid", res)
        self.assertIn("issues", res)
        self.assertTrue(isinstance(res["issues"], list))

    def test_fastapi_endpoints(self):
        client = TestClient(app)

        # Test non-existent file validation
        resp_404 = client.post("/api/validate/non-existent-id")
        self.assertEqual(resp_404.status_code, 404)
        self.assertEqual(resp_404.json(), {"error": "File not found"})

        # Mock entry in DB_FILES
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
                }
            }
        }

        # Validate cached entry
        resp_val = client.post("/api/validate/test-id-123")
        self.assertEqual(resp_val.status_code, 200)
        data = resp_val.json()
        self.assertTrue(data["blacklist"]["blacklisted"])
        self.assertFalse(data["overall_valid"])


if __name__ == "__main__":
    unittest.main()
