import unittest
import os
import tempfile
import cv2
import numpy as np
from modules.ocr import (
    check_field_confidence,
    extract_document_face,
    extract_passport,
    extract_document_fields,
    run_ocr
)


class TestOcrModule(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_img = os.path.join(self.temp_dir.name, "test_doc.jpg")

        # Create synthetic blank image
        img = np.full((300, 400, 3), 255, dtype=np.uint8)
        cv2.imwrite(self.test_img, img)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_check_field_confidence(self):
        # Normal field
        self.assertEqual(check_field_confidence("SMITH JOHN"), "high")
        # Repeating chars (OCR artifact)
        self.assertEqual(check_field_confidence("SMIIIITH"), "low")
        # Overly long string
        self.assertEqual(check_field_confidence("A" * 50, max_len=40), "low")
        # Nationality alpha-only constraint
        self.assertEqual(check_field_confidence("IND", max_len=3, check_alpha_only=True), "high")
        self.assertEqual(check_field_confidence("1N0", max_len=3, check_alpha_only=True), "low")

    def test_extract_document_face_no_face(self):
        # On a blank image, no face is detected
        res = extract_document_face(self.test_img, output_dir=self.temp_dir.name)
        self.assertIn("face_detected", res)
        self.assertFalse(res["face_detected"])
        self.assertIsNone(res["face_image_path"])

    def test_extract_passport_empty(self):
        # Non-passport image returns fallback structure
        res = extract_passport(self.test_img)
        self.assertIn("passport_number", res)
        self.assertIn("mrz_valid_score", res)
        self.assertEqual(res["mrz_valid_score"], 0)

    def test_run_ocr_structure(self):
        res = run_ocr(self.test_img, document_type="passport")
        self.assertIn("document_type", res)
        self.assertIn("method_used", res)
        self.assertIn("fields", res)
        self.assertIn("portrait_face", res)
        self.assertIn("face_detected", res["portrait_face"])
        self.assertIn("detected_regions", res)



if __name__ == "__main__":
    unittest.main()

