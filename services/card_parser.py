import json
import os
import re

import cv2
import numpy as np
import pytesseract

from services.utils import file_sha1


DEBUG = False


def set_tesseract_cmd(cmd=None):
    import pytesseract
    import os

    pytesseract.pytesseract.tesseract_cmd = cmd or os.getenv("TESSERACT_CMD", "tesseract")


def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")

    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect


def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(int(width_a), int(width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(int(height_a), int(height_b))

    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1]
    ], dtype="float32")

    matrix = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, matrix, (max_width, max_height))
    return warped


def resize_for_speed(image, max_width=1600):
    h, w = image.shape[:2]
    if w <= max_width:
        return image
    scale = max_width / w
    return cv2.resize(
        image,
        (int(w * scale), int(h * scale)),
        interpolation=cv2.INTER_AREA
    )


def find_card_contour(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 10000:
            continue

        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

        if len(approx) == 4:
            return approx.reshape(4, 2)

    return None


def find_grid_region(warped):
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

    th = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31, 10
    )

    h, w = th.shape
    top_cut = int(h * 0.18)
    roi = th[top_cut:, :]

    contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    best = None
    best_area = 0

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if area > best_area and cw > w * 0.6 and ch > h * 0.45:
            best = (x, y + top_cut, cw, ch)
            best_area = area

    if best is not None:
        x, y, cw, ch = best
        return warped[y:y + ch, x:x + cw]

    return warped[int(h * 0.21):int(h * 0.95), int(w * 0.05):int(w * 0.95)]


def detect_grid_lines(grid_img):
    gray = cv2.cvtColor(grid_img, cv2.COLOR_BGR2GRAY)

    bw = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        15, 8
    )

    h, w = bw.shape

    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, h // 8)))
    vertical = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vertical_kernel, iterations=1)

    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w // 8), 1))
    horizontal = cv2.morphologyEx(bw, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)

    return vertical, horizontal


def extract_line_positions(line_img, axis="vertical"):
    contours, _ = cv2.findContours(line_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    positions = []

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if axis == "vertical":
            if h < 40:
                continue
            positions.append(x + w // 2)
        else:
            if w < 40:
                continue
            positions.append(y + h // 2)

    positions = sorted(positions)
    merged = []

    for p in positions:
        if not merged or abs(p - merged[-1]) > 10:
            merged.append(p)
        else:
            merged[-1] = (merged[-1] + p) // 2

    return merged


def select_6_lines(positions):
    if len(positions) == 6:
        return positions

    pos = sorted(positions)
    if len(pos) < 6:
        return pos

    best = None
    best_score = float("inf")

    for i in range(len(pos) - 5):
        subset = pos[i:i + 6]
        diffs = [subset[j + 1] - subset[j] for j in range(5)]
        mean_diff = sum(diffs) / len(diffs)
        score = sum(abs(d - mean_diff) for d in diffs)
        if score < best_score:
            best_score = score
            best = subset

    return best


def get_cell_boxes(grid_img):
    vertical, horizontal = detect_grid_lines(grid_img)

    xs = extract_line_positions(vertical, axis="vertical")
    ys = extract_line_positions(horizontal, axis="horizontal")

    if len(xs) < 6 or len(ys) < 6:
        return None

    xs = select_6_lines(xs)
    ys = select_6_lines(ys)

    if len(xs) < 6 or len(ys) < 6:
        return None

    boxes = []
    for r in range(5):
        row = []
        for c in range(5):
            row.append((xs[c], ys[r], xs[c + 1], ys[r + 1]))
        boxes.append(row)

    return boxes


def remove_grid_lines(cell_img):
    gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)

    bw = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        21, 8
    )

    h, w = bw.shape

    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, h // 2)))
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, w // 2), 1))

    vertical = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vertical_kernel)
    horizontal = cv2.morphologyEx(bw, cv2.MORPH_OPEN, horizontal_kernel)

    lines = cv2.bitwise_or(vertical, horizontal)
    clean = cv2.bitwise_and(bw, cv2.bitwise_not(lines))
    return clean


def build_variants(cell_img):
    gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)

    variants = []

    _, th1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(th1)

    _, th2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    variants.append(th2)

    th3 = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 11
    )
    variants.append(th3)

    th4 = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31, 11
    )
    variants.append(th4)

    return variants


def ocr_digits(img_bin):
    config = "--psm 8 -c tessedit_char_whitelist=0123456789"
    text = pytesseract.image_to_string(img_bin, config=config).strip()
    text = "".join(ch for ch in text if ch.isdigit())
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def valid_range_for_col(col_idx):
    ranges = {
        0: (1, 15),
        1: (16, 30),
        2: (31, 45),
        3: (46, 60),
        4: (61, 75),
    }
    return ranges[col_idx]


def score_candidate(n, col_idx):
    if n is None:
        return -999

    lo, hi = valid_range_for_col(col_idx)

    if lo <= n <= hi:
        return 100

    dist = min(abs(n - lo), abs(n - hi))
    return -dist


def normalize_candidate(n, col_idx):
    if n is None:
        return None

    lo, hi = valid_range_for_col(col_idx)
    if lo <= n <= hi:
        return n

    s = str(n)

    if len(s) == 2:
        candidates = []
        try:
            candidates.append(int(s[-1]))
        except ValueError:
            pass
        try:
            candidates.append(int(s[0]))
        except ValueError:
            pass

        for c in candidates:
            if lo <= c <= hi:
                return c

    return n


def ocr_number(cell_img, col_idx):
    clean = remove_grid_lines(cell_img)
    clean_bgr = cv2.cvtColor(clean, cv2.COLOR_GRAY2BGR)

    variants = build_variants(clean_bgr)

    best_num = None
    best_score = -9999

    for var in variants:
        n = ocr_digits(var)
        n = normalize_candidate(n, col_idx)
        score = score_candidate(n, col_idx)

        if score > best_score:
            best_score = score
            best_num = n

    suspicious = best_score < 100
    return best_num if best_num is not None else 0, suspicious


def fallback_boxes(grid_img):
    h, w = grid_img.shape[:2]

    top = int(h * 0.02)
    bottom = int(h * 0.98)
    left = int(w * 0.02)
    right = int(w * 0.98)

    gh = bottom - top
    gw = right - left

    boxes = []
    for r in range(5):
        row = []
        for c in range(5):
            x1 = left + int(c * gw / 5)
            x2 = left + int((c + 1) * gw / 5)
            y1 = top + int(r * gh / 5)
            y2 = top + int((r + 1) * gh / 5)
            row.append((x1, y1, x2, y2))
        boxes.append(row)

    return boxes


def preprocess_id_roi(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    variants = []

    _, th1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(th1)

    th2 = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 8
    )
    variants.append(th2)

    th3 = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31, 8
    )
    variants.append(th3)

    return variants


def rotate_clockwise(img):
    return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)


def rotate_counterclockwise(img):
    return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)


def extract_number_from_text(text):
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()

    patterns = [
        r"N\s*[º°o]?\s*(\d{2,6})",
        r"N[º°o](\d{2,6})",
        r"(\d{3,6})"
    ]

    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            candidate = match.group(1)
            if candidate.isdigit():
                return candidate

    return None


def score_card_number(candidate):
    if not candidate or not candidate.isdigit():
        return -1

    score = 0
    length = len(candidate)

    if length in (3, 4):
        score += 100
    elif length == 2:
        score += 40
    else:
        score += 10

    if candidate.startswith("0"):
        score -= 20

    return score


def ocr_id_from_roi(roi, psm=6):
    variants = preprocess_id_roi(roi)

    for img in variants:
        config = f"--psm {psm} -c tessedit_char_whitelist=NnOoº°0123456789"
        text = pytesseract.image_to_string(img, config=config)
        found = extract_number_from_text(text)
        if found:
            return found

    return None


def extract_card_number(warped):
    h, w = warped.shape[:2]

    candidate_rois = []

    # Topo esquerdo pequeno: melhor para N° 701 / N° 1401
    candidate_rois.append(("top_left_small", warped[0:int(h * 0.12), 0:int(w * 0.22)], 7))

    # Topo esquerdo médio
    candidate_rois.append(("top_left_medium", warped[0:int(h * 0.16), 0:int(w * 0.30)], 6))

    # Faixa superior esquerda mais larga
    candidate_rois.append(("top_left_wide", warped[0:int(h * 0.18), 0:int(w * 0.40)], 6))

    # Lateral esquerda vertical
    left_side = warped[0:int(h * 0.40), 0:int(w * 0.12)]
    candidate_rois.append(("left_vertical", left_side, 6))
    candidate_rois.append(("left_rot_cw", rotate_clockwise(left_side), 7))
    candidate_rois.append(("left_rot_ccw", rotate_counterclockwise(left_side), 7))

    # Lateral esquerda maior
    left_side_big = warped[0:int(h * 0.55), 0:int(w * 0.16)]
    candidate_rois.append(("left_big_vertical", left_side_big, 6))
    candidate_rois.append(("left_big_rot_cw", rotate_clockwise(left_side_big), 7))
    candidate_rois.append(("left_big_rot_ccw", rotate_counterclockwise(left_side_big), 7))

    candidates = []

    for label, roi, psm in candidate_rois:
        found = ocr_id_from_roi(roi, psm=psm)
        if found:
            candidates.append((label, found, score_card_number(found)))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[2], reverse=True)
    return candidates[0][1]


def parse_bingo_card(image_path, cache_folder=None):
    image_hash = file_sha1(image_path)
    cache_file = os.path.join(cache_folder, f"{image_hash}.json") if cache_folder else None

    if cache_file and os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Não foi possível ler a imagem.")

    image = resize_for_speed(image, max_width=1600)

    contour = find_card_contour(image)
    warped = four_point_transform(image, contour) if contour is not None else image.copy()
    grid = find_grid_region(warped)
    boxes = get_cell_boxes(grid)

    if boxes is None:
        boxes = fallback_boxes(grid)

    numbers = []
    suspicious = []

    for r in range(5):
        row = []
        for c in range(5):
            if r == 2 and c == 2:
                row.append(0)
                continue

            x1, y1, x2, y2 = boxes[r][c]

            mx = max(4, int((x2 - x1) * 0.12))
            my = max(4, int((y2 - y1) * 0.12))

            cx1 = min(x2, x1 + mx)
            cy1 = min(y2, y1 + my)
            cx2 = max(cx1 + 1, x2 - mx)
            cy2 = max(cy1 + 1, y2 - my)

            cell = grid[cy1:cy2, cx1:cx2]
            value, is_suspicious = ocr_number(cell, c)
            row.append(value if value is not None else 0)

            if is_suspicious or value == 0:
                suspicious.append({"row": r, "col": c})

        numbers.append(row)

    card_number = extract_card_number(warped)

    result = {
        "numbers": numbers,
        "suspicious": suspicious,
        "card_number": card_number,
    }

    if cache_file:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)

    return result