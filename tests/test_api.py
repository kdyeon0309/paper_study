"""End-to-end: a real server on a free port, real HTTP requests, arXiv replaced by canned data.

Run with: python -m unittest discover -s tests -v
"""
import json
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn

from app import arxiv, config, db

PAPERS = {
    "2010.11929": {"title": "An Image is Worth 16x16 Words", "authors": "Alexey Dosovitskiy, Lucas Beyer", "year": 2020,
                   "published": "2020-10-22", "published_at": "2020-10-22T17:55:59Z", "categories": "cs.CV", "comment": "ICLR",
                   "abstract": "While the Transformer architecture has become the de-facto standard..."},
    "1706.03762": {"title": "Attention Is All You Need", "authors": "Ashish Vaswani", "year": 2017,
                   "published": "2017-06-12", "published_at": "2017-06-12T17:57:34Z", "categories": "cs.CL", "comment": "",
                   "abstract": "The dominant sequence transduction models..."},
}


def fake_get(params):
    """Stands in for arxiv._get: answers id lookups and searches from PAPERS."""
    def item(arxiv_id):
        return {"arxiv_id": arxiv_id, "url": f"https://arxiv.org/abs/{arxiv_id}", "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}", **PAPERS[arxiv_id]}
    if "id_list" in params:
        items = [item(i) for i in params["id_list"].split(",") if i in PAPERS]
    else:
        items = [item(i) for i in PAPERS]
    return {"total": len(items), "items": items, "cached": True}


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        home = Path(cls._tmp.name)
        cls._saved = {k: getattr(config, k) for k in ("HOME", "DB_PATH", "NOTES_DIR", "SURVEYS_DIR", "USER_ROADMAP_FILE")}
        config.HOME, config.DB_PATH = home, home / "papers.db"
        config.NOTES_DIR, config.SURVEYS_DIR = home / "notes", home / "surveys"
        config.USER_ROADMAP_FILE = home / "my_roadmaps.json"
        cls._real_get, arxiv._get = arxiv._get, fake_get
        db.init()

        from app.main import app
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            cls.port = s.getsockname()[1]
        cls.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=cls.port, log_level="error"))
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()
        deadline = time.time() + 10
        while not cls.server.started:
            if time.time() > deadline:
                raise RuntimeError("server did not start")
            time.sleep(0.02)

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.thread.join(timeout=5)
        arxiv._get = cls._real_get
        for key, value in cls._saved.items():
            setattr(config, key, value)
        cls._tmp.cleanup()

    def call(self, method, path, body=None, expect=200):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method,
                                     headers={"Content-Type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                status, raw, headers = res.status, res.read(), res.headers
        except urllib.error.HTTPError as e:
            with e:
                status, raw, headers = e.code, e.read(), e.headers
        self.assertEqual(status, expect, f"{method} {path} -> {status}: {raw[:300]!r}")
        self.last_headers = headers
        return json.loads(raw) if "json" in headers.get("content-type", "") else raw.decode()

    # 한 서버를 계속 쓰므로, 번호 순서대로 하나의 이야기처럼 이어진다
    def test_01_pages_and_static_files(self):
        self.assertIn("<title>Paper Study</title>", self.call("GET", "/"))
        self.call("GET", "/static/js/main.js")
        self.assertEqual(self.last_headers.get("cache-control"), "no-cache", "stale JS must not be reused without checking")
        self.call("GET", "/static/vendor/katex/katex.min.js")
        self.call("GET", "/static/../papers.db", expect=404)
        about = self.call("GET", "/api/about")
        self.assertEqual(about["counts"]["papers"], 0)

    def test_02_search_and_save(self):
        found = self.call("GET", "/api/search?q=transformer&cat=cs.CV")
        self.assertEqual([i["saved_id"] for i in found["items"]], [None, None])
        by_id = self.call("GET", "/api/search?q=https%3A%2F%2Farxiv.org%2Fabs%2F2010.11929v2")
        self.assertEqual([i["arxiv_id"] for i in by_id["items"]], ["2010.11929"])

        saved = self.call("POST", "/api/papers", by_id["items"][0])
        self.assertTrue(saved["created"])
        self.assertEqual(saved["paper"]["slug"], "2010.11929")
        self.assertFalse(self.call("POST", "/api/papers", by_id["items"][0])["created"], "saving twice keeps one copy")
        again = self.call("GET", "/api/search?q=transformer")
        self.assertEqual([i["saved_id"] for i in again["items"]], [saved["paper"]["id"], None])

        added = self.call("POST", "/api/papers/arxiv", {"ids": ["1706.03762", "2010.11929", "9999.99999"]})
        self.assertEqual((len(added["added"]), added["existing"], added["failed"]), (1, ["2010.11929"], ["9999.99999"]))
        listing = self.call("GET", "/api/papers")
        self.assertEqual(len(listing), 2)
        self.assertNotIn("abstract", listing[0], "the list stays small")

    def test_03_validation_messages_are_korean(self):
        cases = [
            ("POST", "/api/papers", {"title": ""}, "제목: 비워둘 수 없어요."),
            ("POST", "/api/papers", {"title": "x", "year": 12}, "연도: 1900 이상이어야 해요."),
            ("POST", "/api/papers", {}, "제목: 꼭 필요한 값이에요."),
            ("PATCH", "/api/papers/1", {"status": "finished"}, "읽기 상태: 'to_read', 'reading', 'done' 중 하나여야 해요."),
            ("PUT", "/api/goals", {"goal_days": 9, "goal_papers": "많이"}, "공부한 날 목표: 7 이하여야 해요. 완독 목표: 숫자로 적어주세요."),
        ]
        for method, path, body, message in cases:
            self.assertEqual(self.call(method, path, body, expect=422)["detail"], message)
        self.assertEqual(self.call("GET", "/api/papers/999", expect=404)["detail"], "논문을 찾을 수 없어요.")

    def test_04_note_cards_and_conflict(self):
        note = self.call("PUT", "/api/papers/1/note", {"content": "# ViT\n\n> 이미지를 패치 토큰으로 본다.\n\n기반: [[1706.03762]]\n\nQ: 패치 크기는?\nA: 16x16\n", "base_mtime": None})
        self.assertEqual([c["question"] for c in note["cards"]], ["패치 크기는?"])
        self.assertEqual([x["id"] for x in note["links"]["out"]], [2])
        self.assertEqual(self.call("PUT", "/api/papers/1/note", {"content": "덮어쓰기", "base_mtime": 1.0}, expect=409)["detail"][:5], "노트 파일")

        card_id = note["cards"][0]["id"]
        self.call("POST", f"/api/review/{card_id}", {"grade": "good"})
        edited = self.call("PATCH", f"/api/cards/{card_id}", {"question": "ViT의 패치 크기는?", "answer": "16x16 픽셀"})
        self.assertEqual((edited["card"]["id"], edited["card"]["box"], edited["card"]["question"]), (card_id, 1, "ViT의 패치 크기는?"))
        self.assertEqual(self.call("PATCH", f"/api/cards/{card_id}", {"question": "q", "answer": "# 제목"}, expect=400)["detail"][:4], "답 안에")

        created = self.call("POST", "/api/papers/1/cards", {"question": "위치 정보는 어떻게 넣나?", "answer": "position embedding을 더한다"})
        self.assertEqual(len(created["cards"]), 2)
        self.call("POST", "/api/papers/1/cards", {"question": "위치 정보는 어떻게 넣나?", "answer": "중복"}, expect=400)
        paper = self.call("GET", "/api/papers/1")
        self.assertIn("Q: ViT의 패치 크기는?\nA: 16x16 픽셀", paper["note"]["content"])
        self.assertIn("Q: 위치 정보는 어떻게 넣나?", paper["note"]["content"])
        self.assertEqual(len(self.call("DELETE", f"/api/cards/{created['cards'][1]['id']}")["cards"]), 1)
        self.assertEqual([x["id"] for x in self.call("GET", "/api/papers/2")["links"]["back"]], [1])
        self.assertEqual([h["paper_id"] for h in self.call("GET", "/api/notes/search?q=%ED%8C%A8%EC%B9%98")], [1])
        graph = self.call("GET", "/api/graph")
        self.assertEqual([(e["from"], e["to"]) for e in graph["edges"]], [(1, 2)])

    def test_05_review_timer_recall_goals(self):
        self.assertEqual(self.call("GET", "/api/review/due"), [], "the only card was graded good and is due later")
        self.assertTrue(self.call("POST", "/api/papers/2/timer", {"action": "start"})["running"])
        self.assertEqual(self.call("GET", "/api/papers/2")["paper"]["status"], "reading")
        self.assertFalse(self.call("POST", "/api/papers/2/timer", {"action": "stop"})["running"])

        self.call("PATCH", "/api/papers/1", {"status": "done", "tags": "vit, backbone"})
        with db.connect() as conn:
            conn.execute("UPDATE papers SET recall_due='2000-01-01' WHERE id=1")
        self.assertEqual([p["id"] for p in self.call("GET", "/api/recall/due")], [1])
        self.assertEqual(self.call("GET", "/api/recall/1/reference"), {"text": "이미지를 패치 토큰으로 본다.", "source": "note"})
        self.call("POST", "/api/recall/1", {"text": "패치를 토큰으로", "grade": "good"})
        self.assertEqual(self.call("GET", "/api/recall/due"), [])

        self.assertEqual(self.call("PUT", "/api/goals", {"goal_days": 1, "goal_papers": 1}), {"goal_days": 1, "goal_papers": 1})
        week = self.call("GET", "/api/weekly")
        self.assertEqual((week["goals"]["days_met"], week["goals"]["papers_met"], week["goal_streak"]), (True, True, 1))
        stats = self.call("GET", "/api/stats")
        self.assertEqual((stats["total"], stats["by_status"]["done"], stats["streak"]), (2, 1, 1))
        self.assertEqual(self.call("GET", "/api/review/weak")["cards"], [])

    def test_06_roadmaps_and_saved_searches(self):
        builtin = len(self.call("GET", "/api/roadmaps"))
        track = self.call("POST", "/api/roadmaps", {"name": "내 트랙", "kind": "새 영역"})
        self.call("POST", f"/api/roadmaps/{track['key']}/papers", {"ref": "1706.03762", "why": "기반"})
        self.call("POST", f"/api/roadmaps/{track['key']}/papers", {"ref": "arxiv.org/abs/2010.11929"})
        self.call("PATCH", f"/api/roadmaps/{track['key']}/papers/2010.11929", {"move": -1})
        mine = self.call("GET", "/api/roadmaps")[0]
        self.assertEqual([(p["arxiv_id"], p["status"]) for p in mine["papers"]], [("2010.11929", "done"), ("1706.03762", "reading")])
        self.assertEqual(self.call("GET", "/api/papers/2")["tracks"][0]["position"], 2)
        self.call("PATCH", "/api/roadmaps/basics", {"name": "x"}, expect=404)
        self.call("DELETE", f"/api/roadmaps/{track['key']}/papers/1706.03762")
        self.assertEqual(len(self.call("GET", "/api/roadmaps")), builtin + 1)

        saved = self.call("POST", "/api/searches", {"q": "vision transformer", "cat": "cs.CV"})
        self.assertEqual(saved["last_seen_at"], "2020-10-22T17:55:59Z", "what is on arXiv now counts as seen")
        self.assertEqual(self.call("GET", f"/api/searches/{saved['id']}/new")["new"], 0)
        PAPERS["2501.00001"] = {**PAPERS["2010.11929"], "title": "A Newer Paper", "published_at": "2025-01-01T00:00:00Z"}
        try:
            self.assertEqual(self.call("GET", f"/api/searches/{saved['id']}/new")["new"], 1)
            self.call("POST", f"/api/searches/{saved['id']}/seen")
            self.assertEqual(self.call("GET", f"/api/searches/{saved['id']}/new")["new"], 0)
        finally:
            del PAPERS["2501.00001"]

    def test_07_backup_restore_and_delete(self):
        backup = self.call("GET", "/api/export.json")
        self.assertEqual((len(backup["papers"]), len(backup["tracks"]), len(backup["searches"])), (2, 1, 1))
        self.assertIn("@misc{dosovitskiy2020image", self.call("GET", "/api/export.bib"))
        self.assertEqual(self.call("POST", "/api/import", backup), {"added": 0, "skipped": 2, "notes_written": 0, "tracks_added": 0})
        self.assertEqual(self.call("POST", "/api/import", {"nope": 1}, expect=400)["detail"], "Paper Study 백업 파일이 아니에요.")

        removed = self.call("DELETE", "/api/papers/1")
        self.assertEqual(removed["note_kept"], "notes/2010.11929.md")
        self.assertTrue((config.NOTES_DIR / "2010.11929.md").exists(), "deleting a paper never deletes the note file")
        self.call("GET", "/api/papers/1", expect=404)
        restored = self.call("POST", "/api/import", backup)
        self.assertEqual((restored["added"], restored["notes_written"]), (1, 0))
        back = self.call("GET", f"/api/papers/{self.call('GET', '/api/papers')[0]['id']}")
        self.assertTrue(back["note"]["exists"], "the re-imported paper finds its note again")
        self.assertEqual(len(back["cards"]), 1)


if __name__ == "__main__":
    unittest.main()
