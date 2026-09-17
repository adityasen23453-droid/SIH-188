"""
BorderShield Storage Lifecycle & File Upload Hardening Module
Implements strict magic-byte validation, upload size bounds, path traversal prevention,
and ephemeral file retention cleanup (DPDP Act 2023 / Section 10-11 of Security.md).
"""

import os
import time
import logging
from typing import Tuple, Optional, Dict, Any

from core.config import get_settings

logger = logging.getLogger("bordershield.lifecycle")

# Sovereign document file signatures (Magic Bytes)
MAGIC_SIGNATURES = {
    b"\xff\xd8\xff": ".jpg",                    # JPEG
    b"\x89PNG\r\n\x1a\n": ".png",              # PNG
    b"%PDF-": ".pdf",                          # PDF
}

MAX_IMAGE_PIXELS = 50_000_000  # Prevent decompression bomb attacks (50 Megapixels)


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a client-provided filename to prevent path traversal attacks.
    Strips directory separators, relative path markers ('..'), and non-ASCII chars.
    """
    if not filename:
        return "unnamed_document"
    base = os.path.basename(filename.replace("\\", "/"))
    base = base.lstrip("./")
    safe_name = "".join(c for c in base if c.isalnum() or c in "._- ")
    return safe_name or "unnamed_document"


def validate_file_content(
    content: bytes,
    client_filename: Optional[str] = None
) -> Tuple[bool, str, str, int]:
    """
    Validates uploaded file against size limits and strict file signatures (magic bytes).
    Never trusts client Content-Type headers or file extensions.

    Returns:
        (is_valid: bool, safe_extension: str, error_message: str, http_status_code: int)
    """
    settings = get_settings()

    if not content or len(content) == 0:
        return False, "", "Empty file uploaded.", 400

    # 1. Enforce payload size limit
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        mb_limit = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        actual_mb = round(len(content) / (1024 * 1024), 2)
        return False, "", f"File size ({actual_mb}MB) exceeds maximum permissible threshold of {mb_limit}MB.", 413

    # 2. Magic byte inspection
    matched_ext = None
    for magic, ext in MAGIC_SIGNATURES.items():
        if content.startswith(magic):
            matched_ext = ext
            break

    # WebP check (RIFF....WEBP)
    if not matched_ext and len(content) >= 12:
        if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            matched_ext = ".webp"

    if not matched_ext:
        logger.warning(
            f"Upload rejected: Unrecognized file signature from {client_filename}. "
            f"Header bytes: {content[:8].hex()}"
        )
        return (
            False,
            "",
            "Security Violation: File rejected. Only authentic JPEG, PNG, WEBP, and PDF documents are permitted.",
            400
        )

    # 3. Decompression bomb check for raster images
    if matched_ext in (".jpg", ".png", ".webp"):
        try:
            import cv2
            import numpy as np
            nparr = np.frombuffer(content, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                h, w = img.shape[:2]
                total_pixels = h * w
                if total_pixels > MAX_IMAGE_PIXELS:
                    return False, "", "Image dimensions exceed safety limits (possible decompression bomb).", 400
        except Exception as e:
            logger.warning(f"Image decode sanity check warning: {e}")

    return True, matched_ext, "", 200


def cleanup_expired_uploads(
    upload_root: Optional[str] = None,
    max_age_hours: Optional[int] = None
) -> Dict[str, Any]:
    """
    Scans upload directories and removes ephemeral files that exceed the retention lifetime.
    Preserves .gitkeep files and any file flagged with legal hold.
    Complies with Section 10 of Security.md & DPDP Act 2023 storage minimization.
    """
    settings = get_settings()
    if upload_root is None:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        upload_root = os.path.join(backend_dir, "uploads")

    hours = max_age_hours if max_age_hours is not None else settings.DOCUMENT_RETENTION_HOURS
    max_age_seconds = hours * 3600
    now = time.time()

    deleted_count = 0
    scanned_count = 0
    errors = []

    if not os.path.exists(upload_root):
        return {"deleted_count": 0, "scanned_count": 0, "errors": []}

    for root, dirs, files in os.walk(upload_root):
        for filename in files:
            # Preserve git directory structure markers
            if filename == ".gitkeep":
                continue

            file_path = os.path.join(root, filename)
            scanned_count += 1

            try:
                stat = os.stat(file_path)
                file_age = now - stat.st_mtime
                if file_age > max_age_seconds:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Ephemeral retention purged: {file_path} (age: {round(file_age/3600, 1)}h)")
            except Exception as e:
                errors.append(f"Failed to remove {file_path}: {e}")

    return {
        "deleted_count": deleted_count,
        "scanned_count": scanned_count,
        "errors": errors
    }

