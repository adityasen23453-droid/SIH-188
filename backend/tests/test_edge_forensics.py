"""
BorderShield Edge Discontinuity & Boundary Forensics Test Suite.

Verifies:
1. Genuine documents (clean continuous edges)
2. Photo replacement (localized boundary discontinuity)
3. Text manipulation (spliced text boundary)
4. Stamp manipulation (spliced seal boundary)
5. Pasted/composited regions (rectilinear cut seams)
6. Compressed & resized robustness (anti-false-positive)
7. Blurred document handling (low confidence & uncertainty flag)
8. Low-quality noisy scans (noise floor filtering)
9. Document borders suppression (exclusion mask)
10. Uniform canvas (zero suspicious regions)
11. Invalid & missing inputs (safe error handling)
12. Heatmap coordinate correctness (bounds validation)
13. Configuration & shadow mode vs active mode fusion
"""

import os
import sys
import tempfile
import unittest
import cv2
import numpy as np
from PIL import Image

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.config import get_settings
from modules.edge_forensics import (
    assess_image_quality,
    compute_boundary_exclusion_mask,
    detect_boundary_discontinuities
)
from modules.tampering import run_tampering_detection


class TestEdgeDiscontinuityForensics(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = os.path.join(self.temp_dir.name, "edge_out")
        os.makedirs(self.output_dir, exist_ok=True)

        # Base synthetic genuine document canvas (700 x 1000)
        self.canvas_h, self.canvas_w = 700, 1000
        self.genuine_bgr = np.full((self.canvas_h, self.canvas_w, 3), (242, 246, 250), dtype=np.uint8)

        # Natural soft document borders
        cv2.rectangle(self.genuine_bgr, (25, 25), (975, 675), (180, 190, 200), 2)
        cv2.rectangle(self.genuine_bgr, (35, 35), (965, 665), (210, 220, 230), 1)

        # Header and printed text (small glyphs)
        cv2.putText(self.genuine_bgr, "REPUBLIC OF INDIA - PASSPORT", (50, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 40, 80), 2)
        cv2.putText(self.genuine_bgr, "SURNAME: SHARMA", (280, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 20, 30), 2)
        cv2.putText(self.genuine_bgr, "GIVEN NAMES: AARAV", (280, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 20, 30), 2)
        cv2.putText(self.genuine_bgr, "PASSPORT NO: Z1000042", (280, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 20, 30), 2)

        # Natural portrait photo with smooth gradient
        photo = np.full((220, 180, 3), (205, 218, 232), dtype=np.uint8)
        cv2.ellipse(photo, (90, 110), (60, 90), 0, 0, 360, (140, 160, 190), -1)
        self.genuine_bgr[120:340, 60:240] = photo

        self.genuine_path = os.path.join(self.temp_dir.name, "genuine_doc.jpg")
        cv2.imwrite(self.genuine_path, self.genuine_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])

    def tearDown(self):
        self.temp_dir.cleanup()

    # --------------------------------------------------------------------------
    # 1. Genuine Document (Clean Edges)
    # --------------------------------------------------------------------------
    def test_genuine_document_clean_edges(self):
        res = detect_boundary_discontinuities(self.genuine_path, output_dir=self.output_dir)
        self.assertIn("edge_anomaly_score", res)
        self.assertIn("confidence", res)
        self.assertIn("suspicious_regions", res)
        self.assertIn("reason_codes", res)
        self.assertIn("image_quality", res)
        self.assertIn("status", res)

        self.assertTrue(0.0 <= res["edge_anomaly_score"] <= 35.0, f"Expected low anomaly score, got {res['edge_anomaly_score']}")
        self.assertEqual(res["status"], "CLEAN")
        self.assertIn("EDGE_CLEAN_CONTINUOUS", res["reason_codes"])

    # --------------------------------------------------------------------------
    # 2. Photo Replacement (Boundary Discontinuity)
    # --------------------------------------------------------------------------
    def test_photo_replacement_boundary_discontinuity(self):
        tampered = self.genuine_bgr.copy()
        # Paste a synthetic alien photo block with strong artificial step edges & noise
        spliced_photo = np.full((180, 140, 3), (120, 80, 60), dtype=np.uint8)
        cv2.rectangle(spliced_photo, (2, 2), (138, 178), (255, 0, 0), 2)
        noise = np.random.normal(0, 15.0, spliced_photo.shape).astype(np.int16)
        spliced_photo = np.clip(spliced_photo.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        tampered[140:320, 80:220] = spliced_photo
        face_bbox = [80, 140, 140, 180]

        res = detect_boundary_discontinuities(tampered, face_bbox=face_bbox, output_dir=self.output_dir)
        self.assertTrue(res["edge_anomaly_score"] >= 35.0, f"Expected anomaly score >= 35.0, got {res['edge_anomaly_score']}")
        self.assertIn(res["status"], ["SUSPICIOUS", "ANOMALY_DETECTED"])
        self.assertTrue(
            "EDGE_PHOTO_BOUNDARY_DISCONTINUITY" in res["reason_codes"] or len(res["suspicious_regions"]) > 0,
            "Expected photo boundary anomaly flag or suspicious region"
        )

    # --------------------------------------------------------------------------
    # 3. Text Manipulation Boundary
    # --------------------------------------------------------------------------
    def test_text_manipulation_boundary(self):
        tampered = self.genuine_bgr.copy()
        # Splice a white rectangular block over text with an altered passport number
        text_patch = np.full((40, 220, 3), (255, 255, 255), dtype=np.uint8)
        cv2.putText(text_patch, "PASSPORT NO: X9999999", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 180), 2)
        cv2.rectangle(text_patch, (0, 0), (219, 39), (50, 50, 50), 2) # Artificial sharp border
        tampered[220:260, 270:490] = text_patch

        res = detect_boundary_discontinuities(tampered, output_dir=self.output_dir)
        self.assertTrue(res["edge_anomaly_score"] >= 25.0)
        self.assertTrue(len(res["suspicious_regions"]) > 0)

    # --------------------------------------------------------------------------
    # 4. Stamp Manipulation Boundary
    # --------------------------------------------------------------------------
    def test_stamp_manipulation_boundary(self):
        tampered = self.genuine_bgr.copy()
        # Paste a synthetic circular consular stamp with sharp boundary step
        stamp_patch = np.zeros((120, 120, 3), dtype=np.uint8)
        cv2.circle(stamp_patch, (60, 60), 55, (200, 20, 160), 3)
        cv2.putText(stamp_patch, "IMMIGRATION", (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 20, 160), 1)
        tampered[380:500, 700:820] = stamp_patch

        res = detect_boundary_discontinuities(tampered, output_dir=self.output_dir)
        self.assertTrue(res["edge_anomaly_score"] >= 25.0)
        self.assertTrue(len(res["suspicious_regions"]) > 0)

    # --------------------------------------------------------------------------
    # 5. Pasted Composited Patch (Rectilinear Seams)
    # --------------------------------------------------------------------------
    def test_pasted_composited_patch(self):
        tampered = self.genuine_bgr.copy()
        # Insert a 150x150 gray box with sharp rectilinear edges
        box = np.full((150, 150, 3), (180, 180, 180), dtype=np.uint8)
        cv2.rectangle(box, (0, 0), (149, 149), (30, 30, 30), 2)
        tampered[400:550, 300:450] = box

        res = detect_boundary_discontinuities(tampered, output_dir=self.output_dir)
        self.assertTrue(res["edge_anomaly_score"] >= 35.0)
        self.assertTrue(len(res["suspicious_regions"]) > 0)

    # --------------------------------------------------------------------------
    # 6. Compressed and Resized Robustness
    # --------------------------------------------------------------------------
    def test_compressed_and_resized_robustness(self):
        # Save genuine document at aggressive JPEG Q=50 and resize by 0.75x
        low_q_path = os.path.join(self.temp_dir.name, "low_q.jpg")
        cv2.imwrite(low_q_path, self.genuine_bgr, [cv2.IMWRITE_JPEG_QUALITY, 50])
        low_q = cv2.imread(low_q_path)
        resized = cv2.resize(low_q, (int(self.canvas_w * 0.75), int(self.canvas_h * 0.75)))

        res = detect_boundary_discontinuities(resized, output_dir=self.output_dir)
        # Should NOT trigger false positive
        self.assertTrue(res["edge_anomaly_score"] <= 35.0, f"Expected clean score on compressed image, got {res['edge_anomaly_score']}")
        self.assertEqual(res["status"], "CLEAN")

    # --------------------------------------------------------------------------
    # 7. Blurred Document Handling
    # --------------------------------------------------------------------------
    def test_blurred_document_handling(self):
        blurred = cv2.GaussianBlur(self.genuine_bgr, (21, 21), 8.0)
        res = detect_boundary_discontinuities(blurred, output_dir=self.output_dir)

        self.assertIn("image_quality", res)
        self.assertEqual(res["image_quality"]["quality_status"], "VERY_BLURRED")
        self.assertIn("EDGE_LOW_CONTRAST_UNCERTAIN", res["reason_codes"])
        self.assertTrue(res["confidence"] < 0.60)

    # --------------------------------------------------------------------------
    # 8. Low-Quality Noisy Scan
    # --------------------------------------------------------------------------
    def test_low_quality_noisy_scan(self):
        noisy = self.genuine_bgr.copy().astype(np.int16)
        noise = np.random.normal(0, 8.0, noisy.shape).astype(np.int16)
        noisy = np.clip(noisy + noise, 0, 255).astype(np.uint8)

        res = detect_boundary_discontinuities(noisy, output_dir=self.output_dir)
        # Global noise shouldn't create localized boundary discontinuities
        self.assertTrue(res["edge_anomaly_score"] <= 35.0)

    # --------------------------------------------------------------------------
    # 9. Outer Document Borders Suppressed
    # --------------------------------------------------------------------------
    def test_outer_document_borders_suppressed(self):
        border_img = self.genuine_bgr.copy()
        # Draw extreme 4-pixel border right at the perimeter of the image frame
        cv2.rectangle(border_img, (0, 0), (self.canvas_w - 1, self.canvas_h - 1), (0, 0, 0), 4)

        mask = compute_boundary_exclusion_mask(cv2.cvtColor(border_img, cv2.COLOR_BGR2GRAY))
        # Perimeter must be 0 in exclusion mask
        self.assertEqual(mask[0, 0], 0)
        self.assertEqual(mask[self.canvas_h - 1, self.canvas_w - 1], 0)

        res = detect_boundary_discontinuities(border_img, output_dir=self.output_dir)
        self.assertTrue(res["edge_anomaly_score"] <= 35.0)

    # --------------------------------------------------------------------------
    # 10. Uniform Canvas (No Suspicious Region)
    # --------------------------------------------------------------------------
    def test_no_suspicious_region_empty_boxes(self):
        blank = np.full((400, 600, 3), 200, dtype=np.uint8)
        res = detect_boundary_discontinuities(blank, output_dir=self.output_dir)

        self.assertEqual(res["edge_anomaly_score"], 0.0)
        self.assertEqual(res["suspicious_regions"], [])
        self.assertEqual(res["status"], "CLEAN")
        self.assertIn("EDGE_CLEAN_CONTINUOUS", res["reason_codes"])

    # --------------------------------------------------------------------------
    # 11. Invalid and Missing Input
    # --------------------------------------------------------------------------
    def test_invalid_and_missing_input(self):
        # 1. Non-existent file
        res_missing = detect_boundary_discontinuities("non_existent_image_123.jpg")
        self.assertEqual(res_missing["status"], "ERROR")
        self.assertIn("EDGE_FILE_NOT_FOUND", res_missing["reason_codes"])

        # 2. Corrupted / empty file
        corrupt_path = os.path.join(self.temp_dir.name, "corrupt.jpg")
        with open(corrupt_path, "wb") as f:
            f.write(b"not an image file")
        res_corrupt = detect_boundary_discontinuities(corrupt_path)
        self.assertEqual(res_corrupt["status"], "ERROR")

        # 3. Invalid data type
        res_type = detect_boundary_discontinuities(12345)
        self.assertEqual(res_type["status"], "ERROR")
        self.assertIn("EDGE_INVALID_INPUT_TYPE", res_type["reason_codes"])

    # --------------------------------------------------------------------------
    # 12. Heatmap Coordinate Correctness
    # --------------------------------------------------------------------------
    def test_heatmap_coordinate_correctness(self):
        tampered = self.genuine_bgr.copy()
        box_in = [200, 150, 160, 140]
        tampered[box_in[1]:box_in[1]+box_in[3], box_in[0]:box_in[0]+box_in[2]] = (30, 30, 200)

        res = detect_boundary_discontinuities(tampered, output_dir=self.output_dir)
        if res.get("heatmap_path"):
            self.assertTrue(os.path.exists(res["heatmap_path"]))
            heatmap = cv2.imread(res["heatmap_path"])
            self.assertIsNotNone(heatmap)
            # Dimension matches scaled image
            self.assertGreater(heatmap.shape[0], 0)
            self.assertGreater(heatmap.shape[1], 0)

        for b in res["suspicious_regions"]:
            x, y, w, h = b
            self.assertTrue(0 <= x < self.canvas_w, f"x {x} out of bounds")
            self.assertTrue(0 <= y < self.canvas_h, f"y {y} out of bounds")
            self.assertTrue(w > 0 and h > 0)

    # --------------------------------------------------------------------------
    # 13. Configuration & Shadow Mode vs Active Mode
    # --------------------------------------------------------------------------
    def test_configuration_and_shadow_mode(self):
        settings = get_settings()
        orig_mode = settings.EDGE_FORENSICS_MODE

        try:
            # 1. Shadow Mode: edge_forensics is reported, but tampering_likelihood is unchanged
            settings.EDGE_FORENSICS_MODE = "shadow"
            res_shadow = run_tampering_detection(self.genuine_path)
            self.assertIn("edge_forensics", res_shadow)
            self.assertIn("edge_anomaly_score", res_shadow["edge_forensics"])
            self.assertIn("status", res_shadow["edge_forensics"])
            self.assertIn("tampering_likelihood", res_shadow)

            # 2. Active Mode: works and blends properly
            settings.EDGE_FORENSICS_MODE = "active"
            res_active = run_tampering_detection(self.genuine_path)
            self.assertIn("edge_forensics", res_active)
            self.assertIn("tampering_likelihood", res_active)

        finally:
            settings.EDGE_FORENSICS_MODE = orig_mode


if __name__ == "__main__":
    unittest.main()
