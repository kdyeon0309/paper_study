"""Terminal access to the library - the bridge Claude Code (or you) uses instead of a paid API.

    python -m app.cli search "open vocabulary detection" --recent --cat cs.CV
    python -m app.cli add 2010.11929 https://arxiv.org/abs/2103.00020
    python -m app.cli list --status reading
    python -m app.cli show 2010.11929        # metadata, abstract, note path
    python -m app.cli pending                 # papers waiting for a note
    python -m app.cli status 2010.11929 done
    python -m app.cli refresh                 # 분류·초록이 빈 arXiv 논문의 정보를 다시 받기
    python -m app.cli today                   # 오늘 할 일과 이번 주 진행
"""
import argparse
import sys

from . import arxiv, config, db, notes

LABEL = {"to_read": "읽을 예정", "reading": "읽는 중", "done": "완료"}


def _need(ref: str) -> dict:
    paper = db.find_paper(ref)
    if not paper:
        sys.exit(f"라이브러리에 없는 논문이에요: {ref}")
    return paper


def _line(p: dict) -> str:
    note = "노트O" if p.get("note_mtime") is not None else "노트X"
    return f"{p['id']:>4}  {p['slug']:<14} {LABEL[p['status']]:<6} {note}  {p['title']}"


def cmd_search(args):
    result = arxiv.search(" ".join(args.query), "recent" if args.recent else "relevance", args.cat)
    saved = db.saved_arxiv_ids()
    print(f"총 {result['total']}건 중 {len(result['items'])}건")
    for item in result["items"]:
        mark = "*" if item["arxiv_id"] in saved else " "
        print(f"{mark} {item['arxiv_id']:<12} {item['published']}  {item['title']}")
    print("\n(* = 이미 라이브러리에 있음)")


def cmd_add(args):
    found = set()
    for item in arxiv.fetch(args.ids):
        found.add(item["arxiv_id"])
        paper, created = db.add_paper({**item, "tags": args.tags})
        print(("추가됨  " if created else "이미 있음") + " " + _line(paper))
    missing = [i for i in args.ids if arxiv.parse_id(i) not in found]
    if missing:
        sys.exit(f"arXiv에서 찾지 못함: {', '.join(missing)}")


def cmd_list(args):
    for p in notes.sync_all():
        if not args.status or p["status"] == args.status:
            print(_line(p))


def cmd_pending(_):
    papers = [p for p in notes.sync_all() if p["note_requested"]]
    if not papers:
        print("노트 요청 대기 중인 논문이 없어요.")
    for p in papers:
        print(_line(p), f"\n      -> {notes.note_path(p['slug']).relative_to(config.HOME)}")


def cmd_show(args):
    p = _need(args.ref)
    notes.sync(p)
    path = notes.note_path(p["slug"])
    print(f"# {p['title']}\n")
    print(f"id: {p['id']}   slug: {p['slug']}   상태: {LABEL[p['status']]}")
    print(f"저자: {p['authors']}\n연도: {p['year']}   분류: {p['categories']}")
    if p["comment"]:
        print(f"코멘트: {p['comment']}")
    print(f"링크: {p['url']}\nPDF: {p['pdf_url']}\n태그: {p['tags']}")
    print(f"노트: {path} ({'있음' if path.exists() else '없음'})\n")
    print(f"## Abstract\n{p['abstract']}")


def cmd_status(args):
    p = _need(args.ref)
    print(_line(db.update_paper(p["id"], {"status": args.status})))


def cmd_today(_):
    papers = notes.sync_all()
    due, recalls, week = db.due_cards(), db.due_recalls(), db.weekly()
    reading = [p for p in papers if p["status"] == "reading"]
    todo = []
    if due:
        todo.append(f"복습 카드 {len(due)}장")
    if recalls:
        todo.append("다시 요약해볼 논문: " + ", ".join(p["title"] for p in recalls[:3]))
    todo += [f"읽는 중: {p['title']}" + ("" if p["note_mtime"] is not None else " (노트 없음)") for p in reading[:3]]
    todo += [f"노트 요청 대기: {p['title']}" for p in papers if p["note_requested"]][:3]
    print("오늘 할 일")
    print("\n".join(f"  - {line}" for line in todo) if todo else "  밀린 일이 없어요.")
    c, g = week["current"], week["goals"]
    goal = lambda value, target, unit: f"{value}{unit}" + (f" / 목표 {target}{unit}" if target else "")
    print(f"\n이번 주 ({week['start']} ~ {week['end']})")
    print(f"  공부한 날 {goal(c['active_days'], g['goal_days'], '일')}, 완독 {goal(c['finished'], g['goal_papers'], '편')}, "
          f"복습 {c['reviews']}장, 읽은 시간 {c['minutes']}분")
    if week["goal_streak"] > 1:
        print(f"  {week['goal_streak']}주 연속 목표 달성 중")


def cmd_refresh(args):
    targets = [p for p in db.list_papers() if p["arxiv_id"] and (args.all or not p["categories"] or not p["abstract"])]
    if not targets:
        print("새로 받을 논문이 없어요.")
        return
    fetched = {i["arxiv_id"]: i for i in arxiv.fetch([p["arxiv_id"] for p in targets])}
    for p in targets:
        if p["arxiv_id"] in fetched:
            print("갱신   ", _line(db.set_metadata(p["id"], fetched[p["arxiv_id"]])))
        else:
            print("못 찾음", _line(p))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Paper Study 라이브러리 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="arXiv 검색")
    s.add_argument("query", nargs="+")
    s.add_argument("--recent", action="store_true", help="최신순")
    s.add_argument("--cat", default="", help="카테고리 (예: cs.CV)")
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("add", help="arXiv ID/URL로 논문 추가")
    s.add_argument("ids", nargs="+")
    s.add_argument("--tags", default="")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("list", help="라이브러리 목록")
    s.add_argument("--status", choices=config.STATUSES)
    s.set_defaults(func=cmd_list)

    sub.add_parser("pending", help="노트 요청 대기 목록").set_defaults(func=cmd_pending)

    s = sub.add_parser("show", help="논문 상세 (id, slug, arXiv ID)")
    s.add_argument("ref")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("status", help="읽기 상태 변경")
    s.add_argument("ref")
    s.add_argument("status", choices=config.STATUSES)
    s.set_defaults(func=cmd_status)

    sub.add_parser("today", help="오늘 할 일과 이번 주 진행").set_defaults(func=cmd_today)

    s = sub.add_parser("refresh", help="arXiv에서 논문 정보 다시 받기")
    s.add_argument("--all", action="store_true", help="정보가 있는 논문도 모두")
    s.set_defaults(func=cmd_refresh)

    args = parser.parse_args(argv)
    db.init()
    try:
        args.func(args)
    except (arxiv.ArxivError, ValueError) as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
