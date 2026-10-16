-- Marksheet AI Database Schema
-- Compatible with SQLite and PostgreSQL

CREATE TABLE IF NOT EXISTS batches (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS students (
    id VARCHAR(64) PRIMARY KEY,
    batch_id VARCHAR(64) REFERENCES batches(id) ON DELETE CASCADE,
    file_name VARCHAR(255),
    reg_no VARCHAR(64),
    subject VARCHAR(128),
    subject_code VARCHAR(64),
    medium VARCHAR(64),
    total_questions INTEGER DEFAULT 70,
    grand_total_computed REAL DEFAULT 0.0,
    evaluator_total_figures REAL DEFAULT 0.0,
    evaluator_total_words VARCHAR(255),
    is_verified BOOLEAN DEFAULT 0,
    is_approved BOOLEAN DEFAULT 0,
    image_data_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS question_marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id VARCHAR(64) REFERENCES students(id) ON DELETE CASCADE,
    q_number INTEGER NOT NULL,
    raw_mark VARCHAR(32) DEFAULT '—',
    computed_score REAL DEFAULT 0.0,
    is_subdivision BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS row_subtotals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id VARCHAR(64) REFERENCES students(id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    label VARCHAR(64),
    start_q INTEGER,
    end_q INTEGER,
    computed_subtotal REAL DEFAULT 0.0,
    written_subtotal REAL DEFAULT 0.0,
    is_matched BOOLEAN DEFAULT 1
);
