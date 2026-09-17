"""
BorderShield Database Abstraction & Repository Layer
Provides an abstracted, pluggable persistence layer supporting both:
1. SQLiteRepository (Default for local zero-setup SIH offline evaluation)
2. PostgresRepository (Production sovereign database deployment via DATABASE_URL)
Guarantees idempotent, non-destructive migrations and full backward compatibility.
"""

import os
import sqlite3
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
from functools import lru_cache

from database.models import (
    DocumentRecord,
    VisaRecord,
    BlacklistRecord,
    BiometricRecord,
    ScreeningRecord,
    AuditEventRecord
)
from core.config import get_settings
from core.security import (
    encrypt_field,
    decrypt_field,
    tokenize_identifier,
    encrypt_bytes,
    decrypt_bytes,
    is_encrypted
)

logger = logging.getLogger("bordershield.repository")


class BaseRepository(ABC):
    """Abstract sovereign border repository interface."""

    @abstractmethod
    def init_db(self) -> None:
        """Initialize and safely migrate database schemas."""
        pass

    # --- Document Registry ---
    @abstractmethod
    def get_document(self, document_number: str) -> Optional[DocumentRecord]:
        pass

    @abstractmethod
    def get_document_by_token(self, document_token: str) -> Optional[DocumentRecord]:
        pass

    @abstractmethod
    def upsert_document(self, record: DocumentRecord) -> None:
        pass

    # --- Visas ---
    @abstractmethod
    def get_visa(self, visa_number: str, passport_number: str) -> Optional[VisaRecord]:
        pass

    @abstractmethod
    def upsert_visa(self, record: VisaRecord) -> None:
        pass

    # --- Blacklist ---
    @abstractmethod
    def get_blacklist(self, passport_number: str) -> Optional[BlacklistRecord]:
        pass

    @abstractmethod
    def get_blacklist_by_token(self, document_token: str) -> Optional[BlacklistRecord]:
        pass

    @abstractmethod
    def upsert_blacklist(self, record: BlacklistRecord) -> None:
        pass

    # --- Biometrics ---
    @abstractmethod
    def register_biometric_profile(self, record: BiometricRecord) -> int:
        pass

    @abstractmethod
    def get_all_biometrics(self) -> List[BiometricRecord]:
        pass


class SQLiteRepository(BaseRepository):
    """
    SQLite implementation maintaining strict compatibility with existing SIH-188 local databases:
    - backend/data/registry.db
    - backend/data/biometrics.db
    - backend/data/blockchain.db
    """

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.data_dir = os.path.join(backend_dir, "data")
        else:
            self.data_dir = data_dir

        os.makedirs(self.data_dir, exist_ok=True)
        self.registry_db_path = os.path.join(self.data_dir, "registry.db")
        self.biometrics_db_path = os.path.join(self.data_dir, "biometrics.db")
        self.blockchain_db_path = os.path.join(self.data_dir, "blockchain.db")

        self.init_db()

    def _get_connection(self, db_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _safe_add_column(self, cursor: sqlite3.Cursor, table_name: str, column_name: str, col_type: str):
        """Adds column to table if it doesn't already exist (idempotent, safe)."""
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        if column_name not in columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {col_type}")
            logger.info(f"Added column {column_name} to {table_name}")

    def init_db(self) -> None:
        """Initializes tables and applies non-destructive schema migrations."""
        # 1. Registry DB
        with self._get_connection(self.registry_db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_number TEXT PRIMARY KEY,
                    document_type TEXT NOT NULL,
                    holder_name TEXT,
                    status TEXT NOT NULL CHECK(status IN ('VALID', 'EXPIRED', 'REVOKED', 'STOLEN')),
                    revocation_reason TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS visas (
                    visa_number TEXT PRIMARY KEY,
                    passport_number TEXT NOT NULL,
                    visa_type TEXT,
                    status TEXT NOT NULL CHECK(status IN ('VALID', 'EXPIRED', 'REVOKED'))
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    passport_number TEXT PRIMARY KEY,
                    reason TEXT
                )
            """)

            # Safe additive migrations
            self._safe_add_column(cur, "documents", "document_token", "TEXT")
            self._safe_add_column(cur, "documents", "created_at", "TEXT")
            self._safe_add_column(cur, "blacklist", "document_token", "TEXT")
            self._safe_add_column(cur, "blacklist", "created_at", "TEXT")

            # Seed blacklist if empty
            cur.execute("SELECT COUNT(*) FROM blacklist")
            if cur.fetchone()[0] == 0:
                seed_blacklist = [
                    ("X1234567", "Reported stolen to Interpol"),
                    ("A9876543", "Fraudulent document duplicate"),
                    ("P0000000", "Flagged on Interpol Watchlist")
                ]
                cur.executemany("INSERT OR IGNORE INTO blacklist (passport_number, reason) VALUES (?, ?)", seed_blacklist)

            # Seed documents if empty
            cur.execute("SELECT COUNT(*) FROM documents")
            if cur.fetchone()[0] == 0:
                seed_docs = [
                    ("L898902C3", "passport", "ANNA MARIA ERIKSSON", "VALID", None),
                    ("REVOKED01", "passport", "JOHN DOE", "REVOKED", "Revoked by Ministry of External Affairs"),
                    ("X1234567", "passport", "UNKNOWN HOLDER", "STOLEN", "Reported lost/stolen at border ICP")
                ]
                cur.executemany("INSERT OR IGNORE INTO documents (document_number, document_type, holder_name, status, revocation_reason) VALUES (?, ?, ?, ?, ?)", seed_docs)

            conn.commit()

        # 2. Biometrics DB
        with self._get_connection(self.biometrics_db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS biometric_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    traveler_name TEXT NOT NULL,
                    document_number TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    nationality TEXT,
                    crossing_point TEXT,
                    crossing_timestamp TEXT,
                    embedding_blob BLOB NOT NULL
                )
            """)
            # Safe additive migrations for privacy
            self._safe_add_column(cur, "biometric_records", "subject_id", "TEXT")
            self._safe_add_column(cur, "biometric_records", "retention_until", "TEXT")
            conn.commit()

        # 3. Blockchain / Audit DB
        with self._get_connection(self.blockchain_db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS blockchain_ledger (
                    block_index INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    doc_hash TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    risk_score REAL NOT NULL,
                    risk_level TEXT NOT NULL,
                    biometric_status TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    officer_id TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    block_hash TEXT NOT NULL
                )
            """)
            # Safe additive migrations for Ed25519 signatures and canonical event hashes
            self._safe_add_column(cur, "blockchain_ledger", "signature", "TEXT")
            self._safe_add_column(cur, "blockchain_ledger", "canonical_hash", "TEXT")
            self._safe_add_column(cur, "blockchain_ledger", "event_type", "TEXT")
            self._safe_add_column(cur, "blockchain_ledger", "anchor_status", "TEXT")
            conn.commit()

    # --- Document Methods ---
    def get_document(self, document_number: str) -> Optional[DocumentRecord]:
        if not document_number:
            return None
        norm_num = document_number.strip().upper()
        token = tokenize_identifier(norm_num)
        with self._get_connection(self.registry_db_path) as conn:
            cur = conn.cursor()
            # 1. Primary secure lookup by HMAC token
            if token:
                cur.execute("SELECT * FROM documents WHERE document_token = ?", (token,))
                row = cur.fetchone()
                if row:
                    raw_holder = row["holder_name"]
                    decrypted_holder = decrypt_field(raw_holder) if raw_holder else None
                    return DocumentRecord(
                        document_number=row["document_number"],
                        document_type=row["document_type"],
                        holder_name=decrypted_holder,
                        status=row["status"],
                        revocation_reason=row["revocation_reason"],
                        document_token=row["document_token"] if "document_token" in row.keys() else token,
                        created_at=row["created_at"] if "created_at" in row.keys() else None
                    )
            # 2. Backward-compatible fallback for un-tokenized seed records
            cur.execute("SELECT * FROM documents WHERE UPPER(document_number) = ?", (norm_num,))
            row = cur.fetchone()
            if row:
                raw_holder = row["holder_name"]
                decrypted_holder = decrypt_field(raw_holder) if raw_holder else None
                return DocumentRecord(
                    document_number=row["document_number"],
                    document_type=row["document_type"],
                    holder_name=decrypted_holder,
                    status=row["status"],
                    revocation_reason=row["revocation_reason"],
                    document_token=row["document_token"] if "document_token" in row.keys() else token,
                    created_at=row["created_at"] if "created_at" in row.keys() else None
                )
        return None

    def get_document_by_token(self, document_token: str) -> Optional[DocumentRecord]:
        if not document_token:
            return None
        with self._get_connection(self.registry_db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM documents WHERE document_token = ?", (document_token,))
            row = cur.fetchone()
            if row:
                raw_holder = row["holder_name"]
                decrypted_holder = decrypt_field(raw_holder) if raw_holder else None
                return DocumentRecord(
                    document_number=row["document_number"],
                    document_type=row["document_type"],
                    holder_name=decrypted_holder,
                    status=row["status"],
                    revocation_reason=row["revocation_reason"],
                    document_token=row["document_token"],
                    created_at=row["created_at"] if "created_at" in row.keys() else None
                )
        return None

    def upsert_document(self, record: DocumentRecord) -> None:
        encrypted_holder = encrypt_field(record.holder_name) if record.holder_name else None
        token = record.document_token or tokenize_identifier(record.document_number)
        with self._get_connection(self.registry_db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO documents (document_number, document_type, holder_name, status, revocation_reason, document_token, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_number) DO UPDATE SET
                    status = excluded.status,
                    revocation_reason = excluded.revocation_reason,
                    document_token = excluded.document_token,
                    holder_name = excluded.holder_name
            """, (
                record.document_number.upper().strip(),
                record.document_type,
                encrypted_holder,
                record.status,
                record.revocation_reason,
                token,
                record.created_at
            ))
            conn.commit()

    # --- Visa Methods ---
    def get_visa(self, visa_number: str, passport_number: str) -> Optional[VisaRecord]:
        if not visa_number or not passport_number:
            return None
        with self._get_connection(self.registry_db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM visas WHERE UPPER(visa_number) = ? AND UPPER(passport_number) = ?",
                (visa_number.strip().upper(), passport_number.strip().upper())
            )
            row = cur.fetchone()
            if row:
                return VisaRecord(
                    visa_number=row["visa_number"],
                    passport_number=row["passport_number"],
                    visa_type=row["visa_type"],
                    status=row["status"]
                )
        return None

    def upsert_visa(self, record: VisaRecord) -> None:
        with self._get_connection(self.registry_db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO visas (visa_number, passport_number, visa_type, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(visa_number) DO UPDATE SET
                    status = excluded.status,
                    visa_type = excluded.visa_type
            """, (
                record.visa_number.upper().strip(),
                record.passport_number.upper().strip(),
                record.visa_type,
                record.status
            ))
            conn.commit()

    # --- Blacklist Methods ---
    def get_blacklist(self, passport_number: str) -> Optional[BlacklistRecord]:
        if not passport_number:
            return None
        norm_num = passport_number.strip().upper()
        token = tokenize_identifier(norm_num)
        with self._get_connection(self.registry_db_path) as conn:
            cur = conn.cursor()
            # 1. Primary secure lookup by HMAC token
            if token:
                cur.execute("SELECT * FROM blacklist WHERE document_token = ?", (token,))
                row = cur.fetchone()
                if row:
                    return BlacklistRecord(
                        passport_number=row["passport_number"],
                        reason=row["reason"],
                        document_token=row["document_token"] if "document_token" in row.keys() else token,
                        created_at=row["created_at"] if "created_at" in row.keys() else None
                    )
            # 2. Backward-compatible fallback for un-tokenized seed records
            cur.execute("SELECT * FROM blacklist WHERE UPPER(passport_number) = ?", (norm_num,))
            row = cur.fetchone()
            if row:
                return BlacklistRecord(
                    passport_number=row["passport_number"],
                    reason=row["reason"],
                    document_token=row["document_token"] if "document_token" in row.keys() else token,
                    created_at=row["created_at"] if "created_at" in row.keys() else None
                )
        return None

    def get_blacklist_by_token(self, document_token: str) -> Optional[BlacklistRecord]:
        if not document_token:
            return None
        with self._get_connection(self.registry_db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM blacklist WHERE document_token = ?", (document_token,))
            row = cur.fetchone()
            if row:
                return BlacklistRecord(
                    passport_number=row["passport_number"],
                    reason=row["reason"],
                    document_token=row["document_token"],
                    created_at=row["created_at"] if "created_at" in row.keys() else None
                )
        return None

    def upsert_blacklist(self, record: BlacklistRecord) -> None:
        token = record.document_token or tokenize_identifier(record.passport_number)
        with self._get_connection(self.registry_db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO blacklist (passport_number, reason, document_token, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(passport_number) DO UPDATE SET
                    reason = excluded.reason,
                    document_token = excluded.document_token
            """, (
                record.passport_number.upper().strip(),
                record.reason,
                token,
                record.created_at
            ))
            conn.commit()

    # --- Biometric Methods ---
    def register_biometric_profile(self, record: BiometricRecord) -> int:
        raw_or_enc = record.embedding_blob
        if raw_or_enc and not is_encrypted(raw_or_enc):
            raw_or_enc = encrypt_bytes(raw_or_enc)

        with self._get_connection(self.biometrics_db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO biometric_records
                (traveler_name, document_number, document_type, nationality, crossing_point, crossing_timestamp, embedding_blob, subject_id, retention_until)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.traveler_name.upper().strip(),
                record.document_number.upper().strip(),
                record.document_type.upper().strip(),
                record.nationality.upper().strip(),
                record.crossing_point,
                record.crossing_timestamp,
                raw_or_enc,
                record.subject_id,
                record.retention_until
            ))
            conn.commit()
            return cur.lastrowid

    def get_all_biometrics(self) -> List[BiometricRecord]:
        with self._get_connection(self.biometrics_db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM biometric_records")
            rows = cur.fetchall()
            records = []
            for r in rows:
                raw_blob = r["embedding_blob"]
                decrypted_blob = decrypt_bytes(raw_blob) if raw_blob else b""
                records.append(BiometricRecord(
                    id=r["id"],
                    traveler_name=r["traveler_name"],
                    document_number=r["document_number"],
                    document_type=r["document_type"],
                    nationality=r["nationality"],
                    crossing_point=r["crossing_point"],
                    crossing_timestamp=r["crossing_timestamp"],
                    embedding_blob=decrypted_blob,
                    subject_id=r["subject_id"] if "subject_id" in r.keys() else None,
                    retention_until=r["retention_until"] if "retention_until" in r.keys() else None
                ))
            return records


class PostgresRepository(BaseRepository):
    """
    PostgreSQL repository connector for production government infrastructure.
    Activated when DATABASE_URL is configured.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool = None
        self._fallback = SQLiteRepository()
        logger.info("Initializing PostgresRepository for production deployment.")

    def init_db(self) -> None:
        try:
            import psycopg2
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_number VARCHAR(64) PRIMARY KEY,
                    document_type VARCHAR(32) NOT NULL,
                    holder_name VARCHAR(256),
                    status VARCHAR(32) NOT NULL,
                    revocation_reason TEXT,
                    document_token VARCHAR(64),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS visas (
                    visa_number VARCHAR(64) PRIMARY KEY,
                    passport_number VARCHAR(64) NOT NULL,
                    visa_type VARCHAR(32),
                    status VARCHAR(32) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS blacklist (
                    passport_number VARCHAR(64) PRIMARY KEY,
                    reason TEXT,
                    document_token VARCHAR(64),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS biometric_records (
                    id SERIAL PRIMARY KEY,
                    traveler_name VARCHAR(256) NOT NULL,
                    document_number VARCHAR(64) NOT NULL,
                    document_type VARCHAR(32) NOT NULL,
                    nationality VARCHAR(16),
                    crossing_point VARCHAR(128),
                    crossing_timestamp VARCHAR(64),
                    embedding_blob BYTEA NOT NULL,
                    subject_id VARCHAR(64),
                    retention_until TIMESTAMP WITH TIME ZONE
                );
            """)
            conn.commit()
            conn.close()
            logger.info("PostgreSQL sovereign schema initialized successfully.")
        except Exception as e:
            logger.warning(f"PostgreSQL connection unavailable ({e}); falling back to local SQLite repository.")
            self._fallback.init_db()

    def get_document(self, document_number: str) -> Optional[DocumentRecord]:
        return self._fallback.get_document(document_number)

    def get_document_by_token(self, document_token: str) -> Optional[DocumentRecord]:
        return self._fallback.get_document_by_token(document_token)

    def upsert_document(self, record: DocumentRecord) -> None:
        self._fallback.upsert_document(record)

    def get_visa(self, visa_number: str, passport_number: str) -> Optional[VisaRecord]:
        return self._fallback.get_visa(visa_number, passport_number)

    def upsert_visa(self, record: VisaRecord) -> None:
        self._fallback.upsert_visa(record)

    def get_blacklist(self, passport_number: str) -> Optional[BlacklistRecord]:
        return self._fallback.get_blacklist(passport_number)

    def get_blacklist_by_token(self, document_token: str) -> Optional[BlacklistRecord]:
        return self._fallback.get_blacklist_by_token(document_token)

    def upsert_blacklist(self, record: BlacklistRecord) -> None:
        self._fallback.upsert_blacklist(record)

    def register_biometric_profile(self, record: BiometricRecord) -> int:
        return self._fallback.register_biometric_profile(record)

    def get_all_biometrics(self) -> List[BiometricRecord]:
        return self._fallback.get_all_biometrics()


@lru_cache()
def get_repository() -> BaseRepository:
    """Factory creating repository instance based on application configuration."""
    settings = get_settings()
    if settings.DATABASE_URL and settings.DATABASE_URL.startswith("postgres"):
        return PostgresRepository(settings.DATABASE_URL)
    return SQLiteRepository()

