"""Ollama-powered explanations and study summaries."""

from __future__ import annotations

from typing import Any

import httpx

EXPLAIN_SYSTEM = """You are a friendly Canadian amateur radio instructor.
Explain why the correct answer is right and briefly why common wrong answers fail.
Use plain language, 2-3 short paragraphs, no markdown headings.
Reference Canadian regulations (ISED/RAC) when relevant."""


SUMMARY_SYSTEM = """You are a Canadian amateur radio study coach.
Summarize the study material for exam preparation.
Use markdown with ## key points and short bullets.
Stay factual — only use the provided reference text."""


def build_explain_prompt(question: dict[str, Any], study_context: str = "") -> str:
    context = f"\n\nStudy reference:\n{study_context[:4000]}" if study_context else ""
    return f"""Question ID: {question['id']}
Level: {question['level']}

{question['stem']}

A) {question['choice_a']}
B) {question['choice_b']}
C) {question['choice_c']}
D) {question['choice_d']}

Correct answer: {question['correct']}
{context}

Explain this for a student preparing for the Canadian amateur radio exam."""


def build_summary_prompt(title: str, body: str) -> str:
    return f"""Study section: {title}

Reference text:
{body[:8000]}

Create a concise study summary for exam prep."""


async def ollama_chat(
    *,
    base_url: str,
    model: str,
    system: str,
    user: str,
    timeout: float = 120.0,
) -> tuple[str | None, str | None]:
    url = f"{base_url.rstrip('/')}/api/chat"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"num_predict": 1024},
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return None, f"Ollama timed out after {timeout:.0f}s"
    except httpx.HTTPStatusError as exc:
        return None, f"Ollama HTTP {exc.response.status_code}"
    except httpx.RequestError as exc:
        return None, f"Ollama unavailable: {exc}"

    if isinstance(data, dict) and data.get("error"):
        return None, str(data["error"])

    message = data.get("message") if isinstance(data, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not content:
        return None, "Empty response from Ollama"
    return str(content).strip(), None


async def explain_answer(
    *,
    base_url: str,
    model: str,
    question: dict[str, Any],
    study_context: str = "",
    timeout: float = 120.0,
) -> tuple[str | None, str | None]:
    return await ollama_chat(
        base_url=base_url,
        model=model,
        system=EXPLAIN_SYSTEM,
        user=build_explain_prompt(question, study_context),
        timeout=timeout,
    )


async def summarize_section(
    *,
    base_url: str,
    model: str,
    title: str,
    body: str,
    timeout: float = 120.0,
) -> tuple[str | None, str | None]:
    return await ollama_chat(
        base_url=base_url,
        model=model,
        system=SUMMARY_SYSTEM,
        user=build_summary_prompt(title, body),
        timeout=timeout,
    )