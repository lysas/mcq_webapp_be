# Database Layer (`database/`)

This directory contains the database persistence layer for the Answer-Booklet Extraction System.

## Contents
- **`database.py`**: SQLAlchemy engine, session maker, and DB initializer. Automatically configures `booklet_system.db` (SQLite) with zero setup required.
- **`models.py`**: ORM classes for:
  - `Batch`: Groups student booklets uploaded together.
  - `Student`: Student metadata (Register No, Subject, Code, Medium, Evaluator Figures & Words, Verified status, Approved status).
  - `QuestionMark`: Question-wise raw string (e.g., `2+2`, `1+1+1`), computed float score, and subdivision flag.
  - `RowSubtotal`: Row block subtotals and consistency match status.
- **`schema.sql`**: Standard SQL schema for SQLite/PostgreSQL.
