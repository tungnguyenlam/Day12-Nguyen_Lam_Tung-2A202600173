"""Resolve shared UI asset paths for the final 06 app."""
from __future__ import annotations

from pathlib import Path


def resolve_chat_ui(current_file: str) -> Path:
    current_path = Path(current_file).resolve()
    candidates: list[Path] = []
    seen: set[Path] = set()

    for base in [current_path.parent, *current_path.parents]:
        candidate = base / "utils" / "chat_ui.html"
        if candidate not in seen:
            candidates.append(candidate)
            seen.add(candidate)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"chat_ui.html not found relative to {current_path}")
