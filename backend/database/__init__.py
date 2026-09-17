"""
BorderShield Database Abstraction Package
"""

from database.models import (
    DocumentRecord,
    VisaRecord,
    BlacklistRecord,
    BiometricRecord,
    ScreeningRecord,
    AuditEventRecord
)
from database.repository import (
    BaseRepository,
    SQLiteRepository,
    PostgresRepository,
    get_repository
)

__all__ = [
    "DocumentRecord",
    "VisaRecord",
    "BlacklistRecord",
    "BiometricRecord",
    "ScreeningRecord",
    "AuditEventRecord",
    "BaseRepository",
    "SQLiteRepository",
    "PostgresRepository",
    "get_repository"
]

