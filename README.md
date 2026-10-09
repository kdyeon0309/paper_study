# Paper Study

퇴근 후 논문 스터디를 위한 로컬 웹앱. 논문을 찾고, 노트를 쓰고, 잊지 않게 복습한다.

**운영비 0원.** 검색은 arXiv 공개 API를 쓰고, 깊은 요약은 Claude Code가 마크다운 파일로 써준다. API 키가 필요 없다.

## 실행

```bash
./run.sh
```

처음이면 가상환경을 만들고 의존성을 설치한 뒤, 서버를 켜고 브라우저를 연다. 다른 포트는 `./run.sh --port 8010`, 브라우저를 열지 않으려면 `--no-open`.

직접 하려면:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app
```

단축키는 화면에서 `?`를 누르면 나온다.

## 화면

| 화면 | 하는 일 |
|---|---|
| 홈 | 연속 학습일, 이번 달 완독 수, 주간 회고(전주 대비, 목표 달성), 20주 학습 기록, 오늘 할 일(새 논문 알림 포함), 로드맵 진행 |
| 검색 | arXiv 키워드 검색(분야·정렬 선택), arXiv ID나 링크를 붙여넣으면 바로 조회, 자주 보는 검색 저장(새 논문 수 표시) |
| 라이브러리 | 저장한 논문. 상태·태그·검색어로 거르기, 노트 본문 검색, 연결 지도, BibTeX 내보내기, 백업과 복원 |
| 논문 | 초록, 태그, 읽기 상태, 노트 편집기(마크다운 + LaTeX 수식, 자동 저장), 읽기 타이머, 복습 카드 추가·수정, 연결된 논문, 노트 인쇄 |
| 복습 | 오늘 차례인 카드를 간격 반복으로 복습 (1 → 3 → 7 → 14 → 30 → 60일). '논문 회상' 탭에서 완독한 논문을 기억으로 다시 요약, '약점' 탭에서 태그별 정답률과 자주 틀린 카드 연습 |
| 로드맵 | 구현 과제 9개(자동 채점). 분야별 필독 논문 8개 트랙 49편. 버튼 하나로 라이브러리에 추가. 내 트랙을 만들어 순서와 읽는 이유를 직접 정리 |
| 서베이 | 주제별 정리 문서. Claude Code에 요청할 프롬프트를 만들어준다. 서베이에 나온 논문을 라이브러리와 잇는다 |

## 공부 방식: 내가 쓰고, Claude가 검사한다

요약을 받아 읽는 것은 공부한 느낌만 준다. 이 앱은 반대로 쓴다. 자세한 순서는 앱의 `사용법` 화면에 있다.

1. **직접 읽고 쓴다.** 3회독 템플릿(훑어보기 → 정독 → 다시 만들어 보기)으로 노트를 쓴다.
2. **Claude에게는 검사를 맡긴다.** 논문 화면의 `Claude와 공부하기`에서 내 노트 검토, 구술시험, 구현 과제를 요청한다. 초안 대필은 지름길로만 둔다.
3. **이해 깊이를 단계로 남긴다.** 훑어봄 → 정독 → 유도 → 구현. 기준을 통과했을 때만 올린다.
4. **기초는 구현으로 채운다.** `exercises/`에 numpy로 직접 짜는 과제 9개와 채점 스크립트가 있다.

   ```bash
   cp exercises/02_iou_nms/solution_template.py exercises/02_iou_nms/solution.py
   python exercises/02_iou_nms/check.py
   ```

5. **잊지 않게 한다.** 노트의 `Q:` / `A:`는 복습 카드가 되어 간격을 늘려가며 다시 나오고, 완독한 논문은 일주일 뒤 기억만으로 다시 요약하게 한다.
6. **연결한다.** 편집기에서 `[[`를 치면 라이브러리 논문을 골라 링크할 수 있고, '연결 지도'에서 전체를 본다.

## Claude Code와 함께 쓰기

이 폴더에서 Claude Code를 열고 말로 시키면 된다.

- "notes/2304.08069.md 를 논문과 대조해서 틀린 곳만 지적해줘"
- "논문 2304.08069 로 구술시험 봐줘"
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
.venv/bin/python -m app.cli today               # 오늘 할 일과 이번 주 진행
```

## 데이터

| 위치 | 내용 | git |
|---|---|---|
| `papers.db` | 논문 목록, 복습 카드 진도, 활동 기록, 저장한 검색 (SQLite) | 제외 |
| `notes/*.md` | 논문 노트. 파일 이름은 arXiv ID | 포함 |
| `surveys/*.md` | 주제 서베이 | 포함 |
| `roadmaps.json` | 기본 로드맵 트랙 | 포함 |
| `exercises/` | 구현 과제(문제, 함수 틀, 채점 스크립트). 내가 쓴 `solution.py`도 여기 | 포함 |
| `my_roadmaps.json` | 화면에서 만든 내 트랙 | 포함 |
| `backups/` | DB 자동 복사본. 하루 한 번, 최근 7개 | 제외 |

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
  __main__.py   python -m app (서버 실행 + 브라우저 열기)
  static/       화면 (빌드 없는 ES 모듈). vendor/ 에 마크다운·수식 라이브러리 포함
tests/          python -m unittest discover -s tests
```

의존성은 `fastapi`, `uvicorn` 둘뿐이다. 화면이 쓰는 marked, DOMPurify, KaTeX는 저장소에 들어 있어서, 노트를 읽고 쓰고 복습하는 데는 인터넷이 필요 없다(arXiv 검색만 필요하다).

## 테스트

```bash
.venv/bin/python -m unittest discover -s tests -v
```

함수 단위 테스트(`test_core.py`)와, 실제 서버를 띄워 HTTP로 확인하는 테스트(`test_api.py`)가 있다. 둘 다 네트워크 없이 돌아간다. 기획은 [PLAN.md](PLAN.md), 개선 이력과 남은 일은 [IMPROVEMENTS.md](IMPROVEMENTS.md)에 있다.
