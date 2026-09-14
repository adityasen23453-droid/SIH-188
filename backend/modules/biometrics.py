import os
import cv2
import torch
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
import sqlite3
from datetime import datetime

# Global model cache
_face_extractor = None
_face_cascade = None


def get_face_cascade():
    global _face_cascade
    if _face_cascade is None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _face_cascade = cv2.CascadeClassifier(cascade_path)
    return _face_cascade


def get_face_extractor():
    """
    Initializes a lightweight, high-performance deep CNN feature extractor (MobileNetV3-Small)
    producing 576-dimensional L2-normalized face embedding vectors.
    """
    global _face_extractor
    if _face_extractor is None:
        model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
        # Remove classifier head to get pooled convolutional features
        model.classifier = torch.nn.Identity()
        model.eval()
        _face_extractor = model
    return _face_extractor


def crop_face_roi(image: np.ndarray, margin: float = 0.25) -> np.ndarray | None:
    """
    Detects the primary frontal face in an image and crops it with a contextual margin.
    Returns cropped BGR image or None if no face detected.
    """
    if image is None or image.size == 0:
        return None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cascade = get_face_cascade()
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))

    if len(faces) == 0:
        # Fallback: try with lower minNeighbors
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=2, minSize=(30, 30))

    if len(faces) == 0:
        return None

    # Pick largest face
    faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
    x, y, w, h = faces[0]

    # Add margin
    h_img, w_img = image.shape[:2]
    mx = int(w * margin)
    my = int(h * margin)

    x1 = max(0, x - mx)
    y1 = max(0, y - my)
    x2 = min(w_img, x + w + mx)
    y2 = min(h_img, y + h + my)

    return image[y1:y2, x1:x2]


def extract_face_embedding(face_img: np.ndarray) -> np.ndarray | None:
    """
    Extracts a 576-dimensional L2-normalized embedding vector from a cropped face image.
    """
    if face_img is None or face_img.size == 0:
        return None

    try:
        model = get_face_extractor()
        rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        tensor = transform(pil_img).unsqueeze(0)

        with torch.no_grad():
            feat = model(tensor)  # Shape: (1, 576, 1, 1) or (1, 576)
            feat = feat.view(feat.size(0), -1).numpy().squeeze()

        # L2-normalize vector
        norm = np.linalg.norm(feat)
        if norm > 1e-6:
            feat = feat / norm
        return feat
    except Exception as e:
        print(f"[Biometrics] Embedding extraction error: {e}")
        return None


def compute_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Computes cosine similarity between two unit vectors.
    Range: [-1.0, 1.0]. Clipped to [0.0, 1.0] for biometric scoring.
    """
    if vec1 is None or vec2 is None:
        return 0.0
    dot = float(np.dot(vec1, vec2))
    return float(np.clip(dot, 0.0, 1.0))


def estimate_liveness_score(face_bgr: np.ndarray) -> dict:
    """
    Evaluates basic physical liveness heuristics:
    1. Focus/Sharpness via Laplacian variance (detects screen/paper moiré or extreme blur).
    2. Color naturalness (detects monochrome paper photocopy).
    """
    if face_bgr is None or face_bgr.size == 0:
        return {"liveness_score": 0.0, "is_live": False, "reason": "No face provided"}

    # Sharpness
    gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Color saturation check (monochrome photocopy detection)
    hsv = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2HSV)
    mean_sat = float(np.mean(hsv[:, :, 1]))

    is_sharp = laplacian_var > 35.0
    is_colored = mean_sat > 15.0

    score = 100.0
    issues = []
    if not is_sharp:
        score -= 40.0
        issues.append("Low image sharpness / potential blur or print scan")
    if not is_colored:
        score -= 50.0
        issues.append("Low color saturation / potential black-and-white photocopy")

    score = max(0.0, min(100.0, score))
    return {
        "liveness_score": round(score, 1),
        "laplacian_variance": round(laplacian_var, 1),
        "mean_saturation": round(mean_sat, 1),
        "is_live": score >= 50.0,
        "issues": issues
    }


# =====================================================================
# 1:N CROSS-BORDER VECTOR DATABASE & ALIAS DETECTION
# =====================================================================

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "biometrics.db")


def init_biometric_db():
    """Initializes the SQLite biometric vector registry and seeds mock historical crossings."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
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
        conn.commit()

        # Seed realistic border crossing records if table is empty
        cursor.execute("SELECT COUNT(*) FROM biometric_records")
        if cursor.fetchone()[0] == 0:
            seed_mock_biometric_records(conn)


def seed_mock_biometric_records(conn):
    """
    Seeds historical crossings so 1:N duplicate identity detection can be demonstrated.
    """
    cursor = conn.cursor()
    # Generate reproducible synthetic embeddings for known test profiles
    np.random.seed(42)
    sample_emb_1 = np.random.randn(576).astype(np.float32)
    sample_emb_1 /= np.linalg.norm(sample_emb_1)

    np.random.seed(1337)
    sample_emb_2 = np.random.randn(576).astype(np.float32)
    sample_emb_2 /= np.linalg.norm(sample_emb_2)

    records = [
        ("RAMESH SHARMA", "M1234567", "PASSPORT", "IND", "Raxaul Checkpost (Nepal Border)", "2026-08-12 14:30:00", sample_emb_1.tobytes()),
        ("TASHI DORJEE", "BT882910", "PASSPORT", "BTN", "Jaigaon Checkpost (Bhutan Border)", "2026-07-04 09:15:00", sample_emb_2.tobytes())
    ]
    cursor.executemany("""
        INSERT INTO biometric_records
        (traveler_name, document_number, document_type, nationality, crossing_point, crossing_timestamp, embedding_blob)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, records)
    conn.commit()


# Initialize database at module load
init_biometric_db()


def register_biometric_profile(
    name: str,
    doc_number: str,
    doc_type: str,
    nationality: str,
    crossing_point: str,
    embedding: np.ndarray
) -> int:
    """Registers a traveler's biometric face embedding in the border database."""
    if embedding is None:
        return -1
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO biometric_records
            (traveler_name, document_number, document_type, nationality, crossing_point, crossing_timestamp, embedding_blob)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            name.upper().strip(),
            doc_number.upper().strip(),
            doc_type.upper().strip(),
            nationality.upper().strip(),
            crossing_point,
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            embedding.astype(np.float32).tobytes()
        ))
        conn.commit()
        return cursor.lastrowid


def search_alias_identities(
    query_embedding: np.ndarray,
    current_name: str,
    current_doc_num: str,
    threshold: float = 0.82
) -> dict:
    """
    1:N Search across border records:
    Detects if the exact same face has previously appeared under a DIFFERENT name or passport number!
    Satisfies SIH PS 26188: 'Multiple identities used by the same person'.
    """
    if query_embedding is None:
        return {"alias_detected": False, "matches": []}

    current_name_clean = (current_name or "").strip().upper()
    current_doc_clean = (current_doc_num or "").strip().upper()

    matches = []
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, traveler_name, document_number, document_type, nationality, crossing_point, crossing_timestamp, embedding_blob
            FROM biometric_records
        """)
        rows = cursor.fetchall()

        for row in rows:
            rec_id, rec_name, rec_doc, rec_type, rec_nat, rec_point, rec_time, emb_blob = row
            stored_emb = np.frombuffer(emb_blob, dtype=np.float32)
            if stored_emb.shape[0] != query_embedding.shape[0]:
                continue

            sim = compute_cosine_similarity(query_embedding, stored_emb)
            if sim >= threshold:
                # Check if identity is different (Name mismatch OR Document mismatch)
                is_different_person = (
                    (current_name_clean and rec_name and current_name_clean != rec_name) or
                    (current_doc_clean and rec_doc and current_doc_clean != rec_doc)
                )

                matches.append({
                    "record_id": rec_id,
                    "previous_name": rec_name,
                    "previous_document_number": rec_doc,
                    "document_type": rec_type,
                    "nationality": rec_nat,
                    "crossing_point": rec_point,
                    "crossing_timestamp": rec_time,
                    "similarity": round(sim, 4),
                    "is_different_identity": is_different_person
                })

    # Sort by highest similarity
    matches.sort(key=lambda m: m["similarity"], reverse=True)
    alias_flag = any(m["is_different_identity"] for m in matches)

    return {
        "alias_detected": alias_flag,
        "match_count": len(matches),
        "top_match": matches[0] if matches else None,
        "all_matches": matches
    }


def verify_face_1to1_and_1toN(
    doc_face_path: str,
    live_face_path_or_bytes: str | bytes,
    traveler_name: str = "",
    doc_number: str = "",
    doc_type: str = "PASSPORT",
    nationality: str = ""
) -> dict:
    """
    Performs complete end-to-end biometric verification:
    1. Loads Document Portrait face and Live Checkpoint camera face.
    2. Crops & normalizes face ROIs.
    3. Evaluates liveness heuristics.
    4. Extracts 576-D deep embeddings.
    5. Computes 1:1 Cosine Similarity.
    6. Runs 1:N Alias search against the historical border crossing database.
    """
    # 1. Load document face
    doc_face_bgr = None
    if os.path.exists(doc_face_path):
        doc_face_bgr = cv2.imread(doc_face_path)

    if doc_face_bgr is None:
        return {
            "verified": False,
            "status": "DOC_FACE_NOT_FOUND",
            "message": "Document portrait face could not be loaded or detected.",
            "similarity": 0.0,
            "liveness": {"is_live": False, "liveness_score": 0.0},
            "alias_check": {"alias_detected": False}
        }

    # 2. Load live face
    live_bgr = None
    if isinstance(live_face_path_or_bytes, bytes):
        nparr = np.frombuffer(live_face_path_or_bytes, np.uint8)
        live_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif isinstance(live_face_path_or_bytes, str) and os.path.exists(live_face_path_or_bytes):
        live_bgr = cv2.imread(live_face_path_or_bytes)

    if live_bgr is None:
        return {
            "verified": False,
            "status": "LIVE_FACE_NOT_FOUND",
            "message": "Live camera capture could not be decoded or loaded.",
            "similarity": 0.0,
            "liveness": {"is_live": False, "liveness_score": 0.0},
            "alias_check": {"alias_detected": False}
        }

    # Crop live face ROI if not pre-cropped
    live_cropped = crop_face_roi(live_bgr)
    if live_cropped is None:
        # Fallback to whole frame if cascade fails on webcam
        live_cropped = live_bgr

    # Crop doc face ROI if needed
    doc_cropped = crop_face_roi(doc_face_bgr)
    if doc_cropped is None:
        doc_cropped = doc_face_bgr

    # 3. Liveness check on live camera face
    liveness_info = estimate_liveness_score(live_cropped)

    # 4. Extract embeddings
    doc_emb = extract_face_embedding(doc_cropped)
    live_emb = extract_face_embedding(live_cropped)

    if doc_emb is None or live_emb is None:
        return {
            "verified": False,
            "status": "EMBEDDING_FAILED",
            "message": "Failed to extract neural face embeddings.",
            "similarity": 0.0,
            "liveness": liveness_info,
            "alias_check": {"alias_detected": False}
        }

    # 5. 1:1 Cosine Similarity
    similarity = compute_cosine_similarity(doc_emb, live_emb)

    # Biometric match thresholds:
    # >= 0.70: Confident match
    # 0.55 - 0.70: Borderline match
    # < 0.55: Mismatch (impersonation)
    if similarity >= 0.70:
        match_status = "MATCH"
        verdict_text = "Verified Traveler: Document face matches live checkpoint biometric capture."
        is_verified = True
    elif similarity >= 0.55:
        match_status = "BORDERLINE"
        verdict_text = "Borderline Match: Facial features show partial correspondence. Secondary physical inspection advised."
        is_verified = True
    else:
        match_status = "MISMATCH"
        verdict_text = "CRITICAL ALERT: Biometric mismatch. The person presenting the document does not match the portrait."
        is_verified = False

    # 6. 1:N Alias search against border crossing registry
    alias_res = search_alias_identities(live_emb, traveler_name, doc_number)

    # If alias detected, elevate alert
    if alias_res.get("alias_detected"):
        match_status = "DUPLICATE_ALIAS_ALERT"
        top = alias_res.get("top_match", {})
        verdict_text = (
            f"CRITICAL FRAUD ALERT: Duplicate Identity / Alias Detected! "
            f"This face matches traveler '{top.get('previous_name')}' (Doc: {top.get('previous_document_number')}) "
            f"screened at {top.get('crossing_point')} on {top.get('crossing_timestamp')}."
        )
        is_verified = False

    return {
        "verified": is_verified,
        "status": match_status,
        "similarity": round(similarity, 4),
        "similarity_percentage": round(similarity * 100.0, 1),
        "verdict": verdict_text,
        "liveness": liveness_info,
        "alias_check": alias_res
    }

