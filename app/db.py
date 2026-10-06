"""SQLite storage: papers, review cards, activity log."""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from . import arxiv, config, review

PAPER_COLUMNS = {
    "title": "TEXT NOT NULL DEFAULT ''",
    "authors": "TEXT DEFAULT ''",
    "year": "INTEGER",
    "url": "TEXT DEFAULT ''",
    "tags": "TEXT DEFAULT ''",
    "status": "TEXT DEFAULT 'to_read'",
    "created_at": "TEXT",
    # v0.2
    "slug": "TEXT",
    "arxiv_id": "TEXT",
    "published": "TEXT DEFAULT ''",
    "pdf_url": "TEXT DEFAULT ''",
    "abstract": "TEXT DEFAULT ''",
    "categories": "TEXT DEFAULT ''",
    "comment": "TEXT DEFAULT ''",
    "note_requested": "INTEGER DEFAULT 0",
    "note_mtime": "REAL",
    "updated_at": "TEXT",
    "finished_at": "TEXT",
}
EDITABLE = {"title", "authors", "year", "url", "pdf_url", "abstract", "tags", "status", "note_requested"}
INSERTABLE = ("title", "authors", "year", "url", "pdf_url", "abstract", "tags", "status",
              "arxiv_id", "published", "categories", "comment")

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    box INTEGER NOT NULL DEFAULT 0,
    due TEXT NOT NULL,
    last_reviewed TEXT,
    UNIQUE (paper_id, question)
);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER REFERENCES papers(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,          -- added | status | note | review
    detail TEXT DEFAULT '',
    day TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_day ON activity(day);
CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_slug ON papers(slug);
CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_arxiv ON papers(arxiv_id) WHERE arxiv_id IS NOT NULL;
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def slug_for(arxiv_id: str | None, paper_id: int) -> str:
    return arxiv_id.replace("/", "_") if arxiv_id else f"local-{paper_id}"


def init():
    """Create tables and bring a v0.1 database forward without losing rows."""
    config.HOME.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS papers (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(papers)")}
        for name, ddl in PAPER_COLUMNS.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE papers ADD COLUMN {name} {ddl}")
        for row in conn.execute("SELECT * FROM papers WHERE slug IS NULL").fetchall():
            arxiv_id = arxiv.parse_id(row["url"])
            if arxiv_id and conn.execute("SELECT 1 FROM papers WHERE arxiv_id=?", (arxiv_id,)).fetchone():
                arxiv_id = None  # v0.1 allowed duplicates; keep the row, drop the clashing id
            abstract = row["abstract"] or (row["summary"] if "summary" in existing else "") or ""
            conn.execute(
                "UPDATE papers SET slug=?, arxiv_id=?, abstract=?, updated_at=COALESCE(updated_at, created_at, ?) WHERE id=?",
                (slug_for(arxiv_id, row["id"]), arxiv_id, abstract, _now(), row["id"]),
            )
        # v0.1 rows kept whatever link arXiv returned (http, versioned) and had no PDF link
        conn.execute(
            "UPDATE papers SET url='https://arxiv.org/abs/' || arxiv_id, pdf_url='https://arxiv.org/pdf/' || arxiv_id "
            "WHERE arxiv_id IS NOT NULL AND COALESCE(pdf_url, '') = ''"
        )
        conn.executescript(SCHEMA)


def normalize_tags(tags: str | None) -> str:
    seen = dict.fromkeys(t.strip() for t in (tags or "").split(",") if t.strip())
    return ", ".join(seen)


def log(conn, kind: str, paper_id: int | None = None, detail: str = "", day: str | None = None, once_per_day: bool = False):
    day = day or date.today().isoformat()
    if once_per_day and conn.execute(
        "SELECT 1 FROM activity WHERE kind=? AND paper_id IS ? AND day=?", (kind, paper_id, day)
    ).fetchone():
        return
    conn.execute(
        "INSERT INTO activity (paper_id, kind, detail, day, created_at) VALUES (?,?,?,?,?)",
        (paper_id, kind, detail, day, _now()),
    )


# ---------- papers ----------

def list_papers() -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM papers ORDER BY updated_at DESC, id DESC")]


def get_paper(paper_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
        return dict(row) if row else None


def find_paper(ref: str) -> dict | None:
    """Look a paper up by numeric id, slug, or arXiv id/URL (used by the CLI)."""
    ref = str(ref).strip()
    with connect() as conn:
        row = None
        if ref.isdigit():
            row = conn.execute("SELECT * FROM papers WHERE id=?", (int(ref),)).fetchone()
        if not row:
            row = conn.execute("SELECT * FROM papers WHERE slug=?", (ref,)).fetchone()
        if not row and (aid := arxiv.parse_id(ref)):
            row = conn.execute("SELECT * FROM papers WHERE arxiv_id=?", (aid,)).fetchone()
        return dict(row) if row else None


def saved_arxiv_ids() -> dict[str, int]:
    with connect() as conn:
        return {r["arxiv_id"]: r["id"] for r in conn.execute("SELECT id, arxiv_id FROM papers WHERE arxiv_id IS NOT NULL")}


def add_paper(data: dict) -> tuple[dict, bool]:
    """Insert a paper. Returns (paper, created); an arXiv id already saved is returned as-is."""
    fields = {k: data.get(k) for k in INSERTABLE if data.get(k) not in (None, "")}
    fields["title"] = " ".join((fields.get("title") or "").split())
    if not fields["title"]:
        raise ValueError("제목은 비워둘 수 없어요.")
    if fields.get("status") not in config.STATUSES:
        fields["status"] = "to_read"
    fields["tags"] = normalize_tags(fields.get("tags"))
    arxiv_id = arxiv.parse_id(fields.get("arxiv_id") or "") or arxiv.parse_id(fields.get("url") or "")
    fields["arxiv_id"] = arxiv_id
    if arxiv_id:
        fields.setdefault("url", f"https://arxiv.org/abs/{arxiv_id}")
        fields.setdefault("pdf_url", f"https://arxiv.org/pdf/{arxiv_id}")
    now = _now()
    fields["created_at"] = fields["updated_at"] = now
    if fields["status"] == "done":
        fields["finished_at"] = now[:10]
    with connect() as conn:
        if arxiv_id:
            row = conn.execute("SELECT * FROM papers WHERE arxiv_id=?", (arxiv_id,)).fetchone()
            if row:
                return dict(row), False
        cols = ", ".join(fields)
        cur = conn.execute(f"INSERT INTO papers ({cols}) VALUES ({', '.join('?' * len(fields))})", tuple(fields.values()))
        paper_id = cur.lastrowid
        conn.execute("UPDATE papers SET slug=? WHERE id=?", (slug_for(arxiv_id, paper_id), paper_id))
        log(conn, "added", paper_id, fields["title"])
        return dict(conn.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()), True


def update_paper(paper_id: int, fields: dict) -> dict | None:
    updates = {k: v for k, v in fields.items() if k in EDITABLE and v is not None}
    if "status" in updates and updates["status"] not in config.STATUSES:
        raise ValueError(f"상태는 {', '.join(config.STATUSES)} 중 하나여야 해요.")
    if "title" in updates:
        updates["title"] = " ".join(updates["title"].split())
        if not updates["title"]:
            raise ValueError("제목은 비워둘 수 없어요.")
    if "tags" in updates:
        updates["tags"] = normalize_tags(updates["tags"])
    if "note_requested" in updates:
        updates["note_requested"] = int(bool(updates["note_requested"]))
    with connect() as conn:
        row = conn.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
        if not row:
            return None
        if updates:
            if "status" in updates and updates["status"] != row["status"]:
                updates["finished_at"] = date.today().isoformat() if updates["status"] == "done" else None
                log(conn, "status", paper_id, updates["status"])
            updates["updated_at"] = _now()
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE papers SET {sets} WHERE id=?", (*updates.values(), paper_id))
        return dict(conn.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone())


def set_note_state(paper_id: int, mtime: float | None, clear_request: bool):
    with connect() as conn:
        conn.execute(
            "UPDATE papers SET note_mtime=?, note_requested=CASE WHEN ? THEN 0 ELSE note_requested END WHERE id=?",
            (mtime, int(clear_request), paper_id),
        )


def delete_paper(paper_id: int) -> bool:
    with connect() as conn:
        return conn.execute("DELETE FROM papers WHERE id=?", (paper_id,)).rowcount > 0


# ---------- cards ----------

def sync_cards(paper_id: int, pairs: list[tuple[str, str]], today: date | None = None):
    """Make the stored cards match the note. A card whose question is unchanged keeps its box."""
    today = today or date.today()
    with connect() as conn:
        current = {r["question"]: r for r in conn.execute("SELECT * FROM cards WHERE paper_id=?", (paper_id,))}
        wanted = dict(pairs)
        for question in current.keys() - wanted.keys():
            conn.execute("DELETE FROM cards WHERE id=?", (current[question]["id"],))
        for question, answer in wanted.items():
            if question in current:
                if current[question]["answer"] != answer:
                    conn.execute("UPDATE cards SET answer=? WHERE id=?", (answer, current[question]["id"]))
            else:
                conn.execute(
                    "INSERT INTO cards (paper_id, question, answer, box, due) VALUES (?,?,?,0,?)",
                    (paper_id, question, answer, today.isoformat()),
                )


def cards_for(paper_id: int) -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM cards WHERE paper_id=? ORDER BY id", (paper_id,))]


def due_cards(today: date | None = None) -> list[dict]:
    today = today or date.today()
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.*, p.title AS paper_title FROM cards c JOIN papers p ON p.id = c.paper_id
               WHERE c.due <= ? ORDER BY c.due, c.id""",
            (today.isoformat(),),
        )
        return [dict(r) for r in rows]


def grade_card(card_id: int, grade: str, today: date | None = None) -> dict | None:
    today = today or date.today()
    with connect() as conn:
        row = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        if not row:
            return None
        box, due = review.next_state(row["box"], grade, today)
        conn.execute("UPDATE cards SET box=?, due=?, last_reviewed=? WHERE id=?",
                     (box, due.isoformat(), today.isoformat(), card_id))
        log(conn, "review", row["paper_id"], grade, day=today.isoformat())
        return dict(conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone())


# ---------- stats ----------

def stats(today: date | None = None, weeks: int = 20) -> dict:
    today = today or date.today()
    # 히트맵은 일요일에서 시작하는 온전한 주 단위로 그린다
    start = today - timedelta(days=(today.weekday() + 1) % 7 + 7 * (weeks - 1))
    with connect() as conn:
        by_status = {s: 0 for s in config.STATUSES}
        for r in conn.execute("SELECT status, COUNT(*) n FROM papers GROUP BY status"):
            by_status[r["status"] if r["status"] in by_status else "to_read"] += r["n"]
        days = {r["day"]: r["n"] for r in conn.execute(
            "SELECT day, COUNT(*) n FROM activity WHERE day >= ? GROUP BY day", (start.isoformat(),))}
        active = {r["day"] for r in conn.execute("SELECT DISTINCT day FROM activity")}
        cards_total = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        cards_due = conn.execute("SELECT COUNT(*) FROM cards WHERE due <= ?", (today.isoformat(),)).fetchone()[0]
        month_done = conn.execute(
            "SELECT COUNT(*) FROM papers WHERE status='done' AND finished_at >= ?",
            (today.replace(day=1).isoformat(),)).fetchone()[0]
        recent = [dict(r) for r in conn.execute(
            """SELECT a.kind, a.detail, a.day, a.paper_id, p.title FROM activity a
               LEFT JOIN papers p ON p.id = a.paper_id ORDER BY a.id DESC LIMIT 12""")]
    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "month_done": month_done,
        "cards_total": cards_total,
        "cards_due": cards_due,
        "streak": review.streak(active, today),
        "active_days": len(active),
        "heatmap": {"start": start.isoformat(), "end": today.isoformat(), "days": days},
        "recent": recent,
    }
