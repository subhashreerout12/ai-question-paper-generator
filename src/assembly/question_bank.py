"""SQLite question bank: store generated questions and read them back."""

import json
import os
import sqlite3

DB_PATH = os.path.join("data", "question_bank.db")

DEFAULT_MARKS = {"mcq": 1, "short": 3}


def connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Open the database, creating the file and table if needed."""
    folder = os.path.dirname(db_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            topic       TEXT NOT NULL,
            qtype       TEXT NOT NULL,
            difficulty  TEXT NOT NULL,
            marks       INTEGER NOT NULL,
            question    TEXT NOT NULL UNIQUE,
            data        TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _marks(q: dict) -> int:
    try:
        return int(q.get("marks", DEFAULT_MARKS[q["type"]]))
    except (TypeError, ValueError):
        return DEFAULT_MARKS[q["type"]]


def _difficulty(q: dict) -> str:
    d = str(q.get("difficulty", "medium")).strip().lower()
    return d if d in ("easy", "medium", "hard") else "medium"


def add_questions(conn: sqlite3.Connection, questions: list[dict], topic: str = "general") -> int:
    """Insert questions; exact duplicates (same question text) are skipped.

    Returns how many new questions were actually added.
    """
    added = 0
    for q in questions:
        cur = conn.execute(
            "INSERT OR IGNORE INTO questions (topic, qtype, difficulty, marks, question, data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                topic,
                q["type"],
                _difficulty(q),
                _marks(q),
                q["question"].strip(),
                json.dumps(q, ensure_ascii=False),
            ),
        )
        added += cur.rowcount
    conn.commit()
    return added


def get_questions(
    conn: sqlite3.Connection, qtype: str | None = None, topic: str | None = None
) -> list[dict]:
    """Return questions as dicts, optionally filtered by type and topic."""
    sql, params = "SELECT * FROM questions WHERE 1=1", []
    if qtype:
        sql += " AND qtype = ?"
        params.append(qtype)
    if topic:
        sql += " AND topic = ?"
        params.append(topic)
    out = []
    for row in conn.execute(sql, params):
        q = json.loads(row["data"])
        q.update(
            id=row["id"],
            topic=row["topic"],
            type=row["qtype"],
            difficulty=row["difficulty"],
            marks=row["marks"],
        )
        out.append(q)
    return out


def topics(conn: sqlite3.Connection) -> list[str]:
    """All topic labels currently in the bank."""
    return [r[0] for r in conn.execute("SELECT DISTINCT topic FROM questions ORDER BY topic")]


def summary(conn: sqlite3.Connection) -> list[tuple]:
    """Counts per (topic, type, difficulty), for printing."""
    rows = conn.execute(
        "SELECT topic, qtype, difficulty, COUNT(*) FROM questions "
        "GROUP BY topic, qtype, difficulty ORDER BY topic, qtype, difficulty"
    )
    return [tuple(r) for r in rows]
