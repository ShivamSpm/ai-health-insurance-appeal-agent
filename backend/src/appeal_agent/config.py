"""Config loading: backend/config.toml for settings, repo-root .env for secrets."""

import os
import tomllib
from functools import cache
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
DATA_DIR = REPO_ROOT / "data"


@cache
def settings() -> dict:
    load_dotenv(REPO_ROOT / ".env")
    with open(BACKEND_DIR / "config.toml", "rb") as f:
        return tomllib.load(f)


def model(role: str) -> str:
    """Model ID for a role in [models], overridable via APPEAL_MODEL_<ROLE>."""
    return os.environ.get(f"APPEAL_MODEL_{role.upper()}") or settings()["models"][role]
