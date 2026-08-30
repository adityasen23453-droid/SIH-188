import io
import os
from PIL import Image, ImageChops, ImageEnhance, ImageStat, ExifTags
import torch
import torch.nn.functional as F


def run_ela(image_path: str, output_dir: str = None) -> dict:
    """
    Performs Error Level Analysis (ELA) on an image file.
    Saves amplified difference map in output_dir and computes numerical ela_score (0-100).
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
                "error": f"Image file not found: {image_path}"
            }

        os.makedirs(output_dir, exist_ok=True)

        note = None
        with Image.open(image_path) as orig_img:
            orig_format = orig_img.format or "UNKNOWN"
            if orig_format.upper() not in ["JPEG", "JPG"]:
                note = f"Input image format is {orig_format}; converted to JPEG for ELA analysis"

            # Convert image to RGB mode
            rgb_img = orig_img.convert("RGB")

            # Re-save to JPEG in-memory at quality=90
            buffer = io.BytesIO()
            rgb_img.save(buffer, format="JPEG", quality=90)
            buffer.seek(0)

            with Image.open(buffer) as resaved_img:
                # Compute absolute pixel difference map
                diff_img = ImageChops.difference(rgb_img, resaved_img)

                # Calculate ELA score based on mean pixel difference
                stat = ImageStat.Stat(diff_img)
                avg_diff = sum(stat.mean) / len(stat.mean) if stat.mean else 0.0

                # Scale avg_diff (typically 0-25) to 0-100 ELA score
                raw_ela_score = avg_diff * 4.0
                ela_score = round(max(0.0, min(100.0, raw_ela_score)), 2)

                # Amplify difference map for visual clarity
                max_diff = max(stat.extrema[0][1], stat.extrema[1][1], stat.extrema[2][1]) if stat.extrema else 1
                enhance_scale = max(10.0, 255.0 / max(1.0, max_diff))
                amplified_diff = ImageEnhance.Brightness(diff_img).enhance(enhance_scale)

                # Determine output filename & path
                base_name = os.path.splitext(os.path.basename(image_path))[0]
                ela_filename = f"{base_name}_ela.png"
                ela_filepath = os.path.join(output_dir, ela_filename)

                amplified_diff.save(ela_filepath, format="PNG")

                ela_url = f"/ela-images/{ela_filename}"

                res = {
                    "ela_score": ela_score,
                    "ela_image_path": ela_filepath,
                    "ela_image_url": ela_url
                }
                if note:
                    res["note"] = note
                return res

    except Exception as e:
        return {
            "ela_score": 0.0,
            "ela_image_path": None,
            "ela_image_url": None,
            "error": f"ELA processing failed: {str(e)}"
        }


def check_metadata(image_path: str) -> dict:
    """
    Reads EXIF metadata and checks for signs of editing software or stripped metadata.
    """
    editing_software_list = [
        "photoshop", "gimp", "paint", "canva", "lightroom",
        "photofiltre", "pixlr", "snapseed", "fotor", "affinity", "pixelmator"
    ]

    try:
        if not os.path.exists(image_path):
            return {
                "editing_software_detected": False,
                "software_name": None,
                "metadata_stripped": True,
                "raw_exif_summary": {},
                "error": "File not found"
            }

        exif_summary = {}
        editing_software_detected = False
        detected_software_name = None

        with Image.open(image_path) as img:
            exif_data = img.getexif()

            if not exif_data or len(exif_data) == 0:
                return {
                    "editing_software_detected": False,
                    "software_name": None,
                    "metadata_stripped": True,
                    "raw_exif_summary": {}
                }

            # Map EXIF tag IDs to human-readable tag names
            for tag_id, value in exif_data.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                # Only keep key fields in raw_exif_summary
                if tag_name in ["Software", "Make", "Model", "DateTime", "DateTimeOriginal", "Orientation", "ImageDescription"]:
                    # Ensure value is string serializable
                    exif_summary[tag_name] = str(value)

                # Check string values for editing software names
                val_str = str(value).lower()
                for soft in editing_software_list:
                    if soft in val_str:
                        editing_software_detected = True
                        detected_software_name = str(value)
                        break

            return {
                "editing_software_detected": editing_software_detected,
                "software_name": detected_software_name,
                "metadata_stripped": len(exif_summary) == 0,
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


def compute_ela_for_model(image_path: str, quality: int = 90, scale: int = 15) -> Image.Image:
    """
    Computes an ELA difference map blended with the original image (alpha=0.3)
    specifically as an input preprocessing step for the document forgery detection ViT model.
    """
    original = Image.open(image_path).convert('RGB')
    buf = io.BytesIO()
    original.save(buf, 'JPEG', quality=quality)
    buf.seek(0)
    recompressed = Image.open(buf).convert('RGB')
    ela = ImageChops.difference(original, recompressed)
    max_diff = max([ex[1] for ex in ela.getextrema()]) or 1
    ela = ela.point(lambda px: min(255, int(px * (255.0 / max_diff) * (scale / 10.0))))
    return Image.blend(original, ela, alpha=0.3)


_forgery_model = None
_forgery_processor = None


def get_forgery_model_and_processor():
    global _forgery_model, _forgery_processor
    if _forgery_model is None or _forgery_processor is None:
        from transformers import ViTForImageClassification, ViTImageProcessor
        model_id = "zodumair/document-forgery-detector"
        _forgery_processor = ViTImageProcessor.from_pretrained(model_id)
        _forgery_model = ViTForImageClassification.from_pretrained(model_id)
    return _forgery_model, _forgery_processor


def check_ai_manipulation(image_path: str) -> dict:
    """
    Runs document forgery detection using pretrained Hugging Face ViT model (zodumair/document-forgery-detector).
    """
    try:
        if not os.path.exists(image_path):
            return {
                "label": None,
                "confidence": None,
                "ai_generated_likelihood": None,
                "error": f"Image file not found: {image_path}"
            }

        blended_img = compute_ela_for_model(image_path)
        model, processor = get_forgery_model_and_processor()

        inputs = processor(images=blended_img, return_tensors="pt")
        with torch.no_grad():
            outputs = model(**inputs)

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
            "ai_generated_likelihood": ai_generated_likelihood
        }
    except Exception as e:
        return {
            "label": None,
            "confidence": None,
            "ai_generated_likelihood": None,
            "error": str(e)
        }


def run_tampering_detection(image_path: str) -> dict:
    """
    Performs ELA, metadata checks, and AI manipulation / document forgery detection,
    returning a combined tampering_likelihood score (0-100) clamped strictly to [0.0, 100.0]
    and risk_level ('low', 'medium', 'high').
    """
    ela_res = run_ela(image_path)
    meta_res = check_metadata(image_path)
    ai_res = check_ai_manipulation(image_path)

    ela_score = ela_res.get("ela_score", 0.0)

    # Base weighted score from ELA
    ela_based_score = ela_score * 0.7

    # Add points for metadata signals
    if meta_res.get("editing_software_detected"):
        ela_based_score += 30.0
    elif meta_res.get("metadata_stripped"):
        ela_based_score += 5.0

    ela_based_score = round(max(0.0, min(100.0, ela_based_score)), 2)

    ai_score = ai_res.get("ai_generated_likelihood")

    if ai_score is not None:
        combined_score = max(ela_based_score, ai_score)
    else:
        combined_score = ela_based_score
        if "note" not in ai_res:
            ai_res["note"] = "AI manipulation detection unavailable; using ELA and metadata scoring only."

    tampering_likelihood = round(max(0.0, min(100.0, combined_score)), 2)

    # Categorize risk level based on simple thresholds
    if tampering_likelihood < 30.0:
        risk_level = "low"
    elif tampering_likelihood <= 60.0:
        risk_level = "medium"
    else:
        risk_level = "high"

    return {
        "ela": ela_res,
        "metadata": meta_res,
        "ai_detection": ai_res,
        "tampering_likelihood": tampering_likelihood,
        "risk_level": risk_level
    }
