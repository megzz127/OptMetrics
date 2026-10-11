"""
Database model and SQLite connection management for OptMetrics.
"""

import os
import sqlite3
import json
from datetime import datetime

DB_FILE = os.environ.get("OPTMETRICS_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "optmetrics.db"))


def get_db_connection():
    """Get a connection to the SQLite database with row factory."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize database tables and default preferences."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # User Profile table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        date_of_birth TEXT,
        college TEXT,
        degree TEXT,
        branch TEXT,
        graduation_year TEXT,
        skills TEXT, -- stored as JSON array string or comma separated
        projects TEXT, -- stored as JSON array or text
        work_experience TEXT, -- stored as JSON array or text
        certifications TEXT, -- stored as JSON array or text
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Custom Profile Fields table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profile_custom_fields (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER DEFAULT 1,
        field_key TEXT NOT NULL,
        field_label TEXT NOT NULL,
        field_value TEXT NOT NULL,
        field_type TEXT DEFAULT 'text',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (profile_id) REFERENCES user_profile (id) ON DELETE CASCADE
    )
    """)

    # Uploaded Documents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        original_name TEXT NOT NULL,
        file_type TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        extracted_data_json TEXT,
        status TEXT DEFAULT 'parsed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Form Sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS form_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        form_name TEXT NOT NULL,
        source TEXT DEFAULT 'pasted', -- pasted, document, html_sample, extension
        raw_input TEXT,
        total_fields INTEGER DEFAULT 0,
        matched_fields INTEGER DEFAULT 0,
        review_needed INTEGER DEFAULT 0,
        status TEXT DEFAULT 'analyzed', -- analyzed, approved, exported
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Detected Form Fields table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS detected_fields (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        field_key TEXT NOT NULL,
        field_label TEXT NOT NULL,
        field_type TEXT DEFAULT 'text',
        original_options TEXT, -- JSON array of options if dropdown/radio
        html_name TEXT,
        html_id TEXT,
        is_required INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES form_sessions (id) ON DELETE CASCADE
    )
    """)

    # Suggested Answers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suggested_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        detected_field_id INTEGER NOT NULL,
        matched_profile_field TEXT,
        proposed_value TEXT,
        confidence_score REAL DEFAULT 0.0,
        matching_method TEXT DEFAULT 'exact', -- exact, synonym, semantic, fallback
        explanation TEXT,
        review_status TEXT DEFAULT 'pending', -- pending, accepted, rejected, edited
        edited_value TEXT,
        validation_status TEXT DEFAULT 'valid', -- valid, warning, invalid
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES form_sessions (id) ON DELETE CASCADE,
        FOREIGN KEY (detected_field_id) REFERENCES detected_fields (id) ON DELETE CASCADE
    )
    """)

    # User Preferences table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        confidence_threshold_high REAL DEFAULT 0.80,
        confidence_threshold_medium REAL DEFAULT 0.50,
        auto_accept_high_confidence INTEGER DEFAULT 0,
        time_saved_per_field_seconds INTEGER DEFAULT 45,
        theme TEXT DEFAULT 'dark',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Form Processing History table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS form_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        form_name TEXT NOT NULL,
        date_processed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fields_detected INTEGER DEFAULT 0,
        fields_matched INTEGER DEFAULT 0,
        fields_reviewed INTEGER DEFAULT 0,
        fields_corrected INTEGER DEFAULT 0,
        completion_status TEXT DEFAULT 'Completed',
        time_saved_seconds INTEGER DEFAULT 0,
        FOREIGN KEY (session_id) REFERENCES form_sessions (id) ON DELETE SET NULL
    )
    """)

    # Seed initial user profile if absent
    cursor.execute("SELECT id FROM user_profile LIMIT 1")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO user_profile (id, full_name, email, phone, college, degree, graduation_year, skills)
            VALUES (1, '', '', '', '', '', '', '[]')
        """)

    # Seed default user preferences if absent
    cursor.execute("SELECT id FROM user_preferences LIMIT 1")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO user_preferences (id, confidence_threshold_high, confidence_threshold_medium, auto_accept_high_confidence, time_saved_per_field_seconds, theme)
            VALUES (1, 0.80, 0.50, 0, 45, 'dark')
        """)

    conn.commit()
    conn.close()


def row_to_dict(row):
    """Convert an sqlite3.Row object to a standard Python dictionary."""
    if row is None:
        return None
    return dict(row)
