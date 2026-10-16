"""
Deterministic Verification & Mark Normalization Engine
=========================================================
Implements strict mark normalization and independent three-way verification:
  A. Question-wise Computed Total (Sum of Q1..Qn scores)
  B. Page-wise Computed Total (Sum of page cell scores)
  C. Evaluator Total (Figures written by evaluator on cover)

Student record is marked VERIFIED iff A == B == C.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
try:
    from .blueprints import BoardBlueprint, SectionRule
except (ImportError, ValueError):
    from blueprints import BoardBlueprint, SectionRule


@dataclass
class VerificationResult:
    questionwise_total: float
    pagewise_total: float
    evaluator_total: float
    difference_question_page: float
    difference_question_evaluator: float
    is_verified: bool
    review_required: bool
    status_message: str


def normalize_mark_expression(raw_mark: str) -> Dict[str, Any]:
    """
    Deterministic mark normalization:
      - "1+1+1" -> 3.0 (subdivision)
      - "2+2"   -> 4.0 (subdivision)
      - "/" or "-" or "—" -> 0.0 (unattempted)
      - Ambiguous -> review_required
    """
    if not raw_mark or raw_mark.strip() == "":
        return {"raw": "/", "score": 0.0, "is_subdivision": False, "status": "blank"}

    t = raw_mark.strip()

    if t in ["/", "\\", "-", "—", "–", "."]:
        return {"raw": "/", "score": 0.0, "is_subdivision": False, "status": "unattempted"}

    if "+" in t:
        parts = t.split("+")
        try:
            nums = [float(p.strip()) for p in parts if p.strip()]
            return {"raw": t, "score": sum(nums), "is_subdivision": True, "status": "valid"}
        except ValueError:
            return {"raw": t, "score": 0.0, "is_subdivision": True, "status": "review_required"}

    # Plain float/int
    m = re.search(r'\d+(\.\d+)?', t)
    if m:
        val = float(m.group(0))
        raw_str = str(int(val)) if val.is_integer() else str(val)
        return {"raw": raw_str, "score": val, "is_subdivision": False, "status": "valid"}

    return {"raw": t, "score": 0.0, "is_subdivision": False, "status": "review_required"}


def calculate_section_totals(
    question_marks: Dict[int, float],
    blueprint: BoardBlueprint
) -> List[Dict[str, Any]]:
    """Calculates section subtotals deterministically based on blueprint rules."""
    section_results = []
    for sec in blueprint.sections:
        subtotal = 0.0
        att_count = 0
        unatt_count = 0
        qs = []

        for q in range(sec.question_start, sec.question_end + 1):
            score = float(question_marks.get(q, 0.0))
            raw = str(question_marks.get(f"{q}_raw", "1" if score > 0 else "/"))
            if score > 0:
                att_count += 1
            else:
                unatt_count += 1
            subtotal += score
            qs.append({"qNumber": q, "raw": raw, "score": score})

        section_results.append({
            "section_id": sec.id,
            "section_name": sec.name,
            "label": sec.label,
            "qFrom": sec.question_start,
            "qTo": sec.question_end,
            "marksPerQuestion": sec.marks_per_question,
            "maxSectionMarks": sec.max_section_marks,
            "computed_subtotal": round(subtotal, 2),
            "written_subtotal": round(subtotal, 2),
            "is_matched": True,
            "attempted_count": att_count,
            "unattempted_count": unatt_count,
            "questions": qs
        })

    return section_results


def verify_three_way_totals(
    questionwise_total: float,
    pagewise_total: float,
    evaluator_total: float
) -> VerificationResult:
    """
    Cross-verifies Questionwise Total vs Pagewise Total vs Evaluator Total.
    Returns VerificationResult with status flags.
    """
    q_tot = round(questionwise_total, 2)
    p_tot = round(pagewise_total, 2)
    e_tot = round(evaluator_total, 2)

    diff_qp = round(abs(q_tot - p_tot), 2)
    diff_qe = round(abs(q_tot - e_tot), 2)

    is_verified = (diff_qp < 0.001) and (diff_qe < 0.001)
    review_req = not is_verified

    if is_verified:
        msg = "VERIFIED MATCH — All totals cross-verified successfully."
    else:
        msg = f"MISMATCH DETECTED — Q-Total: {q_tot}, Page-Total: {p_tot}, Evaluator: {e_tot}"

    return VerificationResult(
        questionwise_total=q_tot,
        pagewise_total=p_tot,
        evaluator_total=e_tot,
        difference_question_page=diff_qp,
        difference_question_evaluator=diff_qe,
        is_verified=is_verified,
        review_required=review_req,
        status_message=msg
    )
