"""
Tamil Nadu State Board / CBSE / IGCSE — Section Schema Registry
================================================================
All Tamil Nadu syllabus papers (State Board, CBSE affiliated TN schools,
IGCSE Cambridge schools in Tamil Nadu) follow rigid section-wise mark
allocations defined by the board blueprint.

This module is the single source of truth for:
  - Section names and descriptions
  - Question number ranges per section
  - Maximum marks per question in each section
  - Full mark totals per section
  - Board-level metadata

Usage:
    from .tn_board_sections import get_board_schema, auto_detect_board

Supported boards:
    "TN_STATE"   Tamil Nadu State Board (Samacheer Kalvi) Class 10, 11, 12
    "CBSE_TN"    CBSE schools in Tamil Nadu — standard CBSE blueprint
    "IGCSE_TN"   IGCSE / Cambridge International schools in Tamil Nadu
"""

import re as _re
from typing import Dict, List, Any, Optional


# ---------------------------------------------------------------------------
# MARK TEXT PARSER  (self-contained — no circular imports)
# ---------------------------------------------------------------------------
def parse_mark_text(text: str) -> Dict[str, Any]:
    """
    Parse a raw OCR text token into a structured mark.
    Handles:
      - slash / dash / empty → unattempted (score=0)
      - arithmetic subdivisions: "1+1", "2+2+1" → sum
      - plain integer or decimal marks
      - Tamil numeral prefix noise stripped
    """
    if not text:
        return {"raw": "/", "score": 0.0, "is_subdivision": False}
    t = text.strip()
    # Unattempted / absent / blank
    if not t or _re.fullmatch(r'[/\\|\-\u2014\u2013lLiI!.xX\u0B66]+', t):
        return {"raw": "/", "score": 0.0, "is_subdivision": False}
    # Strip Tamil OCR noise at start
    t = _re.sub(r'^[\u0B80-\u0BFF\s]+', '', t).strip()
    if not t:
        return {"raw": "/", "score": 0.0, "is_subdivision": False}
    # Arithmetic subdivision: 1+1+1, 2+2 …
    if "+" in t:
        parts = t.split("+")
        try:
            nums = [float(p.strip()) for p in parts if p.strip()]
            return {"raw": t, "score": sum(nums), "is_subdivision": True}
        except ValueError:
            pass
    m = _re.search(r'\d+(\.\d+)?', t)
    if m:
        val = float(m.group(0))
        return {"raw": str(int(val)) if val.is_integer() else str(val),
                "score": val, "is_subdivision": False}
    return {"raw": t, "score": 0.0, "is_subdivision": False}


# ---------------------------------------------------------------------------
# SECTION DEFINITION DATATYPE
# ---------------------------------------------------------------------------
def _section(
    name: str,
    label: str,
    q_from: int,
    q_to: int,
    marks_per_q: float,
    max_section_marks: float,
    description: str = ""
) -> Dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "qFrom": q_from,
        "qTo": q_to,
        "qCount": q_to - q_from + 1,
        "marksPerQuestion": marks_per_q,
        "maxSectionMarks": max_section_marks,
        "description": description
    }


# ---------------------------------------------------------------------------
# BOARD SCHEMAS
# ---------------------------------------------------------------------------

# ── TN State Board (Samacheer Kalvi) ────────────────────────────────────────
# Standard 100-mark answer paper (Class 10, 11, 12):
#   Part I   (Section A) : Q 1–15  — Choose the correct answer (1 mark each) = 15 marks
#   Part II  (Section B) : Q 16–24 — Very Short Answer (2 marks each)         = 18 marks
#   Part III (Section C) : Q 25–33 — Short Answer (3 marks each)              = 27 marks (9 answered out of options)
#   Part IV  (Section D) : Q 34–40 — Long Answer / Essay (5 marks each)       = 35 marks (7 answered out of options)
#   Grand Total          : up to 75 marks (core) or 100 marks depending on subject
#
# Note: actual booklet marks match the ANSWERED questions only; teacher
# records the mark for each attempted question and writes "/" for unattempted.

TN_STATE_BOARD_10 = {
    "boardId": "TN_STATE_10",
    "boardName": "Tamil Nadu State Board (Samacheer Kalvi) — Class 10",
    "totalMarks": 100,
    "layoutMode": "vertical",
    "sections": [
        _section("PART_I",   "Part I — Section A (Choose Correct Answer)",   1, 15, 1.0, 15,
                 "1-mark MCQ / objective questions"),
        _section("PART_II",  "Part II — Section B (Very Short Answer)",      16, 24, 2.0, 18,
                 "2-mark very short answer questions"),
        _section("PART_III", "Part III — Section C (Short Answer)",          25, 33, 3.0, 27,
                 "3-mark short answer questions"),
        _section("PART_IV",  "Part IV — Section D (Long Answer / Essay)",    34, 42, 5.0, 35,
                 "5-mark long answer / essay type"),
    ]
}

TN_STATE_BOARD_11 = {
    "boardId": "TN_STATE_11",
    "boardName": "Tamil Nadu State Board (Samacheer Kalvi) — Class 11",
    "totalMarks": 90,
    "layoutMode": "vertical",
    "sections": [
        _section("PART_I",   "Part I — Section A (Choose Correct Answer)",   1, 15, 1.0, 15,
                 "1-mark MCQ / objective questions"),
        _section("PART_II",  "Part II — Section B (Very Short Answer)",      16, 30, 2.0, 20,
                 "2-mark short answer questions"),
        _section("PART_III", "Part III — Section C (Short Answer)",          31, 45, 3.0, 40,
                 "3-mark short answer questions"),
        _section("PART_IV",  "Part IV — Section D (Long Answer / Essay)",    46, 60, 5.0, 35,
                 "5-mark essay questions"),
    ]
}

TN_STATE_BOARD_12 = {
    "boardId": "TN_STATE_12",
    "boardName": "Tamil Nadu State Board (Samacheer Kalvi) — Class 12",
    "totalMarks": 150,
    "layoutMode": "vertical",
    "sections": [
        _section("PART_I",   "Part I — Section A (Multiple Choice)",         1, 20, 1.0, 20,
                 "1-mark MCQ"),
        _section("PART_II",  "Part II — Section B (Very Short Answer)",      21, 30, 2.0, 20,
                 "2-mark very short answer"),
        _section("PART_III", "Part III — Section C (Short Answer)",          31, 40, 4.0, 40,
                 "4-mark short answer"),
        _section("PART_IV",  "Part IV — Section D (Long Answer)",            41, 50, 6.0, 60,
                 "6-mark long answer"),
        _section("PART_V",   "Part V — Section E (Essay)",                   51, 55, 10.0, 50,
                 "10-mark essay type"),
    ]
}

# Generic TN State (auto-fallback when class not specified)
TN_STATE_BOARD_GENERIC = {
    "boardId": "TN_STATE",
    "boardName": "Tamil Nadu State Board (Samacheer Kalvi)",
    "totalMarks": 100,
    "layoutMode": "vertical",
    "sections": [
        _section("PART_I",   "Part I — Section A (Choose Correct Answer)",   1, 15, 1.0, 15,
                 "1-mark objective questions"),
        _section("PART_II",  "Part II — Section B (Very Short Answer)",      16, 30, 2.0, 30,
                 "2-mark very short answer"),
        _section("PART_III", "Part III — Section C (Short Answer)",          31, 45, 3.0, 45,
                 "3-mark short answer"),
        _section("PART_IV",  "Part IV — Section D (Long Answer / Essay)",    46, 60, 5.0, 75,
                 "5-mark long answer / essay"),
    ]
}

# ── CBSE (TN affiliated) ─────────────────────────────────────────────────────
# CBSE 2024-25 standard 80-mark paper blueprint (common for TN CBSE schools):
#   Section A : Q 1–20   — MCQ / Assertion-Reason (1 mark each) = 20 marks
#   Section B : Q 21–26  — Very Short Answer (2 marks each)      = 12 marks
#   Section C : Q 27–31  — Short Answer (3 marks each)           = 15 marks
#   Section D : Q 32–33  — Case Study / Source (4 marks each)    = 8 marks
#   Section E : Q 34–36  — Long Answer (5 marks each)            = 15 marks
#   Grand Total                                                   = 70 marks (+ 30 internal)

CBSE_TN = {
    "boardId": "CBSE_TN",
    "boardName": "CBSE — Tamil Nadu Schools (Standard 80-mark Paper)",
    "totalMarks": 80,
    "layoutMode": "horizontal",
    "sections": [
        _section("SECTION_A", "Section A — MCQ / Assertion-Reason (1 mark)",  1, 20, 1.0, 20,
                 "1-mark multiple choice and assertion-reason"),
        _section("SECTION_B", "Section B — Very Short Answer (2 marks)",      21, 26, 2.0, 12,
                 "2-mark very short answer questions"),
        _section("SECTION_C", "Section C — Short Answer (3 marks)",           27, 31, 3.0, 15,
                 "3-mark short answer questions"),
        _section("SECTION_D", "Section D — Case Study (4 marks)",             32, 33, 4.0, 8,
                 "4-mark case-based / source-based questions"),
        _section("SECTION_E", "Section E — Long Answer (5 marks)",            34, 36, 5.0, 15,
                 "5-mark long answer questions"),
    ]
}

# ── IGCSE / Cambridge (TN Schools) ─────────────────────────────────────────
# Cambridge IGCSE Paper 1 (Multiple Choice) + Paper 2 (Extended Theory)
# typical combined mark sheet for TN IGCSE schools:
#   Paper 1 : Q 1–40  — MCQ (1 mark each)                       = 40 marks
#   Paper 2A: Q 1–20  — Structured / Short Response (2 marks)   = 40 marks
#   Paper 2B: Q 21–30 — Extended Writing (6 marks each)         = 60 marks
# (Recorded here as a flat sequential Q-list as the booklet presents them)

IGCSE_TN = {
    "boardId": "IGCSE_TN",
    "boardName": "IGCSE / Cambridge International — Tamil Nadu Schools",
    "totalMarks": 140,
    "layoutMode": "horizontal",
    "sections": [
        _section("PAPER_1",  "Paper 1 — Multiple Choice (1 mark)",            1, 40, 1.0, 40,
                 "1-mark MCQ Paper 1"),
        _section("PAPER_2A", "Paper 2 Part A — Structured Short (2 marks)",   41, 60, 2.0, 40,
                 "2-mark structured/short response"),
        _section("PAPER_2B", "Paper 2 Part B — Extended Writing (6 marks)",   61, 70, 6.0, 60,
                 "6-mark extended writing / essay"),
    ]
}


# ---------------------------------------------------------------------------
# REGISTRY
# ---------------------------------------------------------------------------
_REGISTRY: Dict[str, Dict[str, Any]] = {
    "TN_STATE":    TN_STATE_BOARD_GENERIC,
    "TN_STATE_10": TN_STATE_BOARD_10,
    "TN_STATE_11": TN_STATE_BOARD_11,
    "TN_STATE_12": TN_STATE_BOARD_12,
    "CBSE_TN":     CBSE_TN,
    "IGCSE_TN":    IGCSE_TN,
}


def get_board_schema(board_id: str) -> Dict[str, Any]:
    """Return the full board schema for the given board_id. Falls back to TN_STATE."""
    return _REGISTRY.get(board_id.upper(), TN_STATE_BOARD_GENERIC)


def list_boards() -> List[Dict[str, str]]:
    """List all registered board IDs and names."""
    return [{"boardId": v["boardId"], "boardName": v["boardName"]}
            for v in _REGISTRY.values()]


def auto_detect_board(total_q: int, layout_mode: str) -> Dict[str, Any]:
    """
    Heuristically pick the most likely board schema based on question count
    and layout mode.  The teacher can always override via the API.
    """
    if layout_mode == "vertical":
        if total_q <= 42:
            return TN_STATE_BOARD_GENERIC
        if total_q <= 55:
            return TN_STATE_BOARD_11
        return TN_STATE_BOARD_12
    else:
        # horizontal layouts → CBSE or IGCSE
        if total_q <= 36:
            return CBSE_TN
        return IGCSE_TN


def assign_sections_to_marks(
    marks_dict: Dict[int, Any],
    board_schema: Dict[str, Any],
    override_total_q: Optional[int] = None
) -> Dict[str, Any]:
    sections_list = list(board_schema["sections"])
    last_max_q = max(s["qTo"] for s in sections_list) if sections_list else 0
    if override_total_q is not None and override_total_q > last_max_q:
        sections_list.append(_section(
            "PART_EXTRA",
            f"Additional Questions (Q{last_max_q + 1} – Q{override_total_q})",
            last_max_q + 1,
            override_total_q,
            1.0,
            float(override_total_q - last_max_q),
            "Additional questions block"
        ))

    result_sections = []
    grand_total = 0.0

    for sec in sections_list:
        q_from = sec["qFrom"]
        q_to = sec["qTo"]
        if override_total_q is not None:
            if q_from > override_total_q:
                continue
            q_to = min(q_to, override_total_q)

        q_list = []
        scored = 0.0
        attempted = 0
        unattempted = 0

        for q_no in range(q_from, q_to + 1):
            raw_text = marks_dict.get(q_no, "/")
            parsed = parse_mark_text(str(raw_text))

            # Clamp to max marks per question (sanity guard)
            capped_score = min(parsed["score"], sec["marksPerQuestion"])

            if parsed["raw"] in ["/", "—", "-", ""] or (parsed["score"] == 0.0 and parsed["raw"] in ["/", "—"]):
                unattempted += 1
            else:
                attempted += 1

            scored += capped_score
            grand_total += capped_score

            q_list.append({
                "qNumber": q_no,
                "raw": parsed["raw"],
                "score": capped_score,
                "isSubdivision": parsed["is_subdivision"],
                "maxMarks": sec["marksPerQuestion"]
            })

        result_sections.append({
            "name": sec["name"],
            "label": sec["label"],
            "qFrom": sec["qFrom"],
            "qTo": sec["qTo"],
            "marksPerQuestion": sec["marksPerQuestion"],
            "maxSectionMarks": sec["maxSectionMarks"],
            "questions": q_list,
            "scoredMarks": round(scored, 2),
            "attemptedCount": attempted,
            "unattemptedCount": unattempted
        })

    return {
        "sections": result_sections,
        "grandTotal": round(grand_total, 2),
        "boardId": board_schema["boardId"],
        "boardName": board_schema["boardName"],
        "totalMarks": board_schema["totalMarks"]
    }
