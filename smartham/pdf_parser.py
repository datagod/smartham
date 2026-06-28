"""Parse ISED amateur radio question bank PDFs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz

ID_RE = re.compile(r"^([BA]-\d{3}-\d{3}-\d{3})$")
ANS_RE = re.compile(r"^\(([ABCD])\)$")

QUESTION_FILES = {
    "basic": "amateur_basic_questions_en.pdf",
    "advanced": "amateur_advanced_questions_en.pdf",
}

REFERENCE_FILES = [
    "Reference Material for Amateur Radio Training Basic EN 2025.pdf",
    "Reference Material for Amateur Radio Exam Basic EN 2025.pdf",
    "Q_Codes_Decoded_Podcast_Book.pdf",
]


def _append_choice(choices: dict[str, str], letter: str, text: str) -> None:
    if not text:
        return
    prev = choices.get(letter, "")
    choices[letter] = f"{prev} {text}".strip() if prev else text


def _row_label_only(row: list[dict[str, str]]) -> bool:
    return any(it["kind"] == "label" for it in row) and not any(
        it["kind"] == "choice" for it in row
    )


def _extract_col_items(page: fitz.Page, col: int) -> list[dict[str, Any]]:
    if col == 0:
        ranges = {
            "id": (20, 35),
            "stem": (20, 100),
            "label": (20, 30),
            "choice": (35, 100),
            "ans": (95, 115),
        }
    else:
        ranges = {
            "id": (255, 270),
            "stem": (255, 340),
            "label": (255, 265),
            "choice": (268, 340),
            "ans": (330, 350),
        }

    raw: list[dict[str, Any]] = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            x0 = min(span["bbox"][0] for span in line["spans"])
            y0 = min(span["bbox"][1] for span in line["spans"])
            text = "".join(span["text"] for span in line["spans"]).strip()
            if not text:
                continue
            kind = None
            if ranges["id"][0] <= x0 <= ranges["id"][1] and ID_RE.match(text):
                kind = "id"
            elif ranges["ans"][0] <= x0 <= ranges["ans"][1] and ANS_RE.match(text):
                kind = "ans"
            elif ranges["label"][0] <= x0 <= ranges["label"][1] and text in "ABCD":
                kind = "label"
            elif ranges["choice"][0] <= x0 <= ranges["choice"][1]:
                kind = "choice"
            elif ranges["stem"][0] <= x0 <= ranges["stem"][1]:
                kind = "stem"
            if kind:
                raw.append({"y": y0, "text": text, "kind": kind})
    return raw


def _parse_col(items: list[dict[str, Any]], level: str) -> list[dict[str, Any]]:
    rows: dict[int, list[dict[str, Any]]] = {}
    for item in items:
        rows.setdefault(round(item["y"]), []).append(item)
    ys = sorted(rows)
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(ys):
        row = rows[ys[i]]
        ids = [it for it in row if it["kind"] == "id"]
        if not ids:
            i += 1
            continue

        qid = ids[0]["text"]
        ans_items = [it for it in row if it["kind"] == "ans"]
        correct = ANS_RE.match(ans_items[0]["text"]).group(1) if ans_items else None
        i += 1

        stem_parts: list[str] = []
        while i < len(ys):
            row = rows[ys[i]]
            if any(it["kind"] == "id" for it in row):
                break
            if any(it["kind"] == "label" for it in row):
                break
            if any(it["kind"] == "choice" for it in row):
                break
            stem_parts.extend(it["text"] for it in row if it["kind"] == "stem")
            i += 1
        stem = " ".join(stem_parts).strip()

        choices: dict[str, str] = {}
        current: str | None = None
        pending: list[str] = []
        all_labels_seen = False
        while i < len(ys):
            row = rows[ys[i]]
            if any(it["kind"] == "id" for it in row):
                break
            labels = [it for it in row if it["kind"] == "label"]
            parts = [it["text"] for it in row if it["kind"] == "choice"]
            if labels:
                letter = labels[0]["text"]
                chunk = " ".join(pending + parts).strip()
                pending = []
                _append_choice(choices, letter, chunk)
                current = letter
                if len(choices) == 4:
                    all_labels_seen = True
            elif parts:
                if all_labels_seen:
                    if current:
                        _append_choice(choices, current, " ".join(parts))
                else:
                    next_label_only = i + 1 < len(ys) and _row_label_only(rows[ys[i + 1]])
                    if next_label_only:
                        pending.extend(parts)
                    elif current:
                        _append_choice(choices, current, " ".join(parts))
                    else:
                        pending.extend(parts)
            i += 1

        if correct and stem and len(choices) == 4 and all(choices.get(x) for x in "ABCD"):
            out.append(
                {
                    "id": qid,
                    "level": level,
                    "section": "-".join(qid.split("-")[:3]),
                    "stem": stem,
                    "a": choices["A"],
                    "b": choices["B"],
                    "c": choices["C"],
                    "d": choices["D"],
                    "correct": correct,
                }
            )
    return out


def parse_question_bank(path: Path, level: str) -> list[dict[str, Any]]:
    doc = fitz.open(path)
    all_q: dict[str, dict[str, Any]] = {}
    for page in doc:
        for col in (0, 1):
            for question in _parse_col(_extract_col_items(page, col), level):
                all_q[question["id"]] = question
    doc.close()
    return list(all_q.values())


def parse_reference_pdf(path: Path) -> list[dict[str, Any]]:
    doc = fitz.open(path)
    sections: list[dict[str, Any]] = []
    source = path.name
    for page_no, page in enumerate(doc, start=1):
        body = page.get_text().strip()
        if not body or len(body) < 40:
            continue
        title = body.splitlines()[0].strip()[:120] if body.splitlines() else source
        sections.append(
            {
                "source_file": source,
                "page_number": page_no,
                "title": title,
                "body": body[:12000],
            }
        )
    doc.close()
    return sections


def ingest_all(pdf_dir: Path) -> dict[str, Any]:
    questions: list[dict[str, Any]] = []
    study_sections: list[dict[str, Any]] = []
    errors: list[str] = []

    for level, filename in QUESTION_FILES.items():
        path = pdf_dir / filename
        if not path.is_file():
            errors.append(f"Missing question bank: {path}")
            continue
        parsed = parse_question_bank(path, level)
        questions.extend(parsed)

    for filename in REFERENCE_FILES:
        path = pdf_dir / filename
        if not path.is_file():
            errors.append(f"Missing reference PDF: {path}")
            continue
        study_sections.extend(parse_reference_pdf(path))

    return {
        "questions": questions,
        "study_sections": study_sections,
        "errors": errors,
        "counts": {
            "basic": sum(1 for q in questions if q["level"] == "basic"),
            "advanced": sum(1 for q in questions if q["level"] == "advanced"),
            "study_sections": len(study_sections),
        },
    }