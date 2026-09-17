"""
BorderShield Cryptographic Security Module
Production-grade authenticated symmetric encryption (AES-256-GCM) and keyed tokenization.
Compliant with ISO/IEC 19794-5, DPDP Act 2023, and SIH-188 sovereign security mandates.
"""

import os
import hmac
import hashlib
import base64
import logging
from typing import Optional, Union, Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from core.config import get_settings

logger = logging.getLogger("bordershield.security")

# Prefix identifying versioned AES-256-GCM encrypted payloads
ENCRYPTION_PREFIX_STR = "enc:v1:"
ENCRYPTION_PREFIX_BYTES = b"enc:v1:"
NONCE_LENGTH = 12  # Standard 96-bit IV for AES-GCM


class SecurityError(Exception):
    """Base exception for cryptographic security errors."""
    pass


class EncryptionError(SecurityError):
    """Raised when encryption operation fails."""
    pass


class DecryptionError(SecurityError):
    """Raised when authenticated decryption or integrity check fails."""
    pass


def _resolve_key(key: Optional[bytes]) -> bytes:
    """Resolves provided key or fetches application master key from settings."""
    if key is not None:
        if len(key) != 32:
            raise ValueError(f"AES-256-GCM requires exactly 32 bytes (256 bits), got {len(key)} bytes.")
        return key
    return get_settings().get_encryption_key_bytes()


def is_encrypted(val: Any) -> bool:
    """Checks whether a value is already in the versioned encrypted format."""
    if isinstance(val, str):
        return val.startswith(ENCRYPTION_PREFIX_STR)
    if isinstance(val, (bytes, bytearray)):
        return val.startswith(ENCRYPTION_PREFIX_BYTES)
    return False


def encrypt_bytes(
    data: bytes,
    key: Optional[bytes] = None,
    associated_data: Optional[bytes] = None
) -> bytes:
    """
    Encrypts arbitrary byte payloads (e.g. biometric embeddings) using AES-256-GCM.
    Returns: b"enc:v1:" + nonce (12 bytes) + ciphertext_with_tag
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("Data to encrypt must be bytes or bytearray.")

    aes_key = _resolve_key(key)
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(NONCE_LENGTH)

    try:
        ciphertext = aesgcm.encrypt(nonce, data, associated_data)
        return ENCRYPTION_PREFIX_BYTES + nonce + ciphertext
    except Exception as e:
        logger.error(f"Authenticated encryption failed: {e}")
        raise EncryptionError(f"Failed to encrypt byte payload: {e}") from e


def decrypt_bytes(
    payload: bytes,
    key: Optional[bytes] = None,
    associated_data: Optional[bytes] = None
) -> bytes:
    """
    Decrypts byte payloads encrypted with encrypt_bytes.
    Transparently returns legacy unencrypted bytes if prefix is absent.
    Raises DecryptionError if authentication tag verification fails (tampering detected).
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("Payload to decrypt must be bytes or bytearray.")

    # Graceful handling of legacy unencrypted records
    if not payload.startswith(ENCRYPTION_PREFIX_BYTES):
        return bytes(payload)

    aes_key = _resolve_key(key)
    aesgcm = AESGCM(aes_key)

    prefix_len = len(ENCRYPTION_PREFIX_BYTES)
    nonce = payload[prefix_len:prefix_len + NONCE_LENGTH]
    ciphertext = payload[prefix_len + NONCE_LENGTH:]

    try:
        return aesgcm.decrypt(nonce, ciphertext, associated_data)
    except InvalidTag as e:
        logger.critical("DECRYPTION INTEGRITY FAILURE: Authentication tag verification failed. Possible data tampering!")
        raise DecryptionError("Ciphertext integrity verification failed. Data has been tampered with or key is incorrect.") from e
    except Exception as e:
        raise DecryptionError(f"Failed to decrypt byte payload: {e}") from e


def encrypt_field(
    plaintext: Optional[str],
    key: Optional[bytes] = None,
    associated_data: Optional[bytes] = None
) -> Optional[str]:
    """
    Encrypts a text field into a safe URL-safe base64 string format:
    'enc:v1:<b64_nonce>:<b64_ciphertext_with_tag>'
    """
    if plaintext is None:
        return None
    if not isinstance(plaintext, str):
        plaintext = str(plaintext)

    # Avoid double encryption
    if plaintext.startswith(ENCRYPTION_PREFIX_STR):
        return plaintext

    raw_bytes = plaintext.encode("utf-8")
    aes_key = _resolve_key(key)
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(NONCE_LENGTH)

    try:
        ad_bytes = associated_data.encode("utf-8") if isinstance(associated_data, str) else associated_data
        ciphertext = aesgcm.encrypt(nonce, raw_bytes, ad_bytes)
        b64_nonce = base64.urlsafe_b64encode(nonce).decode("ascii")
        b64_cipher = base64.urlsafe_b64encode(ciphertext).decode("ascii")
        return f"{ENCRYPTION_PREFIX_STR}{b64_nonce}:{b64_cipher}"
    except Exception as e:
        logger.error(f"Field encryption failed: {e}")
        raise EncryptionError(f"Failed to encrypt field: {e}") from e


def decrypt_field(
    encrypted_str: Optional[str],
    key: Optional[bytes] = None,
    associated_data: Optional[bytes] = None
) -> Optional[str]:
    """
    Decrypts an encrypted field string back to plaintext.
    Transparently returns legacy unencrypted text if prefix is absent.
    Raises DecryptionError if tampered with or wrong key.
    """
    if encrypted_str is None:
        return None
    if not isinstance(encrypted_str, str):
        return str(encrypted_str)

    # Graceful handling for legacy unencrypted text
    if not encrypted_str.startswith(ENCRYPTION_PREFIX_STR):
        return encrypted_str

    token_body = encrypted_str[len(ENCRYPTION_PREFIX_STR):]
    parts = token_body.split(":")
    if len(parts) != 2:
        raise DecryptionError("Malformed encrypted field structure.")

    b64_nonce, b64_cipher = parts
    try:
        nonce = base64.urlsafe_b64decode(b64_nonce.encode("ascii"))
        ciphertext = base64.urlsafe_b64decode(b64_cipher.encode("ascii"))
    except Exception as e:
        raise DecryptionError(f"Failed to decode base64 components: {e}") from e

    aes_key = _resolve_key(key)
    aesgcm = AESGCM(aes_key)

    try:
        ad_bytes = associated_data.encode("utf-8") if isinstance(associated_data, str) else associated_data
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, ad_bytes)
        return decrypted_bytes.decode("utf-8")
    except InvalidTag as e:
        logger.critical("FIELD DECRYPTION INTEGRITY FAILURE: Authentication tag mismatch. Tampering detected!")
        raise DecryptionError("Field integrity verification failed. Data was tampered with or key is incorrect.") from e
    except Exception as e:
        raise DecryptionError(f"Failed to decrypt field: {e}") from e


# ------------------------------------------------------------------------------
# Keyed Identifier Tokenization (HMAC-SHA-256)
# ------------------------------------------------------------------------------
TOKEN_PREFIX_STR = "tok:v1:"


def _resolve_hmac_key(key: Optional[bytes]) -> bytes:
    """Resolves provided HMAC key or fetches application secret key from settings."""
    if key is not None:
        if len(key) < 16:
            raise ValueError(f"HMAC key must be at least 16 bytes, got {len(key)} bytes.")
        return key
    return get_settings().get_hmac_key_bytes()


def normalize_identifier(identifier: Optional[str]) -> str:
    """
    Normalizes an identity identifier prior to tokenization.
    Converts to uppercase, strips whitespace, hyphens, spaces, and periods.
    """
    if not identifier:
        return ""
    return "".join(ch for ch in str(identifier).strip().upper() if ch not in (" ", "-", "_", "."))


def tokenize_identifier(
    identifier: Optional[str],
    key: Optional[bytes] = None
) -> Optional[str]:
    """
    Computes a keyed cryptographic token for an identity identifier (Passport, Aadhaar, PAN)
    using HMAC-SHA-256. Returns 'tok:v1:<64-char-hex>'.
    Protects against dictionary and rainbow-table attacks on low-entropy numbers.
    """
    if identifier is None:
        return None
    norm = normalize_identifier(identifier)
    if not norm:
        return None

    hmac_key = _resolve_hmac_key(key)
    digest = hmac.new(hmac_key, norm.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{TOKEN_PREFIX_STR}{digest}"


def verify_token(
    identifier: str,
    token: str,
    key: Optional[bytes] = None
) -> bool:
    """Constant-time verification of an identifier against a known token."""
    expected = tokenize_identifier(identifier, key=key)
    if not expected:
        return False
    return hmac.compare_digest(expected, token)

