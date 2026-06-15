from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def load_env() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    candidate_paths = [
        repo_root / ".env",
        repo_root / ".env.local",
        Path(r"C:\Users\elias\Desktop\sosovalue community backend codes\.env"),
    ]
    for path in candidate_paths:
        if path.exists():
            load_dotenv(path, override=False)


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Add it to the repo .env file or the backend codes .env file."
        )
    return value
