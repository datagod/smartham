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
    {
        "id": "net_control",
        "name": "Net Control",
        "description": "50 lifetime correct answers.",
        "icon": "🎙️",
    },
    {
        "id": "dx_hunter",
        "name": "DX Hunter",
        "description": "100 lifetime correct answers.",
        "icon": "🌍",
    },
    {
        "id": "kilowatt_club",
        "name": "Kilowatt Club",
        "description": "200 lifetime correct answers.",
        "icon": "⚡",
    },
    {
        "id": "rubber_stamp",
        "name": "Rubber Stamp",
        "description": "Complete 25 practice attempts.",
        "icon": "📋",
    },
    {
        "id": "field_day",
        "name": "Field Day",
        "description": "Complete 100 practice attempts.",
        "icon": "⛺",
    },
    {
        "id": "honours_graduate",
        "name": "Honours Graduate",
        "description": "Score 90% or higher on a Basic mock exam.",
        "icon": "🏅",
    },
    {
        "id": "advanced_ticket",
        "name": "Advanced Ticket",
        "description": "Pass an Advanced mock exam with 70% or higher.",
        "icon": "📜",
    },
    {
        "id": "band_hopper",
        "name": "Band Hopper",
        "description": "Answer correctly in 5 different topic sections.",
        "icon": "📶",
    },
    {
        "id": "globe_trotter",
        "name": "Globe Trotter",
        "description": "Answer correctly in 15 different topic sections.",
        "icon": "🌐",
    },
    {
        "id": "vhf_vanguard",
        "name": "VHF Vanguard",
        "description": "20 correct Advanced-level answers.",
        "icon": "📡",
    },
    {
        "id": "basic_builder",
        "name": "Basic Builder",
        "description": "50 correct Basic-level answers.",
        "icon": "🔧",
    },
    {
        "id": "golden_swr",
        "name": "Golden SWR",
        "description": "85%+ overall accuracy after 50+ attempts.",
        "icon": "✨",
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


def _lifetime_correct(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM quiz_attempts WHERE is_correct = 1"
    ).fetchone()
    return int(row["n"] or 0)


def _practice_attempts(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM quiz_attempts WHERE mode = 'practice'"
    ).fetchone()
    return int(row["n"] or 0)


def _level_correct(conn: sqlite3.Connection, level: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM quiz_attempts
        WHERE is_correct = 1 AND level = ?
        """,
        (level,),
    ).fetchone()
    return int(row["n"] or 0)


def _sections_with_correct(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT section) AS n FROM quiz_attempts
        WHERE is_correct = 1 AND mode = 'practice'
        """
    ).fetchone()
    return int(row["n"] or 0)


def _overall_accuracy(conn: sqlite3.Connection) -> tuple[float, int]:
    row = conn.execute(
        """
        SELECT
            SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct,
            COUNT(*) AS total
        FROM quiz_attempts
        WHERE mode = 'practice'
        """
    ).fetchone()
    correct = int(row["correct"] or 0)
    total = int(row["total"] or 0)
    accuracy = (correct / total) if total else 0.0
    return accuracy, total


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
        total_correct = _lifetime_correct(conn)
        if total_correct == 1:
            grant("first_contact")

        streak = db.get_streak(conn)
        if streak >= 5:
            grant("copy_perfect")
        if streak >= 10:
            grant("clear_channel")
        if streak >= 25:
            grant("full_quieting")

        if total_correct >= 50:
            grant("net_control")
        if total_correct >= 100:
            grant("dx_hunter")
        if total_correct >= 200:
            grant("kilowatt_club")

        if _level_correct(conn, "basic") >= 50:
            grant("basic_builder")
        if _level_correct(conn, "advanced") >= 20:
            grant("vhf_vanguard")

        sections_hit = _sections_with_correct(conn)
        if sections_hit >= 5:
            grant("band_hopper")
        if sections_hit >= 15:
            grant("globe_trotter")

    attempts = _practice_attempts(conn)
    if attempts >= 25:
        grant("rubber_stamp")
    if attempts >= 100:
        grant("field_day")

    accuracy, total = _overall_accuracy(conn)
    if total >= 50 and accuracy >= 0.85:
        grant("golden_swr")

    reg_acc = _bucket_accuracy(conn, "regulations")
    if reg_acc is not None and reg_acc >= 0.8:
        grant("regulator")

    tech_acc = _bucket_accuracy(conn, "technical")
    if tech_acc is not None and tech_acc >= 0.8:
        grant("ohms_law_hero")

    if mock_result:
        score = mock_result.get("score") or 0
        level = mock_result.get("level")
        if mock_result.get("passed"):
            grant("exam_ready")
        if level == "basic" and score >= 0.8:
            grant("advanced_bound")
        if level == "basic" and score >= 0.9:
            grant("honours_graduate")
        if level == "advanced" and mock_result.get("passed"):
            grant("advanced_ticket")

    return newly_earned


def _award_progress(conn: sqlite3.Connection, award_id: str) -> float:
    streak = db.get_streak(conn)
    reg_acc = _bucket_accuracy(conn, "regulations")
    tech_acc = _bucket_accuracy(conn, "technical")
    lifetime = _lifetime_correct(conn)
    attempts = _practice_attempts(conn)
    sections_hit = _sections_with_correct(conn)
    accuracy, total = _overall_accuracy(conn)

    progress_map: dict[str, float] = {
        "copy_perfect": min(streak / 5, 1.0),
        "clear_channel": min(streak / 10, 1.0),
        "full_quieting": min(streak / 25, 1.0),
        "regulator": min((reg_acc or 0) / 0.8, 1.0) if reg_acc is not None else 0.0,
        "ohms_law_hero": min((tech_acc or 0) / 0.8, 1.0) if tech_acc is not None else 0.0,
        "net_control": min(lifetime / 50, 1.0),
        "dx_hunter": min(lifetime / 100, 1.0),
        "kilowatt_club": min(lifetime / 200, 1.0),
        "rubber_stamp": min(attempts / 25, 1.0),
        "field_day": min(attempts / 100, 1.0),
        "band_hopper": min(sections_hit / 5, 1.0),
        "globe_trotter": min(sections_hit / 15, 1.0),
        "vhf_vanguard": min(_level_correct(conn, "advanced") / 20, 1.0),
        "basic_builder": min(_level_correct(conn, "basic") / 50, 1.0),
        "golden_swr": min(min(total / 50, 1.0), min(accuracy / 0.85, 1.0)) if total else 0.0,
    }
    return progress_map.get(award_id, 0.0)


def awards_status(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    earned = {row["award_id"]: row["earned_at"] for row in db.list_awards(conn)}

    out: list[dict[str, Any]] = []
    for award in AWARD_DEFS:
        item = dict(award)
        item["earned"] = award["id"] in earned
        item["earned_at"] = earned.get(award["id"])
        progress = _award_progress(conn, award["id"])
        if item["earned"]:
            item["progress"] = 1.0
        elif progress > 0:
            item["progress"] = progress
        else:
            item["progress"] = 0.0
        out.append(item)
    return out