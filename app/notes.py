"""Markdown notes on disk. The web editor and Claude Code both write the same files."""
import re
from datetime import date
from pathlib import Path

from . import arxiv, config, db

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


def scan_cards(text: str) -> list[dict]:
    """Find `Q: ... / A: ...` pairs with the line range each one occupies.

    An answer runs until a blank line, a heading, or the next Q.
    """
    found, question, answer, in_fence, start, end = [], None, None, False, 0, 0

    def flush():
        nonlocal question, answer
        if question and answer is not None and (body := "\n".join(answer).strip()):
            found.append({"question": question, "answer": body, "start": start, "end": end})
        question, answer = None, None

    for i, line in enumerate(text.splitlines()):
        if _FENCE.match(line.strip()):
            in_fence = not in_fence
            if answer is not None:
                answer.append(line)
                end = i + 1
            continue
        if in_fence:
            if answer is not None:
                answer.append(line)
                end = i + 1
            continue
        if m := _Q.match(line):
            flush()
            question, start = m.group(1).strip(), i
        elif question and answer is None and (m := _A.match(line)):
            answer, end = [m.group(1)], i + 1
        elif answer is not None:
            if not line.strip() or line.lstrip().startswith("#"):
                flush()
            else:
                answer.append(line.strip())
                end = i + 1
        elif question and line.strip():
            question = None  # a Q with no A right after it is just prose
    flush()
    return found


def parse_cards(text: str) -> list[tuple[str, str]]:
    """Question/answer pairs for the review deck. A repeated question keeps its last answer."""
    return list({c["question"]: c["answer"] for c in scan_cards(text)}.items())


def replace_card(text: str, question: str, new_question: str | None, new_answer: str | None) -> str:
    """Rewrite one card inside a note. Passing None for both removes the card's lines."""
    spans = [c for c in scan_cards(text) if c["question"] == question]
    if not spans:
        raise KeyError(question)
    lines = text.splitlines()
    for span in reversed(spans):  # 뒤에서부터 바꿔야 앞쪽 줄 번호가 유지된다
        if new_question is None:
            end = span["end"] + (1 if span["end"] < len(lines) and not lines[span["end"]].strip() else 0)
            lines[span["start"]:end] = []
        else:
            lines[span["start"]:span["end"]] = [f"Q: {new_question}", f"A: {new_answer}"]
    return "\n".join(lines) + ("\n" if text.endswith("\n") or not text else "")


def clean_card(question: str, answer: str) -> tuple[str, str]:
    """Normalize card text so it survives a round trip through the note file."""
    question = " ".join(str(question).split())
    answer = "\n".join(line.rstrip() for line in str(answer).strip().splitlines() if line.strip())
    if not question or not answer:
        raise ValueError("질문과 답을 모두 적어주세요.")
    if any(_Q.match(line) or line.lstrip().startswith("#") for line in answer.splitlines()):
        raise ValueError("답 안에 'Q:'나 '#'으로 시작하는 줄은 넣을 수 없어요. 카드가 거기서 끊겨요.")
    return question, answer


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


# ---------- full-text search ----------

def _snippets(text: str, needle: str, limit: int = 3) -> list[str]:
    found = []
    for line in text.splitlines():
        clean = line.strip()
        pos = clean.casefold().find(needle)
        if pos < 0:
            continue
        lo = max(0, pos - 60)
        found.append(("…" if lo else "") + clean[lo:pos + len(needle) + 100] + ("…" if len(clean) > pos + len(needle) + 100 else ""))
        if len(found) == limit:
            break
    return found


def search(query: str) -> list[dict]:
    """Find notes and surveys whose text contains the query (case-insensitive substring)."""
    # ponytail: 매 요청마다 파일을 전부 읽는다. 노트 수천 개까지는 충분하고, 느려지면 SQLite FTS5로 옮긴다.
    needle = " ".join(query.split()).casefold()
    if len(needle) < 2:
        return []
    results = []
    for paper in db.list_papers():
        path = note_path(paper["slug"])
        if path.exists() and (hits := _snippets(path.read_text(encoding="utf-8"), needle)):
            results.append({"kind": "note", "paper_id": paper["id"], "title": paper["title"], "snippets": hits})
    for survey in list_surveys():
        text = (config.SURVEYS_DIR / f"{survey['name']}.md").read_text(encoding="utf-8")
        if hits := _snippets(text, needle):
            results.append({"kind": "survey", "name": survey["name"], "title": survey["title"], "snippets": hits})
    return results


# ---------- links between papers ----------

_WIKI = re.compile(r"\[\[([^\[\]\n]{1,200})\]\]")


def _targets(text: str, papers: list[dict]) -> tuple[dict[str, int], set[int]]:
    """Papers a note points at: `[[arXiv id / slug / exact title]]` and bare arXiv ids or links."""
    by_key = {}
    for p in papers:
        by_key[p["slug"].casefold()] = p["id"]
        by_key[p["title"].casefold()] = p["id"]
        if p["arxiv_id"]:
            by_key[p["arxiv_id"].casefold()] = p["id"]
    wiki, linked = {}, set()
    for inner in _WIKI.findall(text):
        key = " ".join(inner.split()).casefold()
        target = by_key.get(key) or by_key.get((arxiv.parse_id(inner) or "").casefold())
        if target:
            wiki[inner] = target
            linked.add(target)
    by_arxiv = {p["arxiv_id"]: p["id"] for p in papers if p["arxiv_id"]}
    for found in arxiv.find_ids(text):
        if found in by_arxiv:
            linked.add(by_arxiv[found])
    return wiki, linked


def links(paper: dict) -> dict:
    """Outgoing links from this paper's note, and the notes that mention this paper."""
    # ponytail: 역방향 링크는 요청마다 모든 노트를 읽는다. 본문 검색과 같은 한계이고, 느려지면 링크 테이블을 둔다.
    papers = db.list_papers()
    titles = {p["id"]: p["title"] for p in papers}
    wiki, out, back = {}, set(), []
    for other in papers:
        path = note_path(other["slug"])
        if not path.exists():
            continue
        found_wiki, linked = _targets(path.read_text(encoding="utf-8"), papers)
        if other["id"] == paper["id"]:
            wiki, out = found_wiki, linked - {paper["id"]}
        elif paper["id"] in linked:
            back.append({"id": other["id"], "title": other["title"]})
    return {
        "wiki": {inner: {"id": target, "title": titles[target]} for inner, target in wiki.items()},
        "out": sorted(({"id": i, "title": titles[i]} for i in out), key=lambda x: x["title"]),
        "back": sorted(back, key=lambda x: x["title"]),
        "surveys": surveys_mentioning(paper),
    }


def graph() -> dict:
    """Every paper that mentions or is mentioned by another, with one edge per mention (from -> to)."""
    papers = db.list_papers()
    edges = set()
    for paper in papers:
        path = note_path(paper["slug"])
        if path.exists():
            _, linked = _targets(path.read_text(encoding="utf-8"), papers)
            edges.update((paper["id"], target) for target in linked if target != paper["id"])
    connected = {i for edge in edges for i in edge}
    return {
        "nodes": [{"id": p["id"], "title": p["title"], "status": p["status"], "year": p["year"],
                   "tags": p["tags"], "arxiv_id": p["arxiv_id"]}
                  for p in papers if p["id"] in connected],
        "edges": [{"from": a, "to": b} for a, b in sorted(edges)],
        "isolated": len(papers) - len(connected),
    }


_CARD_HEADING = re.compile(r"^#{1,6}\s*복습\s*카드")


def append_card(text: str, question: str, answer: str, title: str) -> str:
    """Add a card to a note: inside its '복습 카드' section if there is one, else in a new section at the end."""
    if any(c["question"] == question for c in scan_cards(text)):
        raise ValueError("같은 질문의 카드가 이미 있어요.")
    card = [f"Q: {question}", f"A: {answer}"]
    lines = text.splitlines()
    if not text.strip():
        return "\n".join([f"# {title}", "", "## 복습 카드", *card]) + "\n"
    start = next((i for i, line in enumerate(lines) if _CARD_HEADING.match(line)), None)
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join([*lines, "", "## 복습 카드", *card]) + "\n"
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("#")), len(lines))
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    gap = [""] if end > start + 1 else []
    tail = [""] if end < len(lines) and lines[end].strip() else []
    lines[end:end] = [*gap, *card, *tail]
    return "\n".join(lines) + "\n"


def summary_line(paper: dict) -> str:
    """The note's one-sentence summary: its first blockquote line, without a leading label."""
    path = note_path(paper["slug"])
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith(">"):
            text = line.lstrip()[1:].strip()
            text = re.sub(r"^\**한\s*문장\s*요약\s*[:：]?\**\s*[:：]?\s*", "", text)
            if text:
                return text
    return ""


def survey_links(name: str) -> dict | None:
    """Library papers a survey mentions, and arXiv papers it cites that are not saved yet."""
    text = read_survey(name)
    if text is None:
        return None
    papers = db.list_papers()
    by_id = {p["id"]: p for p in papers}
    wiki, linked = _targets(text, papers)
    saved = {p["arxiv_id"] for p in papers if p["arxiv_id"]}
    return {
        "wiki": {inner: {"id": t, "title": by_id[t]["title"]} for inner, t in wiki.items()},
        "papers": sorted(({"id": i, "title": by_id[i]["title"], "status": by_id[i]["status"]} for i in linked),
                         key=lambda x: x["title"]),
        "missing": sorted(arxiv.find_ids(text) - saved),
    }


def surveys_mentioning(paper: dict) -> list[dict]:
    papers = db.list_papers()
    found = []
    for survey in list_surveys():
        _, linked = _targets(read_survey(survey["name"]) or "", papers)
        if paper["id"] in linked:
            found.append({"name": survey["name"], "title": survey["title"]})
    return found
