"""
BorderShield Centralized Configuration Module
Typed, validated configuration settings loaded from environment variables and .env files.
Compliant with SIH-188 security, privacy, and government deployment guidelines.
"""

import os
import hashlib
import base64
import logging
from functools import lru_cache
from typing import List, Union, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

logger = logging.getLogger("bordershield.config")


class Settings(BaseSettings):
    """Application settings with environment override and production fail-closed security."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # --------------------------------------------------------------------------
    # Deployment Environment
    # --------------------------------------------------------------------------
    ENVIRONMENT: str = Field(
        default="development",
        description="Deployment stage: 'development', 'staging', or 'production'"
    )
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode. Must be False in production."
    )

    # --------------------------------------------------------------------------
    # CORS & Network Security
    # --------------------------------------------------------------------------
    CORS_ALLOWED_ORIGINS: Union[List[str], str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Explicit allowlist of web origins for cross-origin requests."
    )

    # --------------------------------------------------------------------------
    # Cryptographic Keys (Authenticated Encryption & HMAC Tokenization)
    # --------------------------------------------------------------------------
    SECRET_KEY: Optional[str] = Field(
        default=None,
        description="Application master secret for session tokens and signatures."
    )
    ENCRYPTION_MASTER_KEY: Optional[str] = Field(
        default=None,
        description="Base64-encoded 256-bit AES key for PII and biometric vault encryption."
    )
    HMAC_SECRET_KEY: Optional[str] = Field(
        default=None,
        description="Base64-encoded 256-bit key for deterministic identifier tokenization."
    )
    ED25519_PRIVATE_KEY: Optional[str] = Field(
        default=None,
        description="Hex or Base64 Ed25519 private key for signing canonical audit events."
    )

    # --------------------------------------------------------------------------
    # Database Configuration
    # --------------------------------------------------------------------------
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Optional PostgreSQL connection URL (e.g. postgresql://user:pass@host/db). If omitted, SQLite is used."
    )

    # --------------------------------------------------------------------------
    # Ephemeral Storage & Retention Policies (DPDP Act 2023)
    # --------------------------------------------------------------------------
    DOCUMENT_RETENTION_HOURS: int = Field(
        default=24,
        description="Retention lifetime in hours for raw scanned document uploads."
    )
    BIOMETRIC_RETENTION_HOURS: int = Field(
        default=72,
        description="Retention lifetime in hours for ephemeral biometric live capture vectors."
    )
    FORENSIC_ARTIFACT_RETENTION_HOURS: int = Field(
        default=24,
        description="Retention lifetime in hours for ELA heatmaps and HUD overlays."
    )
    MAX_UPLOAD_SIZE_BYTES: int = Field(
        default=15 * 1024 * 1024,  # 15 MB
        description="Maximum permissible file upload size in bytes."
    )
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = Field(
        default=[".jpg", ".jpeg", ".png", ".pdf", ".webp"],
        description="Permissible file extensions for document submission."
    )

    # --------------------------------------------------------------------------
    # Audit Ledger & Sovereign Framework
    # --------------------------------------------------------------------------
    LEDGER_MODE: str = Field(
        default="LOCAL_LEDGER",
        description="Audit ledger backend: 'LOCAL_LEDGER' or 'NBF_PERMISSIONED'"
    )
    NBF_ENDPOINT: Optional[str] = Field(
        default=None,
        description="Endpoint URL for India's National Blockchain Framework / Vishvasya Stack."
    )
    DEFAULT_OFFICER_ID: str = Field(
        default="SSB-OFFICER-7429",
        description="Default identifier for active checkpoint officer station."
    )
    DEFAULT_OFFICER_ROLE: str = Field(
        default="SCREENING_OFFICER",
        description="Default operational role: SCREENING_OFFICER, SUPERVISOR, INVESTIGATOR, AUDITOR, SYSTEM_ADMIN."
    )

    # --------------------------------------------------------------------------
    # Auditable Model & Pipeline Versions
    # --------------------------------------------------------------------------
    OCR_MODEL_VERSION: str = Field(
        default="PaddleOCR_v6_TrOCR_Fallback_v1.0",
        description="Version tag of active sovereign document OCR engine."
    )
    FACE_MODEL_VERSION: str = Field(
        default="MobileNetV3_L2_576d_v1.0",
        description="Version tag of active facial embedding feature extractor."
    )
    TAMPERING_MODEL_VERSION: str = Field(
        default="ViT_Forensics_ELA_Stamp_v1.0",
        description="Version tag of active neural forgery and ELA tampering analyzer."
    )

    # --------------------------------------------------------------------------
    # Validators & Helper Parsers
    # --------------------------------------------------------------------------
    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v: Union[bool, str, int]) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "debug", "on")
        return False

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            # Parse comma-separated or JSON string
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Returns normalized list of CORS allowed origins."""
        if isinstance(self.CORS_ALLOWED_ORIGINS, list):
            return self.CORS_ALLOWED_ORIGINS
        return [str(self.CORS_ALLOWED_ORIGINS)]

    def get_encryption_key_bytes(self) -> bytes:
        """
        Derives or decodes a 32-byte (256-bit) AES key.
        Fails closed in production if not explicitly configured.
        """
        if self.ENCRYPTION_MASTER_KEY:
            try:
                raw_bytes = base64.b64decode(self.ENCRYPTION_MASTER_KEY)
                if len(raw_bytes) == 32:
                    return raw_bytes
                if len(raw_bytes) > 32:
                    return raw_bytes[:32]
            except Exception as e:
                logger.error(f"Failed to decode ENCRYPTION_MASTER_KEY: {e}")

        if self.ENVIRONMENT.lower() == "production":
            raise ValueError(
                "FAIL CLOSED: ENCRYPTION_MASTER_KEY is required and must be a 32-byte base64 string in production."
            )

        # Stable, reproducible development key for offline hackathon demo
        logger.warning(
            "Using deterministic local development key for AES-256-GCM encryption. "
            "Set ENCRYPTION_MASTER_KEY in production."
        )
        return hashlib.sha256(b"BorderShield-Dev-Master-Key-SIH2026-PS26188").digest()

    def get_hmac_key_bytes(self) -> bytes:
        """
        Derives or decodes a 32-byte key for HMAC-SHA-256 tokenization.
        Fails closed in production if not explicitly configured.
        """
        if self.HMAC_SECRET_KEY:
            try:
                raw_bytes = base64.b64decode(self.HMAC_SECRET_KEY)
                if len(raw_bytes) >= 32:
                    return raw_bytes[:32]
            except Exception as e:
                logger.error(f"Failed to decode HMAC_SECRET_KEY: {e}")

        if self.ENVIRONMENT.lower() == "production":
            raise ValueError(
                "FAIL CLOSED: HMAC_SECRET_KEY is required and must be a 32-byte base64 string in production."
            )

        return hashlib.sha256(b"BorderShield-Dev-HMAC-Token-Key-SIH2026").digest()

    def get_ed25519_key_bytes(self) -> bytes:
        """
        Derives or decodes a 32-byte seed for Ed25519 asymmetric audit signing.
        Fails closed in production if not explicitly configured.
        """
        if self.ED25519_PRIVATE_KEY:
            try:
                key_str = self.ED25519_PRIVATE_KEY.strip()
                if len(key_str) == 64 and all(c in "0123456789abcdefABCDEF" for c in key_str):
                    return bytes.fromhex(key_str)
                raw_bytes = base64.b64decode(key_str)
                if len(raw_bytes) >= 32:
                    return raw_bytes[:32]
            except Exception as e:
                logger.error(f"Failed to decode ED25519_PRIVATE_KEY: {e}")

        if self.ENVIRONMENT.lower() == "production":
            raise ValueError(
                "FAIL CLOSED: ED25519_PRIVATE_KEY is required in production for audit ledger signing."
            )

        return hashlib.sha256(b"BorderShield-Dev-Ed25519-Sign-Key-SIH2026").digest()


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton provider for application settings."""
    return Settings()
