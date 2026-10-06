# Paper Study Web

퇴근 후 논문 스터디용 로컬 웹앱. **완전 무료** — arXiv API로 논문을 검색·저장하고,
깊은 요약/노트는 Claude Code 세션에서 작성해 웹에서 본다.

## 실행

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

→ http://localhost:8000 (API 키 불필요)

## 사용 흐름

1. 웹에서 arXiv 검색 → 마음에 드는 논문 "라이브러리에 저장"
2. Claude Code에서: **"논문 3번 노트 써줘"** → Claude가 논문을 읽고 `notes/3.md` 작성
3. 웹 라이브러리 카드의 "노트 📝" 버튼으로 바로 열람

## 구성

- `app/main.py` — FastAPI (검색 프록시 + 논문 CRUD + 노트 서빙)
- `app/arxiv.py` — arXiv API 검색 (stdlib만 사용)
- `app/db.py` — SQLite (`papers.db`)
- `app/static/` — 바닐라 HTML/JS 프론트
- `notes/<paper_id>.md` — 논문별 스터디 노트 (Claude Code가 작성)
