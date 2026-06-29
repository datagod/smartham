"""SQLite persistence for questions, progress, awards, and cached explanations."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            level TEXT NOT NULL,
            section TEXT NOT NULL,
            stem TEXT NOT NULL,
            choice_a TEXT NOT NULL,
            choice_b TEXT NOT NULL,
            choice_c TEXT NOT NULL,
            choice_d TEXT NOT NULL,
            correct TEXT NOT NULL,
            source_page INTEGER
        );

        CREATE TABLE IF NOT EXISTS study_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            title TEXT,
            body TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id TEXT NOT NULL,
            level TEXT NOT NULL,
            section TEXT NOT NULL,
            chosen TEXT NOT NULL,
            correct TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            mode TEXT NOT NULL DEFAULT 'practice',
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_stats (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS awards_earned (
            award_id TEXT PRIMARY KEY,
            earned_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS explanation_cache (
            question_id TEXT PRIMARY KEY,
            explanation TEXT NOT NULL,
            model TEXT,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS summary_cache (
            cache_key TEXT PRIMARY KEY,
            summary TEXT NOT NULL,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mock_exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            question_ids TEXT NOT NULL,
            answers TEXT,
            score REAL,
            passed INTEGER,
            started_at REAL NOT NULL,
            finished_at REAL
        );

        CREATE INDEX IF NOT EXISTS idx_questions_level ON questions(level);
        CREATE INDEX IF NOT EXISTS idx_questions_section ON questions(section);
        CREATE INDEX IF NOT EXISTS idx_attempts_question ON quiz_attempts(question_id);
        """
    )
    conn.commit()
    _ensure_explanation_cache_columns(conn)


def _ensure_explanation_cache_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(explanation_cache)").fetchall()}
    if "model" not in cols:
        conn.execute("ALTER TABLE explanation_cache ADD COLUMN model TEXT")
        conn.commit()


def upsert_questions(conn: sqlite3.Connection, questions: list[dict[str, Any]]) -> int:
    conn.executemany(
        """
        INSERT INTO questions (id, level, section, stem, choice_a, choice_b, choice_c, choice_d, correct, source_page)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            level=excluded.level,
            section=excluded.section,
            stem=excluded.stem,
            choice_a=excluded.choice_a,
            choice_b=excluded.choice_b,
            choice_c=excluded.choice_c,
            choice_d=excluded.choice_d,
            correct=excluded.correct,
            source_page=excluded.source_page
        """,
        [
            (
                q["id"],
                q["level"],
                q["section"],
                q["stem"],
                q["a"],
                q["b"],
                q["c"],
                q["d"],
                q["correct"],
                q.get("page"),
            )
            for q in questions
        ],
    )
    conn.commit()
    return len(questions)


def upsert_study_sections(conn: sqlite3.Connection, sections: list[dict[str, Any]]) -> int:
    conn.execute("DELETE FROM study_sections")
    conn.executemany(
        """
        INSERT INTO study_sections (source_file, page_number, title, body)
        VALUES (?, ?, ?, ?)
        """,
        [
            (s["source_file"], s["page_number"], s.get("title"), s["body"])
            for s in sections
        ],
    )
    conn.commit()
    return len(sections)


def get_stat(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM user_stats WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_stat(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO user_stats (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    conn.commit()


def record_attempt(
    conn: sqlite3.Connection,
    *,
    question_id: str,
    level: str,
    section: str,
    chosen: str,
    correct: str,
    is_correct: bool,
    mode: str = "practice",
) -> None:
    conn.execute(
        """
        INSERT INTO quiz_attempts (question_id, level, section, chosen, correct, is_correct, mode, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (question_id, level, section, chosen, correct, int(is_correct), mode, time.time()),
    )
    conn.commit()


def get_streak(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT is_correct FROM quiz_attempts
        WHERE mode = 'practice'
        ORDER BY id DESC
        LIMIT 200
        """
    ).fetchall()
    streak = 0
    for row in rows:
        if row["is_correct"]:
            streak += 1
        else:
            break
    return streak


def question_progress(
    conn: sqlite3.Connection,
    *,
    level: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if level:
        clauses.append("q.level = ?")
        params.append(level)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT
            q.id,
            q.level,
            q.section,
            EXISTS (
                SELECT 1 FROM quiz_attempts a
                WHERE a.question_id = q.id
                  AND a.mode = 'practice'
                  AND a.is_correct = 1
            ) AS mastered
        FROM questions q
        {where}
        ORDER BY q.id
        """,
        params,
    ).fetchall()
    return [
        {
            "id": row["id"],
            "level": row["level"],
            "section": row["section"],
            "mastered": bool(row["mastered"]),
        }
        for row in rows
    ]


def get_section_accuracy(conn: sqlite3.Connection, section: str) -> tuple[int, int]:
    row = conn.execute(
        """
        SELECT
            SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct,
            COUNT(*) AS total
        FROM quiz_attempts
        WHERE section = ? AND mode = 'practice'
        """,
        (section,),
    ).fetchone()
    return int(row["correct"] or 0), int(row["total"] or 0)


def list_awards(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT award_id, earned_at FROM awards_earned ORDER BY earned_at"
    ).fetchall()


def earn_award(conn: sqlite3.Connection, award_id: str) -> bool:
    existing = conn.execute(
        "SELECT award_id FROM awards_earned WHERE award_id = ?", (award_id,)
    ).fetchone()
    if existing:
        return False
    conn.execute(
        "INSERT INTO awards_earned (award_id, earned_at) VALUES (?, ?)",
        (award_id, time.time()),
    )
    conn.commit()
    return True


def get_cached_explanation(
    conn: sqlite3.Connection,
    question_id: str,
    *,
    model: str | None = None,
) -> str | None:
    if model:
        row = conn.execute(
            """
            SELECT explanation FROM explanation_cache
            WHERE question_id = ? AND model = ?
            """,
            (question_id, model),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT explanation FROM explanation_cache WHERE question_id = ?",
            (question_id,),
        ).fetchone()
    return row["explanation"] if row else None


def cache_explanation(
    conn: sqlite3.Connection,
    question_id: str,
    explanation: str,
    *,
    model: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO explanation_cache (question_id, explanation, model, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(question_id) DO UPDATE SET
            explanation = excluded.explanation,
            model = excluded.model,
            created_at = excluded.created_at
        """,
        (question_id, explanation, model, time.time()),
    )
    conn.commit()


def explanation_cache_stats(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute("SELECT COUNT(*) AS n FROM explanation_cache").fetchone()
    return {"cached_explanations": int(row["n"] or 0)}


def get_cached_summary(conn: sqlite3.Connection, cache_key: str) -> str | None:
    row = conn.execute(
        "SELECT summary FROM summary_cache WHERE cache_key = ?", (cache_key,)
    ).fetchone()
    return row["summary"] if row else None


def cache_summary(conn: sqlite3.Connection, cache_key: str, summary: str) -> None:
    conn.execute(
        """
        INSERT INTO summary_cache (cache_key, summary, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            summary = excluded.summary,
            created_at = excluded.created_at
        """,
        (cache_key, summary, time.time()),
    )
    conn.commit()