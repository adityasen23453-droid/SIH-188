import os
import re
import sqlite3
from datetime import datetime, date


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


def correct_mrz_line2_numeric_fields(mrz_line2: str) -> tuple[str, list[str]]:
    """
    Applies ICAO 9303 letter-to-digit auto-correction strictly to positions
    that must be numeric digits (DOB 13-19, Expiry 21-27, check digits 9, 19, 27, 43).
    Does NOT modify passport number (0-8) or nationality (10-12).
    Returns (corrected_mrz_line2, corrections_applied_list).
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

    numeric_positions = [9, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 24, 25, 26, 27]
    if len(line) >= 44:
        numeric_positions.append(43)

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
    Returns structured results for passport number, date of birth, date of expiry,
    composite check, overall validity boolean, list of failed fields, and applied OCR corrections.
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

    line2, corrections_applied = correct_mrz_line2_numeric_fields(mrz_line2)
    if len(line2) < 28:
        empty_result["note"] = f"MRZ line 2 length ({len(line2)}) is too short for validation"
        empty_result["ocr_corrections_applied"] = corrections_applied
        return empty_result

    failed_fields = []
    malformed_note = "MRZ read appears malformed at this position, skipping checksum check"

    # 1. Passport number check (chars 0..8, check digit at char 9)
    passport_val = line2[0:9]
    passport_exp = line2[9]
    if not passport_exp.isdigit():
        passport_check = {
            "value": passport_val,
            "expected_digit": passport_exp,
            "computed_digit": None,
            "valid": None,
            "field_slice": "0:9",
            "check_digit_pos": 9,
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
            "field_slice": "0:9",
            "check_digit_pos": 9
        }

    # 2. Date of birth check (chars 13..18, check digit at char 19)
    dob_val = line2[13:19]
    dob_exp = line2[19]
    if not dob_exp.isdigit():
        dob_check = {
            "value": dob_val,
            "expected_digit": dob_exp,
            "computed_digit": None,
            "valid": None,
            "field_slice": "13:19",
            "check_digit_pos": 19,
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
            "field_slice": "13:19",
            "check_digit_pos": 19
        }

    # 3. Date of expiry check (chars 21..26, check digit at char 27)
    expiry_val = line2[21:27]
    expiry_exp = line2[27]
    if not expiry_exp.isdigit():
        expiry_check = {
            "value": expiry_val,
            "expected_digit": expiry_exp,
            "computed_digit": None,
            "valid": None,
            "field_slice": "21:27",
            "check_digit_pos": 27,
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
            "field_slice": "21:27",
            "check_digit_pos": 27
        }

    # 4. Composite check
    if len(line2) >= 44:
        composite_field = line2[0:10] + line2[13:20] + line2[21:43]
        composite_exp = line2[43]
        composite_slice_str = "0:10 + 13:20 + 21:43"
        composite_pos = 43
    elif len(line2) >= 30 and line2[-1].isdigit():
        composite_field = line2[0:10] + line2[13:20] + line2[21:-1]
        composite_exp = line2[-1]
        composite_slice_str = f"0:10 + 13:20 + 21:{len(line2)-1}"
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


def parse_date(date_val, date_type: str = None) -> date | None:
    """Parses various date string formats into a datetime.date object."""
    if not date_val:
        return None
    if isinstance(date_val, (date, datetime)):
        return date_val.date() if isinstance(date_val, datetime) else date_val

    date_str = str(date_val).strip()
    if not date_str:
        return None

    # 1. YYMMDD (6 digits, common in MRZ)
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

    # 2. YYYYMMDD (8 digits)
    if len(date_str) == 8 and date_str.isdigit():
        try:
            return datetime.strptime(date_str, "%Y%m%d").date()
        except ValueError:
            pass

    # 3. Standard ISO / hyphen / slash formats
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


def validate_dates(date_of_birth: str = None, date_of_expiry: str = None, date_of_issue: str = None) -> dict:
    """
    Validates date plausibility and expiration.
    Returns { "expiry_valid": bool, "dob_plausible": bool, "issues": [...] }
    """
    issues = []
    today = date.today()

    # 1. Check Date of Expiry
    expiry_valid = True
    if not date_of_expiry:
        expiry_valid = False
        issues.append("Date of expiry is missing")
    else:
        parsed_expiry = parse_date(date_of_expiry, date_type="expiry")
        if not parsed_expiry:
            expiry_valid = False
            issues.append(f"Date of expiry '{date_of_expiry}' is unparseable")
        elif parsed_expiry <= today:
            expiry_valid = False
            issues.append(f"Document expired on {parsed_expiry.isoformat()}")

    # 2. Check Date of Birth
    dob_plausible = True
    if not date_of_birth:
        dob_plausible = False
        issues.append("Date of birth is missing")
    else:
        parsed_dob = parse_date(date_of_birth, date_type="dob")
        if not parsed_dob:
            dob_plausible = False
            issues.append(f"Date of birth '{date_of_birth}' is unparseable")
        else:
            if parsed_dob > today:
                dob_plausible = False
                issues.append(f"Date of birth {parsed_dob.isoformat()} is in the future")
            else:
                age_years = (today - parsed_dob).days / 365.25
                if age_years > 120:
                    dob_plausible = False
                    issues.append(f"Date of birth {parsed_dob.isoformat()} is more than 120 years ago")

    # 3. Check Date of Issue (if provided)
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
        "dob_plausible": dob_plausible,
        "issues": issues
    }


def get_blacklist_db_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base_dir, "data", "blacklist.db")


def check_blacklist(passport_number: str = None) -> dict:
    """
    Checks if a passport number is listed in the local SQLite blacklist database.
    Returns { "blacklisted": bool, "reason": str | None }
    """
    if not passport_number or not isinstance(passport_number, str) or not passport_number.strip():
        return {
            "blacklisted": False,
            "reason": None
        }

    db_path = get_blacklist_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                passport_number TEXT PRIMARY KEY,
                reason TEXT
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM blacklist")
        count = cursor.fetchone()[0]
        if count == 0:
            seed_data = [
                ("X1234567", "Reported stolen"),
                ("A9876543", "Fraudulent document"),
                ("P0000000", "Flagged by Interpol")
            ]
            cursor.executemany("INSERT OR IGNORE INTO blacklist VALUES (?, ?)", seed_data)
            conn.commit()

        norm_num = passport_number.strip().upper()
        cursor.execute("SELECT reason FROM blacklist WHERE UPPER(passport_number) = ?", (norm_num,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "blacklisted": True,
                "reason": row[0]
            }
        return {
            "blacklisted": False,
            "reason": None
        }
    except Exception as e:
        return {
            "blacklisted": False,
            "reason": f"Blacklist check error: {str(e)}"
        }


def run_validation(ocr_result: dict) -> dict:
    """
    Single entry function that accepts full output from run_ocr() and executes validation checks.
    Returns consolidated dict:
    { "checksum": {...}, "dates": {...}, "blacklist": {...}, "overall_valid": bool, "issues": [...] }
    """
    if not isinstance(ocr_result, dict):
        ocr_result = {}

    fields = ocr_result.get("fields") or {}
    if not isinstance(fields, dict):
        fields = {}

    passport_number = fields.get("passport_number") or fields.get("id_number") or fields.get("visa_number")
    date_of_birth = fields.get("date_of_birth")
    date_of_expiry = fields.get("date_of_expiry") or fields.get("valid_until")
    date_of_issue = fields.get("date_of_issue")
    mrz_line2 = fields.get("mrz_line2")

    checksum_res = validate_mrz_checksum(
        passport_number=passport_number,
        date_of_birth=date_of_birth,
        date_of_expiry=date_of_expiry,
        mrz_line2=mrz_line2
    )

    dates_res = validate_dates(
        date_of_birth=date_of_birth,
        date_of_expiry=date_of_expiry,
        date_of_issue=date_of_issue
    )

    blacklist_res = check_blacklist(passport_number=passport_number)

    combined_issues = []

    if checksum_res.get("overall_checksum_valid") is False:
        failed_list = checksum_res.get("failed_fields", [])
        combined_issues.append(f"MRZ checksum failure in field(s): {', '.join(failed_list)}")

    combined_issues.extend(dates_res.get("issues", []))

    if blacklist_res.get("blacklisted") is True:
        combined_issues.append(f"Passport blacklisted: {blacklist_res.get('reason')}")

    overall_valid = (
        checksum_res.get("overall_checksum_valid") is not False and
        dates_res.get("expiry_valid") is True and
        dates_res.get("dob_plausible") is True and
        len(dates_res.get("issues", [])) == 0 and
        blacklist_res.get("blacklisted") is False
    )

    return {
        "checksum": checksum_res,
        "dates": dates_res,
        "blacklist": blacklist_res,
        "overall_valid": overall_valid,
        "issues": combined_issues
    }
