import os
import cv2
import numpy as np


def order_points(pts: np.ndarray) -> np.ndarray:
    """
    Orders 4 points of a quadrilateral in the order: top-left, top-right, bottom-right, bottom-left.
    """
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """
    Applies a perspective transform to flatten/deskew a 4-point ROI to a top-down view.
    """
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    max_width = max(int(width_a), int(width_b))

    height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    max_height = max(int(height_a), int(height_b))

    # Ensure minimum valid dimensions
    max_width = max(max_width, 100)
    max_height = max(max_height, 100)

    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1]
    ], dtype="float32")

    transform_matrix = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, transform_matrix, (max_width, max_height))
    return warped


def apply_clahe(image: np.ndarray) -> np.ndarray:
    """
    Applies Contrast Limited Adaptive Histogram Equalization (CLAHE) on LAB color space L-channel.
    """
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    limg = cv2.merge((cl, a, b))
    return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)


def find_document_contour(image: np.ndarray) -> np.ndarray:
    """
    Finds the largest 4-sided convex contour covering a meaningful portion of the image.
    Rescales high-resolution images for robust edge detection and morphological closing.
    """
    orig_h, orig_w = image.shape[:2]
    target_h = 1000
    scale = float(target_h) / float(orig_h)
    target_w = int(orig_w * scale)

    resized = cv2.resize(image, (target_w, target_h))
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
        if area < total_area * 0.10:
            break

        peri = cv2.arcLength(c, True)

        for eps_ratio in [0.01, 0.02, 0.03, 0.04, 0.05]:
            approx = cv2.approxPolyDP(c, eps_ratio * peri, True)
            if len(approx) == 4:
                pts_scaled = (approx.reshape(4, 2) / scale).astype("float32")
                return pts_scaled

        if 4 <= len(approx) <= 8:
            rect = cv2.minAreaRect(c)
            box = cv2.boxPoints(rect)
            box_scaled = (box / scale).astype("float32")
            return box_scaled

    return None



def detect_and_correct_document(image_path: str, output_dir: str = None) -> dict:
    """
    Detects document boundaries, applies perspective correction if angled/skewed,
    enhances contrast via CLAHE, and saves the preprocessed image.
    """
    if output_dir is None:
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        output_dir = os.path.join(backend_dir, "uploads", "preprocessed")

    try:
        if not os.path.exists(image_path):
            return {
                "processed_image_path": image_path,
                "correction_applied": False,
                "note": f"Image file not found: {image_path}",
                "error": "File not found"
            }

        os.makedirs(output_dir, exist_ok=True)

        img = cv2.imread(image_path)
        if img is None:
            return {
                "processed_image_path": image_path,
                "correction_applied": False,
                "note": f"Failed to read image with OpenCV: {image_path}",
                "error": "Image read error"
            }

        pts = find_document_contour(img)

        if pts is not None:
            warped = four_point_transform(img, pts)
            processed = apply_clahe(warped)
            correction_applied = True
            note = "Perspective correction and contrast enhancement applied"
        else:
            processed = apply_clahe(img)
            correction_applied = False
            note = "No clear document boundary detected, used original image"

        base_name, ext = os.path.splitext(os.path.basename(image_path))
        if not ext:
            ext = ".jpg"
        processed_filename = f"{base_name}_processed{ext}"
        processed_filepath = os.path.join(output_dir, processed_filename)

        cv2.imwrite(processed_filepath, processed)

        return {
            "processed_image_path": processed_filepath,
            "correction_applied": correction_applied,
            "note": note
        }

    except Exception as e:
        return {
            "processed_image_path": image_path,
            "correction_applied": False,
            "note": "Preprocessing failed, using original image",
            "error": str(e)
        }
