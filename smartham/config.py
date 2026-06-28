"""Load SmartHam YAML config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _config_paths() -> list[Path]:
    return [
        ROOT / "config.yaml",
        Path.home() / ".config" / "smartham" / "config.yaml",
    ]


def load_settings() -> dict[str, Any]:
    settings: dict[str, Any] = {}
    for path in _config_paths():
        if path.is_file():
            with path.open(encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            if isinstance(loaded, dict):
                settings = loaded
            break
    return settings


def data_dir(settings: dict[str, Any] | None = None) -> Path:
    s = settings or load_settings()
    raw = str(s.get("data_dir", "data")).strip() or "data"
    path = Path(raw)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def pdf_source_path(settings: dict[str, Any] | None = None) -> Path:
    s = settings or load_settings()
    raw = str(s.get("pdf_source_path", "")).strip()
    if not raw:
        return ROOT / "hamradio"
    path = Path(raw)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return path


def ollama_settings(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    s = settings or load_settings()
    raw = s.get("ollama") if isinstance(s.get("ollama"), dict) else {}
    return {
        "base_url": str((raw or {}).get("base_url", "http://127.0.0.1:11434")).rstrip("/"),
        "model": str((raw or {}).get("model", "llama3.2")),
        "timeout": float((raw or {}).get("timeout", 120)),
    }