"""FastAPI web server for SmartHam."""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Query, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from smartham import __version__
from smartham.awards import awards_status, check_awards
from smartham.sections import section_description
from smartham.config import data_dir, load_settings, ollama_settings, pdf_source_path
from smartham.db import (
    cache_summary,
    connect,
    explanation_cache_stats,
    get_cached_summary,
    get_streak,
    init_db,
    question_progress,
    record_attempt,
    upsert_questions,
    upsert_study_sections,
)
from smartham.explanations import ExplanationManager
from smartham.ollama_tutor import summarize_section
from smartham.pdf_parser import ingest_all

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(WEB_DIR / "templates"))

MOCK_EXAM_SIZES = {"basic": 100, "advanced": 50}
PASS_MARK = 0.70


class AppState:
    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.db_path = data_dir(settings) / "smartham.db"
        self.conn = connect(self.db_path)
        init_db(self.conn)
        self.explanations = ExplanationManager(self.conn, settings)


def _question_row(row: Any) -> dict[str, Any]:
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


def _stats(conn: Any) -> dict[str, Any]:
    total_q = conn.execute("SELECT COUNT(*) AS n FROM questions").fetchone()["n"]
    attempts = conn.execute("SELECT COUNT(*) AS n FROM quiz_attempts").fetchone()["n"]
    correct = conn.execute(
        "SELECT COUNT(*) AS n FROM quiz_attempts WHERE is_correct = 1"
    ).fetchone()["n"]
    accuracy = (correct / attempts) if attempts else 0.0
    sections = conn.execute(
        """
        SELECT section, level,
               SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct,
               COUNT(*) AS total
        FROM quiz_attempts
        WHERE mode = 'practice'
        GROUP BY section, level
        HAVING total > 0
        ORDER BY total DESC
        LIMIT 12
        """
    ).fetchall()
    return {
        "total_questions": total_q,
        "attempts": attempts,
        "correct": correct,
        "accuracy": round(accuracy, 3),
        "streak": get_streak(conn),
        **explanation_cache_stats(conn),
        "sections": [
            {
                "section": r["section"],
                "description": section_description(r["section"]),
                "level": r["level"],
                "correct": r["correct"],
                "total": r["total"],
                "accuracy": round(r["correct"] / r["total"], 3),
            }
            for r in sections
        ],
    }


def _progress_groups(conn: Any, level: str | None = None) -> dict[str, Any]:
    items = question_progress(conn, level=level)
    groups: dict[str, dict[str, Any]] = {}
    mastered = 0
    for item in items:
        section = item["section"]
        if section not in groups:
            groups[section] = {
                "section": section,
                "level": item["level"],
                "description": section_description(section),
                "questions": [],
                "mastered": 0,
                "total": 0,
            }
        group = groups[section]
        group["questions"].append(item)
        group["total"] += 1
        if item["mastered"]:
            group["mastered"] += 1
            mastered += 1
    ordered = sorted(groups.values(), key=lambda g: g["section"])
    return {
        "level": level,
        "total": len(items),
        "mastered": mastered,
        "groups": ordered,
    }


def create_app(settings: dict[str, Any] | None = None) -> FastAPI:
    settings = settings or load_settings()
    state = AppState(settings)
    app = FastAPI(title="SmartHam", version=__version__)
    app.state.smartham = state

    static_dir = WEB_DIR / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def nav_context(request: Request, page: str) -> dict[str, Any]:
        return {
            "request": request,
            "page": page,
            "version": __version__,
            "stats": _stats(state.conn),
        }

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        ctx = nav_context(request, "dashboard")
        ctx["awards"] = awards_status(state.conn)
        return TEMPLATES.TemplateResponse(request, "index.html", ctx)

    @app.get("/quiz", response_class=HTMLResponse)
    async def quiz_page(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "quiz.html", nav_context(request, "quiz"))

    @app.get("/mock-exam", response_class=HTMLResponse)
    async def mock_exam_page(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "mock_exam.html", nav_context(request, "mock"))

    @app.get("/study", response_class=HTMLResponse)
    async def study_page(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "study.html", nav_context(request, "study"))

    @app.get("/awards", response_class=HTMLResponse)
    async def awards_page(request: Request) -> HTMLResponse:
        ctx = nav_context(request, "awards")
        ctx["awards"] = awards_status(state.conn)
        return TEMPLATES.TemplateResponse(request, "awards.html", ctx)

    @app.get("/progress", response_class=HTMLResponse)
    async def progress_page(
        request: Request,
        level: str | None = Query(None),
    ) -> HTMLResponse:
        level_filter = level.strip().lower() if level else None
        if level_filter not in (None, "basic", "advanced"):
            level_filter = None
        ctx = nav_context(request, "progress")
        ctx["progress"] = _progress_groups(state.conn, level_filter)
        ctx["level_filter"] = level_filter
        return TEMPLATES.TemplateResponse(request, "progress.html", ctx)

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request) -> HTMLResponse:
        ctx = nav_context(request, "settings")
        ctx["pdf_path"] = str(pdf_source_path(settings))
        ctx["ollama"] = ollama_settings(settings)
        return TEMPLATES.TemplateResponse(request, "settings.html", ctx)

    @app.post("/api/ingest")
    async def api_ingest() -> JSONResponse:
        pdf_dir = pdf_source_path(settings)
        result = ingest_all(pdf_dir)
        q_count = upsert_questions(state.conn, result["questions"])
        s_count = upsert_study_sections(state.conn, result["study_sections"])
        return JSONResponse(
            {
                "ok": True,
                "questions": q_count,
                "study_sections": s_count,
                "counts": result["counts"],
                "errors": result["errors"],
            }
        )

    @app.get("/api/stats")
    async def api_stats() -> JSONResponse:
        return JSONResponse(_stats(state.conn))

    @app.get("/api/progress")
    async def api_progress(level: str | None = Query(None)) -> JSONResponse:
        level_filter = level.strip().lower() if level else None
        if level_filter not in (None, "basic", "advanced"):
            level_filter = None
        return JSONResponse(_progress_groups(state.conn, level_filter))

    @app.get("/api/questions")
    async def api_questions(
        level: str | None = Query(None),
        section: str | None = Query(None),
        limit: int = Query(1, ge=1, le=50),
    ) -> JSONResponse:
        clauses = []
        params: list[Any] = []
        if level:
            clauses.append("level = ?")
            params.append(level)
        if section:
            clauses.append("section = ?")
            params.append(section)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = state.conn.execute(
            f"SELECT * FROM questions {where} ORDER BY RANDOM() LIMIT ?",
            (*params, limit),
        ).fetchall()
        items = []
        for row in rows:
            q = _question_row(row)
            q.pop("correct", None)
            items.append(q)
        return JSONResponse({"questions": items})

    @app.post("/api/quiz/prefetch-explanation")
    async def api_prefetch_explanation(payload: dict = Body(...)) -> JSONResponse:
        question_id = str(payload.get("question_id", "")).strip()
        if not question_id:
            return JSONResponse({"error": "question_id required"}, status_code=400)
        result = await state.explanations.prefetch(question_id)
        if result.get("status") == "not_found":
            return JSONResponse({"error": "Question not found"}, status_code=404)
        return JSONResponse(result)

    @app.get("/api/quiz/explanation/{question_id}")
    async def api_get_explanation(question_id: str) -> JSONResponse:
        return JSONResponse(state.explanations.get_status(question_id))

    @app.post("/api/quiz/answer")
    async def api_quiz_answer(payload: dict = Body(...)) -> JSONResponse:
        question_id = str(payload.get("question_id", "")).strip()
        chosen = str(payload.get("chosen", "")).strip().upper()
        mode = str(payload.get("mode", "practice")).strip() or "practice"
        if chosen not in {"A", "B", "C", "D"}:
            return JSONResponse({"error": "Invalid choice"}, status_code=400)

        row = state.conn.execute(
            "SELECT * FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        if not row:
            return JSONResponse({"error": "Question not found"}, status_code=404)

        question = _question_row(row)
        is_correct = chosen == question["correct"]
        record_attempt(
            state.conn,
            question_id=question_id,
            level=question["level"],
            section=question["section"],
            chosen=chosen,
            correct=question["correct"],
            is_correct=is_correct,
            mode=mode,
        )
        newly_earned = check_awards(state.conn, is_correct=is_correct)

        explanation, explanation_error = await state.explanations.explanation_for_answer(
            question_id
        )

        return JSONResponse(
            {
                "correct": is_correct,
                "correct_choice": question["correct"],
                "explanation": explanation,
                "explanation_error": explanation_error,
                "streak": get_streak(state.conn),
                "new_awards": newly_earned,
                "stats": _stats(state.conn),
            }
        )

    @app.get("/api/awards")
    async def api_awards() -> JSONResponse:
        return JSONResponse({"awards": awards_status(state.conn)})

    @app.get("/api/study/sections")
    async def api_study_sections() -> JSONResponse:
        rows = state.conn.execute(
            """
            SELECT id, source_file, page_number, title,
                   substr(body, 1, 240) AS preview
            FROM study_sections
            ORDER BY source_file, page_number
            """
        ).fetchall()
        return JSONResponse(
            {
                "sections": [
                    {
                        "id": r["id"],
                        "source_file": r["source_file"],
                        "page_number": r["page_number"],
                        "title": r["title"],
                        "preview": r["preview"],
                    }
                    for r in rows
                ]
            }
        )

    @app.get("/api/study/section/{section_id}")
    async def api_study_section(section_id: int) -> JSONResponse:
        row = state.conn.execute(
            "SELECT * FROM study_sections WHERE id = ?", (section_id,)
        ).fetchone()
        if not row:
            return JSONResponse({"error": "Not found"}, status_code=404)
        return JSONResponse(
            {
                "id": row["id"],
                "source_file": row["source_file"],
                "page_number": row["page_number"],
                "title": row["title"],
                "body": row["body"],
            }
        )

    @app.post("/api/study/summarize")
    async def api_study_summarize(payload: dict = Body(...)) -> JSONResponse:
        section_id = int(payload.get("section_id", 0))
        row = state.conn.execute(
            "SELECT * FROM study_sections WHERE id = ?", (section_id,)
        ).fetchone()
        if not row:
            return JSONResponse({"error": "Not found"}, status_code=404)

        cache_key = f"section:{section_id}"
        cached = get_cached_summary(state.conn, cache_key)
        if cached:
            return JSONResponse({"summary": cached, "cached": True})

        ollama = ollama_settings(settings)
        summary, err = await summarize_section(
            base_url=ollama["base_url"],
            model=ollama["model"],
            title=row["title"] or row["source_file"],
            body=row["body"],
            timeout=ollama["timeout"],
        )
        if err:
            return JSONResponse({"error": err}, status_code=502)
        cache_summary(state.conn, cache_key, summary or "")
        return JSONResponse({"summary": summary, "cached": False})

    @app.post("/api/mock-exam/start")
    async def api_mock_start(payload: dict = Body(...)) -> JSONResponse:
        level = str(payload.get("level", "basic")).strip().lower()
        if level not in MOCK_EXAM_SIZES:
            return JSONResponse({"error": "Invalid level"}, status_code=400)
        size = MOCK_EXAM_SIZES[level]
        rows = state.conn.execute(
            "SELECT id FROM questions WHERE level = ? ORDER BY RANDOM() LIMIT ?",
            (level, size),
        ).fetchall()
        if len(rows) < size:
            return JSONResponse(
                {"error": f"Not enough {level} questions ingested ({len(rows)}/{size})"},
                status_code=400,
            )
        ids = [r["id"] for r in rows]
        cur = state.conn.execute(
            """
            INSERT INTO mock_exams (level, question_ids, started_at)
            VALUES (?, ?, ?)
            """,
            (level, json.dumps(ids), time.time()),
        )
        state.conn.commit()
        exam_id = cur.lastrowid
        questions = state.conn.execute(
            f"""
            SELECT id, level, section, stem, choice_a, choice_b, choice_c, choice_d
            FROM questions WHERE id IN ({','.join('?' * len(ids))})
            """,
            ids,
        ).fetchall()
        random.shuffle(questions)
        return JSONResponse(
            {
                "exam_id": exam_id,
                "level": level,
                "pass_mark": PASS_MARK,
                "time_limit_minutes": 120 if level == "basic" else 90,
                "questions": [
                    {
                        "id": q["id"],
                        "section": q["section"],
                        "stem": q["stem"],
                        "choice_a": q["choice_a"],
                        "choice_b": q["choice_b"],
                        "choice_c": q["choice_c"],
                        "choice_d": q["choice_d"],
                    }
                    for q in questions
                ],
            }
        )

    @app.post("/api/mock-exam/submit")
    async def api_mock_submit(payload: dict = Body(...)) -> JSONResponse:
        exam_id = int(payload.get("exam_id", 0))
        answers = payload.get("answers") if isinstance(payload.get("answers"), dict) else {}
        row = state.conn.execute(
            "SELECT * FROM mock_exams WHERE id = ?", (exam_id,)
        ).fetchone()
        if not row:
            return JSONResponse({"error": "Exam not found"}, status_code=404)

        ids = json.loads(row["question_ids"])
        correct_count = 0
        results = []
        for qid in ids:
            qrow = state.conn.execute(
                "SELECT * FROM questions WHERE id = ?", (qid,)
            ).fetchone()
            if not qrow:
                continue
            chosen = str(answers.get(qid, "")).strip().upper()
            is_correct = chosen == qrow["correct"]
            if is_correct:
                correct_count += 1
            record_attempt(
                state.conn,
                question_id=qid,
                level=qrow["level"],
                section=qrow["section"],
                chosen=chosen or "?",
                correct=qrow["correct"],
                is_correct=is_correct,
                mode="mock",
            )
            results.append(
                {
                    "id": qid,
                    "chosen": chosen,
                    "correct": qrow["correct"],
                    "is_correct": is_correct,
                }
            )

        score = correct_count / len(ids) if ids else 0.0
        passed = score >= PASS_MARK
        state.conn.execute(
            """
            UPDATE mock_exams
            SET answers = ?, score = ?, passed = ?, finished_at = ?
            WHERE id = ?
            """,
            (json.dumps(answers), score, int(passed), time.time(), exam_id),
        )
        state.conn.commit()

        mock_result = {"passed": passed, "level": row["level"], "score": score}
        new_awards = check_awards(state.conn, is_correct=False, mock_result=mock_result)

        return JSONResponse(
            {
                "exam_id": exam_id,
                "level": row["level"],
                "score": round(score, 3),
                "percent": round(score * 100, 1),
                "correct": correct_count,
                "total": len(ids),
                "passed": passed,
                "pass_mark": PASS_MARK,
                "results": results,
                "new_awards": new_awards,
            }
        )

    return app