"""Gamified awards for correct answers and exam milestones."""

from __future__ import annotations

import sqlite3
from typing import Any

from smartham import db

AWARD_DEFS: list[dict[str, Any]] = [
    {
        "id": "first_contact",
        "name": "First Contact",
        "description": "Answer your first question correctly.",
        "icon": "📡",
    },
    {
        "id": "copy_perfect",
        "name": "Copy Perfect",
        "description": "5 correct answers in a row.",
        "icon": "📝",
    },
    {
        "id": "clear_channel",
        "name": "Clear Channel",
        "description": "10 correct answers in a row.",
        "icon": "📻",
    },
    {
        "id": "full_quieting",
        "name": "Full Quieting",
        "description": "25 correct answers in a row.",
        "icon": "🔊",
    },
    {
        "id": "regulator",
        "name": "Regulator",
        "description": "80%+ accuracy in regulations sections (B-001-001 to B-001-005).",
        "icon": "⚖️",
    },
    {
        "id": "ohms_law_hero",
        "name": "Ohm's Law Hero",
        "description": "80%+ accuracy in technical sections (B-002+).",
        "icon": "⚡",
    },
    {
        "id": "exam_ready",
        "name": "Exam Ready",
        "description": "Pass a mock exam with 70% or higher.",
        "icon": "🎓",
    },
    {
        "id": "advanced_bound",
        "name": "Advanced Bound",
        "description": "Pass a Basic mock exam with 80% or higher.",
        "icon": "🚀",
    },
]

REGULATION_SECTIONS = {
    "B-001-001",
    "B-001-002",
    "B-001-003",
    "B-001-004",
    "B-001-005",
}


def _section_bucket(section: str) -> str:
    if section in REGULATION_SECTIONS:
        return "regulations"
    if section.startswith("B-"):
        return "technical"
    return "advanced"


def _bucket_accuracy(conn: sqlite3.Connection, bucket: str) -> float | None:
    if bucket == "regulations":
        sections = REGULATION_SECTIONS
    elif bucket == "technical":
        rows = conn.execute(
            "SELECT DISTINCT section FROM questions WHERE level = 'basic'"
        ).fetchall()
        sections = {r["section"] for r in rows if r["section"] not in REGULATION_SECTIONS}
    else:
        rows = conn.execute(
            "SELECT DISTINCT section FROM questions WHERE level = 'advanced'"
        ).fetchall()
        sections = {r["section"] for r in rows}

    correct = 0
    total = 0
    for section in sections:
        c, t = db.get_section_accuracy(conn, section)
        correct += c
        total += t
    if total < 10:
        return None
    return correct / total


def check_awards(
    conn: sqlite3.Connection,
    *,
    is_correct: bool,
    mock_result: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    newly_earned: list[dict[str, Any]] = []

    def grant(award_id: str) -> None:
        if db.earn_award(conn, award_id):
            match = next((a for a in AWARD_DEFS if a["id"] == award_id), None)
            if match:
                newly_earned.append(match)

    if is_correct:
        total_correct = conn.execute(
            "SELECT COUNT(*) AS n FROM quiz_attempts WHERE is_correct = 1"
        ).fetchone()["n"]
        if total_correct == 1:
            grant("first_contact")

        streak = db.get_streak(conn)
        if streak >= 5:
            grant("copy_perfect")
        if streak >= 10:
            grant("clear_channel")
        if streak >= 25:
            grant("full_quieting")

    reg_acc = _bucket_accuracy(conn, "regulations")
    if reg_acc is not None and reg_acc >= 0.8:
        grant("regulator")

    tech_acc = _bucket_accuracy(conn, "technical")
    if tech_acc is not None and tech_acc >= 0.8:
        grant("ohms_law_hero")

    if mock_result:
        if mock_result.get("passed"):
            grant("exam_ready")
        if mock_result.get("level") == "basic" and (mock_result.get("score") or 0) >= 0.8:
            grant("advanced_bound")

    return newly_earned


def awards_status(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    earned = {row["award_id"]: row["earned_at"] for row in db.list_awards(conn)}
    streak = db.get_streak(conn)
    reg_acc = _bucket_accuracy(conn, "regulations")
    tech_acc = _bucket_accuracy(conn, "technical")

    out: list[dict[str, Any]] = []
    for award in AWARD_DEFS:
        item = dict(award)
        item["earned"] = award["id"] in earned
        item["earned_at"] = earned.get(award["id"])
        item["progress"] = 0.0
        if award["id"] == "copy_perfect":
            item["progress"] = min(streak / 5, 1.0)
        elif award["id"] == "clear_channel":
            item["progress"] = min(streak / 10, 1.0)
        elif award["id"] == "full_quieting":
            item["progress"] = min(streak / 25, 1.0)
        elif award["id"] == "regulator" and reg_acc is not None:
            item["progress"] = min(reg_acc / 0.8, 1.0)
        elif award["id"] == "ohms_law_hero" and tech_acc is not None:
            item["progress"] = min(tech_acc / 0.8, 1.0)
        elif item["earned"]:
            item["progress"] = 1.0
        out.append(item)
    return out