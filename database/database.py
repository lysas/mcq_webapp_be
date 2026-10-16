"""
Database configuration and session management — Tamil Nadu Board Edition
========================================================================
Supports SQLite out of the box with zero external configuration,
and PostgreSQL for production.

New columns are applied via lightweight SQLite ALTER TABLE migrations
so existing databases are automatically upgraded without data loss.
"""

import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

log = logging.getLogger(__name__)

DB_PATH     = os.path.join(os.path.dirname(__file__), "booklet_system.db")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_column_if_missing(conn, table: str, column: str, col_type: str) -> None:
    """Safely add a column to a SQLite table if it doesn't already exist."""
    try:
        result = conn.execute(text(f"PRAGMA table_info({table})"))
        existing_cols = [row[1] for row in result.fetchall()]
        if column not in existing_cols:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            log.info("Migration: added column %s.%s", table, column)
    except Exception as e:
        log.warning("Migration notice for %s.%s: %s", table, column, e)


def _run_migrations(conn) -> None:
    """
    Idempotent schema migrations.
    Add any new columns introduced in the Tamil Nadu Board Edition here.
    Safe to run on both fresh and existing databases.
    """
    # students table — new board columns
    _add_column_if_missing(conn, "students", "board_id",   "VARCHAR(32) DEFAULT 'TN_STATE'")
    _add_column_if_missing(conn, "students", "board_name", "VARCHAR(128) DEFAULT 'Tamil Nadu State Board'")

    # question_marks table — per-question max marks
    _add_column_if_missing(conn, "question_marks", "max_marks", "FLOAT DEFAULT 1.0")

    # row_subtotals table — section-aware columns
    _add_column_if_missing(conn, "row_subtotals", "section_name",       "VARCHAR(64) DEFAULT ''")
    _add_column_if_missing(conn, "row_subtotals", "marks_per_question", "FLOAT DEFAULT 1.0")
    _add_column_if_missing(conn, "row_subtotals", "max_section_marks",  "FLOAT DEFAULT 0.0")
    _add_column_if_missing(conn, "row_subtotals", "attempted_count",    "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "row_subtotals", "unattempted_count",  "INTEGER DEFAULT 0")

    # batches table — board_id
    _add_column_if_missing(conn, "batches", "board_id", "VARCHAR(32) DEFAULT 'TN_STATE'")


def init_db() -> None:
    """
    Initialise the database:
      1. Create all tables that do not yet exist (create_all is safe/idempotent).
      2. Run lightweight ALTER TABLE migrations for new columns.
    """
    from . import models  # noqa: F401 — ensure models are imported so Base knows them
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        _run_migrations(conn)
        conn.commit()
