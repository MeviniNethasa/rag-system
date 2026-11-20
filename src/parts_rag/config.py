"""Settings loaded from .env. Values are read only when asked for, so offline
code (parser, chunker, tests) never needs keys."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = PROJECT_ROOT / "data" / "front_wheel_assembly.txt"

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5"

load_dotenv(PROJECT_ROOT / ".env")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing {name}. Copy .env.example to .env and fill it in."
        )
    return value


def supabase_url() -> str:
    """Base project URL. Accepts a pasted REST URL like
    https://<ref>.supabase.co/rest/v1/ and trims it to https://<ref>.supabase.co"""
    url = require_env("SUPABASE_URL").strip().rstrip("/")
    for suffix in ("/rest/v1",):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    return url


def claude_model() -> str:
    return os.getenv("CLAUDE_MODEL") or DEFAULT_CLAUDE_MODEL
