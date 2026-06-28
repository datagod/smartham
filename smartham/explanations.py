"""Prefetch and cache Ollama explanations for quiz questions."""

from __future__ import annotations

import asyncio
import sqlite3
from typing import Any

from smartham.config import ollama_settings
from smartham.db import cache_explanation, get_cached_explanation
from smartham.ollama_tutor import explain_answer


def _question_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "level": row["level"],
        "section": row["section"],
        "stem": row["stem"],
        "choice_a": row["choice_a"],
        "choice_b": row["choice_b"],
        "choice_c": row["choice_c"],
        "choice_d": row["choice_d"],
        "correct": row["correct"],
    }


def study_context_for_question(conn: sqlite3.Connection, question: dict[str, Any]) -> str:
    section = question.get("section", "")
    row = conn.execute(
        """
        SELECT body FROM study_sections
        WHERE body LIKE ?
        ORDER BY page_number
        LIMIT 1
        """,
        (f"%{section}%",),
    ).fetchone()
    if row:
        return row["body"]
    row = conn.execute(
        "SELECT body FROM study_sections ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    return row["body"] if row else ""


class ExplanationManager:
    def __init__(self, conn: sqlite3.Connection, settings: dict[str, Any]) -> None:
        self.conn = conn
        self.settings = settings
        self._inflight: set[str] = set()
        self._lock = asyncio.Lock()

    def _ollama(self) -> dict[str, Any]:
        return ollama_settings(self.settings)

    def get_status(self, question_id: str) -> dict[str, Any]:
        ollama = self._ollama()
        cached = get_cached_explanation(self.conn, question_id, model=ollama["model"])
        if cached:
            return {
                "question_id": question_id,
                "ready": True,
                "explanation": cached,
                "status": "ready",
            }
        if question_id in self._inflight:
            return {
                "question_id": question_id,
                "ready": False,
                "status": "generating",
            }
        return {
            "question_id": question_id,
            "ready": False,
            "status": "missing",
        }

    async def prefetch(self, question_id: str) -> dict[str, Any]:
        status = self.get_status(question_id)
        if status["ready"] or status["status"] == "generating":
            return status

        row = self.conn.execute(
            "SELECT * FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        if not row:
            return {"question_id": question_id, "ready": False, "status": "not_found"}

        async with self._lock:
            if question_id in self._inflight:
                return {
                    "question_id": question_id,
                    "ready": False,
                    "status": "generating",
                }
            cached = get_cached_explanation(
                self.conn, question_id, model=self._ollama()["model"]
            )
            if cached:
                return {
                    "question_id": question_id,
                    "ready": True,
                    "explanation": cached,
                    "status": "ready",
                }
            self._inflight.add(question_id)

        asyncio.create_task(self._generate(question_id))
        return {
            "question_id": question_id,
            "ready": False,
            "status": "generating",
        }

    async def _generate(self, question_id: str) -> None:
        try:
            row = self.conn.execute(
                "SELECT * FROM questions WHERE id = ?", (question_id,)
            ).fetchone()
            if not row:
                return
            question = _question_row(row)
            ollama = self._ollama()
            study_context = study_context_for_question(self.conn, question)
            explanation, _err = await explain_answer(
                base_url=ollama["base_url"],
                model=ollama["model"],
                question=question,
                study_context=study_context,
                timeout=ollama["timeout"],
            )
            if explanation:
                cache_explanation(
                    self.conn,
                    question_id,
                    explanation,
                    model=ollama["model"],
                )
        finally:
            async with self._lock:
                self._inflight.discard(question_id)

    async def explanation_for_answer(self, question_id: str) -> tuple[str | None, str | None]:
        ollama = self._ollama()
        cached = get_cached_explanation(self.conn, question_id, model=ollama["model"])
        if cached:
            return cached, None
        if question_id in self._inflight:
            return None, "Explanation is still being generated — try again in a moment."
        row = self.conn.execute(
            "SELECT * FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        if not row:
            return None, "Question not found."
        question = _question_row(row)
        study_context = study_context_for_question(self.conn, question)
        explanation, err = await explain_answer(
            base_url=ollama["base_url"],
            model=ollama["model"],
            question=question,
            study_context=study_context,
            timeout=ollama["timeout"],
        )
        if explanation:
            cache_explanation(self.conn, question_id, explanation, model=ollama["model"])
            return explanation, None
        return None, err or "Could not generate explanation."