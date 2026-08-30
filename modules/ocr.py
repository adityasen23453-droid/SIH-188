import os
import re
import pytesseract
from PIL import Image
from passporteye import read_mrz
from paddleocr import PaddleOCR

tesseract_bin = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(tesseract_bin):
    pytesseract.pytesseract.tesseract_cmd = tesseract_bin

_ocr_engine = None


def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = PaddleOCR(use_angle_cls=False, lang='en', enable_mkldnn=False)
    return _ocr_engine


def extract_passport(image_path: str) -> dict:
    try:
        mrz = read_mrz(image_path)
    except Exception:
        mrz = None

    if mrz is None:
        return {
            "name": None,
            "passport_number": None,
            "nationality": None,
            "date_of_birth": None,
            "date_of_expiry": None,
            "gender": None,
            "mrz_valid_score": 0,
            "mrz_line2": None
        }

    mrz_dict = mrz.to_dict()
    names = mrz_dict.get("names", "")
    surname = mrz_dict.get("surname", "")
    full_name = f"{names} {surname}".strip() or None

    raw_text = mrz_dict.get("raw_text", "") or ""
    raw_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    mrz_line2 = raw_lines[1] if len(raw_lines) >= 2 else None

    return {
        "name": full_name,
        "passport_number": mrz_dict.get("number"),
        "nationality": mrz_dict.get("nationality"),
        "date_of_birth": mrz_dict.get("date_of_birth"),
        "date_of_expiry": mrz_dict.get("expiration_date"),
        "gender": mrz_dict.get("sex"),
        "mrz_valid_score": getattr(mrz, "valid_score", 0),
        "mrz_line2": mrz_line2
    }


def extract_generic(image_path: str, document_type: str) -> dict:
    raw_text = []
    try:
        ocr = get_ocr_engine()
        result = ocr.ocr(image_path)
        if isinstance(result, list) and len(result) > 0:
            first = result[0]
            if isinstance(first, dict) and "rec_texts" in first:
                raw_text = [t.strip() for t in first["rec_texts"] if t and t.strip()]
            elif isinstance(first, list):
                for line in first:
                    if line and len(line) >= 2 and line[1]:
                        text = line[1][0]
                        if text:
                            raw_text.append(text.strip())
    except Exception:
        pass

    if not raw_text:
        try:
            img = Image.open(image_path)
            ocr_str = pytesseract.image_to_string(img)
            raw_text = [line.strip() for line in ocr_str.split("\n") if line.strip()]
        except Exception:
            pass

    extracted_fields = {}
    patterns = [
        ("name", r"(?i)^(?:name|full\s*name|hame)\s*[:\-]?\s*(.+)"),
        ("date_of_birth", r"(?i)^(?:dob|date\s*of\s*birth)\s*[:\-]?\s*(.+)"),
        ("visa_number", r"(?i)^(?:visa\s*n(?:o|umber)?)\s*[:\-]?\s*(.+)"),
        ("id_number", r"(?i)^(?:id\s*n(?:o|umber)?|identity\s*n(?:o|umber)?)\s*[:\-]?\s*(.+)"),
        ("nationality", r"(?i)^(?:nationality|nat)\s*[:\-]?\s*(.+)"),
        ("valid_until", r"(?i)^(?:valid\s*until|expiry\s*date|date\s*of\s*expiry|exp)\s*[:\-]?\s*(.+)")
    ]

    for idx, text in enumerate(raw_text):
        for field_key, regex in patterns:
            if field_key not in extracted_fields:
                match = re.search(regex, text)
                if match and match.group(1).strip():
                    extracted_fields[field_key] = match.group(1).strip()
                elif re.match(r"(?i)^(?:name|hame|dob|date\s*of\s*birth|visa\s*n(?:o|umber)?|id\s*n(?:o|umber)?|nationality|valid\s*until)\s*[:\-]?$", text):
                    label_match = re.search(r"(?i)^(name|hame|dob|date\s*of\s*birth|visa\s*n(?:o|umber)?|id\s*n(?:o|umber)?|nationality|valid\s*until)", text)
                    if label_match:
                        matched_label = label_match.group(1).lower()
                        target_key = None
                        if "name" in matched_label or "hame" in matched_label:
                            target_key = "name"
                        elif "dob" in matched_label or "birth" in matched_label:
                            target_key = "date_of_birth"
                        elif "visa" in matched_label:
                            target_key = "visa_number"
                        elif "id" in matched_label:
                            target_key = "id_number"
                        elif "nat" in matched_label:
                            target_key = "nationality"
                        elif "valid" in matched_label or "exp" in matched_label:
                            target_key = "valid_until"

                        if target_key and target_key not in extracted_fields and idx + 1 < len(raw_text):
                            next_val = raw_text[idx + 1].strip()
                            if next_val:
                                extracted_fields[target_key] = next_val

    return {
        "raw_text": raw_text,
        "extracted_fields": extracted_fields
    }


def run_ocr(image_path: str, document_type: str) -> dict:
    if document_type == "passport":
        passport_data = extract_passport(image_path)
        has_valid_mrz = (
            passport_data.get("mrz_valid_score", 0) > 0
            and (passport_data.get("passport_number") or passport_data.get("name"))
        )
        if has_valid_mrz:
            return {
                "document_type": document_type,
                "method_used": "mrz",
                "fields": passport_data,
                "raw_text": None
            }

        generic_data = extract_generic(image_path, document_type)
        return {
            "document_type": document_type,
            "method_used": "generic_ocr",
            "fields": generic_data["extracted_fields"],
            "raw_text": generic_data["raw_text"],
            "note": "MRZ extraction failed or returned empty fields, used generic OCR fallback"
        }

    generic_data = extract_generic(image_path, document_type)
    return {
        "document_type": document_type,
        "method_used": "generic_ocr",
        "fields": generic_data["extracted_fields"],
        "raw_text": generic_data["raw_text"]
    }

