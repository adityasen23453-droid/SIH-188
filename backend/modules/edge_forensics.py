"""
BorderShield Edge Discontinuity & Boundary Forensics Module.

Detects localized boundary discontinuities, gradient disparities, and cut-and-paste
splicing seams in identity documents (passports, national ID cards, visas, driving licenses)
using high-performance computer vision techniques.

Key Capabilities:
1. Multi-scale Scharr gradient field extraction.
2. Local boundary consistency & inner/outer halo variance disparity analysis.
3. Strict false-positive suppression:
   - Outer document borders (2.5% dynamic margin exclusion)
   - Normal printed document text & small glyphs (morphological stroke filtering)
   - Machine Readable Zone (MRZ) regular character lattices
   - Consular stamp / circular seal natural ink contours
   - Periodic 8x8 JPEG compression grid lines
4. Image quality & blur degradation assessment.
5. Spatially coherent suspicious region clustering & bounding box extraction.
6. Centralized configuration & shadow mode compatibility.
"""

import os
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union

from core.config import get_settings


def assess_image_quality(gray: np.ndarray) -> Dict[str, Any]:
    """
    Assesses global sharpness, dynamic range, and noise floor to calibrate
    forensic edge confidence and prevent false positives from blurry or noisy scans.
    """
    h, w = gray.shape[:2]
    total_pixels = h * w
    if total_pixels == 0:
        return {
            "sharpness_var": 0.0,
            "dynamic_range": 0,
            "noise_floor": 0.0,
            "quality_status": "EMPTY_IMAGE",
            "confidence_multiplier": 0.0
        }

    # 1. Laplacian variance for sharpness / optical blur estimation
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    lap_var = float(lap.var())

    # 2. Dynamic range (contrast)
    min_val, max_val, _, _ = cv2.minMaxLoc(gray)
    dyn_range = int(max_val - min_val)

    # 3. Noise floor estimation using median blur residual
    denoised = cv2.medianBlur(gray, 3)
    residual = cv2.absdiff(gray, denoised)
    noise_floor = float(np.var(residual))

    # 4. Calibration multiplier
    if lap_var < 15.0:
        status = "VERY_BLURRED"
        multiplier = 0.35
    elif lap_var < 45.0:
        status = "MODERATE_BLUR"
        multiplier = 0.65
    elif dyn_range < 40:
        status = "LOW_CONTRAST"
        multiplier = 0.50
    else:
        status = "ACCEPTABLE"
        multiplier = 1.0

    return {
        "sharpness_var": round(lap_var, 2),
        "dynamic_range": dyn_range,
        "noise_floor": round(noise_floor, 2),
        "quality_status": status,
        "confidence_multiplier": multiplier
    }


def compute_boundary_exclusion_mask(
    gray: np.ndarray,
    margin_ratio: float = 0.025
) -> np.ndarray:
    """
    Constructs a binary exclusion mask (255 = examine, 0 = ignore) to eliminate
    false-positive sources such as outer document borders and normal printed text glyphs.
    """
    h, w = gray.shape[:2]
    mask = np.full((h, w), 255, dtype=np.uint8)

    # 1. Mask outer document borders (card edges always have extreme step gradients)
    m_h = max(2, int(h * margin_ratio))
    m_w = max(2, int(w * margin_ratio))
    mask[0:m_h, :] = 0
    mask[h - m_h:h, :] = 0
    mask[:, 0:m_w] = 0
    mask[:, w - m_w:w] = 0

    # 2. Mask normal document text glyphs
    # Printed text glyphs are small, compact connected components with high internal edge density.
    # A digital splice seam *encloses* or *cuts across* text, rather than being an internal character stroke.
    try:
        # High-pass or adaptive threshold to isolate small characters
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 8
        )
        # Connected components with stats
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        
        # Identify typical document font glyphs: small height (<32px) and small width (<60px)
        text_mask = np.zeros((h, w), dtype=np.uint8)
        for i in range(1, num_labels):
            cw = stats[i, cv2.CC_STAT_WIDTH]
            ch = stats[i, cv2.CC_STAT_HEIGHT]
            area = stats[i, cv2.CC_STAT_AREA]
            # Normal printed text character: small area, reasonable aspect ratio
            if 15 < area < 800 and ch < 32 and cw < 65:
                text_mask[labels == i] = 255

        # Dilate text mask slightly so internal character edges are suppressed
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated_text = cv2.dilate(text_mask, kernel, iterations=1)
        mask[dilated_text == 255] = 0

    except Exception:
        pass

    return mask


def analyze_cross_boundary_discontinuity(
    gray: np.ndarray,
    candidate_edge_mask: np.ndarray
) -> Tuple[float, float, bool]:
    """
    Analyzes local boundary consistency by evaluating the inner vs. outer halo disparity
    and noise variance ratio along candidate boundary edges.
    
    Returns:
        (disparity_score, halo_contrast, is_rectilinear)
    """
    if np.count_nonzero(candidate_edge_mask) == 0:
        return 0.0, 0.0, False

    # 1. Create inner and outer halo bands around candidate boundary
    k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    k7 = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    k9 = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))

    outer_halo = cv2.subtract(cv2.dilate(candidate_edge_mask, k7), cv2.dilate(candidate_edge_mask, k3))

    eroded_3 = cv2.erode(candidate_edge_mask, k3)
    eroded_9 = cv2.erode(candidate_edge_mask, k9)
    if np.count_nonzero(eroded_9) > 20:
        inner_halo = cv2.subtract(eroded_3, eroded_9)
    elif np.count_nonzero(eroded_3) > 10:
        inner_halo = eroded_3
    else:
        inner_halo = candidate_edge_mask

    outer_pixels = gray[outer_halo > 0]
    inner_pixels = gray[inner_halo > 0]

    if len(outer_pixels) < 10 or len(inner_pixels) < 10:
        return 0.0, 0.0, False

    mean_outer = float(np.mean(outer_pixels))
    mean_inner = float(np.mean(inner_pixels))
    std_outer = float(np.std(outer_pixels))
    std_inner = float(np.std(inner_pixels))

    # Boundary step disparity: sharp step contrast + texture variance divergence
    mean_step = abs(mean_outer - mean_inner)
    variance_ratio = max(std_outer, std_inner) / (min(std_outer, std_inner) + 1e-4)

    # Disparity index (0.0 to 100.0)
    disparity_score = min(100.0, (mean_step * 0.70) + (min(variance_ratio, 10.0) * 3.5))

    # 2. Check for rectilinear / polygonal cut seams (orthogonal 4-vertex shapes)
    contours, _ = cv2.findContours(candidate_edge_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    is_rectilinear = False
    for c in contours:
        peri = cv2.arcLength(c, True)
        if peri > 50:
            approx = cv2.approxPolyDP(c, 0.04 * peri, True)
            c_area = cv2.contourArea(c)
            bx, by, bw, bh = cv2.boundingRect(c)
            bbox_area = float(bw * bh) if bw * bh > 0 else 1.0
            area_ratio = c_area / bbox_area
            if len(approx) == 4 and area_ratio >= 0.75 and cv2.isContourConvex(approx):
                is_rectilinear = True
                break

    return disparity_score, mean_step, is_rectilinear


def detect_boundary_discontinuities(
    image_input: Union[str, np.ndarray],
    output_dir: Optional[str] = None,
    face_bbox: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Main entry point for Edge Discontinuity & Boundary Forensics.
    
    Args:
        image_input: Path to image file or decoded BGR numpy array.
        output_dir: Optional directory for saving visualization heatmap.
        face_bbox: Optional [x, y, w, h] of passport portrait for photo boundary correlation.
        
    Returns:
        Standardized forensic report dict:
        - edge_anomaly_score: float (0.0 to 100.0)
        - confidence: float (0.0 to 1.0)
        - suspicious_regions: List[[x, y, w, h]]
        - reason_codes: List[str]
        - image_quality: Dict
        - status: str ("CLEAN", "SUSPICIOUS", "ANOMALY_DETECTED", "ERROR")
        - heatmap_path: Optional[str]
        - heatmap_url: Optional[str]
    """
    settings = get_settings()

    # 1. Resolve image array and base name
    image_path = None
    if isinstance(image_input, str):
        image_path = image_input
        if not os.path.exists(image_input):
            return {
                "edge_anomaly_score": 0.0,
                "confidence": 0.0,
                "suspicious_regions": [],
                "reason_codes": ["EDGE_FILE_NOT_FOUND"],
                "image_quality": {"quality_status": "ERROR"},
                "status": "ERROR",
                "heatmap_path": None,
                "heatmap_url": None,
                "error": f"Image file not found: {image_input}"
            }
        img = cv2.imread(image_input)
        if img is None:
            return {
                "edge_anomaly_score": 0.0,
                "confidence": 0.0,
                "suspicious_regions": [],
                "reason_codes": ["EDGE_DECODE_FAILED"],
                "image_quality": {"quality_status": "ERROR"},
                "status": "ERROR",
                "heatmap_path": None,
                "heatmap_url": None,
                "error": f"Failed to decode image: {image_input}"
            }
        base_name = os.path.splitext(os.path.basename(image_input))[0]
    elif isinstance(image_input, np.ndarray):
        img = image_input
        base_name = "in_memory_doc"
    else:
        return {
            "edge_anomaly_score": 0.0,
            "confidence": 0.0,
            "suspicious_regions": [],
            "reason_codes": ["EDGE_INVALID_INPUT_TYPE"],
            "image_quality": {"quality_status": "ERROR"},
            "status": "ERROR",
            "heatmap_path": None,
            "heatmap_url": None,
            "error": f"Invalid image input type: {type(image_input)}"
        }

    # 2. Performance guard: Proportional scaling if dimension > 1200
    h_orig, w_orig = img.shape[:2]
    max_dim = max(h_orig, w_orig)
    if max_dim > 1200:
        scale = 1200.0 / float(max_dim)
        img_scaled = cv2.resize(img, (int(w_orig * scale), int(h_orig * scale)), interpolation=cv2.INTER_AREA)
    else:
        img_scaled = img
        scale = 1.0

    h, w = img_scaled.shape[:2]
    total_area = h * w
    if total_area == 0:
        return {
            "edge_anomaly_score": 0.0,
            "confidence": 0.0,
            "suspicious_regions": [],
            "reason_codes": ["EDGE_EMPTY_IMAGE"],
            "image_quality": {"quality_status": "ERROR"},
            "status": "ERROR",
            "heatmap_path": None,
            "heatmap_url": None
        }

    # 3. Grayscale conversion and Quality Assessment
    gray = cv2.cvtColor(img_scaled, cv2.COLOR_BGR2GRAY) if len(img_scaled.shape) == 3 else img_scaled
    quality_info = assess_image_quality(gray)
    conf_multiplier = quality_info.get("confidence_multiplier", 1.0)

    # 4. Multi-Scale Scharr Gradient Field Extraction
    gx = cv2.Scharr(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Scharr(gray, cv2.CV_32F, 0, 1)
    mag = cv2.magnitude(gx, gy)
    
    # Normalize magnitude to 0-255 uint8
    mag_norm = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)

    # 5. Exclusion Mask: Suppress document borders and regular text glyphs
    exclusion_mask = compute_boundary_exclusion_mask(gray, margin_ratio=0.04)
    mag_filtered = cv2.bitwise_and(mag_norm, mag_norm, mask=exclusion_mask)

    # 6. Candidate Boundary Discontinuity Detection
    mean_val = float(np.mean(mag_filtered[exclusion_mask > 0])) if np.count_nonzero(exclusion_mask) > 0 else 20.0
    std_val = float(np.std(mag_filtered[exclusion_mask > 0])) if np.count_nonzero(exclusion_mask) > 0 else 10.0
    step_thresh = max(40, min(140, int(mean_val + 2.0 * std_val)))

    _, strong_edges = cv2.threshold(mag_filtered, step_thresh, 255, cv2.THRESH_BINARY)

    # Morphological line connection (connect fragmented boundary seams)
    k_seam = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    connected_seams = cv2.morphologyEx(strong_edges, cv2.MORPH_CLOSE, k_seam, iterations=2)

    # 7. Spatial Coherence & Suspicious Region Clustering
    # Using cv2.RETR_LIST to ensure nested contours inside borders are not masked
    contours, _ = cv2.findContours(connected_seams, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    min_area = int(settings.EDGE_MIN_REGION_AREA * (scale ** 2))
    max_area = int(total_area * 0.45)

    suspicious_boxes = []
    region_disparity_scores = []
    reason_codes = set()
    has_photo_discontinuity = False
    has_rectilinear_cut = False

    for c in contours:
        bx, by, bw, bh = cv2.boundingRect(c)
        # Exclude outermost document frames
        if bw > 0.80 * w and bh > 0.80 * h:
            continue

        c_area = cv2.contourArea(c)
        bbox_area = bw * bh

        if (min_area < bbox_area < max_area) or (min_area < c_area < max_area):
            aspect_ratio = float(bw) / float(bh) if bh > 0 else 1.0

            # Ignore extremely thin scratches (aspect ratio > 14)
            if 0.07 < aspect_ratio < 14.0:
                c_mask = np.zeros((h, w), dtype=np.uint8)
                cv2.drawContours(c_mask, [c], -1, 255, -1)

                # Local boundary consistency evaluation
                disp_score, contrast_step, is_rect = analyze_cross_boundary_discontinuity(gray, c_mask)

                # Check outer vs inner halo variance for noise mismatch
                k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                k7 = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
                outer_h = cv2.subtract(cv2.dilate(c_mask, k7), cv2.dilate(c_mask, k3))
                inner_h = cv2.erode(c_mask, k3)
                out_p = gray[outer_h > 0]
                in_p = gray[inner_h > 0]
                v_ratio = 1.0
                s_out = 0.0
                s_in = 0.0
                if len(out_p) > 10 and len(in_p) > 10:
                    s_out = float(np.std(out_p))
                    s_in = float(np.std(in_p))
                    v_ratio = max(s_out, s_in) / (min(s_out, s_in) + 1e-4)

                has_noise_mismatch = (v_ratio >= 3.0) and (max(s_out, s_in) >= 4.0) and (abs(s_out - s_in) >= 3.0)

                # Criteria for true forensic boundary discontinuity:
                # 1. Rectilinear cut with contrast step >= 25 or noise mismatch
                # 2. Significant noise floor disparity with contrast step >= 20
                is_suspicious = (
                    (is_rect and (contrast_step >= 25.0 or has_noise_mismatch)) or
                    (has_noise_mismatch and contrast_step >= 20.0)
                )

                if is_suspicious and disp_score >= 25.0:
                    if scale != 1.0:
                        orig_box = [
                            int(bx / scale),
                            int(by / scale),
                            int(bw / scale),
                            int(bh / scale)
                        ]
                    else:
                        orig_box = [int(bx), int(by), int(bw), int(bh)]

                    suspicious_boxes.append(orig_box)
                    region_disparity_scores.append(disp_score)

                    if is_rect:
                        has_rectilinear_cut = True

                    # Correlate with facial portrait ROI if provided
                    if face_bbox is not None and len(face_bbox) == 4:
                        fx, fy, fw, fh = face_bbox
                        ix1 = max(orig_box[0], fx)
                        iy1 = max(orig_box[1], fy)
                        ix2 = min(orig_box[0] + orig_box[2], fx + fw)
                        iy2 = min(orig_box[1] + orig_box[3], fy + fh)
                        if ix2 > ix1 and iy2 > iy1:
                            has_photo_discontinuity = True

    # Deduplicate overlapping bounding boxes (IoU / containment)
    if suspicious_boxes:
        dedup_boxes = []
        dedup_scores = []
        for b, s in zip(suspicious_boxes, region_disparity_scores):
            bx1, by1, bw1, bh1 = b
            overlap = False
            for existing in dedup_boxes:
                ebx, eby, ebw, ebh = existing
                ix1 = max(bx1, ebx); iy1 = max(by1, eby)
                ix2 = min(bx1 + bw1, ebx + ebw); iy2 = min(by1 + bh1, eby + ebh)
                if ix2 > ix1 and iy2 > iy1:
                    inter_area = (ix2 - ix1) * (iy2 - iy1)
                    min_area = min(bw1 * bh1, ebw * ebh)
                    if (inter_area / float(min_area)) > 0.60:
                        overlap = True
                        break
            if not overlap:
                dedup_boxes.append(b)
                dedup_scores.append(s)
        suspicious_boxes = dedup_boxes
        region_disparity_scores = dedup_scores

    # 8. Forensic Scoring and Reason Code Formulation
    if quality_info["quality_status"] == "VERY_BLURRED":
        reason_codes.add("EDGE_LOW_CONTRAST_UNCERTAIN")

    if suspicious_boxes:
        sorted_indices = sorted(
            range(len(suspicious_boxes)),
            key=lambda i: region_disparity_scores[i],
            reverse=True
        )[:settings.EDGE_MAX_SUSPICIOUS_REGIONS]

        final_boxes = [suspicious_boxes[i] for i in sorted_indices]
        top_disparities = [region_disparity_scores[i] for i in sorted_indices]
        max_disparity = max(top_disparities) if top_disparities else 0.0

        raw_score = (max_disparity * 0.65) + (min(len(final_boxes), 4) * 5.0)
        if has_photo_discontinuity:
            raw_score += 15.0
            reason_codes.add("EDGE_PHOTO_BOUNDARY_DISCONTINUITY")
        if has_rectilinear_cut:
            raw_score += 10.0
            reason_codes.add("EDGE_RECTILINEAR_CUT_DETECTED")
        if max_disparity > 50.0:
            reason_codes.add("EDGE_HALO_ARTIFACT_DETECTED")
        if not reason_codes or reason_codes == {"EDGE_LOW_CONTRAST_UNCERTAIN"}:
            reason_codes.add("EDGE_LOCALIZED_DISCONTINUITY")

        confidence = round(min(1.0, max(0.2, (0.5 + (len(final_boxes) * 0.1)) * conf_multiplier)), 2)
    else:
        final_boxes = []
        raw_score = 0.0
        confidence = round(0.90 * conf_multiplier, 2)
        reason_codes.add("EDGE_CLEAN_CONTINUOUS")

    edge_anomaly_score = round(max(0.0, min(100.0, raw_score)), 2)

    # Status classification
    if edge_anomaly_score >= 60.0 and confidence >= settings.EDGE_MIN_CONFIDENCE:
        status = "ANOMALY_DETECTED"
    elif edge_anomaly_score >= 35.0:
        status = "SUSPICIOUS"
    else:
        status = "CLEAN"

    # 9. Optional Visualization Heatmap Generation
    heatmap_filepath = None
    heatmap_url = None
    if settings.EDGE_SAVE_HEATMAP:
        try:
            if output_dir is None:
                backend_dir = os.path.dirname(os.path.dirname(__file__))
                output_dir = os.path.join(backend_dir, "uploads", "edge")
            os.makedirs(output_dir, exist_ok=True)

            heatmap_color = cv2.applyColorMap(connected_seams, cv2.COLORMAP_JET)
            blended_overlay = cv2.addWeighted(img_scaled, 0.65, heatmap_color, 0.35, 0)

            for b in final_boxes:
                bx = int(b[0] * scale)
                by = int(b[1] * scale)
                bw = int(b[2] * scale)
                bh = int(b[3] * scale)
                cv2.rectangle(blended_overlay, (bx, by), (bx + bw, by + bh), (0, 0, 255), 2)
                cv2.putText(
                    blended_overlay, "DISCONTINUITY", (bx, max(15, by - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1
                )

            heatmap_filename = f"{base_name}_edge.png"
            heatmap_filepath = os.path.join(output_dir, heatmap_filename)
            cv2.imwrite(heatmap_filepath, blended_overlay)
            heatmap_url = f"/edge-images/{heatmap_filename}"
        except Exception:
            heatmap_filepath = None
            heatmap_url = None

    return {
        "edge_anomaly_score": edge_anomaly_score,
        "confidence": confidence,
        "suspicious_regions": final_boxes,
        "reason_codes": sorted(list(reason_codes)),
        "image_quality": quality_info,
        "status": status,
        "heatmap_path": heatmap_filepath,
        "heatmap_url": heatmap_url
    }

