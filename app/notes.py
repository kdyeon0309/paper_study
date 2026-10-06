"""Markdown notes on disk. The web editor and Claude Code both write the same files."""
import re
from datetime import date
from pathlib import Path

from . import config, db

SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
TEMPLATE_FILE = "_TEMPLATE.md"
_FENCE = re.compile(r"^(```|~~~)")
_Q = re.compile(r"^\s*(?:[-*]\s+)?\**Q\**\s*[:：]\**\s*(.+)$", re.I)
_A = re.compile(r"^\s*(?:[-*]\s+)?\**A\**\s*[:：]\**\s*(.*)$", re.I)


class Conflict(Exception):
    """The file on disk is newer than the copy the editor started from."""


def note_path(slug: str) -> Path:
    if not SLUG_RE.match(slug or ""):
        raise ValueError(f"잘못된 노트 이름: {slug!r}")
    return config.NOTES_DIR / f"{slug}.md"


def mtime_of(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return None


def parse_cards(text: str) -> list[tuple[str, str]]:
    """Extract `Q: ... / A: ...` pairs. Answers run until a blank line, heading, or next Q."""
    cards, question, answer, in_fence = [], None, None, False

    def flush():
        nonlocal question, answer
        if question and answer is not None and (body := "\n".join(answer).strip()):
            cards.append((question, body))
        question, answer = None, None

    for line in text.splitlines():
        if _FENCE.match(line.strip()):
            in_fence = not in_fence
            if answer is not None:
                answer.append(line)
            continue
        if in_fence:
            if answer is not None:
                answer.append(line)
            continue
        if m := _Q.match(line):
            flush()
            question = m.group(1).strip()
        elif question and answer is None and (m := _A.match(line)):
            answer = [m.group(1)]
        elif answer is not None:
            if not line.strip() or line.lstrip().startswith("#"):
                flush()
            else:
                answer.append(line.strip())
        elif question and line.strip():
            question = None  # a Q with no A right after it is just prose
    flush()
    return list(dict(cards).items())


def read(paper: dict) -> dict:
    path = note_path(paper["slug"])
    mtime = mtime_of(path)
    return {
        "exists": mtime is not None,
        "content": path.read_text(encoding="utf-8") if mtime is not None else "",
        "mtime": mtime,
        "path": f"notes/{path.name}",
    }


def sync(paper: dict) -> bool:
    """Pick up a note that changed on disk: rebuild its cards and log the study day."""
    path = note_path(paper["slug"])
    mtime = mtime_of(path)
    if mtime == paper.get("note_mtime"):
        return False
    if mtime is None:
        db.sync_cards(paper["id"], [])
    else:
        db.sync_cards(paper["id"], parse_cards(path.read_text(encoding="utf-8")))
        with db.connect() as conn:
            db.log(conn, "note", paper["id"], day=date.fromtimestamp(mtime).isoformat(), once_per_day=True)
    db.set_note_state(paper["id"], mtime, clear_request=mtime is not None)
    return True


def sync_all() -> list[dict]:
    papers = db.list_papers()
    if any([sync(p) for p in papers]):
        papers = db.list_papers()
    return papers


def write(paper: dict, content: str, base_mtime: float | None) -> dict:
    """Save from the web editor. Refuses to clobber a file that changed since it was loaded."""
    path = note_path(paper["slug"])
    current = mtime_of(path)
    if current is not None and (base_mtime is None or abs(current - base_mtime) > 1e-6):
        raise Conflict()
    config.NOTES_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)
    sync(paper)
    return read(paper)


def migrate_legacy_names():
    """v0.1 named notes by row id (notes/3.md); v0.2 names them by slug."""
    if not config.NOTES_DIR.exists():
        return
    for paper in db.list_papers():
        old, new = config.NOTES_DIR / f"{paper['id']}.md", note_path(paper["slug"])
        if old.exists() and not new.exists():
            old.rename(new)


def template() -> str:
    path = config.NOTES_DIR / TEMPLATE_FILE
    if not path.exists():
        path = config.REPO / "notes" / TEMPLATE_FILE
    return path.read_text(encoding="utf-8") if path.exists() else ""


# ---------- surveys ----------

def _title_of(path: Path) -> str:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("# "):
                return line[2:].strip()
    return path.stem


def list_surveys() -> list[dict]:
    if not config.SURVEYS_DIR.exists():
        return []
    files = sorted(config.SURVEYS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.stem, "title": _title_of(p), "updated": date.fromtimestamp(p.stat().st_mtime).isoformat()}
            for p in files if SLUG_RE.match(p.stem)]


def read_survey(name: str) -> str | None:
    if not SLUG_RE.match(name or ""):
        return None
    path = config.SURVEYS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8") if path.exists() else None
