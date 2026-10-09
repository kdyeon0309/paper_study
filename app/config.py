"""Paths. PAPER_STUDY_HOME moves all user data (tests point it at a temp dir)."""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("PAPER_STUDY_HOME", REPO))

DB_PATH = HOME / "papers.db"
NOTES_DIR = HOME / "notes"
SURVEYS_DIR = HOME / "surveys"
ROADMAP_FILE = REPO / "roadmaps.json"
USER_ROADMAP_FILE = HOME / "my_roadmaps.json"
EXERCISE_FILE = REPO / "exercises.json"
STATIC_DIR = REPO / "app" / "static"

STATUSES = ("to_read", "reading", "done")
