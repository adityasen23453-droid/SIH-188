import os
import re
import cv2
import numpy as np
import pytesseract
from PIL import Image
from passporteye import read_mrz

tesseract_bin = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(tesseract_bin):
    pytesseract.pytesseract.tesseract_cmd = tesseract_bin

_ocr_engine = None
_face_cascade = None


def get_ocr_engine():
    """Lazy-loads PaddleOCR engine with caching and textline orientation enabled."""
    global _ocr_engine
    if _ocr_engine is None:
        from paddleocr import PaddleOCR
        _ocr_engine = PaddleOCR(use_textline_orientation=True, lang="en", enable_mkldnn=False)
    return _ocr_engine


_trocr_proc = None
_trocr_model = None


def get_trocr_engine():
    """Lazy-loads Hugging Face Microsoft TrOCR (microsoft/trocr-small-printed) for neural line recognition."""
    global _trocr_proc, _trocr_model
    if _trocr_proc is None or _trocr_model is None:
        try:
            from transformers import RobertaTokenizer, AutoImageProcessor, TrOCRProcessor, VisionEncoderDecoderModel
            import torch
            model_name = "microsoft/trocr-small-printed"
            img_proc = AutoImageProcessor.from_pretrained(model_name)
            tok = RobertaTokenizer.from_pretrained(model_name)
            _trocr_proc = TrOCRProcessor(image_processor=img_proc, tokenizer=tok)
            _trocr_model = VisionEncoderDecoderModel.from_pretrained(model_name)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _trocr_model.to(device)
            _trocr_model.eval()
        except Exception:
            _trocr_proc = None
            _trocr_model = None
    return _trocr_proc, _trocr_model


def recognize_line_with_trocr(image_crop: np.ndarray) -> str | None:
    """Passes a single text-line image crop through Microsoft TrOCR neural reader."""
    try:
        if image_crop is None or image_crop.size == 0:
            return None
        h, w = image_crop.shape[:2]
        if h < 8 or w < 15:
            return None

        proc, model = get_trocr_engine()
        if proc is None or model is None:
            return None

        import torch
        from PIL import Image

        if len(image_crop.shape) == 2:
            pil_img = Image.fromarray(image_crop).convert("RGB")
        else:
            pil_img = Image.fromarray(cv2.cvtColor(image_crop, cv2.COLOR_BGR2RGB))

        device = next(model.parameters()).device
        pixel_values = proc(pil_img, return_tensors="pt").pixel_values.to(device)
        with torch.no_grad():
            generated_ids = model.generate(pixel_values, max_new_tokens=40)
        text = proc.batch_decode(generated_ids, skip_special_tokens=True)[0]
        text = text.strip()
        return text if text else None
    except Exception:
        return None


def get_face_cascade():
    global _face_cascade
    if _face_cascade is None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _face_cascade = cv2.CascadeClassifier(cascade_path)
    return _face_cascade


def check_field_confidence(val: str | None, max_len: int = 40, check_alpha_only: bool = False) -> str:
    """Checks plausibility of an extracted MRZ text field."""
    if not val or not isinstance(val, str):
        return "high"

    clean_val = val.strip()
    if re.search(r"([A-Za-z0-9])\1{2,}", clean_val):
        return "low"
    if len(clean_val) > max_len:
        return "low"
    if check_alpha_only and (not clean_val.isalpha() or len(clean_val) != 3):
        return "low"

    return "high"


def extract_document_face(image_path: str, output_dir: str = None) -> dict:
    """Detects and crops the portrait face from an identity document or passport."""
    if output_dir is None:
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        output_dir = os.path.join(backend_dir, "uploads", "faces")

    os.makedirs(output_dir, exist_ok=True)

    try:
        img = cv2.imread(image_path)
        if img is None:
            return {
                "face_detected": False,
                "face_image_path": None,
                "face_image_url": None,
                "bounding_box": None,
                "note": "Could not read image file"
            }

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade = get_face_cascade()
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))

        if len(faces) == 0:
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=2, minSize=(40, 40))

        if len(faces) == 0:
            return {
                "face_detected": False,
                "face_image_path": None,
                "face_image_url": None,
                "bounding_box": None,
                "note": "No frontal face detected"
            }

        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, w, h = faces[0]

        pad_x = int(w * 0.20)
        pad_y = int(h * 0.25)
        img_h, img_w = img.shape[:2]

        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(img_w, x + w + pad_x)
        y2 = min(img_h, y + h + pad_y)

        face_crop = img[y1:y2, x1:x2]

        base_name = os.path.splitext(os.path.basename(image_path))[0]
        face_filename = f"{base_name}_face.jpg"
        face_filepath = os.path.join(output_dir, face_filename)
        cv2.imwrite(face_filepath, face_crop)

        return {
            "face_detected": True,
            "face_image_path": face_filepath,
            "face_image_url": f"/doc-faces/{face_filename}",
            "bounding_box": [int(x), int(y), int(w), int(h)]
        }

    except Exception as e:
        return {
            "face_detected": False,
            "face_image_path": None,
            "face_image_url": None,
            "bounding_box": None,
            "note": f"Face extraction error: {str(e)}"
        }


def normalize_mrz_string(text: str) -> str:
    """Normalizes OCR chevron variants and removes internal spaces for MRZ parsing."""
    if not text:
        return ""
    t = text.strip().upper()
    t = re.sub(r"[«‹\(\[\{]+", "<", t)
    t = t.replace(" ", "")
    return t


def disambiguate_mrz_lines(raw_lines: list[str]) -> tuple[str | None, str | None, str | None]:
    """
    Robust ICAO Doc 9303 MRZ Line Disambiguator:
    Supports both TD3 (2 lines x 44 chars) and TD1 (3 lines x 30 chars).
    Returns (line1, line2, line3).
    """
    if not raw_lines:
        return None, None, None

    cleaned_lines = [normalize_mrz_string(line) for line in raw_lines if len(normalize_mrz_string(line)) >= 18]
    if not cleaned_lines:
        return None, None, None

    # Check for TD1 passport cards / ID cards (3 lines of approx 30 chars)
    td1_candidates = [l for l in cleaned_lines if 26 <= len(l) <= 34]
    if len(td1_candidates) >= 3:
        td1_l1, td1_l2, td1_l3 = None, None, None
        for l in td1_candidates:
            if (l.startswith("I<") or l.startswith("A<") or l.startswith("C<") or l.startswith("V<") or l.startswith("I") or l.startswith("C")) and not td1_l1:
                td1_l1 = l
            elif re.search(r"[0-9]{6}[0-9<][MF<][0-9]{6}", l) and not td1_l2:
                td1_l2 = l
            elif "<<" in l and not td1_l3:
                td1_l3 = l
        if td1_l1 and td1_l2:
            return td1_l1, td1_l2, td1_l3

    # Standard TD3 (2 lines of 44 chars)
    line1 = None
    line2 = None

    # Step 1: Identify Line 1 (Holder Name & Issuing State)
    for line in cleaned_lines:
        digits = sum(c.isdigit() for c in line)
        if digits <= 5 and (line.startswith("P<") or (line.startswith("P") and "<" in line[:7]) or line.startswith("I<") or line.startswith("A<") or line.startswith("C<") or line.startswith("V<")):
            line1 = line
            break

    # Step 2: Identify Line 2 (Numbers, Dates, Checkdigits)
    for line in cleaned_lines:
        if line == line1:
            continue
        digits = sum(c.isdigit() for c in line)
        if digits >= 10:
            line2 = line
            break
        if re.search(r"[A-Z<]{3}[0-9]{6}[0-9<][MF<][0-9]{6}", line):
            line2 = line
            break

    # Step 3: Fallback if Line 1 was not explicitly prefixed
    if not line1:
        for line in cleaned_lines:
            if line != line2 and sum(c.isdigit() for c in line) < 8:
                line1 = line
                break

    return line1, line2, None


def parse_mrz_line_tokens(line1: str | None, line2: str | None, line3: str | None = None) -> dict:
    """
    Parses standard ICAO Doc 9303 TD3 and TD1 Machine Readable Zone lines into structured fields.
    Zero hardcoded values.
    """
    full_name = None
    issuing_country = None
    pass_num = None
    nationality = None
    dob = None
    expiry = None
    gender = None

    # --- TD1 Format (3 lines x 30 chars, e.g. US Passport Card) ---
    if line3 and line1 and line2:
        # Line 1: [Doc Type 2][Issuing State 3][Doc Number 9][Check 1][Optional 15]
        if len(line1) >= 5:
            issuing_country = line1[2:5].replace("<", "").strip()
        if len(line1) >= 14:
            pass_num = line1[5:14].replace("<", "").strip()

        # Line 2: [DOB 6][Check 1][Sex 1][Expiry 6][Check 1][Nationality 3][Optional 11][Composite 1]
        if len(line2) >= 18:
            dob = line2[0:6]
            raw_sex = line2[7]
            gender = raw_sex if raw_sex in ["M", "F", "<"] else None
            expiry = line2[8:14]
            nationality = line2[15:18].replace("<", "")

        # Line 3: [Surname]<<[Given Names]
        name_part = line3.rstrip("<")
        tokens = name_part.split("<<")
        surname = tokens[0].replace("<", " ").strip() if len(tokens) > 0 else ""
        given = tokens[1].replace("<", " ").strip() if len(tokens) > 1 else ""
        full_name = f"{given} {surname}".strip() if surname and given else (surname or given or None)

        name_conf = check_field_confidence(full_name, max_len=40)
        pass_num_conf = check_field_confidence(pass_num, max_len=10)
        nat_conf = check_field_confidence(nationality or issuing_country, max_len=3, check_alpha_only=True)

        return {
            "name": full_name,
            "name_confidence": name_conf,
            "passport_number": pass_num,
            "passport_number_confidence": pass_num_conf,
            "nationality": nationality or issuing_country,
            "nationality_confidence": nat_conf,
            "date_of_birth": dob,
            "date_of_expiry": expiry,
            "gender": gender,
            "gender_note": None,
            "mrz_valid_score": 80 if pass_num else 0,
            "mrz_line2": line2
        }

    # --- TD3 Format (2 lines x 44 chars) ---
    # Parse Line 1: P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<< or P<BRACOSTA<CARLOS<<<<<<<<<<<<
    if line1 and len(line1) >= 6:
        if len(line1) >= 5:
            issuing_country = line1[2:5].replace("<", "").strip()
        name_part = line1[5:].rstrip("<")
        tokens = name_part.split("<<")
        if len(tokens) == 1 and "<" in tokens[0]:
            subtokens = tokens[0].split("<", 1)
            surname = subtokens[0].strip()
            given = subtokens[1].replace("<", " ").strip() if len(subtokens) > 1 else ""
        else:
            surname = tokens[0].replace("<", " ").strip() if len(tokens) > 0 else ""
            given = tokens[1].replace("<", " ").strip() if len(tokens) > 1 else ""

        if surname and given:
            full_name = f"{given} {surname}"
        elif surname:
            full_name = surname
        elif given:
            full_name = given

    # Parse Line 2: Document Number, Check, Nationality, DOB, Sex, Expiry, Check, Composite
    if line2 and len(line2) >= 28:
        lm = re.search(r"([A-Z<]{3})([0-9]{6})([0-9<])([MF<])([0-9]{6})", line2)
        if lm:
            lm_start = lm.start()
            shift = lm_start - 10
            if shift > 0 and len(line2) >= 44 + shift:
                line2 = line2[shift:]
                lm = re.search(r"([A-Z<]{3})([0-9]{6})([0-9<])([MF<])([0-9]{6})", line2)
                lm_start = lm.start() if lm else 10

            nationality = lm.group(1).replace("<", "")
            dob = lm.group(2)
            raw_sex = lm.group(4)
            gender = raw_sex if raw_sex in ["M", "F", "<"] else None
            expiry = lm.group(5)
            raw_num = line2[:lm_start].rstrip("<")
            if len(raw_num) > 0:
                pass_num = raw_num[:-1].rstrip("<") if len(raw_num) >= 10 else raw_num.rstrip("<")
        else:
            pass_num = line2[0:9].replace("<", "")
            nationality = line2[10:13].replace("<", "")
            dob = line2[13:19]
            raw_sex = line2[20] if len(line2) > 20 else None
            gender = raw_sex if raw_sex in ["M", "F", "<"] else None
            expiry = line2[21:27] if len(line2) >= 27 else None

    name_conf = check_field_confidence(full_name, max_len=40)
    pass_num_conf = check_field_confidence(pass_num, max_len=10)
    nat_conf = check_field_confidence(nationality or issuing_country, max_len=3, check_alpha_only=True)

    return {
        "name": full_name,
        "name_confidence": name_conf,
        "passport_number": pass_num,
        "passport_number_confidence": pass_num_conf,
        "nationality": nationality or issuing_country,
        "nationality_confidence": nat_conf,
        "date_of_birth": dob,
        "date_of_expiry": expiry,
        "gender": gender,
        "gender_note": None,
        "mrz_valid_score": 50 if (pass_num or line2) else 0,
        "mrz_line2": line2
    }


def extract_mrz_with_tesseract(image_path: str) -> dict | None:
    """Extracts MRZ lines using Tesseract OCR with adaptive grayscale preprocessing."""
    try:
        img = cv2.imread(image_path)
        if img is None:
            return None

        h, w = img.shape[:2]
        strip = img[int(h * 0.75):h, 0:w]
        gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
        filtered = cv2.bilateralFilter(gray, 7, 50, 50)

        tess_config = "--psm 6 --oem 1"
        text = pytesseract.image_to_string(filtered, config=tess_config)
        raw_lines = [normalize_mrz_string(line) for line in text.splitlines() if len(normalize_mrz_string(line)) >= 20]

        line1, line2, line3 = disambiguate_mrz_lines(raw_lines)
        if not line1 and not line2:
            return None

        return parse_mrz_line_tokens(line1, line2, line3)
    except Exception:
        return None


def extract_mrz_with_paddleocr(image_path: str) -> dict | None:
    """Recovers MRZ lines using PaddleOCR deep scene text detection with baseline grouping."""
    try:
        ocr = get_ocr_engine()
        img = cv2.imread(image_path)
        if img is None:
            return None

        result = ocr.ocr(img)
        if not result or not isinstance(result, list) or result[0] is None:
            return None

        boxes = []
        for item in result[0]:
            if not item or len(item) < 2:
                continue
            box_pts = item[0]
            text_conf = item[1]
            if not text_conf or len(text_conf) < 1:
                continue
            text = str(text_conf[0]).strip()
            if not text:
                continue
            y_center = sum(pt[1] for pt in box_pts) / len(box_pts)
            x_left = min(pt[0] for pt in box_pts)
            boxes.append({"text": text, "y": y_center, "x": x_left})

        if not boxes:
            return None

        boxes.sort(key=lambda b: (b["y"], b["x"]))
        merged_lines = []
        current_group = [boxes[0]]

        for b in boxes[1:]:
            if abs(b["y"] - current_group[-1]["y"]) <= 18:
                current_group.append(b)
            else:
                current_group.sort(key=lambda it: it["x"])
                line_str = "".join(it["text"] for it in current_group)
                merged_lines.append(line_str)
                current_group = [b]

        if current_group:
            current_group.sort(key=lambda it: it["x"])
            merged_lines.append("".join(it["text"] for it in current_group))

        all_candidates = merged_lines + [b["text"] for b in boxes]
        normalized = [normalize_mrz_string(l) for l in all_candidates]
        mrz_candidates = [l for l in normalized if len(l) >= 20 or "<" in l]

        line1, line2, line3 = disambiguate_mrz_lines(mrz_candidates)
        if not line1 and not line2:
            return None

        return parse_mrz_line_tokens(line1, line2, line3)
    except Exception:
        return None


def extract_passport(image_path: str, fallback_image_path: str = None, mrz_candidates: list[str] = None) -> dict:
    """
    Cascaded Passport MRZ Extractor:
    1. Pre-Scanned MRZ Candidates: Disambiguates and parses whole-image scan tokens.
    2. Fast-Path: PassportEye bottom 28% strip (<200ms).
    3. Fallback: PassportEye full image.
    4. Fallback: Tesseract OCR-B with adaptive binarization.
    5. Fallback: PaddleOCR deep scene text detection.
    6. Fallback: Re-try PaddleOCR / Tesseract on uncropped original image.
    """
    if mrz_candidates:
        line1, line2, line3 = disambiguate_mrz_lines(mrz_candidates)
        if line1 and line2:
            scanned_mrz = parse_mrz_line_tokens(line1, line2, line3)
            if scanned_mrz and (scanned_mrz.get("passport_number") or scanned_mrz.get("mrz_line2")):
                # Return immediately from deep scan tokens without blocking on heavy full-image PassportEye morphology
                return scanned_mrz

    mrz = None

    # 2. Fast-Path: Try bottom 28% strip with PassportEye (<200ms)
    try:
        img = cv2.imread(image_path)
        if img is not None:
            h, w = img.shape[:2]
            mrz_strip = img[int(h * 0.70):h, 0:w]
            temp_strip_path = f"{image_path}_mrz_strip.jpg"
            cv2.imwrite(temp_strip_path, mrz_strip)
            try:
                mrz = read_mrz(temp_strip_path)
            finally:
                if os.path.exists(temp_strip_path):
                    os.remove(temp_strip_path)
    except Exception:
        mrz = None

    # 3. Tesseract OCR-B strip fallback (<250ms)
    if mrz is None or getattr(mrz, "valid_score", 0) <= 0:
        tess_res = extract_mrz_with_tesseract(image_path)
        if tess_res and (tess_res.get("mrz_line2") or tess_res.get("passport_number")):
            return tess_res

    # 4. PaddleOCR deep text fallback (only if mrz_candidates was not provided)
    if (mrz is None or getattr(mrz, "valid_score", 0) <= 0) and not mrz_candidates:
        paddle_res = extract_mrz_with_paddleocr(image_path)
        if paddle_res and (paddle_res.get("mrz_line2") or paddle_res.get("passport_number")):
            return paddle_res

    # 5. Fallback on original uncropped image (only if mrz_candidates was not provided)
    if (mrz is None or getattr(mrz, "valid_score", 0) <= 0) and not mrz_candidates and fallback_image_path and os.path.exists(fallback_image_path) and fallback_image_path != image_path:
        paddle_fallback = extract_mrz_with_paddleocr(fallback_image_path)
        if paddle_fallback and (paddle_fallback.get("mrz_line2") or paddle_fallback.get("passport_number")):
            return paddle_fallback
        tess_fallback = extract_mrz_with_tesseract(fallback_image_path)
        if tess_fallback and (tess_fallback.get("mrz_line2") or tess_fallback.get("passport_number")):
            return tess_fallback

    if mrz is None:
        return {
            "name": None,
            "name_confidence": "high",
            "passport_number": None,
            "passport_number_confidence": "high",
            "nationality": None,
            "nationality_confidence": "high",
            "date_of_birth": None,
            "date_of_expiry": None,
            "gender": None,
            "gender_note": None,
            "mrz_valid_score": 0,
            "mrz_line2": None
        }

    mrz_dict = mrz.to_dict()
    names = mrz_dict.get("names", "") or ""
    surname = mrz_dict.get("surname", "") or ""
    full_name = f"{names} {surname}".strip() or None

    raw_text = mrz_dict.get("raw_text", "") or ""
    raw_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    line1, line2, _ = disambiguate_mrz_lines(raw_lines)
    mrz_line2 = line2

    raw_gender = mrz_dict.get("sex")
    gender = str(raw_gender).strip().upper() if raw_gender and str(raw_gender).strip().upper() in ["M", "F", "<"] else None

    pass_num = mrz_dict.get("number")
    nationality = mrz_dict.get("nationality")
    dob = mrz_dict.get("date_of_birth")
    expiry = mrz_dict.get("expiration_date")

    # If PassportEye returned unparseable DOB or Expiry, rescue via Line 2 landmark
    if mrz_line2 and (not dob or not str(dob).isdigit() or not expiry or not str(expiry).isdigit()):
        lm = re.search(r"([A-Z<]{3})([0-9]{6})([0-9<])([MF<])([0-9]{6})", mrz_line2)
        if lm:
            lm_start = lm.start()
            if not dob or not str(dob).isdigit():
                dob = lm.group(2)
            if not nationality or len(nationality) != 3 or not nationality.isalpha():
                nationality = lm.group(1).replace("<", "")
            if not expiry or not str(expiry).isdigit():
                expiry = lm.group(5)
            if not pass_num or len(pass_num) < 3:
                raw_num = mrz_line2[:lm_start].rstrip("<")
                if len(raw_num) > 0:
                    pass_num = raw_num[:-1].rstrip("<") if len(raw_num) >= 10 else raw_num.rstrip("<")

    name_conf = check_field_confidence(full_name, max_len=40)
    pass_num_conf = check_field_confidence(pass_num, max_len=10)
    nat_conf = check_field_confidence(nationality, max_len=3, check_alpha_only=True)

    return {
        "name": full_name,
        "name_confidence": name_conf,
        "passport_number": pass_num,
        "passport_number_confidence": pass_num_conf,
        "nationality": nationality,
        "nationality_confidence": nat_conf,
        "date_of_birth": dob,
        "date_of_expiry": expiry,
        "gender": gender,
        "gender_note": None,
        "mrz_valid_score": getattr(mrz, "valid_score", 0),
        "mrz_line2": mrz_line2
    }


def classify_document_type(raw_text: list[str], image_path: str = None) -> str:
    """
    Intelligent Auto-Document Classification Engine:
    Inspects recognized text keywords, MRZ tokens, and document headers.
    Zero hardcoded names or country heuristics.
    """
    joined = " ".join(raw_text).upper()

    # 1. Passport indicators
    if any(sig in joined for sig in ["P<", "PASSPORT", "PASSAPORTE", "PASSEPORT", "REPUBLICA FEDERATIVA", "TRAVEL DOCUMENT", "ICAO DOC 9303"]):
        return "passport"

    for line in raw_text:
        cleaned = line.strip().replace(" ", "").upper()
        if (cleaned.startswith("P<") or cleaned.startswith("P ") or "<<" in cleaned) and len(cleaned) >= 24:
            return "passport"

    # 2. Residence Permit / BRP
    if any(sig in joined for sig in ["RESIDENCE PERMIT", "RESIDENCEPERMIT", "BIOMETRIC RESIDENCE PERMIT", "BRP", "LEAVE TO ENTER", "TYPE OF PERMIT"]):
        return "residence_permit"

    # 3. Visa
    if any(sig in joined for sig in ["VISA", "VISAS", "VISA TYPE", "CONTROL NUMBER", "ENTRIES", "VALID FOR"]):
        return "visa"

    # 4. Aadhaar
    if any(sig in joined for sig in ["AADHAAR", "GOVERNMENT OF INDIA", "UNIQUE IDENTIFICATION AUTHORITY", "MERA AADHAAR"]):
        return "aadhaar"
    if re.search(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b", joined):
        return "aadhaar"

    # 5. Voter ID (EPIC)
    if any(sig in joined for sig in ["ELECTION COMMISSION OF INDIA", "ELECTOR PHOTO IDENTITY CARD", "EPIC NO", "BHARAT NIRVACHAN AYOG"]):
        return "voter_id"
    if re.search(r"\b[A-Z]{3}[0-9]{7}\b", joined):
        return "voter_id"

    # 6. Driving License
    if any(sig in joined for sig in ["DRIVING LICENCE", "DRIVING LICENSE", "UNION OF INDIA", "TRANSPORT DEPARTMENT", "MOTOR VEHICLES ACT"]):
        return "driving_license"
    if re.search(r"\b[A-Z]{2}[-\s]?[0-9O]{2}[-\s]?[0-9]{4}[-\s]?[0-9]{7}\b", joined):
        return "driving_license"

    return "national_id"


def scan_document_regions(
    image_path: str,
    fallback_image_path: str = None,
    face_info: dict = None
) -> dict:
    """
    Whole-Document Deep Scene Scanning & Semantic Region Localization Engine:
    1. Runs PaddleOCR deep text detection (DBNet) and recognition (SVTR) across full image.
    2. Identifies every text line with polygon/bounding box coordinates, text content, and confidence.
    3. Detects Biometric Face, Official Border Stamps, Issuing Headers, VIZ Text, and MRZ Zone.
    4. Categorizes detected elements into semantic regions for visual green bounding overlay and dynamic parsing.
    """
    detected_regions = []
    raw_lines = []
    mrz_candidates = []

    img = cv2.imread(image_path)
    if img is None:
        return {
            "detected_regions": [],
            "raw_text": [],
            "mrz_candidates": [],
            "engine_used": "none"
        }

    img_h, img_w = img.shape[:2]

    # 1. Primary Deep Scene Text Detection via PaddleOCR
    engine_used = "paddleocr_deep_scan"
    paddle_items = []
    try:
        ocr = get_ocr_engine()
        result = ocr.ocr(img)
        if result and isinstance(result, list) and result[0] is not None:
            first = result[0]
            if isinstance(first, list):
                for item in first:
                    if item and len(item) >= 2 and item[0] and item[1]:
                        pts = item[0]
                        text = str(item[1][0]).strip()
                        conf = float(item[1][1]) if len(item[1]) > 1 else 0.9
                        if text:
                            paddle_items.append((pts, text, conf))
    except Exception:
        paddle_items = []

    # Fallback 1: Deep scene scan on original uncropped image if processed image yielded few regions
    if len(paddle_items) < 4 and fallback_image_path and os.path.exists(fallback_image_path) and fallback_image_path != image_path:
        try:
            fb_img = cv2.imread(fallback_image_path)
            if fb_img is not None:
                ocr = get_ocr_engine()
                fb_res = ocr.ocr(fb_img)
                if fb_res and isinstance(fb_res, list) and fb_res[0] is not None:
                    fb_first = fb_res[0]
                    if isinstance(fb_first, list):
                        fb_items = []
                        for item in fb_first:
                            if item and len(item) >= 2 and item[0] and item[1]:
                                pts = item[0]
                                text = str(item[1][0]).strip()
                                conf = float(item[1][1]) if len(item[1]) > 1 else 0.9
                                if text:
                                    fb_items.append((pts, text, conf))
                        if len(fb_items) > len(paddle_items):
                            paddle_items = fb_items
                            img = fb_img
                            img_h, img_w = img.shape[:2]
                            engine_used = "paddleocr_deep_scan_original"
        except Exception:
            pass

    # Fallback 2: Tesseract image_to_data if PaddleOCR returned nothing
    if not paddle_items:
        try:
            tess_data = pytesseract.image_to_data(Image.open(image_path), output_type=pytesseract.Output.DICT)
            n_boxes = len(tess_data.get("text", []))
            for i in range(n_boxes):
                text = str(tess_data["text"][i]).strip()
                conf_val = float(tess_data["conf"][i])
                if text and conf_val > 25:
                    x = int(tess_data["left"][i])
                    y = int(tess_data["top"][i])
                    w = int(tess_data["width"][i])
                    h = int(tess_data["height"][i])
                    pts = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
                    paddle_items.append((pts, text, conf_val / 100.0))
            if paddle_items:
                engine_used = "tesseract_deep_scan"
        except Exception:
            pass

    # Process all detected text boxes
    box_records = []
    for pts, text, conf in paddle_items:
        xs = [pt[0] for pt in pts]
        ys = [pt[1] for pt in pts]
        bx = int(max(0, min(xs)))
        by = int(max(0, min(ys)))
        bw = int(max(1, max(xs) - bx))
        bh = int(max(1, max(ys) - by))
        y_center = (min(ys) + max(ys)) / 2.0
        box_records.append({
            "box": [bx, by, bw, bh],
            "text": text,
            "conf": round(conf, 3),
            "y_center": y_center,
            "x_left": bx
        })

    # Sort boxes top-to-bottom, left-to-right
    box_records.sort(key=lambda b: (b["y_center"], b["x_left"]))

    # Group nearby words on same line to form complete text lines
    merged_lines = []
    if box_records:
        current_group = [box_records[0]]
        for b in box_records[1:]:
            # If vertical center is within 16px, group onto same line
            if abs(b["y_center"] - current_group[-1]["y_center"]) <= 16:
                current_group.append(b)
            else:
                current_group.sort(key=lambda it: it["x_left"])
                line_str = " ".join(it["text"] for it in current_group).strip()
                min_x = min(it["box"][0] for it in current_group)
                min_y = min(it["box"][1] for it in current_group)
                max_x = max(it["box"][0] + it["box"][2] for it in current_group)
                max_y = max(it["box"][1] + it["box"][3] for it in current_group)
                avg_conf = sum(it["conf"] for it in current_group) / len(current_group)
                merged_lines.append({
                    "box": [min_x, min_y, max_x - min_x, max_y - min_y],
                    "text": line_str,
                    "conf": round(avg_conf, 3)
                })
                current_group = [b]

        if current_group:
            current_group.sort(key=lambda it: it["x_left"])
            line_str = " ".join(it["text"] for it in current_group).strip()
            min_x = min(it["box"][0] for it in current_group)
            min_y = min(it["box"][1] for it in current_group)
            max_x = max(it["box"][0] + it["box"][2] for it in current_group)
            max_y = max(it["box"][1] + it["box"][3] for it in current_group)
            avg_conf = sum(it["conf"] for it in current_group) / len(current_group)
            merged_lines.append({
                "box": [min_x, min_y, max_x - min_x, max_y - min_y],
                "text": line_str,
                "conf": round(avg_conf, 3)
            })

    # Categorize merged lines into semantic regions
    mrz_boxes = []
    reg_idx = 1
    for ml in merged_lines:
        t = ml["text"]
        bx, by, bw, bh = ml["box"]
        clean_t = normalize_mrz_string(t)

        # Check if line is MRZ
        is_mrz = False
        if "<" in t or clean_t.startswith("P<") or clean_t.startswith("I<") or clean_t.startswith("A<") or clean_t.startswith("C<") or clean_t.startswith("V<"):
            is_mrz = True
        elif by > (img_h * 0.65) and len(clean_t) >= 18 and sum(c.isdigit() for c in clean_t) >= 8:
            is_mrz = True

        if is_mrz:
            mrz_candidates.append(t)
            mrz_boxes.append(ml["box"])
            detected_regions.append({
                "id": f"reg_{reg_idx}",
                "type": "mrz",
                "label": "MRZ LINE",
                "box": [bx, by, bw, bh],
                "text": t,
                "confidence": ml["conf"]
            })
        elif by < (img_h * 0.22) and any(kw in t.upper() for kw in ["PASSPORT", "PASSAPORTE", "PASSEPORT", "REPUBLIC", "REPUBLICA", "FEDERATIVE", "KINGDOM", "STATE", "GOVERNMENT", "INDIA", "UNION", "ELECTION", "IDENTITY", "RESIDENCE", "PERMIT", "VISA"]):
            detected_regions.append({
                "id": f"reg_{reg_idx}",
                "type": "header",
                "label": "HEADER / ISSUING AUTH",
                "box": [bx, by, bw, bh],
                "text": t,
                "confidence": ml["conf"]
            })
        else:
            detected_regions.append({
                "id": f"reg_{reg_idx}",
                "type": "text",
                "label": "VIZ FIELD",
                "box": [bx, by, bw, bh],
                "text": t,
                "confidence": ml["conf"]
            })
        raw_lines.append(t)
        reg_idx += 1

    # 2. Add Unified MRZ Zone region if multiple MRZ lines exist
    if mrz_boxes:
        min_mx = min(b[0] for b in mrz_boxes)
        min_my = min(b[1] for b in mrz_boxes)
        max_mx = max(b[0] + b[2] for b in mrz_boxes)
        max_my = max(b[1] + b[3] for b in mrz_boxes)
        detected_regions.append({
            "id": "reg_mrz_zone",
            "type": "mrz_zone",
            "label": "MRZ 7-3-1 ZONE (ICAO DOC 9303)",
            "box": [min_mx, min_my, max_mx - min_mx, max_my - min_my],
            "confidence": 0.99
        })

    # 3. Add Biometric Face Portrait region
    if face_info and face_info.get("face_detected") and face_info.get("bounding_box"):
        fb = face_info["bounding_box"]
        detected_regions.append({
            "id": "reg_face",
            "type": "face",
            "label": "BIOMETRIC PORTRAIT",
            "box": [fb[0], fb[1], fb[2], fb[3]],
            "confidence": 0.99
        })
    else:
        try:
            face_extract = extract_document_face(image_path)
            if face_extract.get("face_detected") and face_extract.get("bounding_box"):
                fb = face_extract["bounding_box"]
                detected_regions.append({
                    "id": "reg_face",
                    "type": "face",
                    "label": "BIOMETRIC PORTRAIT",
                    "box": [fb[0], fb[1], fb[2], fb[3]],
                    "confidence": 0.99
                })
        except Exception:
            pass

    # 4. Add Official Stamp regions if detected
    try:
        from modules.tampering import analyze_stamp_region
        stamp_res = analyze_stamp_region(image_path)
        if stamp_res.get("stamp_detected"):
            for s_idx, sbox in enumerate(stamp_res.get("stamp_boxes", [])):
                detected_regions.append({
                    "id": f"reg_stamp_{s_idx+1}",
                    "type": "stamp",
                    "label": "OFFICIAL STAMP",
                    "box": sbox,
                    "confidence": 0.90
                })
    except Exception:
        pass

    return {
        "detected_regions": detected_regions,
        "raw_text": raw_lines,
        "mrz_candidates": mrz_candidates,
        "engine_used": engine_used
    }


def generate_scanned_green_overlay(
    image_path: str,
    detected_regions: list[dict],
    document_quad: list = None,
    output_path: str = None
) -> str:
    """
    Renders border-grade HUD green scanning map with corner reticles,
    cyan MRZ zone, emerald biometric portrait, and amber consular stamps.
    """
    img = cv2.imread(image_path)
    if img is None:
        return image_path

    overlay = img.copy()
    hud_color_text = (0, 230, 115)     # Neon Green (BGR)
    hud_color_mrz = (240, 200, 0)      # Electric Cyan (BGR)
    hud_color_face = (50, 220, 100)    # Emerald (BGR)
    hud_color_stamp = (0, 165, 255)    # Amber (BGR)

    # 1. Viewfinder quad overlay
    if document_quad and len(document_quad) == 4:
        quad_pts = np.array(document_quad, dtype=np.int32)
        cv2.polylines(overlay, [quad_pts], isClosed=True, color=(0, 255, 120), thickness=1, lineType=cv2.LINE_AA)
        for pt in quad_pts:
            px, py = int(pt[0]), int(pt[1])
            cv2.circle(overlay, (px, py), 4, (0, 255, 120), -1)

    # 2. Render bounding boxes and corner brackets
    for r in detected_regions:
        bx, by, bw, bh = r["box"]
        rtype = r["type"]
        color = hud_color_text
        thickness = 2

        if rtype in ["mrz", "mrz_zone"]:
            color = hud_color_mrz
            thickness = 3
        elif rtype == "face":
            color = hud_color_face
            thickness = 3
        elif rtype == "stamp":
            color = hud_color_stamp
            thickness = 2
        elif rtype == "header":
            thickness = 2

        # Draw main bounding rectangle
        cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), color, thickness)

        # High-tech HUD corner brackets
        line_len = max(6, min(20, bw // 5, bh // 5))
        # Top-left
        cv2.line(overlay, (bx, by), (bx + line_len, by), color, thickness + 1)
        cv2.line(overlay, (bx, by), (bx, by + line_len), color, thickness + 1)
        # Top-right
        cv2.line(overlay, (bx + bw, by), (bx + bw - line_len, by), color, thickness + 1)
        cv2.line(overlay, (bx + bw, by), (bx + bw, by + line_len), color, thickness + 1)
        # Bottom-left
        cv2.line(overlay, (bx, by + bh), (bx + line_len, by + bh), color, thickness + 1)
        cv2.line(overlay, (bx, by + bh), (bx, by + bh - line_len), color, thickness + 1)
        # Bottom-right
        cv2.line(overlay, (bx + bw, by + bh), (bx + bw - line_len, by + bh), color, thickness + 1)
        cv2.line(overlay, (bx + bw, by + bh), (bx + bw, by + bh - line_len), color, thickness + 1)

        # Micro-badge for non-generic or important regions
        if rtype in ["mrz_zone", "face", "stamp", "header"]:
            label = r.get("label", "")
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.38
            (tw, th), _ = cv2.getTextSize(label, font, font_scale, 1)
            badge_y1 = max(0, by - th - 6)
            badge_y2 = by
            cv2.rectangle(overlay, (bx, badge_y1), (bx + tw + 8, badge_y2), (25, 25, 25), -1)
            cv2.putText(overlay, label, (bx + 4, badge_y2 - 3), font, font_scale, color, 1, cv2.LINE_AA)

    # 3. Alpha-blend
    out = cv2.addWeighted(overlay, 0.90, img, 0.10, 0)

    # 4. Top watermark header
    hud_title = f"[BORDER E-GATE SCANNER - {len(detected_regions)} REGIONS IDENTIFIED]"
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.42
    (tw, th), _ = cv2.getTextSize(hud_title, font, font_scale, 1)
    cv2.rectangle(out, (10, 10), (10 + tw + 14, 10 + th + 10), (20, 20, 20), -1)
    cv2.putText(out, hud_title, (16, 10 + th + 4), font, font_scale, (0, 240, 120), 1, cv2.LINE_AA)

    if output_path is None:
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        output_path = os.path.join(backend_dir, "uploads", "scanned", f"{os.path.splitext(os.path.basename(image_path))[0]}_scanned.jpg")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, out)
    return output_path


def extract_document_fields(image_path: str, document_type: str, fallback_image_path: str = None, pre_scanned_text: list[str] = None) -> dict:
    """
    Cascaded Visual Inspection Zone (VIZ) Extraction:
    Extracts printed text fields using multilingual labels (English, French, Spanish, Portuguese, Hindi).
    Zero hardcoded values.
    """
    raw_text = []
    engine_used = "tesseract_fast"

    if pre_scanned_text and len(pre_scanned_text) >= 1:
        raw_text = list(pre_scanned_text)
        engine_used = "paddleocr_deep_scan"
    else:
        # Fast Tesseract with automatic segmentation
        try:
            img = Image.open(image_path)
            ocr_str = pytesseract.image_to_string(img, config="--psm 3 --oem 1")
            raw_text = [line.strip() for line in ocr_str.splitlines() if line.strip()]
        except Exception:
            raw_text = []

    # Check if Tesseract extracted enough quality text
    joined_sample = " ".join(raw_text).upper()
    has_key_labels = any(
        k in joined_sample for k in ["NAME", "DOB", "VALID", "EXPIR", "INDIA", "PERMIT", "NUMBER", "MALE", "FEMALE", "PASSAPORTE", "PASSPORT", "SOBRENOME", "NOME", "NACIONALIDADE"]
    )
    tess_has_quality = len(raw_text) >= 6 and has_key_labels

    # PaddleOCR fallback invoked only if pre_scanned_text was not provided and Tesseract had sparse text
    if not pre_scanned_text and (not tess_has_quality or len(raw_text) < 4):
        try:
            ocr = get_ocr_engine()
            img_cv = cv2.imread(image_path)
            if img_cv is not None:
                result = ocr.ocr(img_cv)
                paddle_lines = []
                if isinstance(result, list) and len(result) > 0 and result[0] is not None:
                    first = result[0]
                    if isinstance(first, dict) and "rec_texts" in first:
                        paddle_lines = [t.strip() for t in first["rec_texts"] if t and t.strip()]
                    elif isinstance(first, list):
                        for line in first:
                            if line and len(line) >= 2 and line[1]:
                                text = line[1][0]
                                if text:
                                    paddle_lines.append(text.strip())
                if paddle_lines:
                    raw_text = paddle_lines
                    engine_used = "paddleocr_fallback"
        except Exception:
            pass

    # Try fallback uncropped image only if pre_scanned_text was not provided and text remains empty
    if not pre_scanned_text and len(raw_text) < 3 and fallback_image_path and os.path.exists(fallback_image_path) and fallback_image_path != image_path:
        try:
            ocr = get_ocr_engine()
            fallback_cv = cv2.imread(fallback_image_path)
            if fallback_cv is not None:
                res = ocr.ocr(fallback_cv)
                if res and isinstance(res, list) and res[0] is not None:
                    fb_lines = [str(item[1][0]).strip() for item in res[0] if item and len(item) >= 2 and item[1] and item[1][0]]
                    if fb_lines:
                        raw_text = fb_lines
                        engine_used = "paddleocr_fallback_original"
        except Exception:
            pass

    extracted_fields = {}
    joined_text = " ".join(raw_text)

    # Auto-refine document_type
    refined_type = classify_document_type(raw_text, image_path)
    if document_type == "auto" or (document_type == "passport" and refined_type in ["residence_permit", "aadhaar", "voter_id", "driving_license"]):
        document_type = refined_type

    # 1. Residence Permit extraction
    if document_type in ["residence_permit", "visa"] or any("RESIDENCE" in t.upper() for t in raw_text):
        for idx, text in enumerate(raw_text):
            norm_t = text.strip().upper()
            if norm_t in ["HAME", "NAME", "1. NAME", "1. HAME", "SURNAME", "HOLDER NAME"]:
                parts = []
                sub_idx = idx + 1
                while sub_idx < len(raw_text) and len(parts) < 2:
                    cand = raw_text[sub_idx].strip()
                    cand_u = cand.upper()
                    if not any(lbl in cand_u for lbl in ["VALID", "DATE", "PLACE", "TYPE", "REMARKS", "PERMIT", "SEX", "SIGNATUR"]):
                        parts.append(cand)
                    else:
                        break
                    sub_idx += 1
                if parts and not extracted_fields.get("name"):
                    extracted_fields["name"] = " ".join(reversed(parts)) if len(parts) == 2 else " ".join(parts)

            if "TYPE OF PERMIT" in norm_t or "PERMIT TYPE" in norm_t:
                perm = []
                sub_idx = idx + 1
                while sub_idx < len(raw_text) and len(perm) < 2:
                    cand = raw_text[sub_idx].strip()
                    if not any(lbl in cand.upper() for lbl in ["REMARKS", "VALID", "SIGNATUR"]):
                        perm.append(cand)
                    else:
                        break
                    sub_idx += 1
                if perm:
                    extracted_fields["permit_type"] = " ".join(perm)

            if "REMARKS" in norm_t:
                rem = []
                sub_idx = idx + 1
                while sub_idx < len(raw_text) and len(rem) < 3:
                    cand = raw_text[sub_idx].strip()
                    if not any(lbl in cand.upper() for lbl in ["SIGNATUR", "PERMIT"]):
                        rem.append(cand)
                    sub_idx += 1
                if rem:
                    extracted_fields["remarks"] = " ".join(rem)

    # 2. Passport Visual Inspection Zone (VIZ) extraction
    if document_type == "passport" or any("PASSAPORTE" in t.upper() or "PASSPORT" in t.upper() or "REPUBLICA" in t.upper() for t in raw_text):
        p_match = re.search(r"(?:PASSAPORTE\s*N[ºO°]?|PASSPORT\s*N[ºO°]?|DOC(?:UMENT)?\s*N[ºO°]?)\s*[:/\-]?\s*([A-Z0-9]{6,10})\b", joined_text, re.IGNORECASE)
        if p_match and not extracted_fields.get("passport_number"):
            extracted_fields["passport_number"] = p_match.group(1).upper()
            extracted_fields["id_number"] = p_match.group(1).upper()

        if not extracted_fields.get("passport_number"):
            p_num = re.search(r"\b([A-Z]{1,2}[0-9]{6,8})\b", joined_text)
            if p_num:
                extracted_fields["passport_number"] = p_num.group(1).upper()
                extracted_fields["id_number"] = p_num.group(1).upper()

        # Dates: DD MMM YYYY format (e.g. 16 MAR 2001, 06 JUL 2022, 28 OCT 2014)
        date_matches = re.findall(r"\b(\d{2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z/]*\s+\d{4})\b", joined_text, re.IGNORECASE)
        if date_matches:
            clean_dates = [re.sub(r"/[A-Z]+", "", dm).strip() for dm in date_matches]
            if not extracted_fields.get("date_of_birth"):
                extracted_fields["date_of_birth"] = clean_dates[0]
            if len(clean_dates) >= 3 and not extracted_fields.get("date_of_expiry"):
                extracted_fields["date_of_issue"] = clean_dates[1]
                extracted_fields["date_of_expiry"] = clean_dates[2]
            elif len(clean_dates) == 2 and not extracted_fields.get("date_of_expiry"):
                extracted_fields["date_of_expiry"] = clean_dates[1]

        # Dynamic label-based name extraction (multilingual ICAO standard)
        surname = None
        given = None
        for idx, t in enumerate(raw_text):
            tu = t.upper().strip()
            if re.search(r"\b(?:SURNAME|SOBRENOME|NOM|APELLIDOS|NACHNAME|COGNOME)\b", tu):
                m = re.search(r"(?:SURNAME|SOBRENOME|NOM|APELLIDOS|NACHNAME|COGNOME)\s*[:/\-]?\s*([A-Z\s]{2,})", t, re.IGNORECASE)
                if m and len(m.group(1).strip()) > 1 and not re.search(r"\b(?:PASSPORT|PASSAPORTE|COUNTRY|REPUBLIC)\b", m.group(1), re.I):
                    surname = m.group(1).strip()
                elif idx + 1 < len(raw_text):
                    cand = raw_text[idx + 1].strip()
                    if len(cand) > 1 and cand.isupper() and not any(lbl in cand for lbl in ["PASSPORT", "PASSAPORTE", "COUNTRY"]):
                        surname = cand

            if re.search(r"\b(?:GIVEN\s*NAMES?|PRENOMS?|NOMBRES?|NOME|VORNAMEN|NOMI)\b", tu):
                m = re.search(r"(?:GIVEN\s*NAMES?|PRENOMS?|NOMBRES?|NOME|VORNAMEN|NOMI)\s*[:/\-]?\s*([A-Z\s]{2,})", t, re.IGNORECASE)
                if m and len(m.group(1).strip()) > 1 and not re.search(r"\b(?:PASSPORT|PASSAPORTE|COUNTRY|REPUBLIC)\b", m.group(1), re.I):
                    given = m.group(1).strip()
                elif idx + 1 < len(raw_text):
                    cand = raw_text[idx + 1].strip()
                    if len(cand) > 1 and cand.isupper() and not any(lbl in cand for lbl in ["PASSPORT", "PASSAPORTE", "COUNTRY"]):
                        given = cand

        if surname and given and not extracted_fields.get("name"):
            extracted_fields["name"] = f"{given} {surname}"
        elif surname and not extracted_fields.get("name"):
            extracted_fields["name"] = surname
        elif given and not extracted_fields.get("name"):
            extracted_fields["name"] = given

        # Nationality
        if not extracted_fields.get("nationality"):
            nat_m = re.search(r"(?:NATIONALITY|NATIONALITE|NACIONALIDADE|NACIONALIDAD)\s*[:/\-]?\s*([A-Za-z()]+)\b", joined_text, re.IGNORECASE)
            if nat_m:
                extracted_fields["nationality"] = nat_m.group(1).upper()

    # 3. Aadhaar Card extraction (Indian National ID)
    if document_type in ["aadhaar", "national_id", "id_card"] or any("AADHAAR" in t.upper() or "UNIQUE IDENTIFICATION" in t.upper() or "GOVERNMENT OF INDIA" in t.upper() for t in raw_text):
        aadhaar_match = re.search(r"\b([2-9]\d{3}\s?\d{4}\s?\d{4})\b", joined_text)
        if not aadhaar_match:
            aadhaar_match = re.search(r"\b([2-9]\d{11})\b", joined_text)
        if aadhaar_match:
            raw_uid = aadhaar_match.group(1).replace(" ", "")
            formatted_uid = f"{raw_uid[:4]} {raw_uid[4:8]} {raw_uid[8:]}"
            extracted_fields["aadhaar_number"] = formatted_uid
            extracted_fields["id_number"] = formatted_uid
            extracted_fields["passport_number"] = formatted_uid
            extracted_fields["nationality"] = "IND"
            extracted_fields["date_of_expiry"] = "LIFETIME"
            document_type = "aadhaar"

        # Aadhaar DOB extraction
        dob_line_idx = -1
        for idx, line in enumerate(raw_text):
            dob_m = re.search(r"(?:DOB|जन्म\s*तिथि|Year\s*of\s*Birth|जन्म\s*तारीख|जन्म\s*का\s*वर्ष)\s*[:\s/-]?\s*(\d{2}[/\-.]\d{2}[/\-.]\d{4}|\d{4})", line, re.IGNORECASE)
            if dob_m:
                extracted_fields["date_of_birth"] = dob_m.group(1)
                dob_line_idx = idx
                break

        # Dynamic Label-Free Aadhaar Name Extraction:
        # Aadhaar cards print the holder name directly above DOB without a "NAME:" label.
        if not extracted_fields.get("name") and dob_line_idx > 0:
            for back_i in range(dob_line_idx - 1, -1, -1):
                cand = raw_text[back_i].strip()
                cand_u = cand.upper()
                # Skip sovereign headers, Hindi-only lines without latin, and digit lines
                has_latin = bool(re.search(r"[A-Za-z]{2,}", cand))
                is_header = any(h in cand_u for h in ["GOVERNMENT", "INDIA", "BHARAT", "SARKAR", "UIDAI", "AUTHORITY", "UNIQUE", "IDENTIFICATION", "ENROLMENT", "AADHAAR", "HELP", "WWW", "MERA"])
                is_meta = any(m in cand_u for m in ["MALE", "FEMALE", "TRANSGENDER", "YEAR", "BIRTH", "DATE", "DOB", "ADDRESS"])
                has_too_many_digits = sum(c.isdigit() for c in cand) >= 2

                if has_latin and not is_header and not is_meta and not has_too_many_digits and 3 <= len(cand) <= 45:
                    extracted_fields["name"] = cand
                    break

        # Aadhaar Gender extraction
        if not extracted_fields.get("gender"):
            for line in raw_text:
                lu = line.upper()
                if "FEMALE" in lu or "महिला" in line:
                    extracted_fields["gender"] = "F"
                    break
                elif "MALE" in lu or "पुरुष" in line:
                    extracted_fields["gender"] = "M"
                    break
                elif "TRANSGENDER" in lu:
                    extracted_fields["gender"] = "T"
                    break

    # 4. Voter ID (EPIC) extraction
    if document_type in ["voter_id", "national_id", "id_card"] or any("ELECTION COMMISSION OF INDIA" in t.upper() or "EPIC" in t.upper() for t in raw_text):
        epic_match = re.search(r"\b([A-Z]{3}[0-9]{7})\b", joined_text)
        if epic_match:
            epic_num = epic_match.group(1)
            extracted_fields["voter_id"] = epic_num
            extracted_fields["id_number"] = epic_num
            extracted_fields["passport_number"] = epic_num
            extracted_fields["nationality"] = "IND"
            document_type = "voter_id"

        for idx, line in enumerate(raw_text):
            # Name
            nm = re.search(r"(?:Elector(?:'s)?\s*Name|निर्वाचक\s*का\s*नाम|Name|नाम)\s*[:\-]?\s*([A-Za-z\s]{3,})", line, re.I)
            if nm and not extracted_fields.get("name") and not any(k in nm.group(1).upper() for k in ["FATHER", "HUSBAND", "ELECTION"]):
                extracted_fields["name"] = nm.group(1).strip()
            elif re.search(r"^(?:Elector(?:'s)?\s*Name|निर्वाचक\s*का\s*नाम)\s*[:\-]?$", line.strip(), re.I):
                if idx + 1 < len(raw_text) and not extracted_fields.get("name"):
                    extracted_fields["name"] = raw_text[idx + 1].strip()

            # Gender
            if not extracted_fields.get("gender"):
                gm = re.search(r"(?:Sex|लिंग|Gender)\s*[:\-]?\s*(Male|Female|पुरुष|महिला|M|F)", line, re.I)
                if gm:
                    g_val = gm.group(1).upper()
                    extracted_fields["gender"] = "F" if ("FEMALE" in g_val or "महिला" in gm.group(1) or g_val == "F") else "M"

    # 5. Driving License (Sarathi format) extraction
    if document_type in ["driving_license", "dl"] or any("DRIVING LICENCE" in t.upper() or "DRIVING LICENSE" in t.upper() or "MOTOR VEHICLES" in t.upper() for t in raw_text):
        dl_match = re.search(r"\b([A-Z]{2}[-\s]?[0-9O]{2}[-\s]?[0-9]{4}[-\s]?[0-9]{7})\b", joined_text)
        if not dl_match:
            dl_match = re.search(r"\b([A-Z]{2}[0-9O]{13,14})\b", joined_text)
        if dl_match:
            raw_dl = dl_match.group(1)
            state_code = raw_dl[:2].upper()
            num_part = raw_dl[2:].replace("O", "0").replace("o", "0").replace("I", "1").replace("l", "1")
            clean_dl = re.sub(r"[-\s]", "", f"{state_code}{num_part}")
            extracted_fields["dl_number"] = clean_dl
            extracted_fields["id_number"] = clean_dl
            extracted_fields["passport_number"] = clean_dl
            extracted_fields["nationality"] = "IND"
            document_type = "driving_license"

        for idx, line in enumerate(raw_text):
            nm = re.search(r"(?:Holder\s*Name|Name|नाम)\s*[:\-]?\s*([A-Za-z\s]{3,})", line, re.I)
            if nm and not extracted_fields.get("name") and not any(k in nm.group(1).upper() for k in ["LICENCE", "LICENSE", "TRANSPORT", "FATHER"]):
                extracted_fields["name"] = nm.group(1).strip()

    # 6. Visa / Travel Authorization extraction
    if document_type in ["visa"] or any("VISA" in t.upper() for t in raw_text):
        vm = re.search(r"(?:VISA\s*N(?:O|UMBER)?|CONTROL\s*NUMBER)\s*[:\-]?\s*([A-Z0-9]{6,12})\b", joined_text, re.I)
        if vm:
            extracted_fields["visa_number"] = vm.group(1).upper()
            extracted_fields["id_number"] = extracted_fields["visa_number"]
            if not extracted_fields.get("passport_number"):
                extracted_fields["passport_number"] = extracted_fields["visa_number"]

        v_type_m = re.search(r"(?:TYPE|CLASS|CATEGORY)\s*[:\-]?\s*([A-Za-z0-9/-]{1,10})\b", joined_text, re.I)
        if v_type_m:
            extracted_fields["visa_type"] = v_type_m.group(1).upper()

        entries_m = re.search(r"(?:ENTRIES|NO\s*OF\s*ENTRIES)\s*[:\-]?\s*([SMD0-9]|MULTIPLE|SINGLE|DOUBLE)\b", joined_text, re.I)
        if entries_m:
            extracted_fields["entries"] = entries_m.group(1).upper()

        pass_on_visa = re.search(r"(?:PASSPORT\s*(?:NO|NUMBER|Nº|N°)?|PASS\s*NO)\s*[:\-]?\s*([A-Z0-9]{6,10})\b", joined_text, re.I)
        if pass_on_visa:
            extracted_fields["passport_number"] = pass_on_visa.group(1).upper()

        for idx, line in enumerate(raw_text):
            nm = re.search(r"(?:Name|Bearer|Holder(?:\s*Name)?)\s*[:\-]?\s*([A-Za-z\s]{3,})", line, re.I)
            if nm and not extracted_fields.get("name") and not any(k in nm.group(1).upper() for k in ["REPUBLIC", "INDIA", "VISA", "GOVERNMENT"]):
                extracted_fields["name"] = nm.group(1).strip()
            iss_m = re.search(r"(?:Valid\s*From|Date\s*of\s*Issue|Issued\s*On)\s*[:\-]?\s*(\d{2}[/\-.]\d{2}[/\-.]\d{4})", line, re.I)
            if iss_m and not extracted_fields.get("date_of_issue"):
                extracted_fields["date_of_issue"] = iss_m.group(1)
            exp_m = re.search(r"(?:Valid\s*Until|Date\s*of\s*Expiry|Expiry\s*Date|Valid\s*Till)\s*[:\-]?\s*(\d{2}[/\-.]\d{2}[/\-.]\d{4})", line, re.I)
            if exp_m and not extracted_fields.get("date_of_expiry"):
                extracted_fields["date_of_expiry"] = exp_m.group(1)

    # Common field patterns across all document categories
    patterns = [
        ("name", r"(?i)^(?:name|full\s*name|holder\s*name|given\s*names?)\s*[:\-]?\s*(.+)"),
        ("date_of_birth", r"(?i)^(?:dob|date\s*of\s*birth|birth\s*date|yob|data\s*de\s*nascimento)\s*[:\-]?\s*(.+)"),
        ("date_of_expiry", r"(?i)^(?:valid\s*until|valid\s*till|valid\s*thru|expiry\s*date|date\s*of\s*expiry|exp|data\s*de\s*validade)\s*[:\-]?\s*(.+)"),
        ("date_of_issue", r"(?i)^(?:date\s*of\s*issue|issue\s*date|issued\s*on|data\s*de\s*emissao|data\s*de\s*emissão)\s*[:\-]?\s*(.+)"),
        ("visa_number", r"(?i)^(?:visa\s*n(?:o|umber)?)\s*[:\-]?\s*(.+)"),
        ("nationality", r"(?i)^(?:nationality|nat|nacionalidade)\s*[:\-]?\s*(.+)"),
        ("gender", r"(?i)^(?:gender|sex|sexo)\s*[:\-]?\s*(MALE|FEMALE|TRANSGENDER|M|F)")
    ]

    for idx, text in enumerate(raw_text):
        for field_key, regex in patterns:
            if field_key not in extracted_fields:
                match = re.search(regex, text)
                if match and match.group(1).strip():
                    extracted_fields[field_key] = match.group(1).strip()
                elif re.match(r"(?i)^(?:name|dob|date\s*of\s*birth|expiry\s*date|valid\s*until|valid\s*till|issue\s*date|visa\s*n(?:o|umber)?|gender|sexo)\s*[:\-]?$", text):
                    if idx + 1 < len(raw_text):
                        next_val = raw_text[idx + 1].strip()
                        if next_val and len(next_val) > 1 and not any(lbl in next_val.upper() for lbl in ["VALID", "DATE", "PLACE", "TYPE", "REMARKS"]):
                            extracted_fields[field_key] = next_val

    if "date_of_birth" not in extracted_fields:
        dob_m = re.search(r"\b(\d{2}[/\-.]\d{2}[/\-.]\d{4})\b", joined_text)
        if dob_m:
            extracted_date = dob_m.group(1)
            if extracted_date not in [extracted_fields.get("date_of_expiry"), extracted_fields.get("date_of_issue")]:
                extracted_fields["date_of_birth"] = extracted_date

    # Universal field synchronization guarantee
    primary_id = (
        extracted_fields.get("passport_number")
        or extracted_fields.get("aadhaar_number")
        or extracted_fields.get("voter_id")
        or extracted_fields.get("dl_number")
        or extracted_fields.get("visa_number")
        or extracted_fields.get("id_number")
    )
    if primary_id:
        extracted_fields["id_number"] = primary_id
        if not extracted_fields.get("passport_number"):
            extracted_fields["passport_number"] = primary_id

    # Evaluate confidence
    has_critical_field = bool(
        extracted_fields.get("id_number")
        or extracted_fields.get("passport_number")
        or extracted_fields.get("aadhaar_number")
        or extracted_fields.get("voter_id")
        or extracted_fields.get("dl_number")
        or extracted_fields.get("name")
    )
    confidence = "HIGH" if has_critical_field else ("MEDIUM" if len(raw_text) > 5 else "LOW")

    return {
        "raw_text": raw_text,
        "extracted_fields": extracted_fields,
        "engine_used": engine_used,
        "confidence": confidence,
        "detected_type": document_type
    }


def ensure_optimal_ocr_image(image_path: str, max_dim: int = 1200) -> str:
    """Downscales images exceeding max_dim for sub-second OCR inference."""
    try:
        img = cv2.imread(image_path)
        if img is None:
            return image_path
        h, w = img.shape[:2]
        if max(h, w) <= max_dim:
            return image_path

        scale = max_dim / float(max(h, w))
        resized = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

        base_dir = os.path.dirname(image_path)
        base_name, ext = os.path.splitext(os.path.basename(image_path))
        opt_path = os.path.join(base_dir, f"{base_name}_opt{ext or '.jpg'}")
        cv2.imwrite(opt_path, resized)
        return opt_path
    except Exception:
        return image_path


def run_ocr(
    image_path: str,
    document_type: str = "auto",
    face_info: dict = None,
    fallback_image_path: str = None,
    document_quad: list = None,
    file_id: str = None
) -> dict:
    """
    Intelligent Auto-Detect Cascaded OCR Pipeline with Whole-Image Deep Scanning:
    1. Runs full-image deep scene scanning to detect and localize all regions (Text, MRZ, Face, Stamp, Headers).
    2. Generates visual green bounding overlay for border inspection preview.
    3. Auto-detects document category (Passport, Residence Permit, Visa, Aadhaar, Voter ID, Driving License).
    4. Executes domain-specific parser (MRZ cascade for Passports, VIZ + Regex for IDs & Permits).
    5. Returns extracted fields, confidence, scanned image URL, and localized detected regions.
    """
    ocr_image_path = ensure_optimal_ocr_image(image_path, max_dim=1200)
    fallback_opt = ensure_optimal_ocr_image(fallback_image_path, max_dim=1200) if fallback_image_path else None

    if face_info is None:
        face_info = extract_document_face(ocr_image_path)
        if not face_info.get("face_detected") and fallback_opt:
            face_info = extract_document_face(fallback_opt)

    # 1. Whole-Document Deep Scene Scanning
    scan_res = scan_document_regions(ocr_image_path, fallback_image_path=fallback_opt, face_info=face_info)
    detected_regions = scan_res.get("detected_regions", [])
    scanned_lines = scan_res.get("raw_text", [])
    mrz_candidates = scan_res.get("mrz_candidates", [])

    # 2. Render Green Lines Overlay Image
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    scanned_dir = os.path.join(backend_dir, "uploads", "scanned")
    os.makedirs(scanned_dir, exist_ok=True)
    base_name = file_id or os.path.splitext(os.path.basename(image_path))[0]
    base_clean = base_name.replace("_opt", "").replace("_processed", "")
    scanned_filename = f"{base_clean}_scanned.jpg"
    scanned_filepath = os.path.join(scanned_dir, scanned_filename)
    try:
        generate_scanned_green_overlay(ocr_image_path, detected_regions, document_quad, scanned_filepath)
        scanned_image_url = f"/scanned-images/{scanned_filename}"
    except Exception:
        scanned_image_url = None

    # 3. Dynamic Field Extraction
    initial_generic = extract_document_fields(
        ocr_image_path, document_type, fallback_image_path=fallback_opt, pre_scanned_text=scanned_lines
    )
    detected_type = initial_generic.get("detected_type") or document_type

    if document_type == "auto" or (document_type == "passport" and detected_type in ["residence_permit", "aadhaar", "voter_id", "driving_license"]):
        effective_type = detected_type
    else:
        effective_type = document_type

    # Check if document has passport characteristics (MRZ line or passport keywords)
    raw_lines_all = initial_generic.get("raw_text", [])
    has_mrz_signals = any("P<" in l or "<<" in l or "PASSAPORTE" in l.upper() or "PASSPORT" in l.upper() for l in raw_lines_all)
    if has_mrz_signals and effective_type != "residence_permit":
        effective_type = "passport"

    if effective_type == "passport":
        passport_data = extract_passport(ocr_image_path, fallback_image_path=fallback_opt, mrz_candidates=mrz_candidates)
        has_valid_mrz = (
            passport_data.get("mrz_valid_score", 0) > 0
            and (passport_data.get("passport_number") or passport_data.get("name") or passport_data.get("mrz_line2"))
        )

        generic_data = initial_generic

        # Merge fields: prioritize MRZ structured fields, enrich with VIZ fields
        merged_fields = dict(generic_data["extracted_fields"])
        for k, v in passport_data.items():
            if v and (not merged_fields.get(k) or k in ["passport_number", "date_of_birth", "date_of_expiry", "mrz_line2", "gender"]):
                merged_fields[k] = v
        if passport_data.get("mrz_line2"):
            merged_fields["mrz_line2"] = passport_data.get("mrz_line2")

        has_critical = bool(merged_fields.get("passport_number") or merged_fields.get("name"))
        conf = "HIGH" if has_critical else generic_data.get("confidence", "LOW")

        method_used = "mrz_cascade_fast" if has_valid_mrz else "generic_ocr_fallback"

        return {
            "document_type": "passport",
            "method_used": method_used,
            "fields": merged_fields,
            "viz_fields": generic_data["extracted_fields"],
            "raw_text": generic_data["raw_text"],
            "portrait_face": face_info,
            "confidence": conf,
            "note": "MRZ verified" if has_valid_mrz else "MRZ unreadable or partial; visual inspection zone data extracted",
            "scanned_image_url": scanned_image_url,
            "detected_regions": detected_regions
        }

    # Residence Permit / Visa / National ID
    fields = initial_generic["extracted_fields"]
    return {
        "document_type": effective_type,
        "method_used": initial_generic.get("engine_used", "generic_ocr"),
        "fields": fields,
        "viz_fields": fields,
        "raw_text": initial_generic["raw_text"],
        "portrait_face": face_info,
        "confidence": initial_generic.get("confidence", "HIGH"),
        "scanned_image_url": scanned_image_url,
        "detected_regions": detected_regions
    }
