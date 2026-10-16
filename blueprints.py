"""
Board Blueprint Registry — SaaS Answer Booklet Valuation System
================================================================
Defines rigid, standardized template blueprints for State Board, CBSE, ICSE,
and IGCSE answer booklets. Controls question grid coordinates, column geometry,
section mark allocations, page ranges, and evaluator total cell locations.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class QuestionGridColumn:
    column_index: int
    start_question: int
    end_question: int
    x_rel_start: float  # Relative position (0.0 - 1.0)
    x_rel_end: float
    y_rel_start: float
    y_rel_end: float


@dataclass
class SectionRule:
    id: str
    name: str
    label: str
    question_start: int
    question_end: int
    marks_per_question: float
    max_section_marks: float
    description: str = ""


@dataclass
class BoardBlueprint:
    board_id: str
    board_name: str
    class_name: str
    subject: str
    template_version: str
    layout_mode: str  # "vertical" or "horizontal"
    total_questions: int
    total_pages: int
    columns: List[QuestionGridColumn]
    sections: List[SectionRule]
    evaluator_total_location: Dict[str, float]  # relative bounding box
    page_grid_location: Optional[Dict[str, float]] = None


# ─────────────────────────────────────────────────────────────────────────────
# BLUEPRINT REGISTRY DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

# 1. Tamil Nadu State Board Class 10 (42 Questions)
# TN HSE booklet layout (portrait, ~460px wide at phone resolution):
#   Each question-pair column = [Q.No col | Marks col], 4 pairs side by side.
#   Evaluator total "Total Marks" box is at TOP-RIGHT of page.
#   Column geometry measured from actual TN HSE scan:
#     Col1 Q1-15:  ~x 6.5%–15%  of width
#     Col2 Q16-24: ~x 20%–28.5% of width
#     Col3 Q25-33: ~x 33.5%–42% of width
#     Col4 Q34-42: ~x 47%–55.5% of width
#   Grid starts: ~y 36% (after header rows), ends ~y 83%
TN_STATE_10_BLUEPRINT = BoardBlueprint(
    board_id="TN_STATE_10",
    board_name="Tamil Nadu State Board (Samacheer Kalvi) — Class 10",
    class_name="10",
    subject="General",
    template_version="1.0",
    layout_mode="vertical",
    total_questions=42,
    total_pages=1,
    columns=[
        QuestionGridColumn(1, 1, 15, 0.065, 0.155, 0.36, 0.84),
        QuestionGridColumn(2, 16, 24, 0.195, 0.290, 0.36, 0.84),
        QuestionGridColumn(3, 25, 33, 0.330, 0.425, 0.36, 0.84),
        QuestionGridColumn(4, 34, 42, 0.465, 0.560, 0.36, 0.84),
    ],
    sections=[
        SectionRule("part_1", "Part I", "Part I — Section A (Choose Correct Answer)", 1, 15, 1.0, 15.0, "1-mark MCQs"),
        SectionRule("part_2", "Part II", "Part II — Section B (Very Short Answer)", 16, 24, 2.0, 18.0, "2-mark Short Answer"),
        SectionRule("part_3", "Part III", "Part III — Section C (Short Answer)", 25, 33, 3.0, 27.0, "3-mark Short Answer"),
        SectionRule("part_4", "Part IV", "Part IV — Section D (Long Answer / Essay)", 34, 42, 5.0, 35.0, "5-mark Essays"),
    ],
    # "Total Marks" box is in TOP-RIGHT corner of TN HSE booklet
    evaluator_total_location={"x_start": 0.76, "x_end": 0.96, "y_start": 0.10, "y_end": 0.22}
)

# 2. Tamil Nadu State Board Class 11 (60 Questions)
# HSE First Year — same layout as Class 10 but Q16-30 (15 rows), Q31-45, Q46-60
TN_STATE_11_BLUEPRINT = BoardBlueprint(
    board_id="TN_STATE_11",
    board_name="Tamil Nadu State Board (Samacheer Kalvi) — Class 11",
    class_name="11",
    subject="General",
    template_version="1.0",
    layout_mode="vertical",
    total_questions=60,
    total_pages=1,
    columns=[
        QuestionGridColumn(1, 1, 15, 0.065, 0.155, 0.35, 0.85),
        QuestionGridColumn(2, 16, 30, 0.195, 0.290, 0.35, 0.85),
        QuestionGridColumn(3, 31, 45, 0.330, 0.425, 0.35, 0.85),
        QuestionGridColumn(4, 46, 60, 0.465, 0.560, 0.35, 0.85),
    ],
    sections=[
        SectionRule("part_1", "Part I", "Part I — Section A (Multiple Choice)", 1, 15, 1.0, 15.0, "1-mark MCQ"),
        SectionRule("part_2", "Part II", "Part II — Section B (Very Short Answer)", 16, 30, 2.0, 20.0, "2-mark VSA"),
        SectionRule("part_3", "Part III", "Part III — Section C (Short Answer)", 31, 45, 3.0, 40.0, "3-mark SA"),
        SectionRule("part_4", "Part IV", "Part IV — Section D (Long Answer)", 46, 60, 5.0, 35.0, "5-mark LA"),
    ],
    # "Total Marks" box is in TOP-RIGHT corner of TN HSE booklet
    evaluator_total_location={"x_start": 0.76, "x_end": 0.96, "y_start": 0.10, "y_end": 0.22}
)

# 3. Tamil Nadu State Board Class 12 (60 Questions)
TN_STATE_12_BLUEPRINT = BoardBlueprint(
    board_id="TN_STATE_12",
    board_name="Tamil Nadu State Board (Samacheer Kalvi) — Class 12",
    class_name="12",
    subject="General",
    template_version="1.0",
    layout_mode="vertical",
    total_questions=60,
    total_pages=1,
    columns=[
        QuestionGridColumn(1, 1, 15, 0.065, 0.155, 0.35, 0.85),
        QuestionGridColumn(2, 16, 30, 0.195, 0.290, 0.35, 0.85),
        QuestionGridColumn(3, 31, 45, 0.330, 0.425, 0.35, 0.85),
        QuestionGridColumn(4, 46, 60, 0.465, 0.560, 0.35, 0.85),
    ],
    sections=[
        SectionRule("part_1", "Part I", "Part I — Section A (Multiple Choice)", 1, 15, 1.0, 15.0, "1-mark MCQ"),
        SectionRule("part_2", "Part II", "Part II — Section B (Very Short Answer)", 16, 30, 2.0, 20.0, "2-mark VSA"),
        SectionRule("part_3", "Part III", "Part III — Section C (Short Answer)", 31, 45, 3.0, 30.0, "3-mark SA"),
        SectionRule("part_4", "Part IV", "Part IV — Section D (Long Answer)", 46, 60, 5.0, 35.0, "5-mark LA"),
    ],
    # "Total Marks" box is in TOP-RIGHT corner of TN HSE booklet
    evaluator_total_location={"x_start": 0.76, "x_end": 0.96, "y_start": 0.10, "y_end": 0.22}
)

# 4. CBSE Board (38 Questions)
CBSE_TN_BLUEPRINT = BoardBlueprint(
    board_id="CBSE_TN",
    board_name="Central Board of Secondary Education (CBSE)",
    class_name="10/12",
    subject="General",
    template_version="1.0",
    layout_mode="horizontal",
    total_questions=38,
    total_pages=1,
    columns=[
        QuestionGridColumn(1, 1, 10, 0.05, 0.95, 0.15, 0.35),
        QuestionGridColumn(2, 11, 20, 0.05, 0.95, 0.35, 0.55),
        QuestionGridColumn(3, 21, 30, 0.05, 0.95, 0.55, 0.75),
        QuestionGridColumn(4, 31, 38, 0.05, 0.95, 0.75, 0.90),
    ],
    sections=[
        SectionRule("sec_a", "Section A", "Section A (Objective / MCQs)", 1, 20, 1.0, 20.0, "Objective Q1-Q20"),
        SectionRule("sec_b", "Section B", "Section B (Very Short Answer)", 21, 25, 2.0, 10.0, "Short Answer Q21-Q25"),
        SectionRule("sec_c", "Section C", "Section C (Short Answer)", 26, 31, 3.0, 18.0, "Short Answer Q26-Q31"),
        SectionRule("sec_d", "Section D", "Section D (Long Answer)", 32, 35, 5.0, 20.0, "Long Answer Q32-Q35"),
        SectionRule("sec_e", "Section E", "Section E (Case-based)", 36, 38, 4.0, 12.0, "Case Study Q36-Q38"),
    ],
    evaluator_total_location={"x_start": 0.70, "x_end": 0.95, "y_start": 0.88, "y_end": 0.98}
)

# 5. IGCSE Board (30 Questions)
IGCSE_TN_BLUEPRINT = BoardBlueprint(
    board_id="IGCSE_TN",
    board_name="Cambridge IGCSE International",
    class_name="10",
    subject="General",
    template_version="1.0",
    layout_mode="horizontal",
    total_questions=30,
    total_pages=1,
    columns=[
        QuestionGridColumn(1, 1, 10, 0.05, 0.95, 0.15, 0.40),
        QuestionGridColumn(2, 11, 20, 0.05, 0.95, 0.40, 0.65),
        QuestionGridColumn(3, 21, 30, 0.05, 0.95, 0.65, 0.90),
    ],
    sections=[
        SectionRule("core", "Core Section", "Core Questions 1-15", 1, 15, 2.0, 30.0, "Core Paper"),
        SectionRule("extended", "Extended Section", "Extended Questions 16-30", 16, 30, 4.0, 60.0, "Extended Paper"),
    ],
    evaluator_total_location={"x_start": 0.70, "x_end": 0.95, "y_start": 0.88, "y_end": 0.98}
)

_BLUEPRINTS: Dict[str, BoardBlueprint] = {
    "TN_STATE_10": TN_STATE_10_BLUEPRINT,
    "TN_STATE_11": TN_STATE_11_BLUEPRINT,
    "TN_STATE_12": TN_STATE_12_BLUEPRINT,
    "TN_STATE": TN_STATE_10_BLUEPRINT,  # default alias
    "CBSE_TN": CBSE_TN_BLUEPRINT,
    "IGCSE_TN": IGCSE_TN_BLUEPRINT,
}


def get_blueprint(board_id: Optional[str]) -> BoardBlueprint:
    """Retrieve a registered board blueprint or fallback to TN_STATE_10."""
    if not board_id:
        return TN_STATE_10_BLUEPRINT
    return _BLUEPRINTS.get(board_id, TN_STATE_10_BLUEPRINT)


def list_blueprints() -> List[Dict[str, Any]]:
    """Return summary metadata for all registered blueprints."""
    return [
        {
            "board_id": b.board_id,
            "board_name": b.board_name,
            "class_name": b.class_name,
            "total_questions": b.total_questions,
            "layout_mode": b.layout_mode,
            "sections": [
                {
                    "id": s.id,
                    "name": s.name,
                    "label": s.label,
                    "question_start": s.question_start,
                    "question_end": s.question_end,
                    "marks_per_question": s.marks_per_question,
                    "max_section_marks": s.max_section_marks
                }
                for s in b.sections
            ]
        }
        for b in [TN_STATE_10_BLUEPRINT, TN_STATE_11_BLUEPRINT, TN_STATE_12_BLUEPRINT, CBSE_TN_BLUEPRINT, IGCSE_TN_BLUEPRINT]
    ]
