"""SQLite storage for the paper library."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "papers.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    authors TEXT DEFAULT '',
    year INTEGER,
    url TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    status TEXT DEFAULT 'to_read',  -- to_read | reading | done
    summary TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def list_papers():
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM papers ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def add_paper(title, authors="", year=None, url="", tags="", status="to_read", summary=""):
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO papers (title, authors, year, url, tags, status, summary) VALUES (?,?,?,?,?,?,?)",
            (title, authors, year, url, tags, status, summary),
        )
        row = conn.execute("SELECT * FROM papers WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)


def update_paper(paper_id, fields):
    allowed = {"title", "authors", "year", "url", "tags", "status", "summary"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return None
    sets = ", ".join(f"{k}=?" for k in updates)
    with _conn() as conn:
        conn.execute(f"UPDATE papers SET {sets} WHERE id=?", (*updates.values(), paper_id))
        row = conn.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
        return dict(row) if row else None


def delete_paper(paper_id):
    with _conn() as conn:
        conn.execute("DELETE FROM papers WHERE id=?", (paper_id,))
