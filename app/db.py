"""SQLite storage: papers, review cards, activity log."""
import json
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
    # v0.6
    "recall_due": "TEXT",
}
RECALL_FIRST, RECALL_GOOD, RECALL_HAZY = 7, 30, 7   # 완독 뒤 첫 회상 / 기억났을 때 / 가물가물할 때 다음 회상까지의 일수
SESSION_GAP = 120                                   # 이 시간(초) 넘게 신호가 없으면 읽기 세션이 끝난 것으로 본다
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
    reviews INTEGER NOT NULL DEFAULT 0,
    lapses INTEGER NOT NULL DEFAULT 0,
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
CREATE TABLE IF NOT EXISTS saved_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    q TEXT NOT NULL,
    cat TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL DEFAULT '',
    UNIQUE (q, cat)
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reading_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    started_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    seconds INTEGER NOT NULL DEFAULT 0,
    open INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS recalls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    day TEXT NOT NULL,
    text TEXT NOT NULL,
    grade TEXT NOT NULL          -- good | hazy
);
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


BACKUPS_KEPT = 7


def backup_dir():
    # DB 옆에 둔다. DB 위치만 바꾼 경우에도 엉뚱한 폴더에 복사본이 섞이지 않는다.
    return config.DB_PATH.parent / "backups"


def backup(today: date | None = None) -> bool:
    """Copy the database once a day into backups/, keeping the newest few. Returns True if a copy was made.

    Review progress and the study log live only in this file (notes are plain files in git), so it gets its own safety net.
    """
    if not config.DB_PATH.exists() or config.DB_PATH.stat().st_size == 0:
        return False
    folder = backup_dir()
    target = folder / f"papers-{(today or date.today()).isoformat()}.db"
    if target.exists():
        return False
    folder.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(config.DB_PATH)
    copy = sqlite3.connect(target)
    try:
        source.backup(copy)  # 쓰는 중이어도 일관된 복사본을 만든다
    finally:
        copy.close()
        source.close()
    for old in sorted(folder.glob("papers-*.db"))[:-BACKUPS_KEPT]:
        old.unlink()
    return True


def init():
    """Create tables and bring a v0.1 database forward without losing rows."""
    config.HOME.mkdir(parents=True, exist_ok=True)
    backup()  # 구조를 바꾸기 전에 먼저 복사해 둔다
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
        card_cols = {r["name"] for r in conn.execute("PRAGMA table_info(cards)")}
        for name in ("reviews", "lapses"):  # v0.3
            if name not in card_cols:
                conn.execute(f"ALTER TABLE cards ADD COLUMN {name} INTEGER NOT NULL DEFAULT 0")
        # v0.6: 이미 완독한 논문도 회상 대상에 넣는다 (완독 7일 뒤)
        conn.execute("UPDATE papers SET recall_due = date(finished_at, '+7 days') "
                     "WHERE status='done' AND recall_due IS NULL AND finished_at IS NOT NULL")
        if "last_seen_at" not in {r["name"] for r in conn.execute("PRAGMA table_info(saved_searches)")}:  # v0.4
            conn.execute("ALTER TABLE saved_searches ADD COLUMN last_seen_at TEXT NOT NULL DEFAULT ''")


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
        fields["recall_due"] = (date.today() + timedelta(days=RECALL_FIRST)).isoformat()
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
                done = updates["status"] == "done"
                updates["finished_at"] = date.today().isoformat() if done else None
                updates["recall_due"] = (date.today() + timedelta(days=RECALL_FIRST)).isoformat() if done else None
                log(conn, "status", paper_id, updates["status"])
            updates["updated_at"] = _now()
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE papers SET {sets} WHERE id=?", (*updates.values(), paper_id))
        return dict(conn.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone())


METADATA = ("title", "authors", "year", "published", "abstract", "categories", "comment", "url", "pdf_url")


def set_metadata(paper_id: int, item: dict) -> dict | None:
    """Overwrite bibliographic fields with what arXiv says now. Tags, status and notes are untouched."""
    updates = {k: item[k] for k in METADATA if item.get(k)}
    if not updates:
        return get_paper(paper_id)
    updates["updated_at"] = _now()
    with connect() as conn:
        sets = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE papers SET {sets} WHERE id=?", (*updates.values(), paper_id))
        row = conn.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
        return dict(row) if row else None


def set_note_state(paper_id: int, mtime: float | None, clear_request: bool):
    with connect() as conn:
        conn.execute(
            "UPDATE papers SET note_mtime=?, note_requested=CASE WHEN ? THEN 0 ELSE note_requested END WHERE id=?",
            (mtime, int(clear_request), paper_id),
        )


def delete_paper(paper_id: int) -> bool:
    with connect() as conn:
        return conn.execute("DELETE FROM papers WHERE id=?", (paper_id,)).rowcount > 0


# ---------- saved searches ----------

def saved_searches() -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT id, q, cat, last_seen_at FROM saved_searches ORDER BY id")]


def get_search(search_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT id, q, cat, last_seen_at FROM saved_searches WHERE id=?", (search_id,)).fetchone()
        return dict(row) if row else None


def save_search(q: str, cat: str = "", last_seen_at: str = "") -> dict:
    q = " ".join(q.split())
    if not q:
        raise ValueError("검색어를 적어주세요.")
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO saved_searches (q, cat, created_at, last_seen_at) VALUES (?,?,?,?)",
                     (q, cat, _now(), last_seen_at))
        return dict(conn.execute("SELECT id, q, cat, last_seen_at FROM saved_searches WHERE q=? AND cat=?", (q, cat)).fetchone())


def mark_search_seen(search_id: int, newest: str):
    """Remember the newest paper shown, so later checks can count what arrived after it. Never moves backwards."""
    with connect() as conn:
        conn.execute("UPDATE saved_searches SET last_seen_at=? WHERE id=? AND last_seen_at < ?", (newest, search_id, newest))


# ---------- settings ----------

GOAL_DEFAULTS = {"goal_days": 4, "goal_papers": 1}


def goals() -> dict:
    with connect() as conn:
        stored = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings WHERE key LIKE 'goal_%'")}
    return {k: int(stored.get(k, default)) for k, default in GOAL_DEFAULTS.items()}


def set_goals(goal_days: int, goal_papers: int) -> dict:
    if not (0 <= goal_days <= 7 and 0 <= goal_papers <= 50):
        raise ValueError("목표는 주 0~7일, 논문 0~50편 사이로 정해주세요.")
    with connect() as conn:
        for key, value in (("goal_days", goal_days), ("goal_papers", goal_papers)):
            conn.execute("INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                         (key, str(value)))
    return goals()


def delete_search(search_id: int) -> bool:
    with connect() as conn:
        return conn.execute("DELETE FROM saved_searches WHERE id=?", (search_id,)).rowcount > 0


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


def get_card(card_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        return dict(row) if row else None


def rename_card(card_id: int, question: str, answer: str):
    """Change a card's text in place so its review progress carries over to the new wording."""
    with connect() as conn:
        row = conn.execute("SELECT paper_id FROM cards WHERE id=?", (card_id,)).fetchone()
        clash = conn.execute("SELECT 1 FROM cards WHERE paper_id=? AND question=? AND id<>?",
                             (row["paper_id"], question, card_id)).fetchone()
        if clash:
            raise ValueError("같은 질문의 카드가 이미 있어요.")
        conn.execute("UPDATE cards SET question=?, answer=? WHERE id=?", (question, answer, card_id))


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
        conn.execute(
            "UPDATE cards SET box=?, due=?, last_reviewed=?, reviews=reviews+1, lapses=lapses+? WHERE id=?",
            (box, due.isoformat(), today.isoformat(), int(grade == "again"), card_id))
        log(conn, "review", row["paper_id"], grade, day=today.isoformat())
        # 잘못 누른 평가를 한 번 되돌릴 수 있게 직전 상태를 남긴다
        undo = {k: row[k] for k in ("id", "box", "due", "last_reviewed", "reviews", "lapses")}
        undo["activity_id"] = conn.execute("SELECT MAX(id) FROM activity").fetchone()[0]
        conn.execute("INSERT INTO settings (key, value) VALUES ('undo_review', ?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(undo),))
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


def weak_cards(limit: int = 30) -> list[dict]:
    """Cards missed at least once, worst miss rate first."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.*, p.title AS paper_title FROM cards c JOIN papers p ON p.id = c.paper_id
               WHERE c.lapses > 0 ORDER BY CAST(c.lapses AS REAL) / c.reviews DESC, c.lapses DESC, c.id LIMIT ?""",
            (limit,))
        return [dict(r) for r in rows]


def tag_accuracy() -> list[dict]:
    """Review accuracy grouped by paper tag, weakest first. Untagged papers are grouped under ''."""
    totals: dict[str, list[int]] = {}
    with connect() as conn:
        rows = conn.execute(
            """SELECT p.tags, SUM(c.reviews) AS reviews, SUM(c.lapses) AS lapses FROM cards c
               JOIN papers p ON p.id = c.paper_id GROUP BY p.id HAVING SUM(c.reviews) > 0""")
        for r in rows:
            for tag in [t.strip() for t in (r["tags"] or "").split(",") if t.strip()] or [""]:
                bucket = totals.setdefault(tag, [0, 0])
                bucket[0] += r["reviews"]
                bucket[1] += r["lapses"]
    result = [{"tag": t, "reviews": n, "lapses": miss, "accuracy": (n - miss) / n} for t, (n, miss) in totals.items()]
    return sorted(result, key=lambda x: (x["accuracy"], -x["reviews"]))


def weekly(today: date | None = None, offset: int = 0) -> dict:
    """One Monday-to-Sunday week of study, with the week before it for comparison."""
    today = today or date.today()
    start = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)

    def summarize(conn, first: date) -> dict:
        a, b = first.isoformat(), (first + timedelta(days=6)).isoformat()
        kinds = {r["kind"]: r["n"] for r in conn.execute(
            "SELECT kind, COUNT(*) n FROM activity WHERE day BETWEEN ? AND ? GROUP BY kind", (a, b))}
        one = lambda sql: conn.execute(sql, (a, b)).fetchone()[0]
        reviews = kinds.get("review", 0)
        missed = one("SELECT COUNT(*) FROM activity WHERE kind='review' AND detail='again' AND day BETWEEN ? AND ?")
        return {
            "added": kinds.get("added", 0),
            "finished": one("SELECT COUNT(*) FROM papers WHERE status='done' AND finished_at BETWEEN ? AND ?"),
            "notes": one("SELECT COUNT(DISTINCT paper_id) FROM activity WHERE kind='note' AND day BETWEEN ? AND ?"),
            "reviews": reviews,
            "accuracy": (reviews - missed) / reviews if reviews else None,
            "active_days": one("SELECT COUNT(DISTINCT day) FROM activity WHERE day BETWEEN ? AND ?"),
            "minutes": one("SELECT COALESCE(SUM(seconds), 0) FROM reading_sessions "
                           "WHERE substr(started_at, 1, 10) BETWEEN ? AND ?") // 60,
        }

    with connect() as conn:
        a, b = start.isoformat(), (start + timedelta(days=6)).isoformat()
        days = {r["day"]: r["n"] for r in conn.execute(
            "SELECT day, COUNT(*) n FROM activity WHERE day BETWEEN ? AND ? GROUP BY day", (a, b))}
        finished = [dict(r) for r in conn.execute(
            "SELECT id, title FROM papers WHERE status='done' AND finished_at BETWEEN ? AND ? ORDER BY finished_at", (a, b))]
        noted = [dict(r) for r in conn.execute(
            """SELECT DISTINCT p.id, p.title FROM activity a JOIN papers p ON p.id = a.paper_id
               WHERE a.kind='note' AND a.day BETWEEN ? AND ? ORDER BY p.title""", (a, b))]
        current = summarize(conn, start)
        targets = goals()
        return {
            "start": a, "end": b, "offset": offset, "is_current": offset == 0,
            "goal_streak": goal_streak(today),
            "goals": {**targets,
                      "days_met": bool(targets["goal_days"]) and current["active_days"] >= targets["goal_days"],
                      "papers_met": bool(targets["goal_papers"]) and current["finished"] >= targets["goal_papers"]},
            "current": current,
            "previous": summarize(conn, start - timedelta(weeks=1)),
            "days": [{"day": (start + timedelta(days=i)).isoformat(),
                      "count": days.get((start + timedelta(days=i)).isoformat(), 0)} for i in range(7)],
            "finished": finished, "noted": noted,
        }


def goal_streak(today: date | None = None, max_weeks: int = 260) -> int:
    """Consecutive weeks that met every enabled goal, counting back from last week.

    The current week is added once it has already met them. Today's goals are applied to past weeks too.
    """
    today = today or date.today()
    targets = goals()
    if not targets["goal_days"] and not targets["goal_papers"]:
        return 0
    monday = lambda d: d - timedelta(days=d.weekday())
    days_by_week: dict[date, set[str]] = {}
    done_by_week: dict[date, int] = {}
    with connect() as conn:
        for r in conn.execute("SELECT DISTINCT day FROM activity"):
            days_by_week.setdefault(monday(date.fromisoformat(r["day"])), set()).add(r["day"])
        for r in conn.execute("SELECT finished_at FROM papers WHERE status='done' AND finished_at IS NOT NULL"):
            week = monday(date.fromisoformat(r["finished_at"]))
            done_by_week[week] = done_by_week.get(week, 0) + 1

    def met(week: date) -> bool:
        return (len(days_by_week.get(week, ())) >= targets["goal_days"]
                and done_by_week.get(week, 0) >= targets["goal_papers"])

    this_week = monday(today)
    count = 1 if met(this_week) else 0
    week = this_week - timedelta(weeks=1)
    while met(week) and count < max_weeks:
        count += 1
        week -= timedelta(weeks=1)
    return count


# ---------- reading time ----------

def _close_stale(conn, now: datetime):
    """End sessions whose page stopped reporting (tab closed, laptop asleep). Time counts up to the last report."""
    limit = (now - timedelta(seconds=SESSION_GAP)).isoformat(timespec="seconds")
    conn.execute("UPDATE reading_sessions SET open=0 WHERE open=1 AND last_seen_at < ?", (limit,))


def timer(paper_id: int, action: str, now: datetime | None = None) -> dict:
    """start / ping / stop the reading timer. Only one paper is timed at a time."""
    if action not in ("start", "ping", "stop"):
        raise ValueError(f"unknown timer action: {action}")
    now = now or datetime.now()
    stamp = now.isoformat(timespec="seconds")
    with connect() as conn:
        _close_stale(conn, now)
        current = conn.execute("SELECT * FROM reading_sessions WHERE open=1 AND paper_id=?", (paper_id,)).fetchone()
        if action == "start" and not current:
            conn.execute("UPDATE reading_sessions SET open=0 WHERE open=1")
            conn.execute("INSERT INTO reading_sessions (paper_id, started_at, last_seen_at) VALUES (?,?,?)",
                         (paper_id, stamp, stamp))
            row = conn.execute("SELECT status FROM papers WHERE id=?", (paper_id,)).fetchone()
            if row and row["status"] == "to_read":
                conn.execute("UPDATE papers SET status='reading', updated_at=? WHERE id=?", (stamp, paper_id))
                log(conn, "status", paper_id, "reading", day=now.date().isoformat())
            log(conn, "read", paper_id, day=now.date().isoformat(), once_per_day=True)
        elif current:
            seconds = int((now - datetime.fromisoformat(current["started_at"])).total_seconds())
            conn.execute("UPDATE reading_sessions SET last_seen_at=?, seconds=?, open=? WHERE id=?",
                         (stamp, max(0, seconds), int(action != "stop"), current["id"]))
    return timer_state(paper_id)


def timer_state(paper_id: int) -> dict:
    with connect() as conn:
        total = conn.execute("SELECT COALESCE(SUM(seconds), 0) FROM reading_sessions WHERE paper_id=?", (paper_id,)).fetchone()[0]
        current = conn.execute("SELECT seconds FROM reading_sessions WHERE open=1 AND paper_id=?", (paper_id,)).fetchone()
    return {"running": current is not None, "seconds": total, "session_seconds": current["seconds"] if current else 0}


# ---------- recall ----------

def due_recalls(today: date | None = None) -> list[dict]:
    """Finished papers whose turn has come to be summarized again from memory."""
    today = today or date.today()
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, slug, title, abstract, finished_at, recall_due FROM papers
               WHERE status='done' AND recall_due IS NOT NULL AND recall_due <= ? ORDER BY recall_due, id""",
            (today.isoformat(),))
        return [dict(r) for r in rows]


def record_recall(paper_id: int, text: str, grade: str, today: date | None = None) -> dict:
    if grade not in ("good", "hazy"):
        raise ValueError(f"unknown recall grade: {grade}")
    text = text.strip()
    if not text:
        raise ValueError("기억나는 대로 한 문장이라도 적어주세요.")
    today = today or date.today()
    wait = RECALL_GOOD if grade == "good" else RECALL_HAZY
    with connect() as conn:
        conn.execute("INSERT INTO recalls (paper_id, day, text, grade) VALUES (?,?,?,?)",
                     (paper_id, today.isoformat(), text, grade))
        conn.execute("UPDATE papers SET recall_due=? WHERE id=?", ((today + timedelta(days=wait)).isoformat(), paper_id))
        log(conn, "recall", paper_id, grade, day=today.isoformat())
    return {"next": (today + timedelta(days=wait)).isoformat()}


def recalls_for(paper_id: int) -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT day, text, grade FROM recalls WHERE paper_id=? ORDER BY id DESC", (paper_id,))]


def undo_review() -> dict | None:
    """Take back the most recent grade: the card and the study log return to how they were. Works once."""
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='undo_review'").fetchone()
        if not row:
            return None
        saved = json.loads(row["value"])
        conn.execute("DELETE FROM settings WHERE key='undo_review'")
        if not conn.execute("SELECT 1 FROM cards WHERE id=?", (saved["id"],)).fetchone():
            return None  # 그 사이 카드가 지워졌다
        conn.execute("UPDATE cards SET box=?, due=?, last_reviewed=?, reviews=?, lapses=? WHERE id=?",
                     (saved["box"], saved["due"], saved["last_reviewed"], saved["reviews"], saved["lapses"], saved["id"]))
        conn.execute("DELETE FROM activity WHERE id=? AND kind='review'", (saved["activity_id"],))
        card = conn.execute(
            "SELECT c.*, p.title AS paper_title FROM cards c JOIN papers p ON p.id = c.paper_id WHERE c.id=?",
            (saved["id"],)).fetchone()
        return dict(card)


def monthly(today: date | None = None, months: int = 12) -> list[dict]:
    """Per-month totals for the last `months` months, oldest first, including months with nothing."""
    today = today or date.today()
    keys = []
    year, month = today.year, today.month
    for _ in range(months):
        keys.append(f"{year:04d}-{month:02d}")
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    keys.reverse()
    rows = {k: {"month": k, "done": 0, "reviews": 0, "notes": 0, "minutes": 0, "active_days": 0} for k in keys}
    since = keys[0] + "-01"
    with connect() as conn:
        for r in conn.execute("SELECT substr(finished_at, 1, 7) m, COUNT(*) n FROM papers "
                              "WHERE status='done' AND finished_at >= ? GROUP BY m", (since,)):
            if r["m"] in rows:
                rows[r["m"]]["done"] = r["n"]
        for r in conn.execute(
                """SELECT substr(day, 1, 7) m, SUM(kind='review') reviews, COUNT(DISTINCT CASE WHEN kind='note' THEN paper_id END) notes,
                          COUNT(DISTINCT day) days FROM activity WHERE day >= ? GROUP BY m""", (since,)):
            if r["m"] in rows:
                rows[r["m"]].update(reviews=r["reviews"] or 0, notes=r["notes"], active_days=r["days"])
        for r in conn.execute("SELECT substr(started_at, 1, 7) m, SUM(seconds) s FROM reading_sessions "
                              "WHERE started_at >= ? GROUP BY m", (since,)):
            if r["m"] in rows:
                rows[r["m"]]["minutes"] = (r["s"] or 0) // 60
    return list(rows.values())
