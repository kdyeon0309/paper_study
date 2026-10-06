"""Reading tracks: built-in ones ship in roadmaps.json, your own live in my_roadmaps.json."""
import json

from . import config

KINDS = ("기초", "논문", "새 영역")


def _load(path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _save(tracks: list[dict]):
    config.HOME.mkdir(parents=True, exist_ok=True)
    tmp = config.USER_ROADMAP_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(tracks, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(config.USER_ROADMAP_FILE)


def all_tracks() -> list[dict]:
    builtin = [{**t, "editable": False} for t in _load(config.ROADMAP_FILE)]
    mine = [{**t, "editable": True} for t in _load(config.USER_ROADMAP_FILE)]
    return mine + builtin


def user_tracks() -> list[dict]:
    return _load(config.USER_ROADMAP_FILE)


def restore(tracks: list) -> int:
    """Bring back tracks from a backup. A track whose name already exists is left alone."""
    current = _load(config.USER_ROADMAP_FILE)
    names = {t["name"] for t in current}
    used = {t["key"] for t in current}
    added = 0
    for track in tracks if isinstance(tracks, list) else []:
        if not isinstance(track, dict) or not track.get("name") or track["name"] in names:
            continue
        n = 1
        while f"my-{n}" in used:
            n += 1
        papers = [p for p in track.get("papers", []) if isinstance(p, dict) and p.get("arxiv_id") and p.get("title")]
        current.append({"key": f"my-{n}", **_clean({"name": track["name"], "kind": track.get("kind") if track.get("kind") in KINDS else "논문",
                                                    "description": track.get("description", "")}), "papers": papers})
        used.add(f"my-{n}")
        names.add(track["name"])
        added += 1
    if added:
        _save(current)
    return added


def _clean(fields: dict) -> dict:
    out = {}
    if "name" in fields:
        out["name"] = " ".join(str(fields["name"]).split())[:80]
        if not out["name"]:
            raise ValueError("트랙 이름을 적어주세요.")
    if "kind" in fields:
        if fields["kind"] not in KINDS:
            raise ValueError(f"종류는 {', '.join(KINDS)} 중 하나여야 해요.")
        out["kind"] = fields["kind"]
    if "description" in fields:
        out["description"] = " ".join(str(fields["description"] or "").split())[:300]
    return out


def create(name: str, kind: str = "논문", description: str = "") -> dict:
    tracks = _load(config.USER_ROADMAP_FILE)
    used = {t["key"] for t in tracks}
    n = 1
    while f"my-{n}" in used:
        n += 1
    track = {"key": f"my-{n}", **_clean({"name": name, "kind": kind, "description": description}), "papers": []}
    _save([track] + tracks)
    return track


def _edit(key: str, change) -> dict:
    """Apply `change(track)` to one of your tracks and save. Built-in tracks are read-only."""
    tracks = _load(config.USER_ROADMAP_FILE)
    track = next((t for t in tracks if t["key"] == key), None)
    if track is None:
        raise KeyError(key)
    change(track)
    _save(tracks)
    return track


def update(key: str, fields: dict) -> dict:
    return _edit(key, lambda t: t.update(_clean(fields)))


def delete(key: str):
    tracks = _load(config.USER_ROADMAP_FILE)
    if not any(t["key"] == key for t in tracks):
        raise KeyError(key)
    _save([t for t in tracks if t["key"] != key])


def add_paper(key: str, item: dict, why: str = "") -> dict:
    def change(track):
        if any(p["arxiv_id"] == item["arxiv_id"] for p in track["papers"]):
            raise ValueError("이미 이 트랙에 있는 논문이에요.")
        track["papers"].append({
            "arxiv_id": item["arxiv_id"], "title": item["title"], "authors": item.get("authors", ""),
            "year": item.get("year"), "why": " ".join(why.split())[:300],
        })
    return _edit(key, change)


def _index(track: dict, arxiv_id: str) -> int:
    for i, p in enumerate(track["papers"]):
        if p["arxiv_id"] == arxiv_id:
            return i
    raise KeyError(arxiv_id)


def remove_paper(key: str, arxiv_id: str) -> dict:
    return _edit(key, lambda t: t["papers"].pop(_index(t, arxiv_id)))


def edit_paper(key: str, arxiv_id: str, why: str | None = None, move: int = 0) -> dict:
    def change(track):
        i = _index(track, arxiv_id)
        if why is not None:
            track["papers"][i]["why"] = " ".join(why.split())[:300]
        j = i + move
        if move and 0 <= j < len(track["papers"]):
            track["papers"][i], track["papers"][j] = track["papers"][j], track["papers"][i]
    return _edit(key, change)
