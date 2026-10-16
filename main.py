"""
FastAPI Main Application Server — Tamil Nadu Board Edition
==========================================================
Connects OCR Engine, Section Schema Registry, Excel Generator, and Database.

KEY: /api/extract and /api/debug-extract are SYNC (def, not async) so FastAPI
     runs them in its built-in thread pool.  This means EasyOCR never blocks
     the event loop and asyncio.CancelledError is impossible.

Endpoints:
  GET  /api/health                    — Service health
  GET  /api/boards                    — List all supported board schemas
  POST /api/extract                   — Extract marks from uploaded image/PDF
  GET  /api/students                  — List all stored student records
  POST /api/export-excel              — Generate section-wise Excel workbook
  POST /api/export-section-excel      — Generate Excel for a specific board schema
  POST /api/debug-extract             — Diagnostic: OCR without DB persist
"""

import sys
import os
import io
import fitz  # PyMuPDF
import cv2
import numpy as np
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from dotenv import load_dotenv
load_dotenv()
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".env"))
if os.path.exists(env_path):
    load_dotenv(env_path)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database.database import get_db, init_db
from database.models import Student, QuestionMark, RowSubtotal, Batch

try:
    from .ocr_engine import extract_universal_booklet_marks
    from .excel_generator import create_excel_workbook
    from .tn_board_sections import list_boards, get_board_schema, assign_sections_to_marks
except (ImportError, ValueError):
    from ocr_engine import extract_universal_booklet_marks
    from excel_generator import create_excel_workbook
    from tn_board_sections import list_boards, get_board_schema, assign_sections_to_marks

app = FastAPI(
    title="Tamil Nadu Board Answer-Booklet Extraction API",
    description=(
        "Section-wise marks extraction and Excel generation for "
        "Tamil Nadu State Board (Samacheer Kalvi), CBSE, and IGCSE schools."
    ),
    version="3.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# ─────────────────────────────────────────────────────────────────────────────
# Shared helper: decode uploaded file → OpenCV BGR image
# ─────────────────────────────────────────────────────────────────────────────

def _decode_upload(content: bytes, filename: str) -> np.ndarray:
    """Convert raw file bytes (image or PDF) to an OpenCV BGR ndarray."""
    if filename.lower().endswith(".pdf"):
        doc  = fitz.open(stream=content, filetype="pdf")
        page = doc.load_page(0)
        pix  = page.get_pixmap(dpi=150)          # 150 dpi is plenty for OCR
        img  = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif pix.n == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        return img
    else:
        nparr = np.frombuffer(content, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)


# ─────────────────────────────────────────────────────────────────────────────
# Health & Board Info
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    has_gemini = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    return {
        "status": "healthy",
        "service": "Tamil Nadu Board Answer-Booklet Extraction System",
        "supportedBoards": ["TN_STATE", "TN_STATE_10", "TN_STATE_11",
                            "TN_STATE_12", "CBSE_TN", "IGCSE_TN"],
        "database": "SQLite connected",
        "geminiKeyDetected": has_gemini,
        "visionEngine": "Gemini 2.5 Flash Vision (Primary AI) + OpenCV/EasyOCR (Fallback)" if has_gemini else "OpenCV + EasyOCR (Local)",
        "excelEngine": "OpenPyXL Section-wise Multi-Sheet"
    }


@app.get("/api/boards")
def get_boards():
    """List all supported board schemas with section details."""
    boards = list_boards()
    detailed = []
    for b in boards:
        schema = get_board_schema(b["boardId"])
        detailed.append({
            "boardId": schema["boardId"],
            "boardName": schema["boardName"],
            "totalMarks": schema["totalMarks"],
            "layoutMode": schema["layoutMode"],
            "sections": [
                {
                    "name": s["name"],
                    "label": s["label"],
                    "qFrom": s["qFrom"],
                    "qTo": s["qTo"],
                    "marksPerQuestion": s["marksPerQuestion"],
                    "maxSectionMarks": s["maxSectionMarks"],
                    "description": s["description"]
                }
                for s in schema["sections"]
            ]
        })
    return detailed


# ─────────────────────────────────────────────────────────────────────────────
# Main Extraction Endpoint  — SYNC so FastAPI threads it automatically
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/extract")
def extract_booklet(
    file: UploadFile = File(...),
    total_questions: Optional[int] = Form(None),
    custom_reg_no:   Optional[str] = Form(None),
    board_id:        Optional[str] = Form(None),
    layout_mode:     Optional[str] = Form(None),
    gemini_api_key:  Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Extract marks from an uploaded image or PDF answer booklet.
    Sync endpoint — FastAPI runs it in a thread pool automatically.
    """
    content  = file.file.read()
    filename = file.filename or "booklet.jpg"

    img_np = _decode_upload(content, filename)
    if img_np is None:
        raise HTTPException(status_code=400, detail="Cannot decode image or PDF.")

    data = extract_universal_booklet_marks(
        img_np,
        filename=filename,
        override_total_q=total_questions,
        layout_mode=layout_mode,
        board_id=board_id,
        gemini_api_key=gemini_api_key
    )

    if custom_reg_no:
        data["regNo"] = custom_reg_no
        data["id"]    = f"std_{custom_reg_no}"

    # Persist to DB (non-fatal)
    try:
        existing = db.query(Student).filter(Student.id == data["id"]).first()
        if existing:
            db.delete(existing)
            db.commit()

        db.add(Student(
            id=data["id"],
            file_name=data["fileName"],
            reg_no=data["regNo"],
            subject=data["subject"],
            subject_code=data["subjectCode"],
            medium=data["medium"],
            board_id=data.get("boardId", "TN_STATE"),
            board_name=data.get("boardName", "Tamil Nadu State Board"),
            total_questions=data["totalQuestions"],
            grand_total_computed=data["grandTotalComputed"],
            evaluator_total_figures=data["evaluatorTotalFigures"],
            evaluator_total_words=data["evaluatorTotalWords"],
            is_verified=data["isVerified"],
            is_approved=data["isApproved"]
        ))

        for r in data["rows"]:
            db.add(RowSubtotal(
                student_id=data["id"],
                row_index=r["rowIndex"],
                label=r["label"],
                start_q=r["start"],
                end_q=r["end"],
                section_name=r.get("sectionName", ""),
                marks_per_question=r.get("marksPerQuestion", 1.0),
                max_section_marks=r.get("maxSectionMarks", 0.0),
                computed_subtotal=r["subtotalComputed"],
                written_subtotal=r["subtotalWritten"],
                is_matched=r["isMatched"],
                attempted_count=r.get("attemptedCount", 0),
                unattempted_count=r.get("unattemptedCount", 0)
            ))
            for q in r["questions"]:
                db.add(QuestionMark(
                    student_id=data["id"],
                    q_number=q["qNumber"],
                    raw_mark=q["raw"],
                    computed_score=q["score"],
                    max_marks=q.get("maxMarks", 1.0),
                    is_subdivision=q["isSubdivision"]
                ))

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[DB] persist notice: {e}")

    return data


# ─────────────────────────────────────────────────────────────────────────────
# Debug / Diagnostic Endpoint  — SYNC
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/debug-extract")
def debug_extract(
    file: UploadFile = File(...),
    board_id:       Optional[str] = Form("TN_STATE"),
    layout_mode:    Optional[str] = Form("vertical"),
    gemini_api_key: Optional[str] = Form(None),
):
    """
    Run OCR and return raw results WITHOUT saving to the database.
    Use to verify OCR quality before a full class batch run.
    """
    content  = file.file.read()
    filename = file.filename or "debug.jpg"

    img_np = _decode_upload(content, filename)
    if img_np is None:
        raise HTTPException(status_code=400, detail="Cannot decode image or PDF.")

    data  = extract_universal_booklet_marks(
        img_np, filename=filename,
        layout_mode=layout_mode, board_id=board_id,
        gemini_api_key=gemini_api_key
    )
    debug = data.get("_debug", {})

    return {
        "engineUsed":     data.get("engineUsed", "Unknown"),
        "tokensFound":    debug.get("tokensFound", 0),
        "marksExtracted": debug.get("marksExtracted", 0),
        "layoutDetected": debug.get("layoutDetected"),
        "boardDetected":  debug.get("boardDetected"),
        "grandTotal":     data.get("grandTotalComputed"),
        "rawMarks":       debug.get("rawMarks", {}),
        "sectionSummary": [
            {
                "name":        s.get("name"),
                "label":       s.get("label"),
                "scored":      s.get("scoredMarks"),
                "attempted":   s.get("attemptedCount"),
                "unattempted": s.get("unattemptedCount"),
                "maxMarks":    s.get("maxSectionMarks")
            }
            for s in data.get("sections", [])
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# Student Records
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/students")
def get_students(db: Session = Depends(get_db)):
    """Retrieve all student records from the database."""
    students = db.query(Student).order_by(Student.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "regNo": s.reg_no,
            "subject": s.subject,
            "subjectCode": s.subject_code,
            "medium": s.medium,
            "boardId": s.board_id,
            "boardName": s.board_name,
            "grandTotal": s.grand_total_computed,
            "isVerified": s.is_verified,
            "isApproved": s.is_approved,
            "fileName": s.file_name
        }
        for s in students
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Excel Export Endpoints
# ─────────────────────────────────────────────────────────────────────────────

class ExcelExportPayload(BaseModel):
    students: List[Dict[str, Any]]


try:
    from .excel_generator import create_excel_workbook, create_single_sheet_excel_workbook
    from .blueprints import list_blueprints, get_blueprint
    from .auth import get_current_user_tenant
except (ImportError, ValueError):
    from excel_generator import create_excel_workbook, create_single_sheet_excel_workbook
    from blueprints import list_blueprints, get_blueprint
    from auth import get_current_user_tenant

@app.get("/api/v1/blueprints")
def get_v1_blueprints():
    """List all registered board blueprints."""
    return list_blueprints()


@app.post("/api/export-excel")
def export_excel_endpoint(payload: ExcelExportPayload):
    """
    Stream a section-wise multi-sheet Excel workbook.
    """
    if not payload.students:
        raise HTTPException(status_code=400, detail="No student records provided.")

    buffer   = create_single_sheet_excel_workbook(payload.students)
    board_id = payload.students[0].get("boardId", "TN")
    filename = f"Marksheet_AI_Results_{board_id}_{_today_str()}.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/api/v1/export-single-sheet")
def export_single_sheet_endpoint(payload: ExcelExportPayload, auth: Dict[str, Any] = Depends(get_current_user_tenant)):
    """
    Stream a single-sheet Excel workbook ('Results' sheet, 1 row per student).
    """
    if not payload.students:
        raise HTTPException(status_code=400, detail="No student records provided.")

    buffer   = create_single_sheet_excel_workbook(payload.students)
    board_id = payload.students[0].get("boardId", "TN")
    filename = f"Marksheet_AI_Results_{board_id}_{_today_str()}.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


class SectionExcelPayload(BaseModel):
    students: List[Dict[str, Any]]
    board_id: str = "TN_STATE"


@app.post("/api/export-section-excel")
def export_section_excel(payload: SectionExcelPayload):
    """
    Re-map student marks to a different board schema then generate Excel.
    Useful when teacher needs to switch between TN_STATE / CBSE_TN / IGCSE_TN.
    """
    if not payload.students:
        raise HTTPException(status_code=400, detail="No student records provided.")

    schema   = get_board_schema(payload.board_id)
    remapped = []

    for std in payload.students:
        flat_marks: Dict[int, str] = {}
        for r in std.get("rows", []):
            for q in r.get("questions", []):
                flat_marks[q["qNumber"]] = q.get("raw", "/")

        section_result = assign_sections_to_marks(flat_marks, schema)

        new_rows = []
        for sec in section_result["sections"]:
            new_rows.append({
                "rowIndex": len(new_rows),
                "label": sec["label"],
                "start": sec["qFrom"],
                "end": sec["qTo"],
                "sectionName": sec["name"],
                "marksPerQuestion": sec["marksPerQuestion"],
                "maxSectionMarks": sec["maxSectionMarks"],
                "questions": sec["questions"],
                "subtotalComputed": sec["scoredMarks"],
                "subtotalWritten": sec["scoredMarks"],
                "isMatched": True,
                "attemptedCount": sec["attemptedCount"],
                "unattemptedCount": sec["unattemptedCount"]
            })

        remapped.append({
            **std,
            "boardId": schema["boardId"],
            "boardName": schema["boardName"],
            "boardTotalMarks": schema["totalMarks"],
            "rows": new_rows,
            "grandTotalComputed": section_result["grandTotal"],
            "evaluatorTotalFigures": section_result["grandTotal"],
        })

    buffer   = create_excel_workbook(remapped)
    filename = f"Marks_SectionWise_{payload.board_id}_{_today_str()}.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _today_str() -> str:
    from datetime import date
    return date.today().strftime("%Y%m%d")


# ─────────────────────────────────────────────────────────────────────────────
# Frontend Static Mount
# ─────────────────────────────────────────────────────────────────────────────

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
