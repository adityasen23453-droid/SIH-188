import unittest
import os
import tempfile
import cv2
import numpy as np
from modules.preprocessing import detect_and_correct_document, find_document_contour, apply_clahe


class TestPreprocessingModule(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_jpg = os.path.join(self.temp_dir.name, "test_doc.jpg")

        # Create synthetic image with a clear rectangular card on a dark background
        img = np.zeros((400, 400, 3), dtype=np.uint8)
        cv2.rectangle(img, (50, 50), (350, 350), (240, 240, 240), -1)
        cv2.imwrite(self.test_jpg, img)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_detect_and_correct_document(self):
        res = detect_and_correct_document(self.test_jpg, output_dir=self.temp_dir.name)
        self.assertIn("processed_image_path", res)
        self.assertIn("correction_applied", res)
        self.assertIn("note", res)
        self.assertTrue(os.path.exists(res["processed_image_path"]))
        self.assertTrue(res["correction_applied"])

    def test_detect_and_correct_document_missing_file(self):
        res = detect_and_correct_document("non_existent_image.jpg", output_dir=self.temp_dir.name)
        self.assertIn("error", res)
        self.assertFalse(res["correction_applied"])
        self.assertEqual(res["processed_image_path"], "non_existent_image.jpg")


if __name__ == "__main__":
    unittest.main()
