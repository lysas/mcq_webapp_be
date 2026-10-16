"""
ROI & Cell Extractor Module
===========================
Performs image pre-processing (deskew, noise reduction, grayscale/threshold variants),
and extracts precise bounding-box ROIs for question cells, page cells, section subtotals,
and evaluator total figures based on the selected Board Blueprint geometry.
"""

import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict
try:
    from .blueprints import BoardBlueprint, get_blueprint
except (ImportError, ValueError):
    from blueprints import BoardBlueprint, get_blueprint


@dataclass
class CellROI:
    q_number: int
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    column: int
    row: int
    roi_image: np.ndarray
    source: str  # "question_grid", "page_grid", "evaluator_total"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "q_number": self.q_number,
            "bbox": list(self.bbox),
            "column": self.column,
            "row": self.row,
            "source": self.source
        }


@dataclass
class PreprocessedVariants:
    original: np.ndarray
    gray: np.ndarray
    enhanced: np.ndarray
    threshold: np.ndarray


def preprocess_image(img_bgr: np.ndarray) -> PreprocessedVariants:
    """
    Creates multiple image variants for robust OCR recognition:
    - original BGR
    - grayscale
    - CLAHE contrast enhanced
    - Otsu adaptive threshold
    """
    if len(img_bgr.shape) == 2:
        gray = img_bgr
        original = cv2.cvtColor(img_bgr, cv2.COLOR_GRAY2BGR)
    else:
        original = img_bgr
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Resize if extremely large to maintain performance
    h, w = gray.shape[:2]
    if h > 2200:
        scale = 2200 / h
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        original = cv2.resize(original, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    # Deskew angle estimation
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(blur)
    _, threshold = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    return PreprocessedVariants(
        original=original,
        gray=gray,
        enhanced=enhanced,
        threshold=threshold
    )


def extract_grid_rois(
    img_bgr: np.ndarray,
    blueprint: BoardBlueprint
) -> Tuple[List[CellROI], Optional[CellROI]]:
    """
    Exploits blueprint geometry to crop exact ROIs for Q1..Qn and Evaluator Total.
    Returns: (list of CellROI for questions, CellROI for evaluator total)
    """
    variants = preprocess_image(img_bgr)
    img = variants.enhanced
    img_h, img_w = img.shape[:2]

    cell_rois: List[CellROI] = []

    # Process each column defined in the blueprint
    for col_info in blueprint.columns:
        col_idx = col_info.column_index
        q_start = col_info.start_question
        q_end = col_info.end_question
        num_q_in_col = q_end - q_start + 1

        if num_q_in_col <= 0:
            continue

        # Compute column bounds in pixels
        x_min = int(col_info.x_rel_start * img_w)
        x_max = int(col_info.x_rel_end * img_w)
        y_min = int(col_info.y_rel_start * img_h)
        y_max = int(col_info.y_rel_end * img_h)

        col_w = max(10, x_max - x_min)
        col_h = max(10, y_max - y_min)
        row_h = col_h / float(num_q_in_col)

        for i in range(num_q_in_col):
            q_num = q_start + i
            cell_y1 = int(y_min + i * row_h)
            cell_y2 = int(y_min + (i + 1) * row_h)

            # Use the FULL column width for the ROI (both Q.No and Mark sub-cells).
            # Taking only the right-half of a narrow column (e.g. 40px) gave an 18px
            # crop — far too small for EasyOCR to read handwritten digits reliably.
            # Full-column crops are passed to the OCR engine which already knows to
            # look for numeric tokens.
            roi_x1 = x_min
            roi_x2 = x_max

            cell_w = max(10, roi_x2 - roi_x1)
            cell_h = max(10, cell_y2 - cell_y1)

            roi_crop = variants.original[cell_y1:cell_y2, roi_x1:roi_x2]
            if roi_crop is None or roi_crop.size == 0:
                roi_crop = np.full((40, 60, 3), 255, dtype=np.uint8)
            else:
                # Upscale tiny cells so EasyOCR can read handwritten digits reliably.
                # Target: at least 60px wide, 40px tall.
                h_c, w_c = roi_crop.shape[:2]
                scale_up = max(1.0, 60.0 / max(w_c, 1), 40.0 / max(h_c, 1))
                if scale_up > 1.05:
                    roi_crop = cv2.resize(
                        roi_crop,
                        (int(w_c * scale_up), int(h_c * scale_up)),
                        interpolation=cv2.INTER_CUBIC
                    )

            cell_rois.append(
                CellROI(
                    q_number=q_num,
                    bbox=(roi_x1, cell_y1, cell_w, cell_h),
                    column=col_idx,
                    row=i + 1,
                    roi_image=roi_crop,
                    source="question_grid"
                )
            )

    # Extract Evaluator Total ROI
    eval_loc = blueprint.evaluator_total_location
    ex1 = int(eval_loc["x_start"] * img_w)
    ex2 = int(eval_loc["x_end"] * img_w)
    ey1 = int(eval_loc["y_start"] * img_h)
    ey2 = int(eval_loc["y_end"] * img_h)

    eval_crop_raw = variants.original[ey1:ey2, ex1:ex2]

    if eval_crop_raw is None or eval_crop_raw.size == 0:
        eval_crop_raw = np.full((60, 100, 3), 255, dtype=np.uint8)
    else:
        # Upscale evaluator total crop so small printed/handwritten digits are clear
        h_e, w_e = eval_crop_raw.shape[:2]
        scale_e = max(1.0, 100.0 / max(w_e, 1), 60.0 / max(h_e, 1))
        if scale_e > 1.05:
            eval_crop_raw = cv2.resize(
                eval_crop_raw,
                (int(w_e * scale_e), int(h_e * scale_e)),
                interpolation=cv2.INTER_CUBIC
            )
        # Apply CLAHE for contrast enhancement
        if len(eval_crop_raw.shape) == 3:
            gray_e = cv2.cvtColor(eval_crop_raw, cv2.COLOR_BGR2GRAY)
        else:
            gray_e = eval_crop_raw.copy()
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        enhanced_e = clahe.apply(gray_e)
        eval_crop_raw = cv2.cvtColor(enhanced_e, cv2.COLOR_GRAY2BGR)

    eval_roi = CellROI(
        q_number=0,
        bbox=(ex1, ey1, max(10, ex2 - ex1), max(10, ey2 - ey1)),
        column=0,
        row=0,
        roi_image=eval_crop_raw,
        source="evaluator_total"
    )

    return cell_rois, eval_roi

