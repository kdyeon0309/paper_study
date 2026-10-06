"""Paper Study Web - local FastAPI server (free: arXiv API + note files)."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import arxiv, db

app = FastAPI(title="Paper Study Web")

STATIC_DIR = Path(__file__).resolve().parent / "static"
NOTES_DIR = Path(__file__).resolve().parent.parent / "notes"


class PaperCreate(BaseModel):
    title: str
    authors: str = ""
    year: int | None = None
    url: str = ""
    tags: str = ""
    status: str = "to_read"
    summary: str = ""


class PaperUpdate(BaseModel):
    title: str | None = None
    authors: str | None = None
    year: int | None = None
    url: str | None = None
    tags: str | None = None
    status: str | None = None
    summary: str | None = None


@app.get("/api/search")
def search(q: str):
    try:
        return arxiv.search(q)
    except Exception as e:
        raise HTTPException(502, f"arXiv 검색 실패: {e}")


@app.get("/api/papers")
def papers_list():
    papers = db.list_papers()
    for p in papers:
        p["has_note"] = (NOTES_DIR / f"{p['id']}.md").exists()
    return papers


@app.post("/api/papers")
def papers_create(paper: PaperCreate):
    return db.add_paper(**paper.model_dump())


@app.patch("/api/papers/{paper_id}")
def papers_update(paper_id: int, fields: PaperUpdate):
    return db.update_paper(paper_id, fields.model_dump(exclude_none=True))


@app.delete("/api/papers/{paper_id}")
def papers_delete(paper_id: int):
    db.delete_paper(paper_id)
    return {"ok": True}


@app.get("/api/notes/{paper_id}", response_class=PlainTextResponse)
def note_read(paper_id: int):
    path = NOTES_DIR / f"{paper_id}.md"
    if not path.exists():
        raise HTTPException(404, "노트 없음")
    return path.read_text()


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
