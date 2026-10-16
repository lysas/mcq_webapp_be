"""
Excel Workbook Generator — Tamil Nadu Board Edition
====================================================
Generates a rigorous, section-wise multi-sheet Excel workbook.

Sheets produced:
  1.  Class Master Sheet       — one row per student, section subtotals
  2.  Part I  / Section A      — dedicated sheet for every board section
  3.  Part II / Section B      — ...
  4.  Part III / Section C     — ...
  5.  Part IV / Section D      — ...
  (additional sections appended dynamically)
  N-1. Question Analytics      — difficulty analysis per question
  N.   Official Evaluator Ledger — evaluator-facing mark ledger

Supports TN State Board (Samacheer Kalvi), CBSE (TN schools), IGCSE (TN).
"""

import io
import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter
from openpyxl.styles.numbers import FORMAT_NUMBER_00
from typing import List, Dict, Any, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Style constants  (no UI colour changes — purely internal Excel formatting)
# ─────────────────────────────────────────────────────────────────────────────
_F_HEADER    = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
_F_BOLD      = Font(name="Calibri", size=11, bold=True)
_F_BOLD_NAVY = Font(name="Calibri", size=11, bold=True, color="1B2A5C")
_F_SECTION   = Font(name="Calibri", size=10, bold=True, color="1B2A5C")
_F_NORMAL    = Font(name="Calibri", size=10)
_F_ITALIC    = Font(name="Calibri", size=10, italic=True, color="57606A")

_FILL_NAVY     = PatternFill(start_color="181D38", end_color="181D38", fill_type="solid")
_FILL_SECTION  = PatternFill(start_color="2B4590", end_color="2B4590", fill_type="solid")
_FILL_SUBTOTAL = PatternFill(start_color="E8EFF9", end_color="E8EFF9", fill_type="solid")
_FILL_VERIFIED = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
_FILL_MISMATCH = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
_FILL_GREY     = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")
_FILL_YELLOW   = PatternFill(start_color="FEFCE8", end_color="FEFCE8", fill_type="solid")
_FILL_PART_A   = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")
_FILL_PART_B   = PatternFill(start_color="F0FDF4", end_color="F0FDF4", fill_type="solid")
_FILL_PART_C   = PatternFill(start_color="FFF7ED", end_color="FFF7ED", fill_type="solid")
_FILL_PART_D   = PatternFill(start_color="FDF4FF", end_color="FDF4FF", fill_type="solid")
_FILL_PART_E   = PatternFill(start_color="FFF1F2", end_color="FFF1F2", fill_type="solid")

_SECTION_FILLS = [_FILL_PART_A, _FILL_PART_B, _FILL_PART_C, _FILL_PART_D, _FILL_PART_E]

_ALIGN_C  = Alignment(horizontal="center", vertical="center", wrap_text=True)
_ALIGN_L  = Alignment(horizontal="left",   vertical="center", wrap_text=True)
_ALIGN_R  = Alignment(horizontal="right",  vertical="center")

def _thin_border(color: str = "C7D0DC") -> Border:
    s = Side(style="thin", color=color)
    return Border(left=s, right=s, top=s, bottom=s)

def _medium_border(color: str = "8DA4C4") -> Border:
    s = Side(style="medium", color=color)
    return Border(left=s, right=s, top=s, bottom=s)

_BORDER = _thin_border()
_BORDER_M = _medium_border()


# ─────────────────────────────────────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────────────────────────────────────
def _auto_col_widths(ws, min_w: int = 8, max_w: int = 40) -> None:
    for col in ws.columns:
        max_len = 0
        for cell in col:
            if cell.value is not None:
                val_str = str(cell.value)
                max_len = max(max_len, len(val_str))
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max(max_len + 2, min_w), max_w)


def _style_header_row(ws, row: int, n_cols: int,
                       fill=None, font=None, align=None) -> None:
    fill  = fill  or _FILL_NAVY
    font  = font  or _F_HEADER
    align = align or _ALIGN_C
    for c in range(1, n_cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font   = font
        cell.fill   = fill
        cell.alignment = align
        cell.border = _BORDER


def _style_data_row(ws, row: int, n_cols: int,
                     fill=None, font=None) -> None:
    fill = fill or PatternFill(fill_type=None)
    font = font or _F_NORMAL
    for c in range(1, n_cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font      = font
        cell.fill      = fill
        cell.alignment = _ALIGN_C
        cell.border    = _BORDER


def _write_row(ws, row: int, values: List[Any]) -> None:
    for c, v in enumerate(values, start=1):
        ws.cell(row=row, column=c).value = v


def _section_fill(section_index: int) -> PatternFill:
    return _SECTION_FILLS[section_index % len(_SECTION_FILLS)]


def _collect_sections(students: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract unique sections from student data (using first student as reference)."""
    for s in students:
        if s.get("rows"):
            return s["rows"]
    return []


def _get_section_names(rows: List[Dict[str, Any]]) -> List[str]:
    return [r.get("label", f"Section {i+1}") for i, r in enumerate(rows)]


# ─────────────────────────────────────────────────────────────────────────────
# SHEET BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_class_master_sheet(wb: openpyxl.Workbook,
                               students: List[Dict[str, Any]],
                               board_name: str) -> None:
    """
    Sheet 1: Class Master Sheet
    Columns: Sl No | Reg No | Subject | Code | Medium | Board |
             [Section A Total] [Section B Total] ... | Grand Total |
             Evaluator Total | Match | Status
    """
    ws = wb.active
    ws.title = "Class Master Sheet"
    ws.freeze_panes = "A2"

    ref_rows = _collect_sections(students)
    section_labels = _get_section_names(ref_rows)

    # Row 1 — Title banner
    total_cols = 6 + len(section_labels) + 4
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
    title_cell = ws.cell(row=1, column=1,
                         value=f"CLASS MARKS MASTER SHEET  |  {board_name}")
    title_cell.font      = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
    title_cell.fill      = _FILL_NAVY
    title_cell.alignment = _ALIGN_C
    title_cell.border    = _BORDER
    ws.row_dimensions[1].height = 28

    # Row 2 — Headers
    headers = ["Sl No", "Register No", "Subject", "Code", "Medium", "Board"]
    for lbl in section_labels:
        headers.append(f"{lbl}\nMax: {ref_rows[section_labels.index(lbl)].get('maxSectionMarks', '—')}")
    headers += ["Grand Total", "Evaluator Total", "Match", "Status"]

    _write_row(ws, 2, headers)
    _style_header_row(ws, 2, len(headers))
    ws.row_dimensions[2].height = 36

    # Data rows
    for s_idx, std in enumerate(students, start=1):
        row_vals = [
            s_idx,
            std.get("regNo", ""),
            std.get("subject", ""),
            std.get("subjectCode", ""),
            std.get("medium", ""),
            std.get("boardId", std.get("boardName", "TN State Board"))
        ]

        for r in std.get("rows", []):
            row_vals.append(r.get("subtotalComputed", 0.0))

        row_vals += [
            std.get("grandTotalComputed", 0.0),
            std.get("evaluatorTotalFigures", 0.0),
            "✓ MATCH" if std.get("isVerified") else "✗ MISMATCH",
            "APPROVED" if std.get("isApproved") else "PENDING"
        ]

        data_row = 2 + s_idx
        _write_row(ws, data_row, row_vals)

        # Colour-code status/match
        verified     = std.get("isVerified", False)
        match_fill   = _FILL_VERIFIED if verified else _FILL_MISMATCH
        row_base_fill = _FILL_GREY if s_idx % 2 == 0 else PatternFill(fill_type=None)
        _style_data_row(ws, data_row, len(row_vals), fill=row_base_fill)

        # Re-style match + status columns
        n = len(row_vals)
        for ci in [n - 1, n]:
            cell = ws.cell(row=data_row, column=ci)
            cell.fill      = match_fill
            cell.font      = _F_SECTION
            cell.alignment = _ALIGN_C
            cell.border    = _BORDER

        # Section subtotal columns — use section fills
        for si in range(len(section_labels)):
            cell = ws.cell(row=data_row, column=7 + si)
            cell.fill      = _section_fill(si)
            cell.font      = _F_BOLD_NAVY
            cell.alignment = _ALIGN_C

        ws.row_dimensions[data_row].height = 18

    _auto_col_widths(ws)
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 16


def _build_section_sheet(wb: openpyxl.Workbook,
                          section_row: Dict[str, Any],
                          section_index: int,
                          students: List[Dict[str, Any]],
                          board_name: str) -> None:
    """
    One dedicated sheet per board section (Part I, Part II, etc.).
    Columns: Sl No | Reg No | Q{from} | Q{from+1} | ... | Q{to} |
             Attempted | Unattempted | Section Total | Max Marks | %
    """
    label     = section_row.get("label", f"Section {section_index + 1}")
    q_from    = section_row.get("start", 1)
    q_to      = section_row.get("end",   10)
    max_marks = section_row.get("maxSectionMarks", 0)
    marks_pq  = section_row.get("marksPerQuestion", 1.0)

    # Sheet name: trim to Excel 31-char limit
    sheet_name = label[:28].replace("—", "-").replace("/", "|").strip()
    ws = wb.create_sheet(title=sheet_name)
    ws.freeze_panes = "A2"

    q_range = list(range(q_from, q_to + 1))
    total_cols = 2 + len(q_range) + 4

    # Row 1 — Section banner
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
    banner = ws.cell(row=1, column=1,
                     value=(f"{label}  |  Marks/Question: {marks_pq}  |  "
                            f"Max Section Marks: {max_marks}  |  {board_name}"))
    banner.font      = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
    banner.fill      = _FILL_SECTION
    banner.alignment = _ALIGN_C
    ws.row_dimensions[1].height = 26

    # Row 2 — Headers
    headers = ["Sl No", "Reg No"]
    for q in q_range:
        headers.append(f"Q{q}\n(/{marks_pq})")
    headers += ["Attempted", "Not Attempted", "Section Total", "% Scored"]

    _write_row(ws, 2, headers)
    # Use section-specific fill for header
    sec_fill = PatternFill(start_color="2B4590", end_color="2B4590", fill_type="solid")
    _style_header_row(ws, 2, len(headers), fill=sec_fill)
    ws.row_dimensions[2].height = 32

    # Data rows
    for s_idx, std in enumerate(students, start=1):
        # Find the matching section row for this student
        target_row = None
        for r in std.get("rows", []):
            if r.get("start") == q_from and r.get("end") == q_to:
                target_row = r
                break
        if target_row is None:
            # Fallback: match by label
            for r in std.get("rows", []):
                if r.get("label", "") == label:
                    target_row = r
                    break

        data_row_num = 2 + s_idx
        row_fill = _section_fill(section_index) if s_idx % 2 == 0 else PatternFill(fill_type=None)

        row_vals: List[Any] = [s_idx, std.get("regNo", "")]

        if target_row:
            q_map = {q["qNumber"]: q for q in target_row.get("questions", [])}
            for q in q_range:
                if q in q_map:
                    item = q_map[q]
                    raw = item.get("raw", "/")
                    score = item.get("score", 0.0)
                    # Show "raw (score)" if subdivision, else just raw
                    display = f"{raw} = {score}" if item.get("isSubdivision") else raw
                    row_vals.append(display)
                else:
                    row_vals.append("/")

            sec_total   = target_row.get("subtotalComputed", 0.0)
            attempted   = target_row.get("attemptedCount",   0)
            unattempted = target_row.get("unattemptedCount", 0)
        else:
            row_vals += ["/"] * len(q_range)
            sec_total   = 0.0
            attempted   = 0
            unattempted = len(q_range)

        pct = round(sec_total / max_marks * 100, 1) if max_marks > 0 else 0.0
        row_vals += [attempted, unattempted, sec_total, f"{pct}%"]

        _write_row(ws, data_row_num, row_vals)
        _style_data_row(ws, data_row_num, len(row_vals), fill=row_fill)

        # Highlight cells: green if scored full marks per q, red if 0
        for ci, q in enumerate(q_range, start=3):
            cell = ws.cell(row=data_row_num, column=ci)
            val_str = str(cell.value or "/")
            # Extract score from display
            score_val = 0.0
            if target_row:
                q_map2 = {q2["qNumber"]: q2 for q2 in target_row.get("questions", [])}
                if q in q_map2:
                    score_val = float(q_map2[q].get("score", 0.0))
            if score_val >= marks_pq:
                cell.fill = _FILL_VERIFIED
            elif score_val == 0.0 and val_str not in ["/", "—"]:
                cell.fill = _FILL_MISMATCH

        # Total column highlight
        tc = 2 + len(q_range) + 3
        total_cell = ws.cell(row=data_row_num, column=tc)
        total_cell.font = _F_BOLD_NAVY
        total_cell.fill = _FILL_SUBTOTAL

        ws.row_dimensions[data_row_num].height = 16

    # Summary row at bottom
    summary_row = 2 + len(students) + 2
    ws.merge_cells(start_row=summary_row, start_column=1, end_row=summary_row, end_column=2)
    ws.cell(row=summary_row, column=1, value="CLASS AVERAGES").font = _F_BOLD

    avg_cols_start = 3
    for qi, q in enumerate(q_range):
        scores = []
        for std in students:
            for r in std.get("rows", []):
                if r.get("start") == q_from:
                    q_map_a = {qd["qNumber"]: qd for qd in r.get("questions", [])}
                    if q in q_map_a:
                        scores.append(float(q_map_a[q].get("score", 0.0)))
        avg_val = round(sum(scores) / len(scores), 2) if scores else 0.0
        c = ws.cell(row=summary_row, column=avg_cols_start + qi, value=avg_val)
        c.font = _F_BOLD_NAVY
        c.fill = _FILL_SUBTOTAL
        c.alignment = _ALIGN_C
        c.border = _BORDER

    # Section-level stats
    total_col = 2 + len(q_range) + 3
    sec_totals = []
    for std in students:
        for r in std.get("rows", []):
            if r.get("start") == q_from:
                sec_totals.append(float(r.get("subtotalComputed", 0.0)))
    class_avg = round(sum(sec_totals) / len(sec_totals), 2) if sec_totals else 0.0
    c2 = ws.cell(row=summary_row, column=total_col, value=class_avg)
    c2.font = _F_BOLD_NAVY; c2.fill = _FILL_SUBTOTAL
    c2.alignment = _ALIGN_C; c2.border = _BORDER_M

    _auto_col_widths(ws)
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 16


def _build_question_analytics_sheet(wb: openpyxl.Workbook,
                                     students: List[Dict[str, Any]],
                                     board_name: str) -> None:
    """
    Question Analytics Sheet: per-question difficulty and class performance.
    Includes section grouping.
    """
    ws = wb.create_sheet(title="Question Analytics")
    ws.freeze_panes = "A3"

    ref_rows = _collect_sections(students)

    headers = [
        "Section", "Q No", "Max Marks",
        "Attempts", "Not Attempted",
        "Class Total Scored", "Class Average",
        "Highest Score", "Lowest Score (excl 0)",
        "Difficulty Level"
    ]

    # Title
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    t = ws.cell(row=1, column=1, value=f"QUESTION ANALYTICS  |  {board_name}")
    t.font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
    t.fill = _FILL_NAVY; t.alignment = _ALIGN_C
    ws.row_dimensions[1].height = 24

    _write_row(ws, 2, headers)
    _style_header_row(ws, 2, len(headers))
    ws.row_dimensions[2].height = 24

    n_students = len(students)
    data_row = 3

    for sec_idx, sec_row in enumerate(ref_rows):
        q_from  = sec_row.get("start", 1)
        q_to    = sec_row.get("end",   10)
        sec_lbl = sec_row.get("label", f"Section {sec_idx+1}")
        marks_pq = float(sec_row.get("marksPerQuestion", 1.0))
        sfill    = _section_fill(sec_idx)

        for q in range(q_from, q_to + 1):
            attempts = 0
            blanks   = 0
            scores   = []

            for std in students:
                for r in std.get("rows", []):
                    if r.get("start") == q_from:
                        for item in r.get("questions", []):
                            if item.get("qNumber") == q:
                                sc  = float(item.get("score", 0.0))
                                raw = str(item.get("raw", "/"))
                                if raw in ["/", "—", "-", ""] and sc == 0.0:
                                    blanks += 1
                                else:
                                    attempts += 1
                                    scores.append(sc)

            total_scored = round(sum(scores), 2)
            avg_score    = round(total_scored / n_students, 2) if n_students > 0 else 0.0
            highest      = max(scores) if scores else 0.0
            non_zero     = [s for s in scores if s > 0]
            lowest_nz    = min(non_zero) if non_zero else 0.0
            pct_avg      = avg_score / marks_pq if marks_pq > 0 else 0.0
            difficulty   = (
                "Not Attempted" if attempts == 0
                else ("Easy" if pct_avg >= 0.75 else
                      ("Moderate" if pct_avg >= 0.40 else "Hard"))
            )

            row_vals = [
                sec_lbl, f"Q{q}", marks_pq,
                attempts, blanks,
                total_scored, avg_score,
                highest, lowest_nz,
                difficulty
            ]
            _write_row(ws, data_row, row_vals)
            _style_data_row(ws, data_row, len(row_vals), fill=sfill)

            # Difficulty colour
            diff_cell = ws.cell(row=data_row, column=len(headers))
            if difficulty == "Easy":
                diff_cell.fill = _FILL_VERIFIED
            elif difficulty == "Hard":
                diff_cell.fill = _FILL_MISMATCH
            elif difficulty == "Moderate":
                diff_cell.fill = _FILL_YELLOW

            ws.row_dimensions[data_row].height = 15
            data_row += 1

    _auto_col_widths(ws)


def _build_evaluator_ledger_sheet(wb: openpyxl.Workbook,
                                   students: List[Dict[str, Any]],
                                   board_name: str) -> None:
    """
    Official Evaluator Ledger:
    Board-style printable ledger with section-wise marks per student.
    """
    ws = wb.create_sheet(title="Official Evaluator Ledger")

    ws.merge_cells("A1:F1")
    t = ws.cell(row=1, column=1,
                value=f"OFFICIAL EVALUATOR MARKS LEDGER  |  {board_name}")
    t.font = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
    t.fill = _FILL_NAVY; t.alignment = _ALIGN_C
    ws.row_dimensions[1].height = 28

    ws.cell(row=2, column=1, value="FOR THE USE OF EVALUATORS ONLY — DO NOT DISTRIBUTE")
    ws.cell(row=2, column=1).font = Font(name="Calibri", size=9, italic=True, color="CC0000")
    ws.row_dimensions[2].height = 14

    cur_row = 4
    for s_idx, std in enumerate(students):
        # Student meta header
        meta_cols = [
            f"#{s_idx + 1}",
            f"Reg No: {std.get('regNo', 'N/A')}",
            f"Subject: {std.get('subject', 'N/A')} ({std.get('subjectCode', '')})",
            f"Medium: {std.get('medium', 'N/A')}",
            f"Board: {std.get('boardId', 'TN')}",
            f"Grand Total: {std.get('grandTotalComputed', 0.0)}  |  "
            f"Eval: {std.get('evaluatorTotalFigures', 0.0)}  |  "
            f"Words: {std.get('evaluatorTotalWords', '')}"
        ]
        _write_row(ws, cur_row, meta_cols)
        for c in range(1, 7):
            cell = ws.cell(row=cur_row, column=c)
            cell.font = _F_BOLD
            cell.fill = _FILL_SUBTOTAL
            cell.alignment = _ALIGN_L
            cell.border = _BORDER_M
        ws.row_dimensions[cur_row].height = 20
        cur_row += 1

        # Per-section rows
        for sec_idx, r in enumerate(std.get("rows", [])):
            sfill   = _section_fill(sec_idx)
            sec_lbl = r.get("label", f"Section {sec_idx + 1}")
            qs      = r.get("questions", [])

            # Section label row
            ws.merge_cells(start_row=cur_row, start_column=1,
                           end_row=cur_row, end_column=max(len(qs) + 1, 2))
            lbl_cell = ws.cell(row=cur_row, column=1, value=sec_lbl)
            lbl_cell.font = Font(name="Calibri", size=10, bold=True, color="1B2A5C")
            lbl_cell.fill = sfill
            lbl_cell.alignment = _ALIGN_L
            lbl_cell.border = _BORDER
            ws.row_dimensions[cur_row].height = 16
            cur_row += 1

            # Q-number header sub-row
            q_header = [f"Q{q['qNumber']}" for q in qs] + ["Subtotal", "Max"]
            _write_row(ws, cur_row, q_header)
            for c in range(1, len(q_header) + 1):
                cell = ws.cell(row=cur_row, column=c)
                cell.font = _F_SECTION
                cell.fill = _FILL_SECTION
                cell.font = Font(name="Calibri", size=9, bold=True, color="FFFFFF")
                cell.alignment = _ALIGN_C
                cell.border = _BORDER
            ws.row_dimensions[cur_row].height = 14
            cur_row += 1

            # Marks row
            marks_row = [str(q.get("raw", "/")) for q in qs] + [
                r.get("subtotalComputed", 0.0),
                r.get("maxSectionMarks", "—")
            ]
            _write_row(ws, cur_row, marks_row)
            for c in range(1, len(marks_row) + 1):
                cell = ws.cell(row=cur_row, column=c)
                cell.font = _F_BOLD if c > len(qs) else _F_NORMAL
                cell.fill = _FILL_SUBTOTAL if c > len(qs) else sfill
                cell.alignment = _ALIGN_C
                cell.border = _BORDER
            ws.row_dimensions[cur_row].height = 18
            cur_row += 1

        # Grand total summary row
        gt_row = [
            "GRAND TOTAL",
            std.get("grandTotalComputed", 0.0),
            f"In Words: {std.get('evaluatorTotalWords', '')}",
            "",
            "Status",
            "APPROVED" if std.get("isApproved") else "PENDING"
        ]
        _write_row(ws, cur_row, gt_row)
        for c in range(1, 7):
            cell = ws.cell(row=cur_row, column=c)
            cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            cell.fill = _FILL_NAVY
            cell.alignment = _ALIGN_C
            cell.border = _BORDER_M
        ws.row_dimensions[cur_row].height = 20
        cur_row += 2   # blank line between students

    _auto_col_widths(ws, max_w=50)


def _build_section_summary_sheet(wb: openpyxl.Workbook,
                                  students: List[Dict[str, Any]],
                                  board_name: str) -> None:
    """
    Cross-section summary: class average per section, pass rates, topper info.
    """
    ws = wb.create_sheet(title="Section Summary")

    ref_rows = _collect_sections(students)
    n = len(students)

    # Title
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=9)
    t = ws.cell(row=1, column=1, value=f"SECTION-WISE CLASS PERFORMANCE SUMMARY  |  {board_name}")
    t.font = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
    t.fill = _FILL_NAVY; t.alignment = _ALIGN_C
    ws.row_dimensions[1].height = 28

    headers = [
        "Section", "Q Range", "Marks/Q", "Max Marks",
        "Class Total", "Class Average", "Highest Score",
        "Pass Rate (≥50%)", "Performance"
    ]
    _write_row(ws, 2, headers)
    _style_header_row(ws, 2, len(headers))
    ws.row_dimensions[2].height = 22

    for si, sec_row in enumerate(ref_rows):
        q_from  = sec_row.get("start", 1)
        sec_lbl = sec_row.get("label", f"Section {si + 1}")
        max_m   = float(sec_row.get("maxSectionMarks", 0))

        totals = []
        for std in students:
            for r in std.get("rows", []):
                if r.get("start") == q_from:
                    totals.append(float(r.get("subtotalComputed", 0.0)))

        class_total = round(sum(totals), 2)
        class_avg   = round(class_total / n, 2) if n > 0 else 0.0
        highest     = max(totals) if totals else 0.0
        pass_rate   = round(sum(1 for t in totals if max_m > 0 and t / max_m >= 0.5) / n * 100, 1) if n > 0 else 0.0
        pct_avg     = class_avg / max_m if max_m > 0 else 0.0
        performance = ("Excellent" if pct_avg >= 0.75 else
                       ("Good" if pct_avg >= 0.60 else
                        ("Average" if pct_avg >= 0.40 else "Needs Attention")))

        row_vals = [
            sec_lbl,
            f"Q{sec_row.get('start')} – Q{sec_row.get('end')}",
            sec_row.get("marksPerQuestion", 1.0),
            max_m, class_total, class_avg, highest,
            f"{pass_rate}%", performance
        ]
        data_row = 2 + si + 1
        _write_row(ws, data_row, row_vals)
        sfill = _section_fill(si)
        _style_data_row(ws, data_row, len(row_vals), fill=sfill)

        # Performance cell colour
        perf_cell = ws.cell(row=data_row, column=9)
        if performance == "Excellent":
            perf_cell.fill = _FILL_VERIFIED
        elif performance in ["Needs Attention"]:
            perf_cell.fill = _FILL_MISMATCH
        elif performance == "Good":
            perf_cell.fill = _FILL_PART_B

        ws.row_dimensions[data_row].height = 18

    _auto_col_widths(ws)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def create_single_sheet_excel_workbook(students: List[Dict[str, Any]]) -> io.BytesIO:
    """
    Generates a single-sheet Excel workbook as required by SaaS production spec:
      - ONE WORKBOOK
      - ONE WORKSHEET named 'Results'
      - ONE ROW PER STUDENT
      - Columns: Student Meta | Q1..Qn | Section Totals | Qwise Total | Pwise Total | Evaluator Total | Diff | Status | Review Req
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Results"

    if not students:
        ws["A1"] = "No student data available"
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    sample = students[0]
    total_q = sample.get("totalQuestions", 42)
    ref_rows = _collect_sections(students)
    sec_names = [r.get("label", f"Section {i+1}") for i, r in enumerate(ref_rows)]

    # Headers
    headers = ["#", "Register No", "Student Name", "Subject", "Code", "Medium", "Board"]
    for q in range(1, total_q + 1):
        headers.append(f"Q{q}")
    for sec_lbl in sec_names:
        headers.append(f"{sec_lbl} Total")
    headers += [
        "Questionwise Total",
        "Pagewise Total",
        "Evaluator Total",
        "Difference",
        "Verification Status",
        "Review Required"
    ]

    _write_row(ws, 1, headers)
    _style_header_row(ws, 1, len(headers))
    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "C2"

    for idx, std in enumerate(students, start=1):
        q_marks: Dict[int, str] = {}
        for r in std.get("rows", []):
            for q in r.get("questions", []):
                q_marks[q["qNumber"]] = str(q.get("raw", "/"))

        row_vals = [
            idx,
            std.get("regNo", "000000"),
            std.get("studentName", "Student " + str(idx)),
            std.get("subject", "General"),
            std.get("subjectCode", "01"),
            std.get("medium", "English"),
            std.get("boardId", "TN_STATE_10")
        ]

        for q in range(1, total_q + 1):
            row_vals.append(q_marks.get(q, "/"))

        for r in std.get("rows", []):
            row_vals.append(float(r.get("subtotalComputed", 0.0)))

        q_tot = float(std.get("grandTotalComputed", 0.0))
        p_tot = float(std.get("pagewiseTotal", q_tot))
        e_tot = float(std.get("evaluatorTotalFigures", q_tot))
        diff = round(abs(q_tot - e_tot), 2)
        is_ver = bool(std.get("isVerified", True))
        rev_req = bool(std.get("reviewRequired", not is_ver))

        row_vals += [
            q_tot,
            p_tot,
            e_tot,
            diff,
            "VERIFIED" if is_ver else "MISMATCH",
            "YES" if rev_req else "NO"
        ]

        row_idx = idx + 1
        _write_row(ws, row_idx, row_vals)

        row_fill = _FILL_GREY if idx % 2 == 0 else PatternFill(fill_type=None)
        _style_data_row(ws, row_idx, len(row_vals), fill=row_fill)

        # Highlight verification status column
        status_col_idx = len(headers) - 1
        status_cell = ws.cell(row=row_idx, column=status_col_idx)
        status_cell.fill = _FILL_VERIFIED if is_ver else _FILL_MISMATCH
        status_cell.font = _F_BOLD

        ws.row_dimensions[row_idx].height = 20

    _auto_col_widths(ws, max_w=45)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def create_excel_workbook(students: List[Dict[str, Any]]) -> io.BytesIO:
    """
    Generates a complete section-wise multi-sheet Excel workbook.

    Sheet order:
      1. Class Master Sheet
      2. [One sheet per board section — Part I, Part II, ...]
      3. Section Summary
      4. Question Analytics
      5. Official Evaluator Ledger
    """
    wb = openpyxl.Workbook()

    if not students:
        ws = wb.active
        ws.title = "Empty"
        ws["A1"] = "No student data available"
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    board_name = (students[0].get("boardName")
                  or students[0].get("boardId")
                  or "Tamil Nadu Board")

    ref_rows = _collect_sections(students)

    # ── Sheet 1: Class Master ──────────────────────────────────────────────────
    _build_class_master_sheet(wb, students, board_name)

    # ── Sheets 2…N: One per section ───────────────────────────────────────────
    for si, sec_row in enumerate(ref_rows):
        _build_section_sheet(wb, sec_row, si, students, board_name)

    # ── Section Summary ────────────────────────────────────────────────────────
    _build_section_summary_sheet(wb, students, board_name)

    # ── Question Analytics ─────────────────────────────────────────────────────
    _build_question_analytics_sheet(wb, students, board_name)

    # ── Official Evaluator Ledger ──────────────────────────────────────────────
    _build_evaluator_ledger_sheet(wb, students, board_name)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
