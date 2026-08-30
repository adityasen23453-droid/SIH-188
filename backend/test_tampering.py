import unittest
import os
import tempfile
from PIL import Image
from fastapi.testclient import TestClient
from main import app, DB_FILES
from modules.tampering import run_ela, check_metadata, check_ai_manipulation, run_tampering_detection


class TestTamperingModule(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_jpg = os.path.join(self.temp_dir.name, "test_doc.jpg")
        self.test_png = os.path.join(self.temp_dir.name, "test_doc.png")

        # Create synthetic test JPEG image
        img = Image.new("RGB", (200, 200), color=(120, 150, 180))
        img.save(self.test_jpg, format="JPEG", quality=95)

        # Create synthetic test PNG image
        img.save(self.test_png, format="PNG")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_run_ela_jpeg(self):
        res = run_ela(self.test_jpg)
        self.assertIn("ela_score", res)
        self.assertIn("ela_image_path", res)
        self.assertIn("ela_image_url", res)
        self.assertIsInstance(res["ela_score"], float)
        self.assertTrue(0.0 <= res["ela_score"] <= 100.0)
        self.assertTrue(os.path.exists(res["ela_image_path"]))
        self.assertTrue(res["ela_image_url"].startswith("/ela-images/"))

    def test_run_ela_png_note(self):
        res = run_ela(self.test_png)
        self.assertIn("note", res)
        self.assertIn("converted", res["note"].lower())
        self.assertTrue(0.0 <= res["ela_score"] <= 100.0)

    def test_run_ela_missing_file(self):
        res = run_ela("non_existent_file.jpg")
        self.assertIn("error", res)
        self.assertEqual(res["ela_score"], 0.0)

    def test_check_metadata(self):
        res = check_metadata(self.test_jpg)
        self.assertIn("editing_software_detected", res)
        self.assertIn("metadata_stripped", res)
        self.assertIn("raw_exif_summary", res)

    def test_check_ai_manipulation(self):
        res = check_ai_manipulation(self.test_jpg)
        self.assertIn("ai_generated_likelihood", res)
        self.assertIn("label", res)
        self.assertIn("confidence", res)
        if res.get("ai_generated_likelihood") is not None:
            self.assertTrue(0.0 <= res["ai_generated_likelihood"] <= 100.0)
            self.assertIn(res["label"].lower(), ["real", "forged"])
            self.assertTrue(0.0 <= res["confidence"] <= 1.0)

    def test_check_ai_manipulation_missing_file(self):
        res = check_ai_manipulation("non_existent_file.jpg")
        self.assertIn("error", res)
        self.assertIsNone(res["ai_generated_likelihood"])
        self.assertIsNone(res["label"])
        self.assertIsNone(res["confidence"])

    def test_run_tampering_detection_clamping(self):
        res = run_tampering_detection(self.test_jpg)
        self.assertIn("ela", res)
        self.assertIn("metadata", res)
        self.assertIn("ai_detection", res)
        self.assertIn("tampering_likelihood", res)
        self.assertIn("risk_level", res)
        self.assertTrue(0.0 <= res["tampering_likelihood"] <= 100.0)
        self.assertIn(res["risk_level"], ["low", "medium", "high"])

    def test_fastapi_tamper_endpoint_and_static_mount(self):
        client = TestClient(app)

        # 1. Non-existent file_id -> 404
        resp_404 = client.post("/api/tamper-check/invalid-file-id")
        self.assertEqual(resp_404.status_code, 404)

        # 2. Mock valid upload in DB_FILES
        DB_FILES["test-tamper-id"] = {
            "file_path": self.test_jpg,
            "filename": "test_doc.jpg",
            "document_type": "passport",
            "ocr_result": None
        }

        # 3. Call /api/tamper-check/test-tamper-id
        resp = client.post("/api/tamper-check/test-tamper-id")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("tampering_likelihood", data)
        self.assertIn("risk_level", data)
        self.assertIn("ela", data)
        self.assertIn("metadata", data)
        self.assertIn("ai_detection", data)
        self.assertTrue(0.0 <= data["tampering_likelihood"] <= 100.0)

        # 4. Access static ELA image via URL
        ela_url = data["ela"]["ela_image_url"]
        resp_img = client.get(ela_url)
        self.assertEqual(resp_img.status_code, 200)
        self.assertEqual(resp_img.headers["content-type"], "image/png")



if __name__ == "__main__":
    unittest.main()
