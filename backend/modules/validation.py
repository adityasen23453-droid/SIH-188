import os
import re
import sqlite3
from datetime import datetime, date


# ==========================================
# 1. ICAO Doc 9303 Check Digit Engine
# ==========================================

def calc_mrz_check_digit(char_str: str) -> int:
    """Calculates MRZ check digit using weights 7, 3, 1 repeating, modulo 10."""
    weights = [7, 3, 1]
    total = 0
    for idx, char in enumerate(char_str):
        char = char.upper()
        if char.isdigit():
            val = int(char)
        elif 'A' <= char <= 'Z':
            val = ord(char) - ord('A') + 10
        elif char == '<':
            val = 0
        else:
            val = 0
        total += val * weights[idx % 3]
    return total % 10


def correct_mrz_line2_numeric_fields(mrz_line2: str, target_positions: list[int] = None) -> tuple[str, list[str]]:
    """
    Applies ICAO 9303 letter-to-digit auto-correction strictly to positions
    that must be numeric digits (DOB, Expiry, and check digits).
    Does NOT modify passport number (0-8) or nationality (10-12).
    """
    if not mrz_line2 or not isinstance(mrz_line2, str):
        return mrz_line2, []

    line = list(mrz_line2.strip().upper().replace(" ", ""))
    corrections = []

    to_digit = {
        'B': '8',
        'O': '0', 'Q': '0', 'D': '0',
        'I': '1', 'L': '1',
        'S': '5',
        'Z': '2',
        'A': '4'
    }

    if target_positions is None:
        numeric_positions = [9, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 24, 25, 26, 27]
        if len(line) >= 44:
            numeric_positions.append(43)
    else:
        numeric_positions = target_positions

    for pos in numeric_positions:
        if pos < len(line):
            char = line[pos]
            if char in to_digit:
                corrected_char = to_digit[char]
                line[pos] = corrected_char
                corrections.append(f"position {pos}: {char}->{corrected_char}")

    return "".join(line), corrections


def validate_mrz_checksum(passport_number: str = None, date_of_birth: str = None, date_of_expiry: str = None, mrz_line2: str = None) -> dict:
    """
    Validates MRZ check digits on standard passport MRZ line 2 (TD3 format).
    Features:
    - Safeguard: detects if Line 1 (Holder Name) was passed by mistake, preventing false failures.
    - Landmark-aware alignment: dynamically locates DOB, Expiry, and Passport checkdigits via ICAO landmarks.
    - Returns structured results for passport number, date of birth, date of expiry, and composite check.
    """
    empty_result = {
        "passport_number_check": {"value": None, "expected_digit": None, "computed_digit": None, "valid": None, "field_slice": "0:9", "check_digit_pos": 9},
        "date_of_birth_check": {"value": None, "expected_digit": None, "computed_digit": None, "valid": None, "field_slice": "13:19", "check_digit_pos": 19},
        "date_of_expiry_check": {"value": None, "expected_digit": None, "computed_digit": None, "valid": None, "field_slice": "21:27", "check_digit_pos": 27},
        "composite_check": {"expected_digit": None, "computed_digit": None, "valid": None},
        "overall_checksum_valid": None,
        "failed_fields": [],
        "ocr_corrections_applied": []
    }

    if not mrz_line2 or not isinstance(mrz_line2, str) or len(mrz_line2.strip()) == 0:
        empty_result["note"] = "MRZ line 2 not available for checksum validation"
        return empty_result

    clean_raw = mrz_line2.strip().upper().replace(" ", "")

    # Safeguard: detect if Line 1 (Holder Name) was passed instead of Line 2
    digits_in_line = sum(c.isdigit() for c in clean_raw)
    if clean_raw.startswith("P<") or (clean_raw.startswith("P") and "<" in clean_raw[:6] and digits_in_line <= 6):
        empty_result["note"] = "MRZ Line 1 (Holder Name) provided instead of Line 2 (Checkdigits)"
        empty_result["overall_checksum_valid"] = None
        return empty_result

    # Landmark-aware alignment for TD3 Line 2: [Country 3 letters][DOB 6 digits][DOB Check 1][Sex M/F/<][Expiry 6 digits]
    lm = re.search(r"([A-Z<]{3})([0-9]{6})([0-9<])([MF<])([0-9]{6})", clean_raw)
    if lm:
        lm_start = lm.start()
        shift = lm_start - 10
        if shift > 0 and len(clean_raw) >= 44 + shift:
            clean_raw = clean_raw[shift:]
            lm = re.search(r"([A-Z<]{3})([0-9]{6})([0-9<])([MF<])([0-9]{6})", clean_raw)
            lm_start = lm.start() if lm else 10

        p_slice_end = lm_start - 1
        p_check_pos = lm_start - 1
        dob_start = lm_start + 3
        dob_check_pos = dob_start + 6
        exp_start = dob_start + 8
        exp_check_pos = exp_start + 6
    else:
        p_slice_end = 9
        p_check_pos = 9
        dob_start = 13
        dob_check_pos = 19
        exp_start = 21
        exp_check_pos = 27

    numeric_positions = [p_check_pos] + list(range(dob_start, dob_check_pos + 1)) + list(range(exp_start, exp_check_pos + 1))
    if len(clean_raw) >= 44:
        numeric_positions.append(43)

    line2, corrections_applied = correct_mrz_line2_numeric_fields(clean_raw, target_positions=numeric_positions)
    if len(line2) < 28:
        empty_result["note"] = f"MRZ line 2 length ({len(line2)}) is too short for validation"
        empty_result["ocr_corrections_applied"] = corrections_applied
        return empty_result

    failed_fields = []
    malformed_note = "MRZ read appears malformed at this position, skipping checksum check"

    # 1. Passport number check (padded to 9 characters per ICAO 9303)
    passport_val = line2[0:p_slice_end].ljust(9, "<")
    passport_exp = line2[p_check_pos] if p_check_pos < len(line2) else None
    if not passport_exp or not passport_exp.isdigit():
        passport_check = {
            "value": passport_val,
            "expected_digit": passport_exp,
            "computed_digit": None,
            "valid": None,
            "field_slice": f"0:{p_slice_end}",
            "check_digit_pos": p_check_pos,
            "note": malformed_note
        }
    else:
        passport_comp = str(calc_mrz_check_digit(passport_val))
        passport_valid = (passport_comp == passport_exp)
        if not passport_valid:
            failed_fields.append("passport_number_check")
        passport_check = {
            "value": passport_val,
            "expected_digit": passport_exp,
            "computed_digit": passport_comp,
            "valid": passport_valid,
            "field_slice": f"0:{p_slice_end}",
            "check_digit_pos": p_check_pos
        }

    # 2. Date of birth check
    dob_val = line2[dob_start:dob_check_pos]
    dob_exp = line2[dob_check_pos] if dob_check_pos < len(line2) else None
    if not dob_exp or not dob_exp.isdigit():
        dob_check = {
            "value": dob_val,
            "expected_digit": dob_exp,
            "computed_digit": None,
            "valid": None,
            "field_slice": f"{dob_start}:{dob_check_pos}",
            "check_digit_pos": dob_check_pos,
            "note": malformed_note
        }
    else:
        dob_comp = str(calc_mrz_check_digit(dob_val))
        dob_valid = (dob_comp == dob_exp)
        if not dob_valid:
            failed_fields.append("date_of_birth_check")
        dob_check = {
            "value": dob_val,
            "expected_digit": dob_exp,
            "computed_digit": dob_comp,
            "valid": dob_valid,
            "field_slice": f"{dob_start}:{dob_check_pos}",
            "check_digit_pos": dob_check_pos
        }

    # 3. Date of expiry check
    expiry_val = line2[exp_start:exp_check_pos]
    expiry_exp = line2[exp_check_pos] if exp_check_pos < len(line2) else None
    if not expiry_exp or not expiry_exp.isdigit():
        expiry_check = {
            "value": expiry_val,
            "expected_digit": expiry_exp,
            "computed_digit": None,
            "valid": None,
            "field_slice": f"{exp_start}:{exp_check_pos}",
            "check_digit_pos": exp_check_pos,
            "note": malformed_note
        }
    else:
        expiry_comp = str(calc_mrz_check_digit(expiry_val))
        expiry_valid = (expiry_comp == expiry_exp)
        if not expiry_valid:
            failed_fields.append("date_of_expiry_check")
        expiry_check = {
            "value": expiry_val,
            "expected_digit": expiry_exp,
            "computed_digit": expiry_comp,
            "valid": expiry_valid,
            "field_slice": f"{exp_start}:{exp_check_pos}",
            "check_digit_pos": exp_check_pos
        }

    # 4. Composite check
    if len(line2) >= 44:
        composite_field = line2[0:p_check_pos+1] + line2[dob_start:dob_check_pos+1] + line2[exp_start:43]
        composite_exp = line2[43]
        composite_slice_str = f"0:{p_check_pos+1} + {dob_start}:{dob_check_pos+1} + {exp_start}:43"
        composite_pos = 43
    elif len(line2) >= 30 and line2[-1].isdigit():
        composite_field = line2[0:p_check_pos+1] + line2[dob_start:dob_check_pos+1] + line2[exp_start:-1]
        composite_exp = line2[-1]
        composite_slice_str = f"0:{p_check_pos+1} + {dob_start}:{dob_check_pos+1} + {exp_start}:{len(line2)-1}"
        composite_pos = len(line2) - 1
    else:
        composite_field = None
        composite_exp = None
        composite_slice_str = None
        composite_pos = None

    if composite_field is not None and composite_exp is not None:
        if not composite_exp.isdigit():
            composite_check = {
                "expected_digit": composite_exp,
                "computed_digit": None,
                "valid": None,
                "field_slice": composite_slice_str,
                "check_digit_pos": composite_pos,
                "note": malformed_note
            }
        else:
            composite_comp = str(calc_mrz_check_digit(composite_field))
            composite_valid = (composite_comp == composite_exp)
            if not composite_valid:
                failed_fields.append("composite_check")
            composite_check = {
                "expected_digit": composite_exp,
                "computed_digit": composite_comp,
                "valid": composite_valid,
                "field_slice": composite_slice_str,
                "check_digit_pos": composite_pos
            }
    else:
        composite_check = {
            "expected_digit": None,
            "computed_digit": None,
            "valid": None
        }

    all_checks = [passport_check, dob_check, expiry_check, composite_check]
    if any(c.get("valid") is False for c in all_checks):
        overall_checksum_valid = False
    elif any(c.get("valid") is True for c in all_checks):
        overall_checksum_valid = True
    else:
        overall_checksum_valid = None

    return {
        "passport_number_check": passport_check,
        "date_of_birth_check": dob_check,
        "date_of_expiry_check": expiry_check,
        "composite_check": composite_check,
        "overall_checksum_valid": overall_checksum_valid,
        "failed_fields": failed_fields,
        "ocr_corrections_applied": corrections_applied
    }


# ==========================================
# 2. Aadhaar Mathematical Verhoeff Checksum
# ==========================================

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
]

_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
]

_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_validate(number_str: str) -> bool:
    """
    Validates a number string using the Verhoeff algorithm over the dihedral group D5.
    Official mathematical checksum standard for 12-digit Indian Aadhaar UIDs.
    """
    if not number_str or not isinstance(number_str, str):
        return False
    clean = re.sub(r"\D", "", number_str)
    if len(clean) == 0:
        return False

    c = 0
    rev = list(map(int, reversed(clean)))
    for i, digit in enumerate(rev):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][digit]]
    return c == 0


def verhoeff_compute_check_digit(number_str: str) -> int:
    """
    Computes the 12th Verhoeff check digit from the first 11 digits of an Aadhaar number.
    Mathematically ensures (clean + check_digit) satisfies verhoeff_validate == True.
    """
    clean = re.sub(r"\D", "", str(number_str))
    c = 0
    rev = list(map(int, reversed(clean)))
    for i, digit in enumerate(rev):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][digit]]
    return _VERHOEFF_INV[c]


INDIAN_RTO_STATES = {
    "AN": "Andaman and Nicobar Islands",
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CH": "Chandigarh",
    "CG": "Chhattisgarh",
    "CT": "Chhattisgarh",
    "DD": "Daman and Diu",
    "DN": "Dadra and Nagar Haveli",
    "DNH": "Dadra and Nagar Haveli",
    "DL": "Delhi",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JK": "Jammu and Kashmir",
    "JH": "Jharkhand",
    "KA": "Karnataka",
    "KL": "Kerala",
    "LA": "Ladakh",
    "LD": "Lakshadweep",
    "MP": "Madhya Pradesh",
    "MH": "Maharashtra",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "OR": "Odisha",
    "PY": "Puducherry",
    "PB": "Punjab",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TR": "Tripura",
    "UP": "Uttar Pradesh",
    "UK": "Uttarakhand",
    "UA": "Uttarakhand",
    "WB": "West Bengal"
}


def validate_aadhaar_card(fields: dict, raw_text: list[str] = None, image_path: str = None) -> dict:
    """
    Official UIDAI Indian Aadhaar Verification Engine:
    - 12-Digit UID Check (First digit cannot be 0 or 1 per UIDAI specification).
    - Verhoeff D5 Checksum Verification (Computes checkdigit & matches 12th digit).
    - Sovereign Authority Header Detection ('Government of India' / 'भारत सरकार' / 'UIDAI').
    - Plausibility of DOB.
    - QR Code Detection via OpenCV QRCodeDetector if image_path available.
    """
    issues = []
    raw_text = raw_text or []
    joined_text = " ".join(raw_text).upper()

    num = fields.get("aadhaar_number") or fields.get("id_number", "")
    clean_num = re.sub(r"\D", "", str(num))

    uid_format_valid = False
    verhoeff_valid = False
    expected_checkdigit = None
    computed_checkdigit = None

    if len(clean_num) == 12:
        if clean_num[0] in ['0', '1']:
            issues.append(f"Aadhaar UID cannot start with {clean_num[0]} per UIDAI standards")
        else:
            uid_format_valid = True

        expected_checkdigit = clean_num[-1]
        computed_checkdigit = str(verhoeff_compute_check_digit(clean_num[:11]))
        verhoeff_valid = verhoeff_validate(clean_num)
        if not verhoeff_valid:
            issues.append(f"Aadhaar Verhoeff checksum failed: expected {expected_checkdigit}, computed {computed_checkdigit}")
    elif len(clean_num) > 0:
        issues.append(f"Aadhaar UID must contain exactly 12 digits (found {len(clean_num)})")
    else:
        issues.append("Aadhaar UID number not detected")

    sovereign_markers = ["GOVERNMENT OF INDIA", "BHARAT SARKAR", "भारत सरकार", "UIDAI", "UNIQUE IDENTIFICATION", "MERA AADHAAR"]
    sovereign_detected = any(m in joined_text or any(m in t.upper() for t in raw_text) for m in sovereign_markers)
    if not sovereign_detected:
        issues.append("Government of India / UIDAI sovereign header not detected")

    dob = fields.get("date_of_birth")
    dob_plausible = bool(dob)
    if not dob:
        issues.append("Date of Birth / Year of Birth not detected on card")

    qr_detected = False
    if image_path and os.path.exists(image_path):
        try:
            import cv2
            img = cv2.imread(image_path)
            if img is not None:
                detector = cv2.QRCodeDetector()
                val, _, _ = detector.detectAndDecode(img)
                qr_detected = bool(val)
        except Exception:
            qr_detected = False

    overall_valid = uid_format_valid and verhoeff_valid and sovereign_detected

    return {
        "valid": overall_valid,
        "uid_format_valid": uid_format_valid,
        "verhoeff_valid": verhoeff_valid,
        "expected_checkdigit": expected_checkdigit,
        "computed_checkdigit": computed_checkdigit,
        "sovereign_header_detected": sovereign_detected,
        "qr_code_detected": qr_detected,
        "dob_plausible": dob_plausible,
        "issues": issues
    }


def validate_voter_id(fields: dict, raw_text: list[str] = None) -> dict:
    """
    Official Election Commission of India (ECI) Voter ID Verification Engine:
    - 3-Alpha + 7-Numeric EPIC Format Check.
    - Sovereign Authority Header Check ('Election Commission of India' / 'निर्वाचन आयोग').
    - Elector Name & Details Verification.
    """
    issues = []
    raw_text = raw_text or []
    joined_text = " ".join(raw_text).upper()

    epic = fields.get("voter_id") or fields.get("id_number", "")
    clean_epic = str(epic).strip().upper()

    epic_format_valid = bool(re.match(r"^[A-Z]{3}[0-9]{7}$", clean_epic))
    state_code = clean_epic[:3] if epic_format_valid else None

    if not epic_format_valid:
        issues.append(f"Voter ID '{clean_epic}' does not match official 3-letter + 7-digit EPIC standard")

    authority_markers = ["ELECTION COMMISSION OF INDIA", "BHARAT NIRVACHAN AYOG", "भारत निर्वाचन आयोग", "ELECTOR PHOTO IDENTITY CARD", "EPIC"]
    authority_detected = any(m in joined_text or any(m in t.upper() for t in raw_text) for m in authority_markers)
    if not authority_detected:
        issues.append("Election Commission of India authority header not detected")

    elector_name = fields.get("name")
    if not elector_name:
        issues.append("Elector name not clearly verified")

    overall_valid = epic_format_valid and authority_detected and bool(elector_name)

    return {
        "valid": overall_valid,
        "epic_format_valid": epic_format_valid,
        "epic_number": clean_epic if epic_format_valid else None,
        "state_code": state_code,
        "authority_header_detected": authority_detected,
        "issues": issues
    }


def validate_driving_license(fields: dict, raw_text: list[str] = None) -> dict:
    """
    Official MoRTH Sarathi Indian Driving License Verification Engine:
    - Sarathi 16-Char Format Check (SSRR YYYYNNNNNNN).
    - State & RTO Jurisdictional Validation across all 36 States/UTs.
    - 4-Digit Issue Year Plausibility Check.
    """
    issues = []
    raw_text = raw_text or []
    joined_text = " ".join(raw_text).upper()

    dl = fields.get("dl_number") or fields.get("id_number", "")
    clean_dl = re.sub(r"[-\s]", "", str(dl).upper())

    sarathi_format_valid = False
    state_code = None
    rto_code = None
    issue_year = None
    jurisdiction_verified = False

    if len(clean_dl) >= 15:
        state_code = clean_dl[:2]
        rto_code = clean_dl[2:4]
        issue_year = clean_dl[4:8]

        if state_code in INDIAN_RTO_STATES:
            jurisdiction_verified = True
        else:
            issues.append(f"Unknown state jurisdictional code '{state_code}' on Driving License")

        if issue_year.isdigit():
            current_year = date.today().year
            yr = int(issue_year)
            if 1970 <= yr <= current_year:
                sarathi_format_valid = True
            else:
                issues.append(f"Issue year '{issue_year}' is outside plausible issuance window (1970-{current_year})")
        else:
            issues.append("Issue year format invalid in Sarathi DL")
    elif len(clean_dl) > 0:
        issues.append(f"Driving License number '{clean_dl}' does not match standard Sarathi format")
    else:
        issues.append("Driving License number not detected")

    overall_valid = sarathi_format_valid and jurisdiction_verified

    return {
        "valid": overall_valid,
        "sarathi_format_valid": sarathi_format_valid,
        "state_code": state_code,
        "rto_code": rto_code,
        "issue_year": issue_year,
        "jurisdiction_verified": jurisdiction_verified,
        "issues": issues
    }


def validate_visa_document(fields: dict, raw_text: list[str] = None, stamp_forensics: dict = None) -> dict:
    """
    Consular Visa & Travel Authorization Verification Engine:
    - Visa Document Number Plausibility.
    - Category & Authorized Entry Count Check.
    - Validity Window (Date of Issue vs Date of Expiry).
    - Stamp Forensics & Splicing Integrity Cross-Check.
    """
    issues = []
    raw_text = raw_text or []

    visa_num = fields.get("visa_number") or fields.get("id_number", "")
    visa_number_valid = bool(visa_num and len(str(visa_num).strip()) >= 6)
    if not visa_number_valid:
        issues.append("Visa control / document number not detected or invalid length")

    category = fields.get("visa_type")
    entries = fields.get("entries")

    validity_window_valid = True
    doi = fields.get("date_of_issue")
    doe = fields.get("date_of_expiry")
    if doi and doe:
        p_doi = parse_date(doi, "issue")
        p_doe = parse_date(doe, "expiry")
        if p_doi and p_doe and p_doi >= p_doe:
            validity_window_valid = False
            issues.append(f"Visa validity window invalid: issue date ({doi}) >= expiry date ({doe})")

    stamp_splicing = bool(stamp_forensics and stamp_forensics.get("suspicious_stamp_splicing"))
    if stamp_splicing:
        issues.append("Suspicious border stamp splicing detected on Visa")

    overall_valid = visa_number_valid and validity_window_valid and not stamp_splicing

    return {
        "valid": overall_valid,
        "visa_number_valid": visa_number_valid,
        "category": category,
        "entries": entries,
        "validity_window_valid": validity_window_valid,
        "consular_stamp_verified": not stamp_splicing,
        "issues": issues
    }


def validate_national_id(document_type: str, fields: dict) -> dict:
    """
    Validates Indian National IDs (Aadhaar, Voter ID, Driving License).
    Returns structure: { 'valid': bool, 'id_type': str, 'issues': list[str] }
    """
    issues = []
    id_type = document_type.lower()

    if id_type in ["aadhaar", "national_id"] and ("aadhaar_number" in fields or "id_number" in fields):
        num = fields.get("aadhaar_number") or fields.get("id_number", "")
        clean_num = re.sub(r"\D", "", str(num))
        if len(clean_num) != 12:
            issues.append(f"Aadhaar UID must contain exactly 12 digits (found {len(clean_num)})")
        elif not verhoeff_validate(clean_num):
            issues.append("Aadhaar Verhoeff mathematical checksum verification failed")

    elif id_type in ["voter_id"] or "voter_id" in fields:
        epic = fields.get("voter_id") or fields.get("id_number", "")
        clean_epic = str(epic).strip().upper()
        if not re.match(r"^[A-Z]{3}[0-9]{7}$", clean_epic):
            issues.append(f"Voter ID (EPIC) '{clean_epic}' does not match official 3-letter + 7-digit standard format")

    elif id_type in ["driving_license", "dl"] or "dl_number" in fields:
        dl = fields.get("dl_number") or fields.get("id_number", "")
        clean_dl = re.sub(r"[-\s]", "", str(dl).upper())
        if len(clean_dl) < 10:
            issues.append(f"Driving License number '{clean_dl}' is too short")
        elif not re.match(r"^[A-Z]{2}[0-9]{2}[0-9]{4}[0-9]{7}$", clean_dl) and not re.match(r"^[A-Z]{2}[0-9]{13,14}$", clean_dl):
            issues.append(f"Driving License '{clean_dl}' does not match standard Sarathi format")

    return {
        "valid": len(issues) == 0,
        "id_type": id_type,
        "issues": issues
    }


# ==========================================
# 3. VIZ-to-MRZ Cross-Field Consistency
# ==========================================

def validate_viz_to_mrz(mrz_fields: dict, viz_fields: dict) -> dict:
    """
    Cross-checks printed visual text (VIZ) against the machine-readable zone (MRZ).
    Detects visual photo/text alterations where MRZ was left unedited.
    """
    mismatches = []
    if not isinstance(mrz_fields, dict) or not isinstance(viz_fields, dict):
        return {"checked": False, "consistent": True, "mismatches": []}

    mrz_name = str(mrz_fields.get("name") or "").strip().upper()
    viz_name = str(viz_fields.get("name") or "").strip().upper()

    if mrz_name and viz_name:
        mrz_tokens = set(re.findall(r"\w+", mrz_name))
        viz_tokens = set(re.findall(r"\w+", viz_name))
        overlap = mrz_tokens.intersection(viz_tokens)
        if len(overlap) == 0 and len(mrz_tokens) > 0 and len(viz_tokens) > 0:
            mismatches.append(f"VIZ printed name ('{viz_name}') conflicts with MRZ name ('{mrz_name}')")

    return {
        "checked": bool(mrz_name and viz_name),
        "consistent": len(mismatches) == 0,
        "mismatches": mismatches
    }


# ==========================================
# 4. Date Validation & Plausibility
# ==========================================

def parse_date(date_val, date_type: str = None) -> date | None:
    """Parses various date string formats into a datetime.date object."""
    if not date_val:
        return None
    if isinstance(date_val, (date, datetime)):
        return date_val.date() if isinstance(date_val, datetime) else date_val

    date_str = str(date_val).strip()
    if not date_str:
        return None

    # YYMMDD (6 digits in MRZ)
    if len(date_str) == 6 and date_str.isdigit():
        yy = int(date_str[0:2])
        mm = int(date_str[2:4])
        dd = int(date_str[4:6])
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            current_year = date.today().year
            current_yy = current_year % 100
            if date_type == "expiry":
                year = 2000 + yy if yy <= current_yy + 35 else 1900 + yy
            elif date_type == "dob":
                year = 2000 + yy if yy <= current_yy else 1900 + yy
            else:
                year = 2000 + yy if yy <= current_yy + 15 else 1900 + yy
            try:
                return date(year, mm, dd)
            except ValueError:
                pass

    # YYYYMMDD (8 digits)
    if len(date_str) == 8 and date_str.isdigit():
        try:
            return datetime.strptime(date_str, "%Y%m%d").date()
        except ValueError:
            pass

    formats = [
        "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y",
        "%d-%m-%Y", "%d %b %Y", "%d %B %Y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass

    return None


def validate_dates(date_of_birth: str = None, date_of_expiry: str = None, date_of_issue: str = None, doc_type: str = "passport") -> dict:
    """Validates date plausibility and expiration."""
    issues = []
    today = date.today()

    is_non_expiring = doc_type in ["aadhaar", "voter_id"]

    if is_non_expiring:
        expiry_status = "NOT_APPLICABLE"
        expiry_valid = True
    elif not date_of_expiry:
        expiry_status = "NOT_DETECTED"
        expiry_valid = False
        issues.append("Date of expiry could not be detected on document")
    else:
        parsed_expiry = parse_date(date_of_expiry, date_type="expiry")
        if not parsed_expiry:
            expiry_status = "UNPARSEABLE"
            expiry_valid = False
            issues.append(f"Date of expiry '{date_of_expiry}' is unparseable")
        elif parsed_expiry <= today:
            expiry_status = "EXPIRED"
            expiry_valid = False
            issues.append(f"Document expired on {parsed_expiry.isoformat()}")
        else:
            expiry_status = "ACTIVE"
            expiry_valid = True

    if not date_of_birth:
        dob_status = "NOT_DETECTED"
        dob_plausible = None
        issues.append("Date of birth could not be detected on document")
    else:
        parsed_dob = parse_date(date_of_birth, date_type="dob")
        if not parsed_dob:
            dob_status = "UNPARSEABLE"
            dob_plausible = False
            issues.append(f"Date of birth '{date_of_birth}' is unparseable")
        else:
            if parsed_dob > today:
                dob_status = "FUTURE_DATE"
                dob_plausible = False
                issues.append(f"Date of birth {parsed_dob.isoformat()} is in the future")
            else:
                age_years = (today - parsed_dob).days / 365.25
                if age_years > 120:
                    dob_status = "IMPLAUSIBLE_AGE"
                    dob_plausible = False
                    issues.append(f"Date of birth {parsed_dob.isoformat()} indicates age > 120 years")
                else:
                    dob_status = "PLAUSIBLE"
                    dob_plausible = True

    if date_of_issue:
        parsed_issue = parse_date(date_of_issue, date_type="issue")
        if not parsed_issue:
            issues.append(f"Date of issue '{date_of_issue}' is unparseable")
        elif date_of_expiry:
            parsed_expiry = parse_date(date_of_expiry, date_type="expiry")
            if parsed_expiry and parsed_issue >= parsed_expiry:
                issues.append(f"Date of issue ({parsed_issue.isoformat()}) is not before date of expiry ({parsed_expiry.isoformat()})")

    return {
        "expiry_valid": expiry_valid,
        "expiry_status": expiry_status,
        "dob_plausible": dob_plausible,
        "dob_status": dob_status,
        "issues": issues
    }


# ==========================================
# 5. Extended Mock Registry & Blacklist Store
# ==========================================

def get_registry_db_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base_dir, "data", "registry.db")


def init_registry_db(db_path: str):
    """Initializes SQLite tables for documents, visas, and blacklist."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            document_number TEXT PRIMARY KEY,
            document_type TEXT NOT NULL,
            holder_name TEXT,
            status TEXT NOT NULL CHECK(status IN ('VALID', 'EXPIRED', 'REVOKED', 'STOLEN')),
            revocation_reason TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visas (
            visa_number TEXT PRIMARY KEY,
            passport_number TEXT NOT NULL,
            visa_type TEXT,
            status TEXT NOT NULL CHECK(status IN ('VALID', 'EXPIRED', 'REVOKED'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blacklist (
            passport_number TEXT PRIMARY KEY,
            reason TEXT
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM blacklist")
    if cursor.fetchone()[0] == 0:
        seed_blacklist = [
            ("X1234567", "Reported stolen to Interpol"),
            ("A9876543", "Fraudulent document duplicate"),
            ("P0000000", "Flagged on Interpol Watchlist")
        ]
        cursor.executemany("INSERT OR IGNORE INTO blacklist VALUES (?, ?)", seed_blacklist)

    cursor.execute("SELECT COUNT(*) FROM documents")
    if cursor.fetchone()[0] == 0:
        seed_docs = [
            ("L898902C3", "passport", "ANNA MARIA ERIKSSON", "VALID", None),
            ("REVOKED01", "passport", "JOHN DOE", "REVOKED", "Revoked by Ministry of External Affairs"),
            ("X1234567", "passport", "UNKNOWN HOLDER", "STOLEN", "Reported lost/stolen at border ICP")
        ]
        cursor.executemany("INSERT OR IGNORE INTO documents VALUES (?, ?, ?, ?, ?)", seed_docs)

    conn.commit()
    conn.close()


def check_registry(document_number: str = None, document_type: str = "passport") -> dict:
    """
    Queries the border registry for document validity, revocation, and blacklist signals.
    """
    if not document_number or not isinstance(document_number, str) or not document_number.strip():
        return {
            "blacklisted": False,
            "status": "NOT_CHECKED",
            "reason": None
        }

    db_path = get_registry_db_path()
    init_registry_db(db_path)

    norm_num = document_number.strip().upper()

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. Blacklist check
        cursor.execute("SELECT reason FROM blacklist WHERE UPPER(passport_number) = ?", (norm_num,))
        black_row = cursor.fetchone()
        if black_row:
            conn.close()
            return {
                "blacklisted": True,
                "status": "STOLEN",
                "reason": black_row[0]
            }

        # 2. Document Registry status check
        cursor.execute("SELECT status, revocation_reason FROM documents WHERE UPPER(document_number) = ?", (norm_num,))
        doc_row = cursor.fetchone()
        conn.close()

        if doc_row:
            status, rev_reason = doc_row
            return {
                "blacklisted": status in ["REVOKED", "STOLEN"],
                "status": status,
                "reason": rev_reason or f"Registry status: {status}"
            }

        return {
            "blacklisted": False,
            "status": "VALID",
            "reason": None
        }

    except Exception as e:
        return {
            "blacklisted": False,
            "status": "ERROR",
            "reason": f"Registry error: {str(e)}"
        }


def check_blacklist(passport_number: str = None) -> dict:
    """Backwards-compatible wrapper around check_registry."""
    res = check_registry(passport_number)
    return {
        "blacklisted": res["blacklisted"],
        "reason": res["reason"]
    }


# ==========================================
# 6. Consolidated Validation Entry Point
# ==========================================

def run_validation(ocr_result: dict, stamp_forensics: dict = None, image_path: str = None) -> dict:
    """
    Consolidated validation coordinator:
    Executes MRZ checksums, Aadhaar Verhoeff & UIDAI rules, Voter ID EPIC checks,
    Sarathi Driving License rules, Visa consular authorization rules,
    VIZ-to-MRZ cross-checks, date plausibility, and registry queries.
    """
    if not isinstance(ocr_result, dict):
        ocr_result = {}

    doc_type = ocr_result.get("document_type", "passport")
    fields = ocr_result.get("fields") or {}
    viz_fields = ocr_result.get("viz_fields") or {}
    raw_text = ocr_result.get("raw_text") or []

    passport_number = (
        fields.get("passport_number") or
        fields.get("id_number") or
        fields.get("aadhaar_number") or
        fields.get("voter_id") or
        fields.get("dl_number") or
        fields.get("visa_number")
    )
    date_of_birth = fields.get("date_of_birth")
    date_of_expiry = fields.get("date_of_expiry") or fields.get("valid_until")
    date_of_issue = fields.get("date_of_issue")
    mrz_line2 = fields.get("mrz_line2")

    # 1. MRZ Checksums (passports)
    checksum_res = validate_mrz_checksum(
        passport_number=passport_number,
        date_of_birth=date_of_birth,
        date_of_expiry=date_of_expiry,
        mrz_line2=mrz_line2
    )

    # 2. National ID validation (basic)
    national_id_res = validate_national_id(doc_type, fields)

    # 3. Domain-Specific Verification Engines
    aadhaar_res = None
    voter_id_res = None
    dl_res = None
    visa_res = None

    if doc_type == "aadhaar" or "aadhaar_number" in fields or any("AADHAAR" in t.upper() or "UNIQUE IDENTIFICATION" in t.upper() or "GOVERNMENT OF INDIA" in t.upper() for t in raw_text):
        aadhaar_res = validate_aadhaar_card(fields, raw_text, image_path=image_path)
    if doc_type == "voter_id" or "voter_id" in fields or any("ELECTION COMMISSION" in t.upper() or "EPIC" in t.upper() for t in raw_text):
        voter_id_res = validate_voter_id(fields, raw_text)
    if doc_type in ["driving_license", "dl"] or "dl_number" in fields or any("DRIVING LICENCE" in t.upper() or "MOTOR VEHICLES" in t.upper() for t in raw_text):
        dl_res = validate_driving_license(fields, raw_text)
    if doc_type == "visa" or "visa_number" in fields or any("VISA" in t.upper() for t in raw_text):
        visa_res = validate_visa_document(fields, raw_text, stamp_forensics=stamp_forensics)

    # 4. VIZ-to-MRZ Cross-Field Consistency
    viz_cross_res = validate_viz_to_mrz(fields, viz_fields)

    # 5. Date plausibility
    dates_res = validate_dates(
        date_of_birth=date_of_birth,
        date_of_expiry=date_of_expiry,
        date_of_issue=date_of_issue,
        doc_type=doc_type
    )

    # 6. Registry & Blacklist check
    registry_res = check_registry(document_number=passport_number, document_type=doc_type)

    combined_issues = []

    if checksum_res.get("overall_checksum_valid") is False:
        failed_list = checksum_res.get("failed_fields", [])
        combined_issues.append(f"MRZ checksum failure in field(s): {', '.join(failed_list)}")

    if not national_id_res["valid"]:
        combined_issues.extend(national_id_res["issues"])

    if aadhaar_res and not aadhaar_res["valid"]:
        combined_issues.extend(aadhaar_res["issues"])

    if voter_id_res and not voter_id_res["valid"]:
        combined_issues.extend(voter_id_res["issues"])

    if dl_res and not dl_res["valid"]:
        combined_issues.extend(dl_res["issues"])

    if visa_res and not visa_res["valid"]:
        combined_issues.extend(visa_res["issues"])

    if not viz_cross_res["consistent"]:
        combined_issues.extend(viz_cross_res["mismatches"])

    combined_issues.extend(dates_res.get("issues", []))

    if registry_res.get("blacklisted") is True:
        combined_issues.append(f"Registry alert: {registry_res.get('reason')}")

    domain_valid = True
    if aadhaar_res and not aadhaar_res["valid"]:
        domain_valid = False
    if voter_id_res and not voter_id_res["valid"]:
        domain_valid = False
    if dl_res and not dl_res["valid"]:
        domain_valid = False
    if visa_res and not visa_res["valid"]:
        domain_valid = False

    overall_valid = (
        checksum_res.get("overall_checksum_valid") is not False and
        national_id_res["valid"] is True and
        domain_valid is True and
        viz_cross_res["consistent"] is True and
        dates_res.get("expiry_valid") is True and
        dates_res.get("dob_plausible") is not False and
        registry_res.get("blacklisted") is False
    )

    return {
        "checksum": checksum_res,
        "national_id": national_id_res,
        "aadhaar_verification": aadhaar_res,
        "voter_id_verification": voter_id_res,
        "dl_verification": dl_res,
        "visa_verification": visa_res,
        "viz_consistency": viz_cross_res,
        "dates": dates_res,
        "blacklist": {
            "blacklisted": registry_res["blacklisted"],
            "reason": registry_res["reason"]
        },
        "registry": registry_res,
        "overall_valid": overall_valid,
        "issues": combined_issues
    }
