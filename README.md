# Paper Study

퇴근 후 논문 스터디를 위한 로컬 웹앱. 논문을 찾고, 노트를 쓰고, 잊지 않게 복습한다.

**운영비 0원.** 검색은 arXiv 공개 API를 쓰고, 깊은 요약은 Claude Code가 마크다운 파일로 써준다. API 키가 필요 없다.

## 실행

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000
```

브라우저에서 http://localhost:8000 을 연다.

## 화면

| 화면 | 하는 일 |
|---|---|
| 홈 | 연속 학습일, 이번 달 완독 수, 주간 회고(전주 대비), 20주 학습 기록, 오늘 할 일, 로드맵 진행 |
| 검색 | arXiv 키워드 검색(분야·정렬 선택), arXiv ID나 링크를 붙여넣으면 바로 조회, 자주 보는 검색 저장 |
| 라이브러리 | 저장한 논문. 상태·태그·검색어로 거르기, 노트 본문 검색, BibTeX 내보내기, 백업과 복원 |
| 논문 | 초록, 태그, 읽기 상태, 노트 편집기(마크다운 + LaTeX 수식, 자동 저장), 복습 카드 |
| 복습 | 오늘 차례인 카드를 간격 반복으로 복습 (1 → 3 → 7 → 14 → 30 → 60일). '약점' 탭에서 태그별 정답률과 자주 틀린 카드 연습 |
| 로드맵 | 분야별 필독 논문 8개 트랙 49편. 버튼 하나로 라이브러리에 추가. 내 트랙을 만들어 순서와 읽는 이유를 직접 정리 |
| 서베이 | 주제별 정리 문서. Claude Code에 요청할 프롬프트를 만들어준다 |

## 공부 흐름

1. **고르기** — 로드맵에서 트랙을 고르거나 검색해서 라이브러리에 저장한다.
2. **읽고 쓰기** — 논문 페이지에서 노트를 쓴다. 직접 써도 되고, `Claude에게 요청` 버튼이 만든 프롬프트를 Claude Code에 붙여넣어도 된다. 어느 쪽이든 `notes/<arXiv ID>.md` 한 파일에 저장되고, Claude Code가 쓴 내용은 몇 초 안에 화면에 나타난다.
3. **복습하기** — 노트에 아래처럼 적으면 복습 카드가 된다.

   ```markdown
   Q: DETR에 NMS가 필요 없는 이유는?
   A: 헝가리안 매칭으로 GT 하나에 예측 하나만 대응시키기 때문.
   ```

   맞힌 카드는 간격이 늘어나고, 틀린 카드는 내일 다시 나온다. 노트에서 질문을 고쳐도 다른 카드의 진도는 유지된다.

## Claude Code와 함께 쓰기

이 폴더에서 Claude Code를 열고 말로 시키면 된다.

- "논문 2304.08069 노트 써줘" → `notes/2304.08069.md`
- "open-vocabulary detection 서베이 써줘" → `surveys/open-vocabulary-detection.md`

Claude Code는 터미널 명령으로 라이브러리를 읽고 쓴다. 직접 써도 된다.

```bash
.venv/bin/python -m app.cli search "open vocabulary detection" --cat cs.CV --recent
.venv/bin/python -m app.cli add 2010.11929 https://arxiv.org/abs/2103.00020
.venv/bin/python -m app.cli list --status reading
.venv/bin/python -m app.cli show 2010.11929     # 메타데이터, 초록, 노트 경로
.venv/bin/python -m app.cli pending             # 노트를 요청해둔 논문
.venv/bin/python -m app.cli status 2010.11929 done
.venv/bin/python -m app.cli refresh             # 분류·초록이 빈 논문의 정보를 arXiv에서 다시 받기
```

## 데이터

| 위치 | 내용 | git |
|---|---|---|
| `papers.db` | 논문 목록, 복습 카드 진도, 활동 기록, 저장한 검색 (SQLite) | 제외 |
| `notes/*.md` | 논문 노트. 파일 이름은 arXiv ID | 포함 |
| `surveys/*.md` | 주제 서베이 | 포함 |
| `roadmaps.json` | 기본 로드맵 트랙 | 포함 |
| `my_roadmaps.json` | 화면에서 만든 내 트랙 | 포함 |

라이브러리 화면의 `백업`은 논문 목록, 노트, 내 트랙, 저장한 검색을 JSON 한 파일로 내려받고, `가져오기`는 없는 논문만 추가한다(기존 논문과 노트는 덮어쓰지 않는다). `PAPER_STUDY_HOME` 환경변수로 데이터 폴더를 다른 곳에 둘 수 있다.

## 구조

```
app/
  main.py       FastAPI 라우트
  arxiv.py      arXiv API 클라이언트 (표준 라이브러리만 사용)
  db.py         SQLite: 논문, 카드, 활동 기록, v0.1 → v0.2 마이그레이션
  notes.py      노트 파일 읽기/쓰기, Q/A 카드 추출, 외부 변경 감지
  review.py     간격 반복 일정, 연속 학습일 계산
  roadmaps.py   기본 트랙과 내 트랙
  exporter.py   BibTeX, 백업/복원
  cli.py        터미널 명령
  static/       화면 (빌드 없는 ES 모듈). vendor/ 에 마크다운·수식 라이브러리 포함
tests/          python -m unittest discover -s tests
```

의존성은 `fastapi`, `uvicorn` 둘뿐이다. 화면이 쓰는 marked, DOMPurify, KaTeX는 저장소에 들어 있어서, 노트를 읽고 쓰고 복습하는 데는 인터넷이 필요 없다(arXiv 검색만 필요하다).

## 테스트

```bash
.venv/bin/python -m unittest discover -s tests -v
```

네트워크 없이 돌아간다. 기획은 [PLAN.md](PLAN.md), 개선 이력과 남은 일은 [IMPROVEMENTS.md](IMPROVEMENTS.md)에 있다.
