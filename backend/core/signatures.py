"""
BorderShield Sovereign Digital Signatures Module
Implements Section 15 & 33 of Security.md:
- Ed25519 asymmetric cryptography (RFC 8032)
- High-performance, constant-time digital signatures
- Signs canonical event hashes to guarantee non-repudiation and officer provenance
- Signature format: 'sig:ed25519:<hex_signature>'
- Fail-closed in production, deterministic key derivation in local demo mode
"""

import os
import base64
import logging
from typing import Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

from core.config import get_settings

logger = logging.getLogger("bordershield.signatures")

SIGNATURE_PREFIX = "sig:ed25519:"


def get_signing_private_key() -> ed25519.Ed25519PrivateKey:
    """Loads station Ed25519 private key from configured settings seed."""
    settings = get_settings()
    seed = settings.get_ed25519_key_bytes()
    return ed25519.Ed25519PrivateKey.from_private_bytes(seed)


def get_station_public_key() -> ed25519.Ed25519PublicKey:
    """Derives station Ed25519 public key from active private key."""
    return get_signing_private_key().public_key()


def get_station_public_key_hex() -> str:
    """Returns 32-byte raw public key as 64-char hexadecimal string."""
    pub_key = get_station_public_key()
    raw_bytes = pub_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return raw_bytes.hex()


def sign_canonical_hash(canonical_hash: str) -> str:
    """
    Signs a 64-character hex canonical event hash using the station's Ed25519 private key.
    Returns formatted signature string: 'sig:ed25519:<128-char hex>'.
    """
    if not canonical_hash:
        raise ValueError("Cannot sign empty canonical hash.")

    priv_key = get_signing_private_key()
    data_bytes = canonical_hash.strip().lower().encode("utf-8")
    signature_bytes = priv_key.sign(data_bytes)
    return f"{SIGNATURE_PREFIX}{signature_bytes.hex()}"


def verify_signature(
    canonical_hash: str,
    signature_str: str,
    public_key_hex: Optional[str] = None
) -> bool:
    """
    Verifies an Ed25519 digital signature against a canonical event hash.
    Accepts signatures in 'sig:ed25519:<hex>' or raw 128-char hex format.
    Returns True if valid, False if tampered or invalid.
    """
    if not canonical_hash or not signature_str:
        return False

    # Extract hex string
    if signature_str.startswith(SIGNATURE_PREFIX):
        raw_hex = signature_str[len(SIGNATURE_PREFIX):]
    else:
        raw_hex = signature_str.strip()

    try:
        signature_bytes = bytes.fromhex(raw_hex)
        if len(signature_bytes) != 64:
            return False
    except ValueError:
        return False

    try:
        if public_key_hex:
            pub_bytes = bytes.fromhex(public_key_hex.strip())
            pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        else:
            pub_key = get_station_public_key()

        data_bytes = canonical_hash.strip().lower().encode("utf-8")
        pub_key.verify(signature_bytes, data_bytes)
        return True
    except (InvalidSignature, ValueError, Exception) as e:
        logger.warning(f"Ed25519 signature verification failed: {e}")
        return False


def generate_station_keypair() -> Tuple[str, str]:
    """
    Generates a fresh Ed25519 keypair for sovereign border checkpoint deployment.
    Returns (private_key_hex, public_key_hex).
    """
    priv = ed25519.Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return priv_bytes.hex(), pub_bytes.hex()

