"""
BorderShield Normalized Database Models
Defines structured data entities for document registry, visas, blacklists,
biometrics, screening cases, and audit ledger events.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class DocumentRecord:
    """Normalized document registry record."""
    document_number: str
    document_type: str
    holder_name: Optional[str] = None
    status: str = "VALID"  # VALID, EXPIRED, REVOKED, STOLEN
    revocation_reason: Optional[str] = None
    document_token: Optional[str] = None  # Keyed HMAC token for privacy lookup
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_number": self.document_number,
            "document_type": self.document_type,
            "holder_name": self.holder_name,
            "status": self.status,
            "revocation_reason": self.revocation_reason,
            "document_token": self.document_token,
            "created_at": self.created_at or datetime.utcnow().isoformat() + "Z"
        }


@dataclass
class VisaRecord:
    """Normalized consular visa record."""
    visa_number: str
    passport_number: str
    visa_type: str = "TOURIST"
    status: str = "VALID"  # VALID, EXPIRED, REVOKED
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "visa_number": self.visa_number,
            "passport_number": self.passport_number,
            "visa_type": self.visa_type,
            "status": self.status,
            "created_at": self.created_at or datetime.utcnow().isoformat() + "Z"
        }


@dataclass
class BlacklistRecord:
    """National/Interpol Watchlist alert record."""
    passport_number: str
    reason: str
    document_token: Optional[str] = None  # Keyed HMAC token
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passport_number": self.passport_number,
            "reason": self.reason,
            "document_token": self.document_token,
            "created_at": self.created_at or datetime.utcnow().isoformat() + "Z"
        }


@dataclass
class BiometricRecord:
    """Encrypted biometric crossing profile."""
    id: Optional[int] = None
    traveler_name: str = ""
    document_number: str = ""
    document_type: str = "PASSPORT"
    nationality: str = "IND"
    crossing_point: str = "Raxaul ICP"
    crossing_timestamp: Optional[str] = None
    embedding_blob: bytes = b""
    subject_id: Optional[str] = None  # Pseudonymized subject identifier
    retention_until: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "traveler_name": self.traveler_name,
            "document_number": self.document_number,
            "document_type": self.document_type,
            "nationality": self.nationality,
            "crossing_point": self.crossing_point,
            "crossing_timestamp": self.crossing_timestamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "subject_id": self.subject_id,
            "retention_until": self.retention_until
        }


@dataclass
class ScreeningRecord:
    """Screening session record."""
    screening_id: str
    file_id: str
    document_type: str
    risk_score: float
    risk_level: str
    decision: str
    officer_id: str
    created_at: Optional[str] = None
    ocr_model_version: Optional[str] = None
    tamper_model_version: Optional[str] = None
    retention_until: Optional[str] = None
    legal_hold: bool = False


@dataclass
class AuditEventRecord:
    """Canonical append-only audit event record."""
    event_id: str
    event_type: str  # SCREENING_DECISION, BIOMETRIC_VERIFIED, OFFICER_OVERRIDE
    screening_id: str
    doc_hash: str
    risk_score: float
    decision: str
    officer_id: str
    timestamp: str
    previous_event_hash: str
    event_hash: str
    signature: Optional[str] = None  # Ed25519 signature
    anchor_status: str = "LOCAL_ANCHORED"  # LOCAL_ANCHORED, PENDING_SYNC, NBF_ANCHORED

