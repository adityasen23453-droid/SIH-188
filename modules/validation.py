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


def validate_mrz_checksum(passport_number: str = None, date_of_birth: str = None, date_of_expiry: str = None, mrz_line2: str = None) -> dict:
    """
    Validates MRZ check digits on standard passport MRZ line 2 (TD3 format).
    Returns { "checksum_valid": bool | None, "details": "..." }
    """
    if not mrz_line2 or not isinstance(mrz_line2, str) or len(mrz_line2.strip()) == 0:
        return {
            "checksum_valid": None,
            "details": "MRZ not available for checksum validation"
        }

    line2 = mrz_line2.strip()
    if len(line2) < 28:
        return {
            "checksum_valid": False,
            "details": f"MRZ line 2 length ({len(line2)}) is too short for validation"
        }

    failed_checks = []

    # 1. Passport number check digit (chars 0..8, check digit at char 9)
    passport_field = line2[0:9]
    passport_check_char = line2[9]
    if not passport_check_char.isdigit():
        failed_checks.append("Passport number check digit is non-numeric")
    else:
        calc_check = calc_mrz_check_digit(passport_field)
        if calc_check != int(passport_check_char):
            failed_checks.append(f"Passport check digit mismatch (computed {calc_check}, expected {passport_check_char})")

    # 2. Date of birth check digit (chars 13..18, check digit at char 19)
    dob_field = line2[13:19]
    dob_check_char = line2[19]
    if not dob_check_char.isdigit():
        failed_checks.append("DOB check digit is non-numeric")
    else:
        calc_check = calc_mrz_check_digit(dob_field)
        if calc_check != int(dob_check_char):
            failed_checks.append(f"DOB check digit mismatch (computed {calc_check}, expected {dob_check_char})")

    # 3. Date of expiry check digit (chars 21..26, check digit at char 27)
    expiry_field = line2[21:27]
    expiry_check_char = line2[27]
    if not expiry_check_char.isdigit():
        failed_checks.append("Expiry check digit is non-numeric")
    else:
        calc_check = calc_mrz_check_digit(expiry_field)
        if calc_check != int(expiry_check_char):
            failed_checks.append(f"Expiry check digit mismatch (computed {calc_check}, expected {expiry_check_char})")

    # 4. Composite check digit if 44 characters
    if len(line2) >= 44:
        composite_field = line2[0:10] + line2[13:20] + line2[21:43]
        composite_check_char = line2[43]
        if composite_check_char.isdigit():
            calc_check = calc_mrz_check_digit(composite_field)
            if calc_check != int(composite_check_char):
                failed_checks.append(f"Composite check digit mismatch (computed {calc_check}, expected {composite_check_char})")

    if failed_checks:
        return {
            "checksum_valid": False,
            "details": "MRZ checksum failure: " + "; ".join(failed_checks)
        }

    return {
        "checksum_valid": True,
        "details": "MRZ checksums valid"
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

    # Try standard ISO / hyphen / slash formats first
    formats = [
        "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y",
        "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%Y%m%d"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass

    # YYMMDD (6 digits, common in MRZ)
    if len(date_str) == 6 and date_str.isdigit():
        yy = int(date_str[0:2])
        mm = int(date_str[2:4])
        dd = int(date_str[4:6])
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            current_year = date.today().year
            current_yy = current_year % 100

            if date_type == "expiry":
                # Expiry dates are typically in the 2000s unless very old
                year = 2000 + yy if yy <= current_yy + 30 else 1900 + yy
            elif date_type == "dob":
                # DOB: if YY <= current_yy, usually born 2000s; if YY > current_yy, born 1900s
                year = 2000 + yy if yy <= current_yy else 1900 + yy
            else:
                year = 2000 + yy if yy <= current_yy + 15 else 1900 + yy

            try:
                return date(year, mm, dd)
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

    if checksum_res.get("checksum_valid") is False:
        combined_issues.append(f"Checksum error: {checksum_res.get('details')}")

    combined_issues.extend(dates_res.get("issues", []))

    if blacklist_res.get("blacklisted") is True:
        combined_issues.append(f"Passport blacklisted: {blacklist_res.get('reason')}")

    overall_valid = (
        checksum_res.get("checksum_valid") is not False and
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
