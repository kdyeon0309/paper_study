"""Paper Study - local FastAPI server. No API key: arXiv for search, files for notes."""
import json
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import arxiv, config, db, exporter, notes

Status = Literal["to_read", "reading", "done"]

db.init()
notes.migrate_legacy_names()

app = FastAPI(title="Paper Study", docs_url="/api/docs", redoc_url=None)


class PaperCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    authors: str = ""
    year: int | None = Field(default=None, ge=1900, le=2100)
    url: str = ""
    pdf_url: str = ""
    abstract: str = ""
    tags: str = ""
    status: Status = "to_read"
    arxiv_id: str | None = None
    published: str = ""
    categories: str = ""
    comment: str = ""


class PaperUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    authors: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    url: str | None = None
    abstract: str | None = None
    tags: str | None = None
    status: Status | None = None
    note_requested: bool | None = None


class ArxivAdd(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=50)


class NoteWrite(BaseModel):
    content: str = Field(max_length=500_000)
    base_mtime: float | None = None


class Grade(BaseModel):
    grade: Literal["again", "hard", "good"]


def _paper_or_404(paper_id: int) -> dict:
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(404, "논문을 찾을 수 없어요.")
    return paper


def _decorate(paper: dict) -> dict:
    paper["has_note"] = paper.get("note_mtime") is not None
    return paper


@app.exception_handler(arxiv.ArxivError)
async def arxiv_error(_, exc: arxiv.ArxivError):
    return JSONResponse({"detail": str(exc)}, status_code=502)


@app.exception_handler(ValueError)
async def value_error(_, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=400)


# ---------- search ----------

@app.get("/api/search")
def search(q: str, sort: Literal["relevance", "recent"] = "relevance", cat: str = "", start: int = 0):
    q = q.strip()
    if arxiv.looks_like_id(q):
        items = arxiv.fetch([q])
        result = {"total": len(items), "items": items}
    else:
        result = arxiv.search(q, sort, cat, max(0, start))
    saved = db.saved_arxiv_ids()
    return {
        "total": result["total"],
        "page_size": arxiv.PAGE_SIZE,
        "items": [{**item, "saved_id": saved.get(item["arxiv_id"])} for item in result["items"]],
    }


# ---------- papers ----------

@app.get("/api/papers")
def papers_list():
    return [_decorate(p) for p in notes.sync_all()]


@app.post("/api/papers")
def papers_create(paper: PaperCreate):
    saved, created = db.add_paper(paper.model_dump())
    return {"paper": _decorate(saved), "created": created}


@app.post("/api/papers/arxiv")
def papers_add_arxiv(body: ArxivAdd):
    """Add papers by arXiv id or URL; metadata comes from arXiv."""
    wanted = list(dict.fromkeys(i for i in (arxiv.parse_id(x) for x in body.ids) if i))
    if not wanted:
        raise HTTPException(400, "arXiv ID를 찾지 못했어요. 예: 2010.11929")
    saved = db.saved_arxiv_ids()
    existing = [i for i in wanted if i in saved]
    fetched = {item["arxiv_id"]: item for item in arxiv.fetch([i for i in wanted if i not in saved])}
    added = [db.add_paper(fetched[i])[0] for i in wanted if i in fetched]
    return {
        "added": [_decorate(p) for p in added],
        "existing": existing,
        "failed": [i for i in wanted if i not in saved and i not in fetched],
    }


@app.get("/api/papers/{paper_id}")
def papers_get(paper_id: int):
    paper = _paper_or_404(paper_id)
    if notes.sync(paper):
        paper = _paper_or_404(paper_id)
    return {
        "paper": _decorate(paper),
        "note": notes.read(paper),
        "cards": db.cards_for(paper_id),
        "bibtex": exporter.bibtex(paper),
    }


@app.patch("/api/papers/{paper_id}")
def papers_update(paper_id: int, fields: PaperUpdate):
    paper = db.update_paper(paper_id, fields.model_dump(exclude_none=True))
    if not paper:
        raise HTTPException(404, "논문을 찾을 수 없어요.")
    return _decorate(paper)


@app.delete("/api/papers/{paper_id}")
def papers_delete(paper_id: int):
    """Removes the library entry. The note file stays on disk on purpose."""
    paper = _paper_or_404(paper_id)
    db.delete_paper(paper_id)
    return {"ok": True, "note_kept": notes.read(paper)["path"] if notes.read(paper)["exists"] else None}


@app.put("/api/papers/{paper_id}/note")
def note_write(paper_id: int, body: NoteWrite):
    paper = _paper_or_404(paper_id)
    try:
        note = notes.write(paper, body.content, body.base_mtime)
    except notes.Conflict:
        raise HTTPException(409, "노트 파일이 다른 곳에서 바뀌었어요. 다시 불러온 뒤 수정해주세요.")
    return {"note": note, "cards": db.cards_for(paper_id)}


@app.get("/api/note-template", response_class=PlainTextResponse)
def note_template():
    return notes.template()


# ---------- review ----------

@app.get("/api/review/due")
def review_due():
    notes.sync_all()
    return db.due_cards()


@app.post("/api/review/{card_id}")
def review_grade(card_id: int, body: Grade):
    card = db.grade_card(card_id, body.grade)
    if not card:
        raise HTTPException(404, "카드를 찾을 수 없어요.")
    return card


# ---------- dashboard / roadmap / surveys ----------

@app.get("/api/stats")
def stats():
    papers = notes.sync_all()
    result = db.stats()
    result["notes"] = sum(p["note_mtime"] is not None for p in papers)
    result["note_requests"] = sum(bool(p["note_requested"]) for p in papers)
    return result


@app.get("/api/roadmaps")
def roadmaps():
    if not config.ROADMAP_FILE.exists():
        return []
    tracks = json.loads(config.ROADMAP_FILE.read_text(encoding="utf-8"))
    by_arxiv = {p["arxiv_id"]: p for p in db.list_papers() if p["arxiv_id"]}
    for track in tracks:
        for item in track["papers"]:
            saved = by_arxiv.get(item["arxiv_id"])
            item["paper_id"] = saved["id"] if saved else None
            item["status"] = saved["status"] if saved else None
    return tracks


@app.get("/api/surveys")
def surveys_list():
    return notes.list_surveys()


@app.get("/api/surveys/{name}", response_class=PlainTextResponse)
def surveys_get(name: str):
    content = notes.read_survey(name)
    if content is None:
        raise HTTPException(404, "서베이를 찾을 수 없어요.")
    return content


# ---------- export / import ----------

@app.get("/api/export.json")
def export_json():
    return JSONResponse(exporter.export_all(), headers={"Content-Disposition": 'attachment; filename="paper-study-backup.json"'})


@app.get("/api/export.bib", response_class=PlainTextResponse)
def export_bib():
    return PlainTextResponse(exporter.bibtex_all(db.list_papers()),
                             headers={"Content-Disposition": 'attachment; filename="paper-study.bib"'})


@app.post("/api/import")
def import_json(data: dict):
    return exporter.import_all(data)


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
