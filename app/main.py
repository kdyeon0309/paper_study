"""Paper Study - local FastAPI server. No API key: arXiv for search, files for notes."""
import json
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import VERSION, arxiv, config, db, exporter, notes, roadmaps as tracks

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


class SavedSearch(BaseModel):
    q: str = Field(min_length=1, max_length=200)
    cat: str = Field(default="", max_length=20)


class CardEdit(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=5000)


class TimerAction(BaseModel):
    action: Literal["start", "ping", "stop"]


class Recall(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    grade: Literal["good", "hazy"]


class Goals(BaseModel):
    goal_days: int = Field(ge=0, le=7)
    goal_papers: int = Field(ge=0, le=50)


class TrackCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["기초", "논문", "새 영역"] = "논문"
    description: str = Field(default="", max_length=300)


class TrackUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    kind: Literal["기초", "논문", "새 영역"] | None = None
    description: str | None = Field(default=None, max_length=300)


class TrackPaperAdd(BaseModel):
    ref: str = Field(min_length=1, max_length=200)
    why: str = Field(default="", max_length=300)


class TrackPaperEdit(BaseModel):
    why: str | None = Field(default=None, max_length=300)
    move: Literal[-1, 0, 1] = 0


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


FIELD_NAMES = {
    "title": "제목", "authors": "저자", "year": "연도", "url": "링크", "tags": "태그", "status": "읽기 상태",
    "question": "질문", "answer": "답", "content": "노트 내용", "grade": "평가", "text": "내용", "q": "검색어",
    "name": "이름", "kind": "종류", "description": "설명", "ref": "arXiv ID", "why": "읽는 이유", "ids": "arXiv ID 목록",
    "goal_days": "공부한 날 목표", "goal_papers": "완독 목표", "action": "동작", "move": "이동",
}


def _explain(error: dict) -> str:
    """One validation error as a Korean sentence."""
    kind, ctx = error.get("type", ""), error.get("ctx") or {}
    field = next((str(p) for p in reversed(error.get("loc", ())) if isinstance(p, str) and p not in ("body", "query", "path")), "")
    name = FIELD_NAMES.get(field, field or "입력값")
    if kind == "missing":
        return f"{name}: 꼭 필요한 값이에요."
    if kind in ("string_too_short", "too_short"):
        return f"{name}: 비워둘 수 없어요."
    if kind in ("string_too_long", "too_long"):
        return f"{name}: 너무 길어요 (최대 {ctx.get('max_length', '?')})."
    if kind in ("less_than_equal", "greater_than_equal", "less_than", "greater_than"):
        bound = ctx.get("le", ctx.get("ge", ctx.get("lt", ctx.get("gt"))))
        return f"{name}: {bound} {'이하여야' if kind.startswith('less') else '이상이어야'} 해요."
    if kind in ("int_parsing", "int_type", "int_from_float", "float_parsing"):
        return f"{name}: 숫자로 적어주세요."
    if kind in ("literal_error", "enum"):
        return f"{name}: {str(ctx.get('expected', '정해진 값')).replace(' or ', ', ')} 중 하나여야 해요."
    if kind in ("json_invalid", "dict_type", "model_attributes_type"):
        return "보낸 내용의 형식이 올바르지 않아요."
    if kind in ("string_type", "bool_parsing", "bool_type", "list_type"):
        return f"{name}: 값의 종류가 맞지 않아요."
    return f"{name}: 값을 확인해주세요."


@app.exception_handler(RequestValidationError)
async def validation_error(_, exc: RequestValidationError):
    return JSONResponse({"detail": " ".join(dict.fromkeys(_explain(e) for e in exc.errors()))}, status_code=422)


@app.exception_handler(KeyError)
async def key_error(_, exc: KeyError):
    return JSONResponse({"detail": "찾을 수 없어요."}, status_code=404)


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


@app.get("/api/searches")
def searches_list():
    return db.saved_searches()


def _newest(q: str, cat: str) -> tuple[list[dict], bool]:
    result = arxiv.search(q, "recent", cat)
    return result["items"], result["cached"]


@app.post("/api/searches")
def searches_save(body: SavedSearch):
    """Save a search. What is on arXiv right now counts as already seen."""
    try:
        items, _ = _newest(body.q, body.cat)
    except arxiv.ArxivError:
        items = []  # 기준점은 첫 확인 때 잡는다
    return db.save_search(body.q, body.cat, max((i["published_at"] for i in items), default=""))


@app.get("/api/searches/{search_id}/new")
def searches_new(search_id: int):
    """How many papers appeared for this search since it was last looked at."""
    saved = db.get_search(search_id)
    if not saved:
        raise HTTPException(404, "저장한 검색을 찾을 수 없어요.")
    items, cached = _newest(saved["q"], saved["cat"])
    if not saved["last_seen_at"]:
        db.mark_search_seen(search_id, max((i["published_at"] for i in items), default=""))
        return {"new": 0, "more": False, "cached": cached}
    fresh = [i for i in items if i["published_at"] > saved["last_seen_at"]]
    return {"new": len(fresh), "more": bool(items) and len(fresh) == len(items), "cached": cached}


@app.post("/api/searches/{search_id}/seen")
def searches_seen(search_id: int):
    saved = db.get_search(search_id)
    if not saved:
        raise HTTPException(404, "저장한 검색을 찾을 수 없어요.")
    items, _ = _newest(saved["q"], saved["cat"])
    db.mark_search_seen(search_id, max((i["published_at"] for i in items), default=""))
    return {"ok": True}


@app.delete("/api/searches/{search_id}")
def searches_delete(search_id: int):
    if not db.delete_search(search_id):
        raise HTTPException(404, "저장한 검색을 찾을 수 없어요.")
    return {"ok": True}


# ---------- papers ----------

@app.get("/api/papers")
def papers_list():
    # 목록 화면은 초록을 쓰지 않는다. 빼면 논문 1,000편 기준 응답이 1.9MB에서 수백 KB로 준다.
    return [_decorate({k: v for k, v in p.items() if k != "abstract"}) for p in notes.sync_all()]


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


def _tracks_of(paper: dict) -> list[dict]:
    """Where this paper sits in each roadmap track, and what comes after it."""
    if not paper["arxiv_id"]:
        return []
    index = _library_index()
    found = []
    for track in tracks.all_tracks():
        ids = [p["arxiv_id"] for p in track["papers"]]
        if paper["arxiv_id"] not in ids:
            continue
        i = ids.index(paper["arxiv_id"])
        nxt = track["papers"][i + 1] if i + 1 < len(ids) else None
        found.append({
            "key": track["key"], "name": track["name"], "position": i + 1, "total": len(ids),
            "next": nxt and {"title": nxt["title"], "arxiv_id": nxt["arxiv_id"],
                             "paper_id": index.get(nxt["arxiv_id"], {}).get("id")},
        })
    return found


@app.get("/api/papers/{paper_id}")
def papers_get(paper_id: int):
    paper = _paper_or_404(paper_id)
    if notes.sync(paper):
        paper = _paper_or_404(paper_id)
    return {
        "paper": _decorate(paper),
        "tracks": _tracks_of(paper),
        "links": notes.links(paper),
        "timer": db.timer_state(paper_id),
        "recalls": db.recalls_for(paper_id),
        "note": notes.read(paper),
        "cards": db.cards_for(paper_id),
        "bibtex": exporter.bibtex(paper),
    }


@app.post("/api/papers/{paper_id}/refresh")
def papers_refresh(paper_id: int):
    """Re-read title, authors, abstract and categories from arXiv."""
    paper = _paper_or_404(paper_id)
    if not paper["arxiv_id"]:
        raise HTTPException(400, "arXiv 논문만 정보를 새로 가져올 수 있어요.")
    items = arxiv.fetch([paper["arxiv_id"]])
    if not items:
        raise HTTPException(502, "arXiv에서 이 논문을 찾지 못했어요.")
    return _decorate(db.set_metadata(paper_id, items[0]))


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
    return {"note": note, "cards": db.cards_for(paper_id), "links": notes.links(paper)}


def _rewrite_card(card_id: int, question: str | None, answer: str | None) -> dict:
    """Edit or remove a card by rewriting its Q/A lines in the note, which stays the single source."""
    card = db.get_card(card_id)
    if not card:
        raise HTTPException(404, "카드를 찾을 수 없어요.")
    paper = _paper_or_404(card["paper_id"])
    note = notes.read(paper)
    try:
        text = notes.replace_card(note["content"], card["question"], question, answer)
    except KeyError:
        raise HTTPException(409, "노트에서 이 카드를 찾지 못했어요. 노트가 바뀌었을 수 있으니 새로고침해주세요.")
    if question is not None:
        db.rename_card(card_id, question, answer)
    notes.write(paper, text, note["mtime"])
    return {"cards": db.cards_for(paper["id"]), "card": db.get_card(card_id)}


@app.post("/api/papers/{paper_id}/cards")
def cards_create(paper_id: int, body: CardEdit):
    """Add a card without opening the editor: it is appended to the note's 복습 카드 section."""
    paper = _paper_or_404(paper_id)
    question, answer = notes.clean_card(body.question, body.answer)
    note = notes.read(paper)
    notes.write(paper, notes.append_card(note["content"], question, answer, paper["title"]), note["mtime"])
    return {"cards": db.cards_for(paper_id)}


@app.get("/api/graph")
def graph():
    notes.sync_all()
    return notes.graph()


@app.patch("/api/cards/{card_id}")
def cards_edit(card_id: int, body: CardEdit):
    return _rewrite_card(card_id, *notes.clean_card(body.question, body.answer))


@app.delete("/api/cards/{card_id}")
def cards_delete(card_id: int):
    return _rewrite_card(card_id, None, None)


@app.post("/api/papers/{paper_id}/timer")
def paper_timer(paper_id: int, body: TimerAction):
    _paper_or_404(paper_id)
    return db.timer(paper_id, body.action)


@app.get("/api/recall/due")
def recall_due():
    return [{k: p[k] for k in ("id", "title", "finished_at")} for p in db.due_recalls()]


@app.get("/api/recall/{paper_id}/reference")
def recall_reference(paper_id: int):
    """What to compare a from-memory summary against: the note's own summary line, else the abstract."""
    paper = _paper_or_404(paper_id)
    summary = notes.summary_line(paper)
    return {"text": summary or paper["abstract"], "source": "note" if summary else "abstract"}


@app.post("/api/recall/{paper_id}")
def recall_record(paper_id: int, body: Recall):
    _paper_or_404(paper_id)
    return db.record_recall(paper_id, body.text, body.grade)


@app.get("/api/about")
def about():
    """Version and where the data lives, for the settings screen."""
    return {
        "version": VERSION,
        "home": str(config.HOME),
        "files": {"db": config.DB_PATH.name, "notes": config.NOTES_DIR.name, "surveys": config.SURVEYS_DIR.name,
                  "tracks": config.USER_ROADMAP_FILE.name, "backups": db.backup_dir().name},
        "backups": sorted(p.name for p in db.backup_dir().glob("papers-*.db")),
        "counts": {"papers": len(db.list_papers()), "surveys": len(notes.list_surveys()),
                   "tracks": len(tracks.user_tracks()), "searches": len(db.saved_searches())},
    }


@app.get("/api/goals")
def goals_get():
    return db.goals()


@app.put("/api/goals")
def goals_set(body: Goals):
    return db.set_goals(body.goal_days, body.goal_papers)


@app.get("/api/note-template", response_class=PlainTextResponse)
def note_template():
    return notes.template()


# ---------- review ----------

@app.get("/api/review/due")
def review_due():
    notes.sync_all()
    return db.due_cards()


@app.get("/api/review/weak")
def review_weak():
    notes.sync_all()
    return {"cards": db.weak_cards(), "tags": db.tag_accuracy()}


@app.post("/api/review/undo")
def review_undo():
    card = db.undo_review()
    if not card:
        raise HTTPException(404, "되돌릴 평가가 없어요.")
    return card


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
    result["recalls_due"] = len(db.due_recalls())
    return result


@app.get("/api/monthly")
def monthly():
    notes.sync_all()
    return db.monthly()


@app.get("/api/weekly")
def weekly(offset: int = 0):
    notes.sync_all()
    return db.weekly(offset=max(-520, min(0, offset)))


@app.get("/api/notes/search")
def notes_search(q: str):
    return notes.search(q)


def _with_library(track: dict, by_arxiv: dict) -> dict:
    for item in track["papers"]:
        saved = by_arxiv.get(item["arxiv_id"])
        item["paper_id"] = saved["id"] if saved else None
        item["status"] = saved["status"] if saved else None
    return track


def _library_index() -> dict:
    return {p["arxiv_id"]: p for p in db.list_papers() if p["arxiv_id"]}


@app.get("/api/roadmaps")
def roadmaps():
    index = _library_index()
    return [_with_library(t, index) for t in tracks.all_tracks()]


@app.post("/api/roadmaps")
def roadmaps_create(body: TrackCreate):
    return {**tracks.create(body.name, body.kind, body.description), "editable": True}


@app.patch("/api/roadmaps/{key}")
def roadmaps_update(key: str, body: TrackUpdate):
    return tracks.update(key, body.model_dump(exclude_none=True))


@app.delete("/api/roadmaps/{key}")
def roadmaps_delete(key: str):
    tracks.delete(key)
    return {"ok": True}


@app.post("/api/roadmaps/{key}/papers")
def roadmaps_add_paper(key: str, body: TrackPaperAdd):
    arxiv_id = arxiv.parse_id(body.ref)
    if not arxiv_id:
        raise HTTPException(400, "arXiv ID나 링크를 적어주세요. 예: 2010.11929")
    saved = _library_index().get(arxiv_id)
    item = saved or next(iter(arxiv.fetch([arxiv_id])), None)
    if not item:
        raise HTTPException(404, "arXiv에서 이 논문을 찾지 못했어요.")
    return tracks.add_paper(key, item, body.why)


@app.patch("/api/roadmaps/{key}/papers/{arxiv_id:path}")
def roadmaps_edit_paper(key: str, arxiv_id: str, body: TrackPaperEdit):
    return tracks.edit_paper(key, arxiv_id, body.why, body.move)


@app.delete("/api/roadmaps/{key}/papers/{arxiv_id:path}")
def roadmaps_remove_paper(key: str, arxiv_id: str):
    return tracks.remove_paper(key, arxiv_id)


@app.get("/api/surveys")
def surveys_list():
    return notes.list_surveys()


@app.get("/api/surveys/{name}/links")
def surveys_links(name: str):
    found = notes.survey_links(name)
    if found is None:
        raise HTTPException(404, "서베이를 찾을 수 없어요.")
    return found


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


class FreshStatic(StaticFiles):
    """Static files the browser must revalidate before reuse.

    Without this, a browser keeps running the JS modules it cached before an update. ETags keep the check cheap (304).
    """

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/static", FreshStatic(directory=config.STATIC_DIR), name="static")
