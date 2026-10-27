"""Shared constants, default file locations, and credential loading."""

from __future__ import annotations

import os
from pathlib import Path

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# Public Azure APIM subscription key embedded in window.coopSettings.serviceAccess
APIM_SUBSCRIPTION_KEY = "3becf0ce306f41a1ae94077c16798187"
DEFAULT_STORE_ID = "030500"
DEFAULT_CUSTOMER_GROUPS = "CUSTOMER_PRIVATE,CUSTOMER_MEDMERA"

# Skill root directory (contains `coop`, `coop_cli/`, and optional `.env`).
BASE_DIR = Path(__file__).resolve().parent.parent

# Runtime state and caches live globally under ~/.cache/coop (or $XDG_CACHE_HOME/coop).
CACHE_DIR = (
    Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "coop"
)
CONFIG_DIR = (
    Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "coop"
)

DEFAULT_ENV_FILE = BASE_DIR / ".env"
DEFAULT_COOKIE_FILE = CACHE_DIR / "cookies.txt"
DEFAULT_SESSION_CACHE = CACHE_DIR / "session_cache.json"
DEFAULT_ORDERS_CACHE = CACHE_DIR / "orders_cache.json"


def load_env(env_path: Path) -> None:
    """Load key=value pairs from a .env file into os.environ if not already set."""
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def get_credentials(env_file: Path = DEFAULT_ENV_FILE) -> tuple[str | None, str | None]:
    """Return (COOP_USERNAME, COOP_PASSWORD) from the environment or .env files."""
    for candidate in (env_file, CONFIG_DIR / ".env", CACHE_DIR / ".env"):
        load_env(candidate)
    return os.environ.get("COOP_USERNAME"), os.environ.get("COOP_PASSWORD")

