"""
Cloud entrypoint that exposes the same production chatbot app used in 02-docker.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "02-docker" / "production" / "main.py"
SPEC = importlib.util.spec_from_file_location("shared_cloud_app", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load app module from {MODULE_PATH}")

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
app = MODULE.app
