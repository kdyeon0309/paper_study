"""Run with: python -m unittest discover -s tests -v   (no network, no extra packages)"""
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import arxiv, config, db, exporter, notes, review, roadmaps

FEED = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/" xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns="http://www.w3.org/2005/Atom">
  <opensearch:totalResults>731</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2010.11929v2</id>
    <title>An Image is Worth 16x16 Words:
      Transformers for Image Recognition at Scale</title>
    <published>2020-10-22T17:55:59Z</published>
    <summary>  While the Transformer architecture has become
    the de-facto standard.  </summary>
    <author><name>Alexey Dosovitskiy</name></author>
    <author><name>Lucas Beyer</name></author>
    <arxiv:comment>ICLR camera-ready</arxiv:comment>
    <arxiv:primary_category term="cs.CV"/>
    <category term="cs.AI"/><category term="cs.CV"/>
  </entry>
  <entry><id>http://arxiv.org/api/errors#incorrect_id</id><title>Error</title><summary>bad id</summary></entry>
</feed>"""


class TempHome(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        home = Path(self._tmp.name)
        self._saved = {k: getattr(config, k) for k in ("HOME", "DB_PATH", "NOTES_DIR", "SURVEYS_DIR", "USER_ROADMAP_FILE")}
        config.HOME, config.DB_PATH = home, home / "papers.db"
        config.NOTES_DIR, config.SURVEYS_DIR = home / "notes", home / "surveys"
        config.USER_ROADMAP_FILE = home / "my_roadmaps.json"
        db.init()

    def tearDown(self):
        for key, value in self._saved.items():
            setattr(config, key, value)
        self._tmp.cleanup()

    def paper(self, **over):
        data = {"title": "Sparse DETR", "authors": "Byungseok Roh, JaeWoong Shin", "year": 2021,
                "url": "https://arxiv.org/abs/2111.14330v2", "categories": "cs.CV, cs.LG"}
        return db.add_paper({**data, **over})[0]


class ArxivTest(unittest.TestCase):
    def test_parse_id(self):
        cases = {
            "2111.14330": "2111.14330",
            "https://arxiv.org/abs/2111.14330v2": "2111.14330",
            "http://arxiv.org/pdf/2010.11929.pdf": "2010.11929",
            "arXiv:1706.03762": "1706.03762",
            "https://arxiv.org/abs/hep-th/9901001v1": "hep-th/9901001",
            "open vocabulary detection": None,
            "yolo 2024": None,
            "": None,
        }
        for text, want in cases.items():
            self.assertEqual(arxiv.parse_id(text), want, text)

    def test_looks_like_id(self):
        self.assertTrue(arxiv.looks_like_id(" 2111.14330 "))
        self.assertTrue(arxiv.looks_like_id("https://arxiv.org/abs/2111.14330"))
        self.assertFalse(arxiv.looks_like_id("DETR 2111.14330 follow-ups"))
        self.assertFalse(arxiv.looks_like_id("object detection"))

    def test_build_query(self):
        self.assertEqual(arxiv.build_query("open vocabulary"), "all:open AND all:vocabulary")
        self.assertEqual(arxiv.build_query('"gaussian splatting" slam', "cs.CV"),
                         'cat:cs.CV AND (all:"gaussian splatting" AND all:slam)')
        self.assertEqual(arxiv.build_query("  ", "cs.CV"), "cat:cs.CV")
        self.assertEqual(arxiv.build_query("a) OR all:x"), "all:a AND all:OR AND all:all AND all:x")

    def test_parse_feed(self):
        result = arxiv.parse_feed(FEED)
        self.assertEqual(result["total"], 731)
        self.assertEqual(len(result["items"]), 1, "the arXiv error entry must be dropped")
        item = result["items"][0]
        self.assertEqual(item["arxiv_id"], "2010.11929")
        self.assertEqual(item["title"], "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale")
        self.assertEqual(item["authors"], "Alexey Dosovitskiy, Lucas Beyer")
        self.assertEqual((item["year"], item["published"]), (2020, "2020-10-22"))
        self.assertEqual(item["categories"], "cs.CV, cs.AI", "primary category comes first")
        self.assertEqual(item["url"], "https://arxiv.org/abs/2010.11929")
        self.assertTrue(item["abstract"].startswith("While the Transformer"))


class ReviewTest(unittest.TestCase):
    def test_schedule(self):
        today = date(2026, 10, 7)
        self.assertEqual(review.next_state(0, "good", today), (1, today + timedelta(days=3)))
        self.assertEqual(review.next_state(2, "hard", today), (2, today + timedelta(days=7)))
        self.assertEqual(review.next_state(4, "again", today), (0, today + timedelta(days=1)))
        self.assertEqual(review.next_state(5, "good", today), (5, today + timedelta(days=60)), "top box is capped")
        with self.assertRaises(ValueError):
            review.next_state(0, "easy", today)

    def test_streak(self):
        today = date(2026, 10, 7)
        days = lambda *offsets: {(today - timedelta(days=o)).isoformat() for o in offsets}
        self.assertEqual(review.streak(days(0, 1, 2), today), 3)
        self.assertEqual(review.streak(days(1, 2), today), 2, "today not studied yet keeps the streak alive")
        self.assertEqual(review.streak(days(2, 3), today), 0)
        self.assertEqual(review.streak(set(), today), 0)


class CardParseTest(unittest.TestCase):
    def test_parse(self):
        text = """# Note
본문에 Q: 가 섞여 있어도 A가 바로 안 오면 카드가 아니다.

## 복습 카드
Q: DETR에 NMS가 필요 없는 이유는?
A: 헝가리안 매칭으로 GT 하나에 예측 하나만 대응시키기 때문.

- **Q:** 여러 줄 답?
- **A:** 첫 줄
  둘째 줄

Q: 답이 없는 질문

Q: 코드 포함
A: 아래처럼 쓴다
```python
# Q: 이건 카드가 아니다
x = 1
```

## 다음 섹션
Q: 중복 질문
A: 첫 답
Q: 중복 질문
A: 나중 답
"""
        cards = dict(notes.parse_cards(text))
        self.assertEqual(list(cards), ["DETR에 NMS가 필요 없는 이유는?", "여러 줄 답?", "코드 포함", "중복 질문"])
        self.assertEqual(cards["여러 줄 답?"], "첫 줄\n둘째 줄")
        self.assertIn("x = 1", cards["코드 포함"])
        self.assertEqual(cards["중복 질문"], "나중 답")
        self.assertEqual(notes.parse_cards("그냥 글"), [])


class LibraryTest(TempHome):
    def test_add_dedupes_by_arxiv_id(self):
        first = self.paper()
        self.assertEqual((first["slug"], first["arxiv_id"]), ("2111.14330", "2111.14330"))
        self.assertEqual(first["pdf_url"], "https://arxiv.org/pdf/2111.14330")
        again, created = db.add_paper({"title": "same paper, other link", "url": "https://arxiv.org/pdf/2111.14330"})
        self.assertFalse(created)
        self.assertEqual(again["id"], first["id"])
        manual, created = db.add_paper({"title": "  A   book chapter ", "tags": "math, , math,linear algebra"})
        self.assertTrue(created)
        self.assertEqual((manual["slug"], manual["title"]), (f"local-{manual['id']}", "A book chapter"))
        self.assertEqual(manual["tags"], "math, linear algebra")
        with self.assertRaises(ValueError):
            db.add_paper({"title": "   "})

    def test_status_change_is_logged_and_dated(self):
        p = self.paper()
        done = db.update_paper(p["id"], {"status": "done"})
        self.assertEqual(done["finished_at"], date.today().isoformat())
        self.assertIsNone(db.update_paper(p["id"], {"status": "reading"})["finished_at"])
        with self.assertRaises(ValueError):
            db.update_paper(p["id"], {"status": "finished"})
        self.assertIsNone(db.update_paper(999, {"status": "done"}))
        s = db.stats()
        self.assertEqual(s["by_status"], {"to_read": 0, "reading": 1, "done": 0})
        self.assertEqual(s["streak"], 1)
        self.assertEqual([a["kind"] for a in s["recent"]], ["status", "status", "added"])

    def test_find_paper(self):
        p = self.paper()
        for ref in (str(p["id"]), "2111.14330", "https://arxiv.org/abs/2111.14330v3"):
            self.assertEqual(db.find_paper(ref)["id"], p["id"], ref)
        self.assertIsNone(db.find_paper("nope"))

    def test_cards_keep_progress_across_note_edits(self):
        p = self.paper()
        today = date(2026, 10, 7)
        db.sync_cards(p["id"], [("q1", "a1"), ("q2", "a2")], today)
        q1 = next(c for c in db.due_cards(today) if c["question"] == "q1")
        self.assertEqual(db.grade_card(q1["id"], "good", today)["box"], 1)
        db.sync_cards(p["id"], [("q1", "a1 reworded"), ("q3", "a3")], today)
        cards = {c["question"]: c for c in db.cards_for(p["id"])}
        self.assertEqual(set(cards), {"q1", "q3"})
        self.assertEqual((cards["q1"]["box"], cards["q1"]["answer"]), (1, "a1 reworded"))
        self.assertEqual([c["question"] for c in db.due_cards(today)], ["q3"])
        self.assertEqual(len(db.due_cards(today + timedelta(days=3))), 2)
        db.delete_paper(p["id"])
        self.assertEqual(db.due_cards(today + timedelta(days=99)), [])

    def test_heatmap_window_starts_on_sunday(self):
        for offset in range(7):
            today = date(2026, 10, 4) + timedelta(days=offset)
            window = db.stats(today, weeks=20)["heatmap"]
            start = date.fromisoformat(window["start"])
            self.assertEqual(start.weekday(), 6, today)
            self.assertEqual((today - start).days // 7, 19)


class MigrationTest(TempHome):
    def test_v01_database_is_upgraded_in_place(self):
        config.DB_PATH.unlink()
        conn = sqlite3.connect(config.DB_PATH)
        conn.executescript("""
            CREATE TABLE papers (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, authors TEXT DEFAULT '',
                year INTEGER, url TEXT DEFAULT '', tags TEXT DEFAULT '', status TEXT DEFAULT 'to_read',
                summary TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now', 'localtime')));
            INSERT INTO papers (title, url, summary, status) VALUES
                ('Sparse DETR', 'http://arxiv.org/abs/2111.14330v2', 'DETR is the first', 'reading'),
                ('Sparse DETR dup', 'http://arxiv.org/abs/2111.14330v1', '', 'to_read'),
                ('Blog post', 'https://example.com/post', '', 'done');
        """)
        conn.commit()
        conn.close()
        config.NOTES_DIR.mkdir()
        (config.NOTES_DIR / "1.md").write_text("# old note\nQ: q\nA: a\n", encoding="utf-8")

        db.init()
        db.init()  # idempotent
        notes.migrate_legacy_names()

        papers = {p["id"]: p for p in db.list_papers()}
        self.assertEqual([papers[i]["slug"] for i in (1, 2, 3)], ["2111.14330", "local-2", "local-3"])
        self.assertEqual((papers[1]["abstract"], papers[1]["status"]), ("DETR is the first", "reading"))
        self.assertIsNone(papers[2]["arxiv_id"])
        self.assertEqual((papers[1]["url"], papers[1]["pdf_url"]),
                         ("https://arxiv.org/abs/2111.14330", "https://arxiv.org/pdf/2111.14330"))
        self.assertEqual(papers[3]["url"], "https://example.com/post")
        self.assertTrue((config.NOTES_DIR / "2111.14330.md").exists())
        self.assertFalse((config.NOTES_DIR / "1.md").exists())
        self.assertEqual(len(notes.sync_all()), 3)
        self.assertEqual([c["question"] for c in db.cards_for(1)], ["q"])


class NotesTest(TempHome):
    def test_write_read_and_conflict(self):
        p = self.paper(status="reading")
        p = db.update_paper(p["id"], {"note_requested": True})
        self.assertFalse(notes.read(p)["exists"])
        saved = notes.write(p, "# n\nQ: one\nA: 1\n", None)
        self.assertTrue(saved["exists"])
        self.assertEqual(saved["path"], "notes/2111.14330.md")
        p = db.get_paper(p["id"])
        self.assertEqual(p["note_requested"], 0, "a written note clears the request")
        self.assertEqual(len(db.cards_for(p["id"])), 1)

        with self.assertRaises(notes.Conflict):
            notes.write(p, "stale editor", None)
        with self.assertRaises(notes.Conflict):
            notes.write(p, "stale editor", saved["mtime"] - 5)
        self.assertEqual(notes.read(p)["content"], "# n\nQ: one\nA: 1\n")
        notes.write(p, "# n\n", saved["mtime"])
        self.assertEqual(db.cards_for(p["id"]), [])

    def test_external_edit_is_picked_up_once(self):
        p = self.paper()
        config.NOTES_DIR.mkdir(exist_ok=True)
        notes.note_path(p["slug"]).write_text("Q: from claude code\nA: yes\n", encoding="utf-8")
        self.assertTrue(notes.sync(db.get_paper(p["id"])))
        self.assertFalse(notes.sync(db.get_paper(p["id"])))
        self.assertEqual(len(db.cards_for(p["id"])), 1)
        kinds = [a["kind"] for a in db.stats()["recent"]]
        self.assertEqual(kinds.count("note"), 1)
        notes.note_path(p["slug"]).unlink()
        notes.sync(db.get_paper(p["id"]))
        self.assertEqual(db.cards_for(p["id"]), [])
        self.assertIsNone(db.get_paper(p["id"])["note_mtime"])

    def test_note_names_cannot_escape_the_notes_dir(self):
        for bad in ("../secret", "a/b", "", ".hidden", "_TEMPLATE", "x" * 200):
            with self.assertRaises(ValueError, msg=bad):
                notes.note_path(bad)
        self.assertIsNone(notes.read_survey("../papers"))


class ExportTest(TempHome):
    def test_bibtex(self):
        p = self.paper(title="The {Sparse} DETR: Efficient Detection", authors="Byungseok Roh, José Álvarez")
        self.assertEqual(exporter.bib_key(p), "roh2021sparse")
        bib = exporter.bibtex(p)
        self.assertIn("author = {Byungseok Roh and José Álvarez}", bib)
        self.assertIn("title = {{The Sparse DETR: Efficient Detection}}", bib)
        self.assertIn("eprint = {2111.14330}", bib)
        self.assertIn("primaryClass = {cs.CV}", bib)
        self.assertEqual(exporter.bib_key({"title": "", "authors": ""}), "anon")

    def test_backup_roundtrip(self):
        p = self.paper(tags="detr")
        notes.write(p, "# my note\n", None)
        db.add_paper({"title": "Manual entry"})
        roadmaps.create("내 트랙", "새 영역")
        roadmaps.add_paper("my-1", {"arxiv_id": "2010.11929", "title": "ViT"}, "이유")
        db.save_search("open vocabulary", "cs.CV")
        backup = exporter.export_all()

        self.tearDown()
        self.setUp()
        self.assertEqual(exporter.import_all(backup), {"added": 2, "skipped": 0, "notes_written": 1, "tracks_added": 1})
        self.assertEqual(exporter.import_all(backup), {"added": 0, "skipped": 2, "notes_written": 0, "tracks_added": 0},
                         "importing the same backup twice adds nothing")
        mine = roadmaps.user_tracks()
        self.assertEqual([(t["name"], t["kind"], [p["why"] for p in t["papers"]]) for t in mine], [("내 트랙", "새 영역", ["이유"])])
        self.assertEqual([(x["q"], x["cat"]) for x in db.saved_searches()], [("open vocabulary", "cs.CV")])
        self.assertEqual(exporter.import_all({"papers": []})["tracks_added"], 0, "v0.2 backups have no tracks")
        restored = db.find_paper("2111.14330")
        self.assertEqual((restored["tags"], notes.read(restored)["content"]), ("detr", "# my note\n"))
        with self.assertRaises(ValueError):
            exporter.import_all({"something": "else"})


class InsightTest(TempHome):
    def test_weak_cards_and_tag_accuracy(self):
        today = date(2026, 10, 7)
        a = self.paper(tags="detr, detection")
        b = db.add_paper({"title": "Adam", "url": "https://arxiv.org/abs/1412.6980", "tags": "optimization"})[0]
        c = db.add_paper({"title": "Untagged"})[0]
        db.sync_cards(a["id"], [("a1", "x"), ("a2", "x")], today)
        db.sync_cards(b["id"], [("b1", "x")], today)
        db.sync_cards(c["id"], [("c1", "x")], today)
        ids = {card["question"]: card["id"] for card in db.due_cards(today)}
        for question, grades in {"a1": ["again", "again", "good"], "a2": ["good"], "b1": ["good", "good"], "c1": ["again"]}.items():
            for grade in grades:
                db.grade_card(ids[question], grade, today)

        weak = db.weak_cards()
        self.assertEqual([(w["question"], w["lapses"], w["reviews"]) for w in weak], [("c1", 1, 1), ("a1", 2, 3)])
        tags = {t["tag"]: t for t in db.tag_accuracy()}
        self.assertEqual(set(tags), {"detr", "detection", "optimization", ""})
        self.assertEqual((tags["detr"]["reviews"], tags["detr"]["lapses"]), (4, 2))
        self.assertEqual(tags["optimization"]["accuracy"], 1.0)
        self.assertEqual(db.tag_accuracy()[0]["tag"], "", "weakest group first")

    def test_weekly_runs_monday_to_sunday_and_compares(self):
        wednesday = date(2026, 10, 7)
        p = self.paper()
        with db.connect() as conn:
            conn.execute("DELETE FROM activity")
            for day, kind, detail in [("2026-10-05", "added", ""), ("2026-10-05", "review", "good"),
                                      ("2026-10-07", "review", "again"), ("2026-10-07", "note", ""),
                                      ("2026-10-04", "review", "good"), ("2026-09-28", "added", "")]:
                db.log(conn, kind, p["id"], detail, day=day)
            conn.execute("UPDATE papers SET status='done', finished_at='2026-10-06' WHERE id=?", (p["id"],))
        week = db.weekly(wednesday)
        self.assertEqual((week["start"], week["end"]), ("2026-10-05", "2026-10-11"))
        self.assertEqual(week["current"], {"added": 1, "finished": 1, "notes": 1, "reviews": 2, "accuracy": 0.5, "active_days": 2, "minutes": 0})
        self.assertEqual(week["previous"]["reviews"], 1, "Sunday the 4th belongs to the previous week")
        self.assertEqual(week["previous"]["added"], 1)
        self.assertEqual([d["count"] for d in week["days"]], [2, 0, 2, 0, 0, 0, 0])
        self.assertEqual([f["title"] for f in week["finished"]], ["Sparse DETR"])
        last = db.weekly(wednesday, offset=-1)
        self.assertEqual((last["start"], last["current"]["reviews"], last["current"]["accuracy"]), ("2026-09-28", 1, 1.0))
        self.assertIsNone(db.weekly(wednesday, offset=-5)["current"]["accuracy"])

    def test_metadata_refresh_keeps_user_fields(self):
        p = self.paper(tags="mine", status="reading")
        updated = db.set_metadata(p["id"], {"title": "Sparse DETR: Full Title", "categories": "cs.CV", "abstract": "new",
                                             "tags": "ignored", "status": "done", "comment": ""})
        self.assertEqual((updated["title"], updated["categories"], updated["abstract"]), ("Sparse DETR: Full Title", "cs.CV", "new"))
        self.assertEqual((updated["tags"], updated["status"], updated["slug"]), ("mine", "reading", "2111.14330"))

    def test_note_search(self):
        p = self.paper()
        notes.write(p, "# Sparse DETR\n\n## 핵심\nEncoder 토큰의 일부만 갱신한다.\n다른 줄\n", None)
        config.SURVEYS_DIR.mkdir()
        (config.SURVEYS_DIR / "detr-family.md").write_text("# DETR 계보\n\nencoder 병목을 줄이는 흐름\n", encoding="utf-8")
        hits = notes.search("  ENCODER ")
        self.assertEqual([(h["kind"], h["title"]) for h in hits], [("note", "Sparse DETR"), ("survey", "DETR 계보")])
        self.assertEqual(hits[0]["snippets"], ["Encoder 토큰의 일부만 갱신한다."])
        self.assertEqual(hits[0]["paper_id"], p["id"])
        self.assertEqual(notes.search("없는말"), [])
        self.assertEqual(notes.search("e"), [], "one-character queries are ignored")

    def test_saved_searches(self):
        first = db.save_search("  open   vocabulary ", "cs.CV")
        self.assertEqual((first["q"], first["cat"]), ("open vocabulary", "cs.CV"))
        self.assertEqual(db.save_search("open vocabulary", "cs.CV")["id"], first["id"], "same search is stored once")
        db.save_search("open vocabulary")
        self.assertEqual([(x["q"], x["cat"]) for x in db.saved_searches()], [("open vocabulary", "cs.CV"), ("open vocabulary", "")])
        with self.assertRaises(ValueError):
            db.save_search("   ")
        self.assertTrue(db.delete_search(first["id"]))
        self.assertFalse(db.delete_search(first["id"]))
        self.assertEqual(len(db.saved_searches()), 1)

    def test_old_cards_table_gains_counters(self):
        with db.connect() as conn:
            conn.executescript("DROP TABLE cards; CREATE TABLE cards (id INTEGER PRIMARY KEY, paper_id INTEGER, "
                               "question TEXT, answer TEXT, box INTEGER DEFAULT 0, due TEXT, last_reviewed TEXT, "
                               "UNIQUE (paper_id, question));")
        db.init()
        p = self.paper()
        db.sync_cards(p["id"], [("q", "a")])
        card = db.grade_card(db.cards_for(p["id"])[0]["id"], "again")
        self.assertEqual((card["reviews"], card["lapses"]), (1, 1))


class CardEditTest(TempHome):
    NOTE = """# 제목

본문 Q: 는 카드가 아니다.

## 복습 카드
Q: 첫 질문
A: 첫 답
  둘째 줄

- **Q:** 둘째 질문
- **A:** 둘째 답

## 끝
마지막 줄
"""

    def test_replace_card_touches_only_its_lines(self):
        edited = notes.replace_card(self.NOTE, "첫 질문", "고친 질문", "고친 답\n추가 줄")
        self.assertEqual(notes.parse_cards(edited), [("고친 질문", "고친 답\n추가 줄"), ("둘째 질문", "둘째 답")])
        self.assertIn("본문 Q: 는 카드가 아니다.", edited)
        self.assertTrue(edited.endswith("## 끝\n마지막 줄\n"))
        self.assertEqual(len(edited.splitlines()), len(self.NOTE.splitlines()), "two answer lines became two")

        removed = notes.replace_card(self.NOTE, "둘째 질문", None, None)
        self.assertEqual(notes.parse_cards(removed), [("첫 질문", "첫 답\n둘째 줄")])
        self.assertNotIn("둘째", removed.replace("둘째 줄", ""))
        self.assertNotIn("\n\n\n", removed, "no doubled blank line is left behind")
        with self.assertRaises(KeyError):
            notes.replace_card(self.NOTE, "없는 질문", "x", "y")

    def test_append_card(self):
        fresh = notes.append_card("", "q1", "a1", "논문 제목")
        self.assertEqual(fresh, "# 논문 제목\n\n## 복습 카드\nQ: q1\nA: a1\n")
        no_section = notes.append_card("# n\n본문\n\n\n", "q1", "a1", "t")
        self.assertEqual(no_section, "# n\n본문\n\n## 복습 카드\nQ: q1\nA: a1\n")

        added = notes.append_card(self.NOTE, "새 질문", "새 답\n둘째 줄", "t")
        self.assertEqual([q for q, _ in notes.parse_cards(added)], ["첫 질문", "둘째 질문", "새 질문"])
        lines = added.splitlines()
        self.assertLess(lines.index("Q: 새 질문"), lines.index("## 끝"), "goes inside the 복습 카드 section")
        self.assertEqual(lines[lines.index("Q: 새 질문") - 1], "")
        self.assertEqual(lines[lines.index("## 끝") - 1], "")
        self.assertTrue(added.endswith("마지막 줄\n"))

        empty_section = notes.append_card("# n\n## 복습 카드\n\n## 다음\n끝\n", "q", "a", "t")
        self.assertEqual(empty_section, "# n\n## 복습 카드\nQ: q\nA: a\n\n## 다음\n끝\n")
        with self.assertRaises(ValueError):
            notes.append_card(self.NOTE, "첫 질문", "x", "t")

    def test_clean_card(self):
        self.assertEqual(notes.clean_card("  여러   공백  ", "\n답\n\n둘째  \n"), ("여러 공백", "답\n둘째"))
        for question, answer in (("", "답"), ("질문", "  "), ("질문", "답\nQ: 끼어든 질문"), ("질문", "# 제목")):
            with self.assertRaises(ValueError, msg=(question, answer)):
                notes.clean_card(question, answer)

    def test_editing_a_card_keeps_its_progress(self):
        p = self.paper()
        notes.write(p, self.NOTE, None)
        card = next(c for c in db.cards_for(p["id"]) if c["question"] == "첫 질문")
        db.grade_card(card["id"], "good")
        question, answer = notes.clean_card("고친 질문", "고친 답")
        note = notes.read(p)
        text = notes.replace_card(note["content"], card["question"], question, answer)
        db.rename_card(card["id"], question, answer)
        notes.write(db.get_paper(p["id"]), text, note["mtime"])
        after = db.get_card(card["id"])
        self.assertEqual((after["question"], after["answer"], after["box"], after["reviews"]), ("고친 질문", "고친 답", 1, 1))
        self.assertEqual(len(db.cards_for(p["id"])), 2)
        with self.assertRaises(ValueError):
            db.rename_card(card["id"], "둘째 질문", "x")


class LinkTest(TempHome):
    def test_find_ids_ignores_plain_decimals(self):
        text = "정확도 2304.08069 는 숫자일 뿐. arXiv:2010.11929 와 https://arxiv.org/abs/1706.03762v5 는 논문."
        self.assertEqual(arxiv.find_ids(text), {"2010.11929", "1706.03762"})
        self.assertEqual(arxiv.find_ids(""), set())

    def test_links_and_backlinks(self):
        detr = self.paper()
        vit = db.add_paper({"title": "An Image is Worth 16x16 Words", "url": "https://arxiv.org/abs/2010.11929"})[0]
        book = db.add_paper({"title": "Linear Algebra Done Right"})[0]
        lonely = db.add_paper({"title": "Unrelated", "url": "https://arxiv.org/abs/1412.6980"})[0]
        notes.write(detr, "backbone은 [[2010.11929]] 참고. 수학은 [[linear algebra done right]].\n"
                          "자기 자신 [[2111.14330]] 과 없는 [[논문 X]] 도 적음.\n", None)
        notes.write(vit, "후속 연구: https://arxiv.org/abs/2111.14330 (Sparse DETR)\n", None)

        got = notes.links(db.get_paper(detr["id"]))
        self.assertEqual([x["id"] for x in got["out"]], [vit["id"], book["id"]])
        self.assertEqual(got["wiki"], {"2010.11929": {"id": vit["id"], "title": "An Image is Worth 16x16 Words"},
                                       "linear algebra done right": {"id": book["id"], "title": "Linear Algebra Done Right"},
                                       "2111.14330": {"id": detr["id"], "title": "Sparse DETR"}})
        self.assertEqual([x["id"] for x in got["back"]], [vit["id"]])
        self.assertEqual([x["id"] for x in notes.links(db.get_paper(vit["id"]))["back"]], [detr["id"]])
        self.assertEqual(notes.links(db.get_paper(lonely["id"])), {"wiki": {}, "out": [], "back": [], "surveys": []})

        g = notes.graph()
        self.assertEqual({n["id"] for n in g["nodes"]}, {detr["id"], vit["id"], book["id"]})
        self.assertEqual({(e["from"], e["to"]) for e in g["edges"]},
                         {(detr["id"], vit["id"]), (detr["id"], book["id"]), (vit["id"], detr["id"])})
        self.assertEqual(g["isolated"], 1)


class GoalTest(TempHome):
    def test_goals_and_weekly_progress(self):
        self.assertEqual(db.goals(), {"goal_days": 4, "goal_papers": 1})
        self.assertEqual(db.set_goals(2, 0), {"goal_days": 2, "goal_papers": 0})
        with self.assertRaises(ValueError):
            db.set_goals(8, 1)
        p = self.paper()
        with db.connect() as conn:
            conn.execute("DELETE FROM activity")
            db.log(conn, "added", p["id"], day="2026-10-05")
            db.log(conn, "review", p["id"], "good", day="2026-10-06")
        week = db.weekly(date(2026, 10, 7))
        self.assertEqual(week["goals"], {"goal_days": 2, "goal_papers": 0, "days_met": True, "papers_met": False},
                         "a goal of zero is switched off, not automatically met")
        self.assertFalse(db.weekly(date(2026, 10, 7), offset=-1)["goals"]["days_met"])

    def test_goal_streak(self):
        today = date(2026, 10, 7)  # 수요일. 이번 주 월요일은 10/5
        p = self.paper()
        db.set_goals(2, 0)

        def study(*days):
            with db.connect() as conn:
                conn.execute("DELETE FROM activity")
                for day in days:
                    db.log(conn, "review", p["id"], "good", day=day)

        study()
        self.assertEqual(db.goal_streak(today), 0)
        study("2026-09-28", "2026-09-30", "2026-09-21", "2026-09-27")           # 지난주, 지지난주 달성
        self.assertEqual(db.goal_streak(today), 2, "an unfinished current week does not break the streak")
        study("2026-09-28", "2026-09-30", "2026-09-21", "2026-09-27", "2026-10-05", "2026-10-06")
        self.assertEqual(db.goal_streak(today), 3, "the current week counts once it is met")
        study("2026-09-21", "2026-09-27", "2026-10-05", "2026-10-06")           # 지난주가 비었다
        self.assertEqual(db.goal_streak(today), 1)
        db.set_goals(2, 1)
        self.assertEqual(db.goal_streak(today), 0, "every enabled goal has to be met")
        with db.connect() as conn:
            conn.execute("UPDATE papers SET status='done', finished_at='2026-10-06' WHERE id=?", (p["id"],))
        self.assertEqual(db.goal_streak(today), 1)
        db.set_goals(0, 0)
        self.assertEqual(db.goal_streak(today), 0, "no goals, no streak")

    def test_saved_search_seen_marker_only_moves_forward(self):
        saved = db.save_search("detr", "cs.CV", "2026-10-01T00:00:00Z")
        db.mark_search_seen(saved["id"], "2026-09-01T00:00:00Z")
        self.assertEqual(db.get_search(saved["id"])["last_seen_at"], "2026-10-01T00:00:00Z")
        db.mark_search_seen(saved["id"], "2026-10-05T00:00:00Z")
        self.assertEqual(db.get_search(saved["id"])["last_seen_at"], "2026-10-05T00:00:00Z")
        self.assertIsNone(db.get_search(999))


class TimerTest(TempHome):
    def test_reading_time_counts_only_while_the_page_reports(self):
        from datetime import datetime
        p = self.paper()
        other = db.add_paper({"title": "Other"})[0]
        t0 = datetime(2026, 10, 7, 21, 0, 0)
        at = lambda seconds: t0 + timedelta(seconds=seconds)

        self.assertEqual(db.timer(p["id"], "ping", t0), {"running": False, "seconds": 0, "session_seconds": 0}, "ping without start does nothing")
        self.assertTrue(db.timer(p["id"], "start", t0)["running"])
        self.assertEqual(db.get_paper(p["id"])["status"], "reading", "starting to read moves it out of to_read")
        db.timer(p["id"], "ping", at(60))
        self.assertEqual(db.timer(p["id"], "ping", at(100))["seconds"], 100)
        self.assertEqual(db.timer(p["id"], "start", at(110))["session_seconds"], 110, "start while running continues the same session")

        # 탭을 닫아 신호가 끊기면, 마지막 신호까지만 센다
        state = db.timer(p["id"], "ping", at(110 + db.SESSION_GAP + 500))
        self.assertEqual(state, {"running": False, "seconds": 110, "session_seconds": 0})

        db.timer(p["id"], "start", at(2000))
        db.timer(other["id"], "start", at(2030))
        self.assertFalse(db.timer_state(p["id"])["running"], "only one paper is timed at a time")
        self.assertEqual(db.timer(other["id"], "stop", at(2090)), {"running": False, "seconds": 60, "session_seconds": 0})
        self.assertEqual(db.timer_state(p["id"])["seconds"], 110, "a session cut off by another paper counts up to its last report")
        self.assertEqual(db.weekly(date(2026, 10, 7))["current"]["minutes"], 2)
        with self.assertRaises(ValueError):
            db.timer(p["id"], "pause", t0)


class RecallTest(TempHome):
    def test_finished_papers_come_back_for_recall(self):
        today = date.today()
        p = self.paper()
        self.assertEqual(db.due_recalls(today + timedelta(days=99)), [])
        db.update_paper(p["id"], {"status": "done"})
        self.assertEqual(db.due_recalls(today + timedelta(days=db.RECALL_FIRST - 1)), [])
        due = today + timedelta(days=db.RECALL_FIRST)
        self.assertEqual([x["id"] for x in db.due_recalls(due)], [p["id"]])

        self.assertEqual(db.record_recall(p["id"], " encoder 토큰 일부만 갱신 ", "hazy", due)["next"],
                         (due + timedelta(days=db.RECALL_HAZY)).isoformat())
        self.assertEqual(db.due_recalls(due), [])
        later = due + timedelta(days=db.RECALL_HAZY)
        db.record_recall(p["id"], "더 잘 기억남", "good", later)
        self.assertEqual(db.get_paper(p["id"])["recall_due"], (later + timedelta(days=db.RECALL_GOOD)).isoformat())
        self.assertEqual([(r["text"], r["grade"]) for r in db.recalls_for(p["id"])],
                         [("더 잘 기억남", "good"), ("encoder 토큰 일부만 갱신", "hazy")])
        for text, grade in (("  ", "good"), ("x", "perfect")):
            with self.assertRaises(ValueError):
                db.record_recall(p["id"], text, grade)

        db.update_paper(p["id"], {"status": "reading"})
        self.assertIsNone(db.get_paper(p["id"])["recall_due"], "a paper being re-read is not asked about")

    def test_summary_line(self):
        p = self.paper()
        self.assertEqual(notes.summary_line(p), "")
        notes.write(p, "# 제목\n\n> **한 문장 요약:** 토큰 일부만 갱신한다.\n\n> 다른 인용\n", None)
        self.assertEqual(notes.summary_line(db.get_paper(p["id"])), "토큰 일부만 갱신한다.")

    def test_already_finished_papers_get_a_recall_date_on_upgrade(self):
        p = self.paper()
        with db.connect() as conn:
            conn.execute("UPDATE papers SET status='done', finished_at='2026-09-01', recall_due=NULL WHERE id=?", (p["id"],))
        db.init()
        self.assertEqual(db.get_paper(p["id"])["recall_due"], "2026-09-08")


class SurveyLinkTest(TempHome):
    def test_survey_links(self):
        detr = self.paper()
        config.SURVEYS_DIR.mkdir()
        (config.SURVEYS_DIR / "detr-family.md").write_text(
            "# DETR 계보\n\n출발점 [[2111.14330]]. 다음: https://arxiv.org/abs/2010.04159 , arXiv:2304.08069\n", encoding="utf-8")
        found = notes.survey_links("detr-family")
        self.assertEqual(found["papers"], [{"id": detr["id"], "title": "Sparse DETR", "status": "to_read"}])
        self.assertEqual(found["wiki"], {"2111.14330": {"id": detr["id"], "title": "Sparse DETR"}})
        self.assertEqual(found["missing"], ["2010.04159", "2304.08069"])
        self.assertEqual(notes.links(detr)["surveys"], [{"name": "detr-family", "title": "DETR 계보"}])
        self.assertIsNone(notes.survey_links("nope"))


class SafetyTest(TempHome):
    def test_daily_backup_and_pruning(self):
        folder = db.backup_dir()
        self.assertEqual(folder.parent, config.DB_PATH.parent, "backups sit next to the database they copy")
        self.assertEqual(len(list(folder.glob("*.db"))), 0, "an empty new database is not worth copying yet")
        p = self.paper()
        day = date(2026, 10, 1)
        self.assertTrue(db.backup(day))
        self.assertFalse(db.backup(day), "one copy per day")
        for offset in range(1, 10):
            db.backup(day + timedelta(days=offset))
        names = sorted(f.name for f in folder.glob("*.db"))
        self.assertEqual(len(names), db.BACKUPS_KEPT)
        self.assertEqual((names[0], names[-1]), ("papers-2026-10-04.db", "papers-2026-10-10.db"))
        copy = sqlite3.connect(folder / names[-1])
        self.assertEqual(copy.execute("SELECT title FROM papers").fetchall(), [(p["title"],)])
        copy.close()

    def test_undo_review_restores_card_and_log(self):
        today = date(2026, 10, 7)
        p = self.paper()
        db.sync_cards(p["id"], [("q1", "a1"), ("q2", "a2")], today)
        first, second = db.cards_for(p["id"])
        db.grade_card(first["id"], "good", today)
        before = db.get_card(second["id"])
        reviews_before = db.weekly(today)["current"]["reviews"]
        db.grade_card(second["id"], "again", today)
        self.assertEqual(db.get_card(second["id"])["lapses"], 1)

        restored = db.undo_review()
        self.assertEqual(restored["paper_title"], "Sparse DETR")
        self.assertEqual({k: restored[k] for k in before}, before)
        self.assertEqual(db.weekly(today)["current"]["reviews"], reviews_before)
        self.assertEqual(db.get_card(first["id"])["box"], 1, "only the last grade is undone")
        self.assertIsNone(db.undo_review(), "undo works once")

        db.grade_card(first["id"], "good", today)
        db.sync_cards(p["id"], [("q2", "a2")], today)   # q1이 노트에서 지워짐
        self.assertIsNone(db.undo_review())

    def test_monthly_totals(self):
        from datetime import datetime
        p = self.paper()
        with db.connect() as conn:
            conn.execute("DELETE FROM activity")
            for day, kind in [("2026-10-05", "review"), ("2026-10-05", "review"), ("2026-10-06", "note"), ("2026-08-30", "review"), ("2025-10-31", "review")]:
                db.log(conn, kind, p["id"], "good", day=day)
            conn.execute("UPDATE papers SET status='done', finished_at='2026-08-15' WHERE id=?", (p["id"],))
        start = datetime(2026, 10, 7, 21, 0, 0)
        db.timer(p["id"], "start", start)
        for seconds in range(30, 25 * 60 + 30, 30):   # 페이지가 30초마다 보내는 신호
            db.timer(p["id"], "ping", start + timedelta(seconds=seconds))
        db.timer(p["id"], "stop", start + timedelta(minutes=25, seconds=30))
        months = db.monthly(date(2026, 10, 7))
        self.assertEqual((len(months), months[0]["month"], months[-1]["month"]), (12, "2025-11", "2026-10"))
        by = {m["month"]: m for m in months}
        self.assertEqual(by["2026-10"], {"month": "2026-10", "done": 0, "reviews": 2, "notes": 1, "minutes": 25, "active_days": 3})
        self.assertEqual((by["2026-08"]["done"], by["2026-08"]["reviews"]), (1, 1))
        self.assertEqual(by["2026-09"]["active_days"], 0, "empty months are still listed")
        self.assertEqual(db.monthly(date(2026, 1, 15), months=3)[0]["month"], "2025-11", "the window crosses the year boundary")


class RoadmapTest(TempHome):
    ITEM = {"arxiv_id": "2010.11929", "title": "ViT", "authors": "A, B", "year": 2020}

    def test_user_tracks(self):
        builtin = len(roadmaps.all_tracks())
        self.assertGreater(builtin, 0)
        t = roadmaps.create("  내  트랙 ", "새 영역", "설명")
        self.assertEqual((t["key"], t["name"]), ("my-1", "내 트랙"))
        self.assertEqual(roadmaps.create("둘째")["key"], "my-2")
        listed = roadmaps.all_tracks()
        self.assertEqual([x["key"] for x in listed[:2]], ["my-2", "my-1"])
        self.assertEqual([x["editable"] for x in listed[:3]], [True, True, False])

        roadmaps.add_paper("my-1", self.ITEM, " 이유 ")
        roadmaps.add_paper("my-1", {**self.ITEM, "arxiv_id": "1706.03762", "title": "Attention"})
        with self.assertRaises(ValueError):
            roadmaps.add_paper("my-1", self.ITEM)
        order = lambda: [p["arxiv_id"] for p in roadmaps.all_tracks()[1]["papers"]]
        self.assertEqual(order(), ["2010.11929", "1706.03762"])
        roadmaps.edit_paper("my-1", "1706.03762", why="먼저 읽기", move=-1)
        self.assertEqual(order(), ["1706.03762", "2010.11929"])
        roadmaps.edit_paper("my-1", "1706.03762", move=-1)  # already first: stays
        self.assertEqual(order(), ["1706.03762", "2010.11929"])
        self.assertEqual(roadmaps.all_tracks()[1]["papers"][0]["why"], "먼저 읽기")
        roadmaps.remove_paper("my-1", "1706.03762")
        self.assertEqual(order(), ["2010.11929"])

        self.assertEqual(roadmaps.update("my-1", {"name": "새 이름"})["name"], "새 이름")
        with self.assertRaises(ValueError):
            roadmaps.update("my-1", {"name": "  "})
        with self.assertRaises(ValueError):
            roadmaps.update("my-1", {"kind": "기타"})
        roadmaps.delete("my-2")
        self.assertEqual(len(roadmaps.all_tracks()), builtin + 1)

    def test_builtin_tracks_are_read_only(self):
        key = roadmaps.all_tracks()[0]["key"]
        for call in (lambda: roadmaps.update(key, {"name": "x"}), lambda: roadmaps.delete(key),
                     lambda: roadmaps.add_paper(key, self.ITEM), lambda: roadmaps.remove_paper("my-9", "x")):
            with self.assertRaises(KeyError):
                call()


if __name__ == "__main__":
    unittest.main()
