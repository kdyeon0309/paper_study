"""Backup (JSON) and citation (BibTeX) export, plus JSON import."""
import re
import unicodedata

from . import db, notes

_STOP = {"a", "an", "the", "on", "of", "for", "to", "in", "and", "with", "is", "are", "towards", "toward"}


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def bib_key(paper: dict) -> str:
    first_author = (paper.get("authors") or "").split(",")[0].split()
    surname = re.sub(r"[^a-z]", "", _ascii(first_author[-1]).lower()) if first_author else ""
    words = re.findall(r"[a-z0-9]+", _ascii(paper.get("title") or "").lower())
    word = next((w for w in words if w not in _STOP), "")
    return f"{surname or 'anon'}{paper.get('year') or ''}{word}"


def bibtex(paper: dict) -> str:
    def clean(value):
        return str(value or "").replace("{", "").replace("}", "")

    fields = [
        ("title", f"{{{clean(paper['title'])}}}"),
        ("author", clean(paper.get("authors")).replace(", ", " and ")),
        ("year", clean(paper.get("year"))),
    ]
    if paper.get("arxiv_id"):
        primary = (paper.get("categories") or "").split(",")[0].strip()
        fields += [("eprint", paper["arxiv_id"]), ("archivePrefix", "arXiv"), ("primaryClass", primary)]
    fields.append(("url", paper.get("url")))
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields if v)
    return f"@misc{{{bib_key(paper)},\n{body}\n}}"


def bibtex_all(papers: list[dict]) -> str:
    return "\n\n".join(bibtex(p) for p in papers) + "\n"


EXPORT_FIELDS = ("slug", "arxiv_id", "title", "authors", "year", "published", "url", "pdf_url", "abstract",
                 "categories", "comment", "tags", "status", "created_at", "finished_at")


def export_all() -> dict:
    items = []
    for paper in db.list_papers():
        item = {k: paper.get(k) for k in EXPORT_FIELDS}
        note = notes.read(paper)
        if note["exists"]:
            item["note"] = note["content"]
        items.append(item)
    return {"app": "paper-study", "version": 2, "papers": items}


def import_all(data: dict) -> dict:
    """Add papers that are not in the library yet. Existing papers and notes are never overwritten."""
    if not isinstance(data, dict) or not isinstance(data.get("papers"), list):
        raise ValueError("Paper Study 백업 파일이 아니에요.")
    added = skipped = notes_written = 0
    # arXiv 논문은 ID로 중복을 거르고, ID가 없는 항목은 제목으로 거른다
    manual_titles = {p["title"] for p in db.list_papers() if not p["arxiv_id"]}
    for item in data["papers"]:
        title = " ".join(str(item.get("title") or "").split()) if isinstance(item, dict) else ""
        if not title or (not item.get("arxiv_id") and title in manual_titles):
            skipped += 1
            continue
        paper, created = db.add_paper(item)
        added += created
        skipped += not created
        if isinstance(item.get("note"), str) and not notes.read(paper)["exists"]:
            notes.write(paper, item["note"], None)
            notes_written += 1
    return {"added": added, "skipped": skipped, "notes_written": notes_written}
