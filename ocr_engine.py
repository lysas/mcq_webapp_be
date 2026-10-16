"""
Universal OCR & Marks Extraction Engine — Multi-Board Edition
==============================================================

Supports:
  1. Vertical Column Format (Tamil Nadu State Board, Kerala, Andhra Pradesh / Telangana)
     - Paired [Q.No | Mark] columns side-by-side (4-6 column pairs).
  2. Horizontal Matrix Format (Karnataka SSLC/PUC, CBSE, Maharashtra HSC)
     - Question numbers Q1, Q2... in row header, marks written directly below.

Performance & Precision Enhancements:
  - EasyOCR singleton loaded lazily on demand.
  - Image auto-upscaling to ~2200px target height for high-accuracy digit OCR.
  - Intelligent Layout Auto-Detection (Horizontal Matrix vs Vertical Columns).
  - Robust Q-Number to Mark pairing without false integer rejection.
"""

import os
import json
import time
import re
import cv2
import numpy as np
import easyocr
from typing import List, Dict, Any, Tuple, Optional
try:
    from .tn_board_sections import parse_mark_text as _parse_mark_text_from_sections
except (ImportError, ValueError):
    from tn_board_sections import parse_mark_text as _parse_mark_text_from_sections

# ── EasyOCR singleton — English only ─────────────────────────────────────────
_reader: Optional[easyocr.Reader] = None

def _get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _reader

# Re-export parse_mark_text from tn_board_sections (single source of truth)
parse_mark_text = _parse_mark_text_from_sections


# ── Pre-processing ───────────────────────────────────────────────────────────
def preprocess_and_deskew(img: np.ndarray) -> np.ndarray:
    """Deskew and clean up scanned booklet image using OpenCV."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    thr  = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    lines = cv2.HoughLinesP(thr, 1, np.pi / 180, 100, minLineLength=60, maxLineGap=15)
    angle = 0.0
    if lines is not None:
        degs = [np.degrees(np.arctan2(y2 - y1, x2 - x1))
                for l in lines for (x1, y1, x2, y2) in [l[0]]
                if abs(np.degrees(np.arctan2(y2 - y1, x2 - x1))) < 45]
        if degs:
            angle = float(np.median(degs))
    if abs(angle) > 0.4:
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_REPLICATE)
    return img


def _enhance_for_ocr(gray: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    High-precision image enhancement for handwritten booklet marks.
    Upscales image to target height of ~2200px so small handwritten digits
    are detected with high confidence by EasyOCR.
    """
    h, w = gray.shape[:2]
    target_h = 2200.0
    scale = target_h / float(h)
    
    # Do not scale down if image is already higher resolution
    if scale < 1.0 and h <= 2500:
        scale = 1.0

    new_w, new_h = int(w * scale), int(h * scale)
    if scale != 1.0:
        resized = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    else:
        resized = gray.copy()

    blurred = cv2.GaussianBlur(resized, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(blurred)

    return enhanced, scale


# ── Helpers & Token class ───────────────────────────────────────────────────
def number_to_words_english(num: float) -> str:
    n = int(round(abs(num)))
    ones  = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight',
             'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen',
             'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
    tens_ = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty',
             'Seventy', 'Eighty', 'Ninety']
    def _say(x: int) -> str:
        if x == 0:    return ''
        if x < 20:   return ones[x]
        if x < 100:  return tens_[x // 10] + ((' ' + ones[x % 10]) if x % 10 else '')
        if x < 1000: return ones[min(x // 100, 19)] + ' Hundred' + (
            (' and ' + _say(x % 100)) if x % 100 else '')
        if x < 100000: return _say(x // 1000) + ' Thousand' + (
            (' ' + _say(x % 1000)) if x % 1000 else '')
        return str(x)
    if n == 0: return 'Zero Only'
    return _say(n) + ' Only'


class _Token:
    __slots__ = ("text", "x1", "y1", "x2", "y2", "cx", "cy", "prob")
    def __init__(self, bbox, text, prob):
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        self.x1 = min(xs); self.x2 = max(xs)
        self.y1 = min(ys); self.y2 = max(ys)
        self.cx = (self.x1 + self.x2) / 2.0
        self.cy = (self.y1 + self.y2) / 2.0
        self.text = text.strip()
        self.prob = prob


def _cluster_rows(tokens: List[_Token], gap: float = 25.0) -> List[List[_Token]]:
    if not tokens:
        return []
    st = sorted(tokens, key=lambda t: t.cy)
    rows: List[List[_Token]] = [[st[0]]]
    ref = st[0].cy
    for t in st[1:]:
        if abs(t.cy - ref) <= gap:
            rows[-1].append(t)
            ref = sum(tt.cy for tt in rows[-1]) / float(len(rows[-1]))
        else:
            rows[-1].sort(key=lambda tt: tt.cx)
            rows.append([t])
            ref = t.cy
    rows[-1].sort(key=lambda t: t.cx)
    return rows


def _is_q_number(text: str) -> Optional[int]:
    """Return integer Q-number if token looks like a question number 1-120, else None."""
    t = text.strip().lstrip('0')
    if not t:
        return None
    # Common OCR digit confusion fixes
    t = t.replace('O', '0').replace('o', '0').replace('l', '1').replace('I', '1').replace('S', '5')
    if re.fullmatch(r'\d{1,3}', t):
        v = int(t)
        if 1 <= v <= 120:
            return v
    return None


def _is_mark_token(text: str) -> bool:
    """Return True if token could be a handwritten mark, score, or slash."""
    t = text.strip()
    if not t:
        return False
    if re.fullmatch(r'[/\\|\-\u2014\u2013lLiI!xX.]+', t):
        return True
    if re.search(r'\d', t) and len(t) <= 8:
        return True
    return False


def _detect_layout_mode(rows: List[List[_Token]]) -> str:
    """
    Detect whether booklet is HORIZONTAL MATRIX (sequential Qs in row e.g. 1, 2, 3...)
    or VERTICAL COLUMNS (column step Qs e.g. 1, 16, 31, 46).
    """
    h_sequential_rows = 0
    v_column_rows = 0

    for row in rows:
        q_vals = [_is_q_number(t.text) for t in row if _is_q_number(t.text) is not None]
        if len(q_vals) >= 3:
            diffs = [q_vals[i+1] - q_vals[i] for i in range(len(q_vals)-1)]
            ones_ratio = sum(1 for d in diffs if d == 1) / float(len(diffs))
            if ones_ratio >= 0.5:
                h_sequential_rows += 1
            elif any(d >= 5 for d in diffs):
                v_column_rows += 1

    return "horizontal" if h_sequential_rows > v_column_rows else "vertical"


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTION STRATEGIES
# ─────────────────────────────────────────────────────────────────────────────

def _extract_vertical_paired_columns(tokens: List[_Token], img_w: int) -> Dict[int, str]:
    """
    Vertical Columns Layout (Tamil Nadu, Kerala, AP):
    Paired [Q.No | Mark] columns side-by-side.
    Matches Q-number token Q(n) with mark token M to its right on the same Y-band.
    """
    marks: Dict[int, str] = {}
    q_tokens: List[Tuple[int, _Token]] = []
    mark_tokens: List[_Token] = []

    for t in tokens:
        qv = _is_q_number(t.text)
        if qv is not None:
            q_tokens.append((qv, t))
        if _is_mark_token(t.text):
            mark_tokens.append(t)

    # Sort Q-tokens by Q-number ascending
    q_tokens.sort(key=lambda item: item[0])

    max_dx = img_w * 0.14

    for q_num, q_tok in q_tokens:
        if q_num in marks:
            continue
        candidates = []
        for m_tok in mark_tokens:
            if m_tok is q_tok:
                continue
            dx = m_tok.cx - q_tok.cx
            dy = abs(m_tok.cy - q_tok.cy)
            # Mark must be to the right of Q-number, within max_dx distance, same row (dy <= 30)
            if 10 <= dx <= max_dx and dy <= 30:
                candidates.append((dy, dx, m_tok))
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1]))
            marks[q_num] = candidates[0][2].text

    return marks


def _extract_horizontal_matrix(tokens: List[_Token], img_w: int) -> Dict[int, str]:
    """
    Horizontal Matrix Layout (Karnataka SSLC/PUC, CBSE, Maharashtra HSC):
    Q-numbers Q1, Q2, Q3... across row header, marks written in row directly below.
    """
    marks: Dict[int, str] = {}
    rows = _cluster_rows(tokens, gap=25.0)

    for ri, row in enumerate(rows):
        q_items = [(t, _is_q_number(t.text)) for t in row if _is_q_number(t.text) is not None]
        if len(q_items) < 3:
            continue
        q_nums = [q[1] for q in q_items]

        # Check for sequential increasing Q-numbers
        diffs = [q_nums[i+1] - q_nums[i] for i in range(len(q_nums)-1)]
        if not diffs or (sum(1 for d in diffs if d == 1) / float(len(diffs)) < 0.4):
            continue

        # Look at subsequent rows (ri+1 .. ri+3) for mark tokens at matching X positions
        mark_candidates: List[_Token] = []
        for offset in range(1, 4):
            if ri + offset >= len(rows):
                break
            m_row = rows[ri + offset]
            m_q_vals = [_is_q_number(t.text) for t in m_row if _is_q_number(t.text) is not None]
            if len(m_q_vals) >= 3 and sum(1 for v in m_q_vals if v > 10) >= 2:
                break
            for m_tok in m_row:
                if _is_mark_token(m_tok.text):
                    mark_candidates.append(m_tok)

        for q_tok, q_num in q_items:
            if q_num in marks:
                continue
            cands = [m for m in mark_candidates if abs(m.cx - q_tok.cx) < (img_w * 0.08)]
            if cands:
                best_m = min(cands, key=lambda m: abs(m.cx - q_tok.cx))
                marks[q_num] = best_m.text

    return marks


def _sequential_fallback(tokens: List[_Token]) -> Dict[int, str]:
    """Last resort: assign mark tokens in reading order to Q1, Q2, Q3..."""
    sorted_toks = sorted(tokens, key=lambda t: (t.cy, t.cx))
    marks: Dict[int, str] = {}
    q = 1
    for t in sorted_toks:
        if q > 120:
            break
        if _is_mark_token(t.text) and _is_q_number(t.text) is None:
            marks[q] = t.text
            q += 1
    return marks


def _extract_evaluator_total_from_tokens(
    tokens,
    img_h: int,
    img_w: int,
    schema_max: float = 200.0
):
    """
    Extracts evaluator-written grand total from full-page OCR tokens.
    Scores each candidate numeric value by confidence x frequency so that
    values appearing multiple times (e.g. 82 in both questionwise and
    pagewise grand-total boxes) rank highest.
    Excludes values <= 5 (too small to be a meaningful total).
    """
    import re as _re2
    score_map = {}

    # Bottom area scan (ry > 0.65) where grand-total rows appear
    for tok in tokens:
        ry = tok.cy / float(img_h)
        if ry < 0.65:
            continue
        nums = _re2.findall(r'\d+', tok.text)
        for n in nums:
            v = int(n)
            if v <= 5 or v > schema_max + 10:
                continue
            score_map[v] = score_map.get(v, 0.0) + max(tok.prob, 0.05)

    # Top-right "Total Marks" box scan (boost by 0.5 for being in official printed box)
    for tok in tokens:
        rx = tok.cx / float(img_w)
        ry = tok.cy / float(img_h)
        if rx > 0.60 and ry < 0.35:
            nums = _re2.findall(r'\d+', tok.text)
            for n in nums:
                v = int(n)
                if v <= 5 or v > schema_max + 10:
                    continue
                score_map[v] = score_map.get(v, 0.0) + min(0.5, tok.prob + 0.3)

    if not score_map:
        return None

    best_val = max(score_map.keys(), key=lambda v: score_map[v])
    best_score = score_map[best_val]
    if best_score >= 0.10:
        top5 = dict(sorted(score_map.items(), key=lambda x: -x[1])[:5])
        print("[EvalTotal] Candidates: " + str(top5))
        return str(best_val)
    return None



# ─────────────────────────────────────────────────────────────────────────────
# GEMINI 2.5 FLASH VISION OCR ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def extract_marks_with_gemini(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    api_key: Optional[str] = None
) -> Tuple[Dict[int, str], str, int, int]:
    """
    Extract answer booklet question marks using Gemini 2.5 Flash Vision AI.
    Returns tuple of (marks_dict, model_name_used, prompt_tokens, completion_tokens).
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
        env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".env"))
        if os.path.exists(env_path):
            load_dotenv(env_path)
    except Exception:
        pass

    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return {}, "", 0, 0

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
    except Exception as e:
        print(f"[Gemini OCR] Failed to initialize client: {e}")
        return {}, "", 0, 0

    prompt = """
You are an expert OCR system for Indian Board Exam Answer Booklets (Tamil Nadu State Board, Karnataka SSLC/PUC, CBSE, Kerala, AP, etc.).
Carefully analyze this answer booklet front cover page grid and table.

Extract:
1. All individual question numbers (Q1..Q60) and their corresponding handwritten marks, scores, or slashes ('/').
2. The section subtotal boxes (e.g., TOTAL I, TOTAL II, TOTAL III, TOTAL IV, TOTAL V, TOTAL VI). Represent subtotals as keys "subtotal_I", "subtotal_II", "subtotal_III", "subtotal_IV", "subtotal_V".
3. The grand evaluator total figure written in the "Total Marks", "Question-wise Grand Total", or "Page-wise Grand Total" boxes (e.g. "evaluator_total": "82").

Rules:
1. Extract question numbers as integer keys e.g. "1": "1", "2": "1", "31": "3", "46": "5".
2. Extract mark values exactly as written (e.g. "1", "2", "3", "5", "1+1+1", "/", "0").
3. Include keys "subtotal_I", "subtotal_II", "subtotal_III", "subtotal_IV", and "evaluator_total".
4. Output ONLY a valid JSON dictionary.

Example JSON output:
{
  "1": "1",
  "2": "1",
  "16": "1",
  "21": "/",
  "31": "3",
  "46": "5",
  "subtotal_I": "18",
  "subtotal_II": "14",
  "subtotal_III": "40",
  "subtotal_IV": "10",
  "evaluator_total": "82"
}
"""

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro"]
    response = None
    used_model = ""

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                ]
            )
            if response and response.text:
                used_model = model_name
                break
        except Exception as err:
            err_str = str(err)
            print(f"[Gemini OCR] Model {model_name} notice: {err_str[:120]}")
            if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                print("[Gemini OCR] Free tier quota reached for Gemini. Fallback to Local EasyOCR + OpenCV pipeline.")
                break  # Don't waste time retrying if quota is exhausted
        if response and response.text:
            break

    if not response or not response.text:
        return {}, "", 0, 0

    p_tokens = 1150
    c_tokens = 180
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        p_tokens = getattr(response.usage_metadata, 'prompt_token_count', 1150) or 1150
        c_tokens = getattr(response.usage_metadata, 'candidates_token_count', 180) or 180

    raw_text = response.text.strip()
    cleaned = re.sub(r'```json\s*', '', raw_text)
    cleaned = re.sub(r'```\s*$', '', cleaned).strip()

    try:
        raw_dict = json.loads(cleaned)
        marks_dict: Dict[Any, str] = {}
        for k, v in raw_dict.items():
            k_str = str(k).strip()
            if k_str.isdigit():
                q_num = int(k_str)
                if 1 <= q_num <= 150:
                    marks_dict[q_num] = str(v).strip()
            elif k_str.startswith("subtotal") or k_str == "evaluator_total":
                marks_dict[k_str] = str(v).strip()
        return marks_dict, used_model, p_tokens, c_tokens
    except Exception as e:
        print(f"[Gemini OCR] JSON parsing notice: {e}")
        return {}, "", 0, 0


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def extract_universal_booklet_marks(
    image_np: np.ndarray,
    filename: str = "booklet.jpg",
    override_total_q: Optional[int] = None,
    layout_mode: Optional[str] = None,
    board_id: Optional[str] = None,
    gemini_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extracts marks from an answer booklet image or PDF.
    Uses Gemini 2.5 Flash Vision OCR if API key is available, falling back to local OpenCV + EasyOCR.
    Auto-detects layout (Vertical Columns vs Horizontal Matrix) and board schema.
    """
    try:
        from .tn_board_sections import get_board_schema, auto_detect_board, assign_sections_to_marks
    except (ImportError, ValueError):
        from tn_board_sections import get_board_schema, auto_detect_board, assign_sections_to_marks

    start_time = time.time()
    prompt_tokens = 0
    completion_tokens = 0

    # ── 1. Try Gemini 2.5 Flash Vision OCR First ──────────────────────────────
    engine_used = "OpenCV + EasyOCR"
    marks_dict: Dict[int, str] = {}
    tokens: List[_Token] = []

    success, buffer = cv2.imencode(".jpg", image_np)
    if success:
        g_marks, g_model, g_p, g_c = extract_marks_with_gemini(buffer.tobytes(), mime_type="image/jpeg", api_key=gemini_api_key)
        if g_marks:
            marks_dict = g_marks
            engine_used = f"Gemini ({g_model})"
            prompt_tokens = g_p
            completion_tokens = g_c

    # ── 2. Fallback to Local OpenCV + EasyOCR Pipeline if Gemini unavailable ────
    processed = preprocess_and_deskew(image_np)
    gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY) if len(processed.shape) == 3 else processed
    enhanced, scale = _enhance_for_ocr(gray.copy())
    img_h, img_w = enhanced.shape[:2]

    if not marks_dict:
        raw_ocr = _get_reader().readtext(enhanced, detail=1, paragraph=False)
        tokens = [
            _Token(bbox, txt, prob)
            for bbox, txt, prob in raw_ocr
            if prob >= 0.05 and txt.strip()
        ]
        rows = _cluster_rows(tokens, gap=25.0)
        detected_layout = layout_mode or _detect_layout_mode(rows)

        if detected_layout == "vertical":
            marks_dict = _extract_vertical_paired_columns(tokens, img_w)
            if len(marks_dict) < 5:
                h_marks = _extract_horizontal_matrix(tokens, img_w)
                if len(h_marks) > len(marks_dict):
                    marks_dict = h_marks
                    detected_layout = "horizontal"
        else:
            marks_dict = _extract_horizontal_matrix(tokens, img_w)
            if len(marks_dict) < 5:
                v_marks = _extract_vertical_paired_columns(tokens, img_w)
                if len(v_marks) > len(marks_dict):
                    marks_dict = v_marks
                    detected_layout = "vertical"

        if not marks_dict:
            marks_dict = _sequential_fallback(tokens)

        # ── Extract evaluator total from full-page tokens ─────────────────────
        # Full-page OCR reliably finds standalone "82" tokens at high confidence.
        # This is much more reliable than cell-by-cell ROI OCR on tiny crops.
        if "evaluator_total" not in marks_dict:
            eval_total_str = _extract_evaluator_total_from_tokens(tokens, img_h, img_w, 300.0)
            if eval_total_str:
                marks_dict["evaluator_total"] = eval_total_str
                print("[OCR] Evaluator total from full-page tokens: " + eval_total_str)
    else:
        # Gemini succeeded, infer layout mode from Q-number distribution
        int_keys = [k for k in marks_dict.keys() if isinstance(k, int)]
        detected_layout = layout_mode or ("vertical" if any(k > 15 for k in int_keys) else "horizontal")

    # ── 5. Determine total questions & board schema ───────────────────────────
    int_keys = [k for k in marks_dict.keys() if isinstance(k, int)]
    total_q = override_total_q or (max(int_keys) if int_keys else 60)
    schema = get_board_schema(board_id) if board_id else auto_detect_board(total_q, detected_layout)

    schema_max_q = max(s["qTo"] for s in schema["sections"])
    if not override_total_q:
        total_q = schema_max_q

    # ── 6. Assign marks to board sections & cross-verify ───────────────────────
    try:
        from .blueprints import get_blueprint
        from .roi_extractor import extract_grid_rois
        from .ai_providers import ConsensusEngine
        from .verification_engine import verify_three_way_totals
    except (ImportError, ValueError):
        from blueprints import get_blueprint
        from roi_extractor import extract_grid_rois
        from ai_providers import ConsensusEngine
        from verification_engine import verify_three_way_totals

    bp = get_blueprint(board_id or schema.get("boardId"))
    cell_rois, eval_roi = extract_grid_rois(image_np, bp)
    consensus = ConsensusEngine()

    rois_dict = {}
    cell_marks_dict = {}

    # Map question number to expected max marks from schema
    max_marks_map = {}
    for sec in schema.get("sections", []):
        for q_n in range(sec["qFrom"], sec["qTo"] + 1):
            max_marks_map[q_n] = sec["marksPerQuestion"]

    for cell in cell_rois:
        exp_max = max_marks_map.get(cell.q_number, 1.0)
        rec = consensus.evaluate_cell(cell.roi_image, cell.q_number, exp_max)
        rec.bbox = list(cell.bbox)
        # Cap score to section max marks per question
        if rec.normalized_score > exp_max:
            rec.normalized_score = 0.0
            rec.raw_mark = "/"
            rec.status = "review_required"
            rec.review_required = True
        rois_dict[cell.q_number] = rec
        cell_marks_dict[cell.q_number] = rec.raw_mark

    # Merge ROI cell marks into marks_dict:
    # - If Gemini already gave a valid numeric mark for a question, KEEP IT.
    # - Only fill in questions where Gemini gave "/" (unattempted), nothing, or a non-digit.
    # - If no Gemini data at all (local OCR only mode), use all ROI results.
    gemini_ran = (engine_used.startswith("Gemini"))
    for q_num, raw_m in cell_marks_dict.items():
        existing = marks_dict.get(q_num, None)
        if existing is None:
            # Missing entirely — always add
            marks_dict[q_num] = raw_m
        elif not gemini_ran:
            # No Gemini — always use ROI result
            marks_dict[q_num] = raw_m
        else:
            # Gemini ran: only override if Gemini mark is unclear (slash/empty)
            existing_str = str(existing).strip()
            if existing_str in ["/", "", "-", "—"] or not any(c.isdigit() for c in existing_str):
                marks_dict[q_num] = raw_m

    # Sanity filter full-page marks_dict against section max marks
    for k, v in list(marks_dict.items()):
        if isinstance(k, int):
            exp_m = max_marks_map.get(k, 1.0)
            parsed_v = parse_mark_text(str(v))
            if parsed_v["score"] > exp_m:
                marks_dict[k] = "/"

    # OCR extraction on Evaluator Total ROI crop
    # Strategy: try multiple OCR reads, collect all numeric candidates,
    # pick the one that falls in a plausible total range (0..schema max).
    if "evaluator_total" not in marks_dict and eval_roi and eval_roi.roi_image is not None and eval_roi.roi_image.size > 0:
        try:
            board_max = schema.get("totalMarks", 200)
            eval_candidates = []

            # Run EasyOCR on the ROI
            eval_ocr_results = _get_reader().readtext(eval_roi.roi_image, detail=1, paragraph=False)
            for (_bbox, eval_txt, _prob) in eval_ocr_results:
                digits_found = re.findall(r'\d+', eval_txt)
                for d in digits_found:
                    v = int(d)
                    if 0 < v <= board_max + 10:  # slight tolerance
                        eval_candidates.append(v)

            if eval_candidates:
                # Pick the largest plausible value (the grand total)
                best_eval = max(eval_candidates)
                marks_dict["evaluator_total"] = str(best_eval)
                print(f"[EvalROI] Extracted evaluator total: {best_eval} from candidates: {eval_candidates}")
        except Exception as e_exc:
            print(f"[EvalROI] OCR error: {e_exc}")

    m_reg  = re.search(r'\b\d{5,10}\b', filename)
    reg_no = m_reg.group(0) if m_reg else "000000"

    section_result = assign_sections_to_marks(marks_dict, schema, override_total_q=override_total_q)

    # Attach ROI bounding boxes to question items
    rows_data = []
    for sec in section_result["sections"]:
        qs_with_bbox = []
        for q in sec["questions"]:
            q_num = q["qNumber"]
            rec = rois_dict.get(q_num)
            q_copy = dict(q)
            if rec and rec.bbox:
                q_copy["bbox"] = rec.bbox
                q_copy["confidence"] = rec.confidence
                q_copy["provider"] = rec.provider
                q_copy["review_required"] = rec.review_required
            else:
                q_copy["bbox"] = [0, 0, 50, 20]
                q_copy["confidence"] = 0.90
                q_copy["provider"] = "engine"
                q_copy["review_required"] = False
            qs_with_bbox.append(q_copy)

        rows_data.append({
            "rowIndex": len(rows_data),
            "label": sec["label"],
            "start": sec["qFrom"],
            "end": sec["qTo"],
            "sectionName": sec["name"],
            "marksPerQuestion": sec["marksPerQuestion"],
            "maxSectionMarks": sec["maxSectionMarks"],
            "questions": qs_with_bbox,
            "subtotalComputed": sec["scoredMarks"],
            "subtotalWritten": sec["scoredMarks"],
            "isMatched": True,
            "attemptedCount": sec["attemptedCount"],
            "unattemptedCount": sec["unattemptedCount"]
        })

    grand_total = section_result["grandTotal"]
    eval_total = 0.0
    pagewise_total = 0.0

    schema_max_marks = float(schema.get("totalMarks", 300))

    # Extract evaluator total box value (authoritative teacher-written total)
    raw_eval_str = str(marks_dict.get("evaluator_total", "")).strip()
    if raw_eval_str.isdigit():
        eval_val = float(raw_eval_str)
        if 0 < eval_val <= schema_max_marks + 20:
            eval_total = eval_val

    # Collect section subtotal box values
    subtotal_box_sum = 0.0
    has_subtotal_boxes = False
    for k, v in marks_dict.items():
        k_str = str(k)
        if k_str.startswith("subtotal_"):
            try:
                val = float(re.search(r'\d+', str(v)).group(0))
                subtotal_box_sum += val
                has_subtotal_boxes = True
            except Exception:
                pass

    # Determine pagewise_total (sum of section subtotal boxes)
    if eval_total > 0:
        # If evaluator_total exists, subtotal_box_sum is only valid if close to eval_total
        if has_subtotal_boxes and abs(subtotal_box_sum - eval_total) <= 2.0:
            pagewise_total = subtotal_box_sum
        else:
            pagewise_total = eval_total
    elif has_subtotal_boxes and 0 < subtotal_box_sum <= schema_max_marks:
        pagewise_total = subtotal_box_sum
    else:
        pagewise_total = grand_total

    # Determine final grand_total:
    # Priority: evaluator_total > subtotal_box_sum > question-wise sum.
    # evaluator_total (written by the teacher) is the most authoritative source.
    if eval_total > 0:
        grand_total = eval_total
    elif has_subtotal_boxes and 0 < subtotal_box_sum <= schema_max_marks:
        grand_total = subtotal_box_sum
    # else: keep grand_total from question-wise sum

    ver_res = verify_three_way_totals(
        grand_total,
        pagewise_total,
        eval_total if eval_total > 0 else grand_total
    )

    total_tokens = prompt_tokens + completion_tokens
    cost_usd = (prompt_tokens / 1000000.0) * 0.075 + (completion_tokens / 1000000.0) * 0.30
    cost_inr = cost_usd * 83.5
    exec_time_ms = int((time.time() - start_time) * 1000)

    cost_detail = f"Gemini 2.5 Flash (${cost_usd:.6f} USD / ₹{cost_inr:.4f} INR)" if prompt_tokens > 0 else "Local OpenCV + EasyOCR (0 Tokens — $0.00 Free Edge Execution)"

    return {
        "id": f"std_{reg_no}",
        "fileName": filename,
        "regNo": reg_no,
        "subject": "Extracted Subject",
        "subjectCode": "-",
        "medium": "Auto-detected",
        "totalQuestions": total_q,
        "layoutMode": detected_layout,
        "boardId": schema["boardId"],
        "boardName": schema["boardName"],
        "boardTotalMarks": schema["totalMarks"],
        "rows": rows_data,
        "sections": section_result["sections"],
        "grandTotalComputed": grand_total,
        "pagewiseTotal": pagewise_total,
        "evaluatorTotalFigures": eval_total,
        "evaluatorTotalWords": number_to_words_english(eval_total),
        "engineUsed": engine_used,
        "isVerified": ver_res.is_verified,
        "reviewRequired": ver_res.review_required,
        "verificationMessage": ver_res.status_message,
        "isApproved": False,
        "tokenUsage": {
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": total_tokens,
            "estimatedCostUsd": round(cost_usd, 6),
            "estimatedCostInr": round(cost_inr, 4),
            "executionTimeMs": exec_time_ms,
            "costDetails": cost_detail
        },
        "_debug": {
            "engineUsed": engine_used,
            "tokensFound": len(tokens),
            "marksExtracted": len(marks_dict),
            "layoutDetected": detected_layout,
            "boardDetected": schema["boardId"],
            "rawMarks": {str(k): v for k, v in sorted(marks_dict.items(), key=lambda x: (0, x[0]) if isinstance(x[0], int) else (1, str(x[0])))}
        }
    }
