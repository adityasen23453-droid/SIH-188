import os
import io
import hashlib
import cv2
import numpy as np
from dataclasses import dataclass, field


@dataclass
class DocumentContext:
    """
    Unified In-Memory Document Context (Phase 3):
    Decodes once, resizes once, deskews once, and provides pre-sliced reusable ROIs
    for MRZ, VIZ, Face, and Tampering forensics without duplicate I/O or resizing.
    """
    file_path: str
    doc_hash: str
    original_bgr: np.ndarray
    deskewed_bgr: np.ndarray
    clahe_bgr: np.ndarray
    clahe_gray: np.ndarray
    mrz_roi: np.ndarray
    viz_roi: np.ndarray
    face_roi: np.ndarray | None = None
    face_bbox: list[int] | None = None
    face_image_path: str | None = None
    face_image_url: str | None = None
    correction_applied: bool = False
    document_quad: list[list[float]] | None = None
    processed_image_path: str = ""
    note: str = ""


def order_points(pts: np.ndarray) -> np.ndarray:
    """Orders 4 points of a quadrilateral: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Applies a perspective transform to flatten/deskew a 4-point ROI to a top-down view."""
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    max_width = max(int(width_a), int(width_b), 100)

    height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    max_height = max(int(height_a), int(height_b), 100)

    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1]
    ], dtype="float32")

    transform_matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, transform_matrix, (max_width, max_height))


def apply_clahe(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Applies CLAHE on LAB color space L-channel. Returns (clahe_bgr, clahe_gray)."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    clahe_bgr = cv2.cvtColor(cv2.merge((cl, a, b)), cv2.COLOR_LAB2BGR)
    clahe_gray = cl
    return clahe_bgr, clahe_gray


def detect_and_fix_orientation(image: np.ndarray) -> tuple[np.ndarray, int]:
    """
    Robust 4-Way Multi-Angle Document Orientation Engine:
    1. ICAO MRZ Spatial Position Prior: In ICAO 9303 passports and visas, MRZ lines (P<, V<, <<)
       are strictly anchored at the bottom 30% of the document. If MRZ tokens appear
       in the top 35%, the document is 180° inverted; automatically rotate 180° upright.
    2. Multi-Angle Frontal Face Verification: Evaluates 0°, 90°, 180°, 270° with Haar Cascade.
       If an upright frontal face is detected in 90°, 180°, or 270° while 0° has no face, rotate upright.
    3. Tesseract OSD (Fast-path if sufficient text confidence).
    """
    if image is None:
        return image, 0

    h, w = image.shape[:2]

    # Heuristic 1: Fast Multi-Angle Face Detection (0°, 90°, 180°, 270°) with multi-face aggregate weighting
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        thumb_scale = 500.0 / max(h, w) if max(h, w) > 500 else 1.0
        thumb = cv2.resize(image, (int(w * thumb_scale), int(h * thumb_scale)), interpolation=cv2.INTER_AREA)
        gray_thumb = cv2.cvtColor(thumb, cv2.COLOR_BGR2GRAY)

        def get_face_score(g_img):
            faces = face_cascade.detectMultiScale(g_img, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))
            if len(faces) == 0:
                return 0, 0
            total_area = sum(f[2] * f[3] for f in faces)
            return len(faces) * 2000 + total_area, len(faces)

        score0, cnt0 = get_face_score(gray_thumb)
        # Fast path early exit: If face is detected upright at 0° with good confidence, exit in < 15ms!
        if cnt0 > 0 and score0 > 3000:
            return image, 0

        score90, cnt90 = get_face_score(cv2.rotate(gray_thumb, cv2.ROTATE_90_CLOCKWISE))
        score180, cnt180 = get_face_score(cv2.rotate(gray_thumb, cv2.ROTATE_180))
        score270, cnt270 = get_face_score(cv2.rotate(gray_thumb, cv2.ROTATE_90_COUNTERCLOCKWISE))

        face_scores = {0: score0, 90: score90, 180: score180, 270: score270}
        best_rot = max(face_scores, key=face_scores.get)

        if best_rot != 0 and face_scores[best_rot] > score0 * 1.3 and face_scores[best_rot] > 2500:
            if best_rot == 90:
                return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE), 90
            elif best_rot == 180:
                return cv2.rotate(image, cv2.ROTATE_180), 180
            elif best_rot == 270:
                return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE), 270
        elif cnt0 > 0:
            return image, 0
    except Exception:
        pass

    # Heuristic 2: ICAO MRZ Inversion Check (Controlled fallback when face detection had no signal)
    try:
        import pytesseract
        tesseract_bin = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(tesseract_bin):
            pytesseract.pytesseract.tesseract_cmd = tesseract_bin

        top_strip = image[0:int(h * 0.35), 0:w]
        top_scale = 500.0 / w if w > 500 else 1.0
        if top_scale < 1.0:
            top_strip = cv2.resize(top_strip, (int(w * top_scale), int(h * 0.35 * top_scale)), interpolation=cv2.INTER_AREA)
        top_gray = cv2.cvtColor(top_strip, cv2.COLOR_BGR2GRAY)
        top_text = pytesseract.image_to_string(top_gray, config="--psm 6")
        if "<<" in top_text or "P<" in top_text or "V<" in top_text or "I<" in top_text or "C<" in top_text:
            return cv2.rotate(image, cv2.ROTATE_180), 180
    except Exception:
        pass

    # Heuristic 3: Tesseract OSD fallback (only if OSD confidence is high >= 2.0)
    try:
        from PIL import Image
        rgb_thumb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_thumb)
        osd = pytesseract.image_to_osd(pil_img, output_type=pytesseract.Output.DICT)
        rotate_angle = osd.get("rotate", 0)
        conf = float(osd.get("orientation_conf", 0.0))

        if conf >= 2.0:
            if rotate_angle == 90:
                return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE), 90
            elif rotate_angle == 180:
                return cv2.rotate(image, cv2.ROTATE_180), 180
            elif rotate_angle == 270:
                return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE), 270
    except Exception:
        pass

    return image, 0


def find_document_contour(image: np.ndarray) -> np.ndarray | None:
    """Finds the largest 4-sided convex contour covering >= 35% of the image with valid ID aspect ratio."""
    orig_h, orig_w = image.shape[:2]
    target_h = 800
    scale = float(target_h) / float(orig_h)
    target_w = int(orig_w * scale)

    resized = cv2.resize(image, (target_w, target_h), interpolation=cv2.INTER_AREA)
    total_area = target_h * target_w

    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    canny = cv2.Canny(blur, 30, 150)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(canny, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    for c in contours:
        area = cv2.contourArea(c)
        if area < total_area * 0.35:
            break
        peri = cv2.arcLength(c, True)
        for eps_ratio in [0.01, 0.02, 0.03, 0.04, 0.05]:
            approx = cv2.approxPolyDP(c, eps_ratio * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                _, _, w, h = cv2.boundingRect(approx)
                if h > 0 and w > 0:
                    aspect = float(w) / float(h)
                    if 0.55 <= aspect <= 1.85:
                        return (approx.reshape(4, 2) / scale).astype("float32")

    return None



def extract_face_from_bgr(image: np.ndarray, output_dir: str, base_name: str) -> tuple[np.ndarray | None, list[int] | None, str | None, str | None]:
    """Extracts frontal face ROI from BGR image, saves to disk, and returns metadata."""
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))

        if len(faces) == 0:
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=2, minSize=(40, 40))

        if len(faces) == 0:
            return None, None, None, None

        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, w, h = faces[0]

        img_h, img_w = image.shape[:2]
        pad_x = int(w * 0.20)
        pad_y = int(h * 0.25)
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(img_w, x + w + pad_x)
        y2 = min(img_h, y + h + pad_y)

        face_crop = image[y1:y2, x1:x2]
        os.makedirs(output_dir, exist_ok=True)
        face_filename = f"{base_name}_face.jpg"
        face_path = os.path.join(output_dir, face_filename)
        cv2.imwrite(face_path, face_crop)
        return face_crop, [int(x), int(y), int(w), int(h)], face_path, f"/doc-faces/{face_filename}"
    except Exception:
        return None, None, None, None


def create_document_context(image_path: str, max_dim: int = 1200) -> DocumentContext:
    """
    Creates a unified DocumentContext:
    1. Reads and decodes image once.
    2. Computes SHA-256 document fingerprint once.
    3. Resizes to max_dim (1200px) once.
    4. Computes 4-point perspective warp and CLAHE once.
    5. Pre-slices MRZ (bottom 28%), VIZ (top 72%), and auto-crops Face ROI.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    # 1. SHA-256 fingerprint
    hasher = hashlib.sha256()
    with open(image_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    doc_hash = hasher.hexdigest()

    # 2. Decode image
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not decode image at {image_path}")

    # 2a. Scale image immediately if > max_dim so orientation and contour operators run in sub-second time
    orig_h, orig_w = img.shape[:2]
    curr_max = max(orig_h, orig_w)
    if curr_max > max_dim:
        scale = max_dim / float(curr_max)
        img = cv2.resize(img, (int(orig_w * scale), int(orig_h * scale)), interpolation=cv2.INTER_AREA)

    # 2b. Auto-Orientation detection & correction (now runs on scaled image!)
    img, rot_angle = detect_and_fix_orientation(img)
    rot_applied = (rot_angle != 0)
    rot_note = f"Auto-orientation corrected ({rot_angle}° rotation applied); " if rot_applied else ""

    # 4. Deskew
    pts = find_document_contour(img)
    correction_applied = rot_applied
    note = rot_note + ("Perspective correction and contrast enhancement applied" if pts is not None else "Standard contrast enhancement applied")

    if pts is not None:
        warped = four_point_transform(img, pts)
        w_h, w_w = warped.shape[:2]
        if w_h >= orig_h * 0.35 and w_w >= orig_w * 0.35:
            if max(w_h, w_w) > max_dim:
                w_scale = max_dim / float(max(w_h, w_w))
                warped = cv2.resize(warped, (int(w_w * w_scale), int(w_h * w_scale)), interpolation=cv2.INTER_AREA)
            deskewed = warped
            correction_applied = True
        else:
            deskewed = img
    else:
        deskewed = img

    # Cap maximum dimension so high-resolution uploads (e.g. 8MB+ images) run in sub-second time
    d_h, d_w = deskewed.shape[:2]
    if max(d_h, d_w) > max_dim:
        d_scale = max_dim / float(max(d_h, d_w))
        deskewed = cv2.resize(deskewed, (int(d_w * d_scale), int(d_h * d_scale)), interpolation=cv2.INTER_AREA)

    # 5. CLAHE
    clahe_bgr, clahe_gray = apply_clahe(deskewed)

    # 6. Sliced ROIs
    d_h, d_w = deskewed.shape[:2]
    mrz_roi = deskewed[int(d_h * 0.70):d_h, 0:d_w]
    viz_roi = deskewed[0:int(d_h * 0.72), 0:d_w]

    # 7. Save preprocessed image for UI
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    prep_dir = os.path.join(backend_dir, "uploads", "preprocessed")
    faces_dir = os.path.join(backend_dir, "uploads", "faces")
    os.makedirs(prep_dir, exist_ok=True)
    os.makedirs(faces_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(image_path))[0]
    processed_path = os.path.join(prep_dir, f"{base_name}_processed.jpg")
    cv2.imwrite(processed_path, clahe_bgr)

    # 8. Face ROI
    face_roi, face_bbox, face_path, face_url = extract_face_from_bgr(deskewed, faces_dir, base_name)

    return DocumentContext(
        file_path=image_path,
        doc_hash=doc_hash,
        original_bgr=img,
        deskewed_bgr=deskewed,
        clahe_bgr=clahe_bgr,
        clahe_gray=clahe_gray,
        mrz_roi=mrz_roi,
        viz_roi=viz_roi,
        face_roi=face_roi,
        face_bbox=face_bbox,
        face_image_path=face_path,
        face_image_url=face_url,
        correction_applied=correction_applied,
        document_quad=pts.tolist() if pts is not None else None,
        processed_image_path=processed_path,
        note=note
    )


def detect_and_correct_document(image_path: str, output_dir: str = None) -> dict:
    """Backwards-compatible wrapper returning dictionary format."""
    try:
        ctx = create_document_context(image_path)
        return {
            "processed_image_path": ctx.processed_image_path,
            "correction_applied": ctx.correction_applied,
            "note": ctx.note
        }
    except Exception as e:
        return {
            "processed_image_path": image_path,
            "correction_applied": False,
            "note": f"Preprocessing error: {str(e)}",
            "error": str(e)
        }
