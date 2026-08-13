"""
database.py
===========
Database initialization and helper functions.
SQLite database with 6 tables.
"""

import sqlite3
import os

# ── Paths ──────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "data", "scholarship.db")

# ── Schema ─────────────────────────────────────────────────────
SCHEMA = """

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    is_verified     INTEGER NOT NULL DEFAULT 0,
    is_admin        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS otp_codes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT    NOT NULL,
    otp         TEXT    NOT NULL,
    purpose     TEXT    NOT NULL DEFAULT 'verify',
    expires_at  TEXT    NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reset_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    token       TEXT    NOT NULL UNIQUE,
    expires_at  TEXT    NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS scholarship_schemes (
    scheme_id           TEXT PRIMARY KEY,
    scheme_name         TEXT NOT NULL,
    awarding_body       TEXT,
    min_z_score         REAL,
    max_annual_income   INTEGER,
    monthly_amount      INTEGER,
    deadline_month      TEXT,
    eligible_streams    TEXT DEFAULT 'ALL',
    eligible_districts  TEXT DEFAULT 'ALL',
    description         TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS predictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER,
    z_score         REAL    NOT NULL,
    stream          TEXT    NOT NULL,
    grade_a_count   INTEGER DEFAULT 0,
    annual_income   INTEGER NOT NULL,
    district        TEXT    NOT NULL,
    income_adjusted INTEGER,
    results_json    TEXT,
    eligible_count  INTEGER DEFAULT 0,
    created_at      TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS saved_scholarships (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    scheme_id   TEXT    NOT NULL,
    saved_at    TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)   REFERENCES users(id),
    FOREIGN KEY (scheme_id) REFERENCES scholarship_schemes(scheme_id),
    UNIQUE(user_id, scheme_id)
);

CREATE INDEX IF NOT EXISTS idx_users_email      ON users(email);
CREATE INDEX IF NOT EXISTS idx_otp_email        ON otp_codes(email);
CREATE INDEX IF NOT EXISTS idx_predictions_user ON predictions(user_id);
CREATE INDEX IF NOT EXISTS idx_reset_token      ON reset_tokens(token);
"""

# ── Scholarship seed data ───────────────────────────────────────
SCHEMES = [
    (
        "SCH001",
        "Mahapola Higher Education Scholarship",
        "Mahapola Trust Fund",
        1.40, 600000, 7500, "October",
        "ALL", "ALL",
        "National scholarship for academically excellent students with financial need."
    ),
    (
        "SCH002",
        "UGC Bursary Scheme",
        "University Grants Commission",
        1.20, 500000, 5000, "November",
        "ALL", "ALL",
        "Income-based bursary for financially disadvantaged university students."
    ),
    (
        "SCH003",
        "North Western Provincial Council Scholarship",
        "North Western Provincial Council",
        1.10, 450000, 3000, "September",
        "ALL", "Kurunegala,Puttalam",
        "Provincial award for students from Kurunegala and Puttalam districts."
    ),
    (
        "SCH004",
        "Science and Technology Merit Award",
        "Ministry of Education",
        1.70, 700000, 6000, "October",
        "Biological Science,Physical Science,Technology", "ALL",
        "Merit award for high-achieving STEM students."
    ),
    (
        "SCH005",
        "Arts and Humanities Bursary",
        "University Grants Commission",
        1.00, 400000, 4000, "November",
        "Arts", "ALL",
        "Need-based bursary for Arts stream university students."
    ),
    (
        "SCH006",
        "Rural Excellence Scholarship",
        "Ministry of Education",
        1.20, 480000, 4500, "September",
        "ALL",
        "Monaragala,Mullaitivu,Kilinochchi,Mannar,Vavuniya,Polonnaruwa,Ampara,Batticaloa,Trincomalee",
        "Award for students from underserved remote districts."
    ),
]


# ── Helper functions ────────────────────────────────────────────
def get_db():
    """Get a database connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    """Create all tables and seed data."""
    print("Initializing database...")
    con = get_db()
    con.executescript(SCHEMA)

    for scheme in SCHEMES:
        con.execute("""
            INSERT OR IGNORE INTO scholarship_schemes (
                scheme_id, scheme_name, awarding_body,
                min_z_score, max_annual_income, monthly_amount,
                deadline_month, eligible_streams,
                eligible_districts, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, scheme)

    con.commit()
    con.close()
    print(f"Database created at: {DB_PATH}")


def execute(sql, params=(), fetchone=False, fetchall=False, commit=False):
    """Simple database query wrapper."""
    con = get_db()
    cur = con.cursor()
    cur.execute(sql, params)
    result = None
    if fetchone:
        result = cur.fetchone()
    elif fetchall:
        result = cur.fetchall()
    if commit:
        con.commit()
        result = cur.lastrowid
    con.close()
    return result


# ── Test when run directly ──────────────────────────────────────
if __name__ == "__main__":
    init_db()

    con = get_db()
    schemes = con.execute(
        "SELECT scheme_id, scheme_name, min_z_score, max_annual_income "
        "FROM scholarship_schemes"
    ).fetchall()
    con.close()

    print(f"\n{len(schemes)} scholarship schemes loaded:")
    print("-" * 60)
    for s in schemes:
        print(f"  {s['scheme_id']} | {s['scheme_name']}")
        print(
            f"           Min Z: {s['min_z_score']} | Max Income: Rs.{s['max_annual_income']:,}")
    print("-" * 60)
    print("\nAll tables created successfully!")
