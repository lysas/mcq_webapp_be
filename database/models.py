"""
SQLAlchemy ORM models — Tamil Nadu Board Edition
================================================
Stores batches, students, question marks, and section/row subtotals
with full section-awareness for TN State Board, CBSE, and IGCSE.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base


class Batch(Base):
    __tablename__ = "batches"

    id         = Column(String(64), primary_key=True, index=True)
    title      = Column(String(255), default="Answer Booklet Batch")
    board_id   = Column(String(32),  default="TN_STATE")
    created_at = Column(DateTime, default=datetime.utcnow)

    students = relationship("Student", back_populates="batch",
                            cascade="all, delete-orphan")


class Student(Base):
    __tablename__ = "students"

    id                      = Column(String(64), primary_key=True, index=True)
    batch_id                = Column(String(64), ForeignKey("batches.id"), nullable=True)
    file_name               = Column(String(255), default="booklet_scan.jpg")
    reg_no                  = Column(String(64),  index=True, default="")
    subject                 = Column(String(128), default="General")
    subject_code            = Column(String(64),  default="")
    medium                  = Column(String(64),  default="English")

    # Board identification (TN_STATE / CBSE_TN / IGCSE_TN / etc.)
    board_id                = Column(String(32),  default="TN_STATE")
    board_name              = Column(String(128), default="Tamil Nadu State Board")

    total_questions         = Column(Integer,     default=42)
    grand_total_computed    = Column(Float,       default=0.0)
    evaluator_total_figures = Column(Float,       default=0.0)
    evaluator_total_words   = Column(String(255), default="")
    is_verified             = Column(Boolean,     default=False)
    is_approved             = Column(Boolean,     default=False)
    image_data_url          = Column(Text,        nullable=True)
    created_at              = Column(DateTime,    default=datetime.utcnow)

    batch     = relationship("Batch", back_populates="students")
    questions = relationship("QuestionMark", back_populates="student",
                             cascade="all, delete-orphan",
                             order_by="QuestionMark.q_number")
    subtotals = relationship("RowSubtotal", back_populates="student",
                             cascade="all, delete-orphan",
                             order_by="RowSubtotal.row_index")


class QuestionMark(Base):
    __tablename__ = "question_marks"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    student_id     = Column(String(64), ForeignKey("students.id"), nullable=False)
    q_number       = Column(Integer,    nullable=False)
    raw_mark       = Column(String(32), default="/")
    computed_score = Column(Float,      default=0.0)
    max_marks      = Column(Float,      default=1.0)   # per-question max from section schema
    is_subdivision = Column(Boolean,    default=False)

    student = relationship("Student", back_populates="questions")


class RowSubtotal(Base):
    __tablename__ = "row_subtotals"

    id                 = Column(Integer,     primary_key=True, autoincrement=True)
    student_id         = Column(String(64),  ForeignKey("students.id"), nullable=False)
    row_index          = Column(Integer,     nullable=False)
    label              = Column(String(128), default="")
    section_name       = Column(String(64),  default="")      # e.g. PART_I, SECTION_A
    start_q            = Column(Integer,     default=1)
    end_q              = Column(Integer,     default=10)
    marks_per_question = Column(Float,       default=1.0)     # max marks per Q in this section
    max_section_marks  = Column(Float,       default=0.0)     # total possible marks for section
    computed_subtotal  = Column(Float,       default=0.0)
    written_subtotal   = Column(Float,       default=0.0)
    is_matched         = Column(Boolean,     default=True)
    attempted_count    = Column(Integer,     default=0)
    unattempted_count  = Column(Integer,     default=0)

    student = relationship("Student", back_populates="subtotals")
