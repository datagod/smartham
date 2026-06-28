"""SmartHam CLI."""

from __future__ import annotations

import argparse
import sys

import uvicorn

from smartham.config import data_dir, load_settings, pdf_source_path
from smartham.db import connect, init_db, upsert_questions, upsert_study_sections
from smartham.pdf_parser import ingest_all
from smartham.web.server import create_app


def cmd_ingest(settings: dict) -> int:
    pdf_dir = pdf_source_path(settings)
    if not pdf_dir.is_dir():
        print(f"PDF source path not found: {pdf_dir}", file=sys.stderr)
        return 1

    result = ingest_all(pdf_dir)
    for err in result["errors"]:
        print(f"warning: {err}", file=sys.stderr)

    db_path = data_dir(settings) / "smartham.db"
    conn = connect(db_path)
    init_db(conn)
    q_count = upsert_questions(conn, result["questions"])
    s_count = upsert_study_sections(conn, result["study_sections"])
    conn.close()

    counts = result["counts"]
    print(
        f"Ingested {q_count} questions "
        f"(basic={counts['basic']}, advanced={counts['advanced']}) "
        f"and {s_count} study sections from {pdf_dir}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="SmartHam — Canadian ham radio study platform")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("serve", help="Start the web server")
    ingest_parser = sub.add_parser("ingest", help="Parse PDFs from pdf_source_path into SQLite")

    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    settings = load_settings()
    command = args.command or "serve"

    if command == "ingest":
        raise SystemExit(cmd_ingest(settings))

    host = args.host or str(settings.get("host", "127.0.0.1"))
    port = args.port or int(settings.get("port", 8091))
    app = create_app(settings)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()