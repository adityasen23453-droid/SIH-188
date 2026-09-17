import io
import os
from typing import Optional, Any
import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageStat, ExifTags
import torch
import torch.nn.functional as F

from core.config import get_settings
from modules.edge_forensics import detect_boundary_discontinuities

_forgery_model = None
_forgery_processor = None


def get_forgery_model_and_processor():
    """
    Loads Hugging Face Vision Transformer (zodumair/document-forgery-detector).
    Uses local cache (~/.cache/huggingface/hub) with fast offline persistence.
    """
    global _forgery_model, _forgery_processor
    if _forgery_model is None or _forgery_processor is None:
        try:
            from transformers import ViTForImageClassification, ViTImageProcessor
            model_id = "zodumair/document-forgery-detector"
            snapshot_base = os.path.expanduser("~/.cache/huggingface/hub/models--zodumair--document-forgery-detector/snapshots")
            load_path = model_id
            if os.path.exists(snapshot_base):
                snapshots = [os.path.join(snapshot_base, s) for s in os.listdir(snapshot_base) if os.path.isdir(os.path.join(snapshot_base, s))]
                if snapshots:
                    load_path = snapshots[0]

            _forgery_processor = ViTImageProcessor.from_pretrained(load_path)
            _forgery_model = ViTForImageClassification.from_pretrained(load_path)
            _forgery_model.eval()
        except Exception as e:
            print(f"Warning: Could not initialize HF ViT model: {e}")
            _forgery_model = None
            _forgery_processor = None
    return _forgery_model, _forgery_processor


def compute_ela_for_model(image_path: str, quality: int = 90, scale: int = 15) -> Image.Image:
    """
    Computes an ELA difference map blended with the original image (alpha=0.3)
    specifically as an input preprocessing step for the document forgery detection ViT model.
    """
    original = Image.open(image_path).convert("RGB")
    if max(original.size) > 1200:
        original.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    original.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    recompressed = Image.open(buf).convert("RGB")
    ela = ImageChops.difference(original, recompressed)
    max_diff = max([ex[1] for ex in ela.getextrema()]) or 1
    ela = ela.point(lambda px: min(255, int(px * (255.0 / max_diff) * (scale / 10.0))))
    return Image.blend(original, ela, alpha=0.3)



def detect_ela_hotspots(diff_img: Image.Image) -> list[list[int]]:
    """
    Detects clusters of high-compression anomaly pixels from ELA difference map.
    Returns list of bounding boxes [x, y, w, h] indicating localized tamper hotspots.
    """
    try:
        diff_arr = np.array(diff_img.convert("L"))
        img_h, img_w = diff_arr.shape
        total_area = img_h * img_w

        mean_val = np.mean(diff_arr)
        std_val = np.std(diff_arr)
        thresh_val = max(20, min(120, int(mean_val + 2.2 * std_val)))

        _, binary = cv2.threshold(diff_arr, thresh_val, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        dilated = cv2.dilate(binary, kernel, iterations=2)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for c in contours:
            area = cv2.contourArea(c)
            if 150 < area < (total_area * 0.45):
                x, y, w, h = cv2.boundingRect(c)
                boxes.append([int(x), int(y), int(w), int(h)])

        boxes_sorted = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
        return boxes_sorted[:5]
    except Exception:
        return []


def run_ela(image_path: str, output_dir: str = None) -> dict:
    """
    Performs Error Level Analysis (ELA) on an image file.
    Re-saves at JPEG Q=90 and measures pixel delta to detect spliced or re-saved regions.
    """
    if output_dir is None:
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        output_dir = os.path.join(backend_dir, "uploads", "ela")

    try:
        if not os.path.exists(image_path):
            return {
                "ela_score": 0.0,
                "ela_image_path": None,
                "ela_image_url": None,
                "tamper_boxes": [],
                "error": f"Image file not found: {image_path}"
            }

        os.makedirs(output_dir, exist_ok=True)

        with Image.open(image_path) as orig_img:
            is_png = (getattr(orig_img, "format", "") == "PNG") or image_path.lower().endswith(".png")
            note = "Image converted from PNG to JPEG baseline for ELA analysis." if is_png else None

            rgb_img = orig_img.convert("RGB")
            if max(rgb_img.size) > 1200:
                rgb_img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            rgb_img.save(buffer, format="JPEG", quality=90)
            buffer.seek(0)

            with Image.open(buffer) as resaved_img:
                diff_img = ImageChops.difference(rgb_img, resaved_img)
                tamper_boxes = detect_ela_hotspots(diff_img)

                stat = ImageStat.Stat(diff_img)
                avg_diff = sum(stat.mean) / len(stat.mean) if stat.mean else 0.0

                raw_ela_score = avg_diff * 4.0
                ela_score = round(max(0.0, min(100.0, raw_ela_score)), 2)

                max_diff = max(stat.extrema[0][1], stat.extrema[1][1], stat.extrema[2][1]) if stat.extrema else 1
                enhance_scale = max(10.0, 255.0 / max(1.0, max_diff))
                amplified_diff = ImageEnhance.Brightness(diff_img).enhance(enhance_scale)

                base_name = os.path.splitext(os.path.basename(image_path))[0]
                ela_filename = f"{base_name}_ela.png"
                ela_filepath = os.path.join(output_dir, ela_filename)
                amplified_diff.save(ela_filepath, format="PNG")

                # In-memory blend for ViT model (eliminates duplicate disk I/O and recompression)
                blended_for_vit = Image.blend(rgb_img, amplified_diff.convert("RGB"), alpha=0.3)

                res = {
                    "ela_score": ela_score,
                    "ela_image_path": ela_filepath,
                    "ela_image_url": f"/ela-images/{ela_filename}",
                    "tamper_boxes": tamper_boxes,
                    "_blended_img": blended_for_vit
                }
                if note:
                    res["note"] = note
                return res

    except Exception as e:
        return {
            "ela_score": 0.0,
            "ela_image_path": None,
            "ela_image_url": None,
            "tamper_boxes": [],
            "error": f"ELA processing failed: {str(e)}"
        }


def check_metadata(image_path: str) -> dict:
    """
    Extracts EXIF metadata and detects signs of digital manipulation software:
    Photoshop, GIMP, Canva, Corel, Pixelmator.
    """
    manipulation_tools = ["photoshop", "gimp", "canva", "coreldraw", "pixelmator", "affinity", "paint.net"]

    try:
        if not os.path.exists(image_path):
            return {
                "editing_software_detected": False,
                "software_name": None,
                "metadata_stripped": True,
                "raw_exif_summary": {},
                "error": "File not found"
            }

        with Image.open(image_path) as img:
            raw_exif = img._getexif()

            if not raw_exif:
                return {
                    "editing_software_detected": False,
                    "software_name": None,
                    "metadata_stripped": True,
                    "raw_exif_summary": {},
                    "note": "EXIF metadata is absent (common in web uploads or metadata-stripped forged images)"
                }

            exif_data = {}
            for tag_id, value in raw_exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                try:
                    if isinstance(value, bytes):
                        value = value.decode("utf-8", errors="replace")
                    elif not isinstance(value, (str, int, float, list, dict)):
                        value = str(value)
                    exif_data[tag_name] = value
                except Exception:
                    exif_data[tag_name] = str(value)

            detected_software = None
            for key in ["Software", "ProcessingSoftware", "ImageDescription", "Artist"]:
                val = str(exif_data.get(key, "")).lower()
                for tool in manipulation_tools:
                    if tool in val:
                        detected_software = exif_data.get(key)
                        break
                if detected_software:
                    break

            exif_summary = {
                k: exif_data[k]
                for k in ["Make", "Model", "Software", "DateTime", "DateTimeOriginal"]
                if k in exif_data
            }

            return {
                "editing_software_detected": detected_software is not None,
                "software_name": detected_software,
                "metadata_stripped": False,
                "raw_exif_summary": exif_summary
            }

    except Exception as e:
        return {
            "editing_software_detected": False,
            "software_name": None,
            "metadata_stripped": True,
            "raw_exif_summary": {},
            "error": f"Metadata extraction error: {str(e)}"
        }


def analyze_stamp_region(image_path: str) -> dict:
    """
    Forensic analysis of border control stamps and consular seals:
    Isolates ink colors (cyan, magenta, dark blue, purple) in HSV space,
    checks edge continuity, and detects digitally copy-pasted or spliced stamps.
    """
    try:
        if not os.path.exists(image_path):
            return {"stamp_detected": False, "stamp_count": 0, "stamp_boxes": [], "suspicious_stamp_splicing": False}

        img = cv2.imread(image_path)
        if img is None:
            return {"stamp_detected": False, "stamp_count": 0, "stamp_boxes": [], "suspicious_stamp_splicing": False}

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        img_h, img_w = img.shape[:2]
        total_area = img_h * img_w

        # Common border ink color masks (Blue / Magenta / Violet / Red)
        lower_blue = np.array([100, 50, 50])
        upper_blue = np.array([140, 255, 255])
        mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)

        lower_magenta = np.array([140, 50, 50])
        upper_magenta = np.array([170, 255, 255])
        mask_magenta = cv2.inRange(hsv, lower_magenta, upper_magenta)

        stamp_mask = cv2.bitwise_or(mask_blue, mask_magenta)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        stamp_cleaned = cv2.morphologyEx(stamp_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(stamp_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        stamp_boxes = []
        suspicious_splicing = False

        for c in contours:
            area = cv2.contourArea(c)
            if (total_area * 0.005) < area < (total_area * 0.15):
                x, y, w, h = cv2.boundingRect(c)
                aspect_ratio = float(w) / float(h)
                if 0.5 < aspect_ratio < 2.0:
                    stamp_boxes.append([int(x), int(y), int(w), int(h)])

                    stamp_roi = img[y:y+h, x:x+w]
                    stamp_gray = cv2.cvtColor(stamp_roi, cv2.COLOR_BGR2GRAY)
                    lap_var = cv2.Laplacian(stamp_gray, cv2.CV_64F).var()

                    # Abnormally sharp rectangular boundary or zero noise indicates digital insertion
                    if lap_var > 320.0 or lap_var < 8.0:
                        suspicious_splicing = True

        return {
            "stamp_detected": len(stamp_boxes) > 0,
            "stamp_count": len(stamp_boxes),
            "stamp_boxes": stamp_boxes[:4],
            "suspicious_stamp_splicing": suspicious_splicing,
            "note": "Border stamp HSV ink forensics analyzed."
        }
    except Exception as e:
        return {
            "stamp_detected": False,
            "stamp_count": 0,
            "stamp_boxes": [],
            "suspicious_stamp_splicing": False,
            "error": str(e)
        }


def extract_noise_residual_features(image_bgr: np.ndarray) -> dict:
    """
    Phase 4 Noise Residual Feature Extraction:
    Computes high-frequency spatial noise residual variance across document quadrants.
    Uses patch-based background noise floor estimation to distinguish localized digital splicing
    from regular document content (photographs, printed text).
    """
    try:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # High-frequency residual (removes low/mid-frequency visual structure)
        denoised = cv2.medianBlur(gray, 3)
        residual = cv2.absdiff(gray, denoised)

        mid_h, mid_w = h // 2, w // 2
        quads = [
            residual[0:mid_h, 0:mid_w],
            residual[0:mid_h, mid_w:w],
            residual[mid_h:h, 0:mid_w],
            residual[mid_h:h, mid_w:w]
        ]

        def compute_quadrant_noise_stats(quad):
            qh, qw = quad.shape
            ps = 32
            variances = []
            for y in range(0, qh - ps, ps):
                for x in range(0, qw - ps, ps):
                    patch = quad[y:y+ps, x:x+ps]
                    variances.append(float(np.var(patch)))
            if not variances:
                return float(np.var(quad)), 1.0
            variances.sort()
            # 25th percentile represents true background noise floor
            floor = variances[len(variances) // 4]
            # Ratio of max patch outlier to median patch evaluates localized spliced injection
            med = max(0.5, float(np.median(variances)))
            max_outlier_ratio = max(variances) / med
            return floor, max_outlier_ratio

        stats = [compute_quadrant_noise_stats(q) for q in quads]
        floors = [s[0] for s in stats]
        outlier_ratios = [s[1] for s in stats]

        min_f = max(0.5, min(floors))
        max_f = max(floors)
        floor_disparity = round(max_f / min_f, 2)
        max_patch_outlier = round(max(outlier_ratios), 2)

        # Splicing is detected if background noise floors between quadrants diverge wildly (> 4.5)
        is_anomalous = floor_disparity > 4.5
        residual_score = min(100.0, max(0.0, (floor_disparity - 2.5) * 20.0)) if is_anomalous else 0.0

        return {
            "quadrant_variances": [round(f, 2) for f in floors],
            "noise_disparity_ratio": floor_disparity,
            "noise_splicing_detected": is_anomalous,
            "residual_anomaly_score": round(residual_score, 1)
        }
    except Exception:
        return {
            "quadrant_variances": [],
            "noise_disparity_ratio": 1.0,
            "max_patch_outlier_ratio": 1.0,
            "noise_splicing_detected": False,
            "residual_anomaly_score": 0.0
        }


def check_ai_manipulation(image_path: str, blended_img: Image.Image = None) -> dict:
    """
    Hugging Face Vision Transformer (zodumair/document-forgery-detector) + High-Frequency Noise Forensics:
    Runs ViT model over alpha-blended ELA composite map (alpha=0.3).
    Extracts high-frequency noise residual quadrant analysis for multi-signal forensics.
    """
    try:
        if not os.path.exists(image_path):
            return {
                "label": None,
                "confidence": None,
                "ai_generated_likelihood": None,
                "error": f"Image file not found: {image_path}"
            }

        img_bgr = cv2.imread(image_path)
        noise_res = extract_noise_residual_features(img_bgr) if img_bgr is not None else {}

        model, processor = get_forgery_model_and_processor()
        if model is not None and processor is not None:
            if blended_img is None:
                blended_img = compute_ela_for_model(image_path)

            # Pre-scale directly to 224x224 to make ViT preprocessing and tensor transfer instantaneous
            if blended_img.size != (224, 224):
                blended_img = blended_img.resize((224, 224), Image.Resampling.BILINEAR)

            inputs = processor(images=blended_img, return_tensors="pt")

            # Throttle torch CPU threads during inference to prevent starving PaddleOCR/FastAPI worker
            prev_num_threads = torch.get_num_threads()
            try:
                if prev_num_threads > 2:
                    torch.set_num_threads(2)
                with torch.no_grad():
                    outputs = model(**inputs)
            finally:
                if prev_num_threads > 2:
                    torch.set_num_threads(prev_num_threads)

            probs = F.softmax(outputs.logits, dim=-1)[0]
            id2label = model.config.id2label or {0: "real", 1: "forged"}

            predicted_idx = torch.argmax(probs).item()
            predicted_label = id2label.get(predicted_idx, "real" if predicted_idx == 0 else "forged")
            predicted_confidence = float(probs[predicted_idx].item())

            forged_idx = next((idx for idx, label in id2label.items() if "forged" in str(label).lower()), 1)
            forged_prob = float(probs[forged_idx].item())

            ai_generated_likelihood = round(max(0.0, min(100.0, forged_prob * 100.0)), 2)

            return {
                "label": predicted_label,
                "confidence": round(predicted_confidence, 4),
                "ai_generated_likelihood": ai_generated_likelihood,
                "model_name": "zodumair/document-forgery-detector (ViT)",
                "noise_residuals": noise_res
            }
        else:
            residual_score = noise_res.get("residual_anomaly_score", 0.0)
            combined_likelihood = round(residual_score, 2)
            label = "forged" if combined_likelihood > 50.0 else "real"
            return {
                "label": label,
                "confidence": 0.75,
                "ai_generated_likelihood": combined_likelihood,
                "model_name": "local_noise_residual_fallback",
                "noise_residuals": noise_res
            }

    except Exception as e:
        return {
            "label": None,
            "confidence": None,
            "ai_generated_likelihood": None,
            "error": str(e)
        }


def run_tampering_detection(
    image_path: str,
    context: Optional[Any] = None,
    image_bgr: Optional[np.ndarray] = None
) -> dict:
    """
    Multi-Signal Tampering Forensics Coordinator:
    Combines Hugging Face ViT Forgery Detector, ELA compression analysis,
    EXIF metadata tool detection, border stamp HSV forensics, noise residual disparity,
    and Edge Discontinuity Forensics.
    """
    settings = get_settings()

    ela_res = run_ela(image_path)
    blended = ela_res.pop("_blended_img", None)
    meta_res = check_metadata(image_path)
    ai_res = check_ai_manipulation(image_path, blended_img=blended)
    stamp_res = analyze_stamp_region(image_path)

    ela_score = ela_res.get("ela_score", 0.0)

    # Base weighted score from ELA
    ela_based_score = ela_score * 0.50

    # Points for metadata signals
    if meta_res.get("editing_software_detected"):
        ela_based_score += 25.0
    elif meta_res.get("metadata_stripped"):
        ela_based_score += 5.0

    # Points for suspicious stamp splicing
    if stamp_res.get("suspicious_stamp_splicing"):
        ela_based_score += 20.0

    # Points for localized tamper hotspots
    tamper_boxes = ela_res.get("tamper_boxes", [])
    if len(tamper_boxes) >= 2:
        ela_based_score += 15.0
    elif len(tamper_boxes) == 1:
        ela_based_score += 8.0

    # Points for Hugging Face ViT model prediction
    ai_score = ai_res.get("ai_generated_likelihood")
    noise_anomaly = ai_res.get("noise_residuals", {}).get("noise_splicing_detected", False)

    if ai_score is not None:
        final_likelihood = max(ela_based_score, (ela_based_score * 0.4) + (ai_score * 0.6))
    else:
        final_likelihood = ela_based_score

    final_likelihood = round(max(0.0, min(100.0, final_likelihood)), 2)

    # Edge Discontinuity & Boundary Forensics Integration
    edge_res = None
    if getattr(settings, "EDGE_FORENSICS_ENABLED", True):
        img_input = image_bgr
        if img_input is None and context is not None and getattr(context, "clahe_bgr", None) is not None:
            img_input = context.clahe_bgr
        elif img_input is None and context is not None and getattr(context, "image_bgr", None) is not None:
            img_input = context.image_bgr
        if img_input is None:
            img_input = image_path

        face_bbox = None
        if context is not None and getattr(context, "face_bbox", None) is not None:
            face_bbox = context.face_bbox

        try:
            edge_res = detect_boundary_discontinuities(img_input, face_bbox=face_bbox)
        except Exception as e:
            edge_res = {
                "edge_anomaly_score": 0.0,
                "confidence": 0.0,
                "suspicious_regions": [],
                "reason_codes": ["EDGE_EXECUTION_ERROR"],
                "image_quality": {"quality_status": "ERROR"},
                "status": "ERROR",
                "heatmap_path": None,
                "heatmap_url": None,
                "error": str(e)
            }

        # Handle Mode: shadow vs active
        mode = getattr(settings, "EDGE_FORENSICS_MODE", "shadow").lower()
        if mode == "active" and edge_res and edge_res.get("status") != "ERROR":
            edge_score = edge_res.get("edge_anomaly_score", 0.0)
            weight = getattr(settings, "EDGE_FORENSICS_WEIGHT", 0.15)
            final_likelihood = round(
                max(0.0, min(100.0, (final_likelihood * (1.0 - weight)) + (edge_score * weight))),
                2
            )

    if final_likelihood < 30.0:
        risk_level = "low"
    elif final_likelihood <= 60.0:
        risk_level = "medium"
    else:
        risk_level = "high"

    result = {
        "ela": ela_res,
        "metadata": meta_res,
        "ai_detection": ai_res,
        "stamp_forensics": stamp_res,
        "tampering_likelihood": final_likelihood,
        "risk_level": risk_level
    }
    if edge_res is not None:
        result["edge_forensics"] = edge_res

    return result
