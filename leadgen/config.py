from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is in requirements.txt
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    search_provider: str = os.getenv("SEARCH_PROVIDER", "manual").strip().lower()
    brave_search_api_key: str = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    bing_search_api_key: str = os.getenv("BING_SEARCH_API_KEY", "").strip()
    serpapi_api_key: str = os.getenv("SERPAPI_API_KEY", os.getenv("SERPAPI_KEY", "")).strip()

    user_agent: str = os.getenv(
        "LEADGEN_USER_AGENT",
        "CargroLeadGenResearchBot/0.1 (+manual lead research; no automated outreach)",
    ).strip()
    request_timeout: float = float(os.getenv("LEADGEN_TIMEOUT", "12"))
    rate_limit_seconds: float = float(os.getenv("LEADGEN_RATE_LIMIT_SECONDS", "1.5"))
    max_pages_per_domain: int = int(os.getenv("LEADGEN_MAX_PAGES_PER_DOMAIN", "8"))
    max_crawl_depth: int = int(os.getenv("LEADGEN_MAX_CRAWL_DEPTH", "2"))
    respect_robots: bool = _env_bool("LEADGEN_RESPECT_ROBOTS", True)
    enable_playwright: bool = _env_bool("LEADGEN_ENABLE_PLAYWRIGHT", False)


DEFAULT_STATUS_OPTIONS = [
    "New",
    "Reviewed",
    "Interesting",
    "Contacted",
    "Follow-up",
    "Not relevant",
    "Won",
    "Lost",
]
