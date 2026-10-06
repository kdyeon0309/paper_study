"""Leitner-box spaced repetition. Pure functions so the schedule is testable."""
from datetime import date, timedelta

# 박스 번호 -> 다음 복습까지의 일수
INTERVALS = (1, 3, 7, 14, 30, 60)
GRADES = ("again", "hard", "good")


def next_state(box: int, grade: str, today: date) -> tuple[int, date]:
    """again: 처음부터 / hard: 같은 박스 한 번 더 / good: 다음 박스로."""
    if grade not in GRADES:
        raise ValueError(f"unknown grade: {grade}")
    box = max(0, min(box, len(INTERVALS) - 1))
    if grade == "again":
        box = 0
    elif grade == "good":
        box = min(box + 1, len(INTERVALS) - 1)
    return box, today + timedelta(days=INTERVALS[box])


def streak(active_days: set[str], today: date) -> int:
    """Consecutive active days ending today, or yesterday if today is still empty."""
    day = today if today.isoformat() in active_days else today - timedelta(days=1)
    count = 0
    while day.isoformat() in active_days:
        count += 1
        day -= timedelta(days=1)
    return count
