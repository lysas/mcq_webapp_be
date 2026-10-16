"""
Multi-Tenant SaaS ORM Models & Audit Log
=========================================
SQLAlchemy models for enterprise multi-tenancy:
- Organization (Tenant)
- User (ADMIN, EXAMINER, REVIEWER)
- Exam & Subject
- AnswerScript & ExtractionJob
- VerificationEvent & AuditLog
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from .database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id          = Column(String(64), primary_key=True, index=True)
    name        = Column(String(255), nullable=False)
    slug        = Column(String(64), unique=True, index=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    users       = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    exams       = relationship("Exam", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id              = Column(String(64), primary_key=True, index=True)
    organization_id = Column(String(64), ForeignKey("organizations.id"), nullable=False)
    email           = Column(String(255), unique=True, index=True, nullable=False)
    full_name       = Column(String(255), default="")
    password_hash   = Column(String(255), nullable=False)
    role            = Column(String(32), default="EXAMINER")  # "ADMIN", "EXAMINER", "REVIEWER"
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    organization    = relationship("Organization", back_populates="users")


class Exam(Base):
    __tablename__ = "exams"

    id              = Column(String(64), primary_key=True, index=True)
    organization_id = Column(String(64), ForeignKey("organizations.id"), nullable=False)
    title           = Column(String(255), nullable=False)
    board_id        = Column(String(64), default="TN_STATE_10")
    class_name      = Column(String(32), default="10")
    subject         = Column(String(128), default="General")
    academic_year   = Column(String(32), default="2025-2026")
    created_at      = Column(DateTime, default=datetime.utcnow)

    organization    = relationship("Organization", back_populates="exams")
    scripts         = relationship("AnswerScript", back_populates="exam", cascade="all, delete-orphan")


class AnswerScript(Base):
    __tablename__ = "answer_scripts"

    id                 = Column(String(64), primary_key=True, index=True)
    exam_id            = Column(String(64), ForeignKey("exams.id"), nullable=False)
    register_number    = Column(String(64), index=True, default="000000")
    student_name       = Column(String(255), default="Unknown")
    file_name          = Column(String(255), default="script.pdf")
    status             = Column(String(32), default="PROCESSING")  # "PROCESSING", "VERIFIED", "REVIEW_REQUIRED"
    qwise_total        = Column(Float, default=0.0)
    pwise_total        = Column(Float, default=0.0)
    evaluator_total    = Column(Float, default=0.0)
    is_verified        = Column(Boolean, default=False)
    review_required    = Column(Boolean, default=False)
    created_at         = Column(DateTime, default=datetime.utcnow)

    exam               = relationship("Exam", back_populates="scripts")
    audit_logs         = relationship("AuditLog", back_populates="script", cascade="all, delete-orphan")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    script_id     = Column(String(64), ForeignKey("answer_scripts.id"), nullable=False)
    user_id       = Column(String(64), nullable=True)
    q_number      = Column(Integer, nullable=False)
    old_value     = Column(String(32), default="")
    new_value     = Column(String(32), default="")
    reason        = Column(String(255), default="Faculty Manual Review")
    timestamp     = Column(DateTime, default=datetime.utcnow)

    script        = relationship("AnswerScript", back_populates="audit_logs")
