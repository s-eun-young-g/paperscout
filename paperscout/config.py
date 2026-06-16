"""Runtime configuration. Override with FENCESTATS-style env vars (PAPERSCOUT_*)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

__version__ = "0.1.0"

DEFAULT_CACHE_DIR = Path(
    os.environ.get("PAPERSCOUT_CACHE_DIR", Path.home() / ".cache" / "paperscout")
)

# OpenAlex / NCBI etc. reward a contact email with the faster "polite pool".
MAILTO = os.environ.get("PAPERSCOUT_MAILTO", "")

USER_AGENT = os.environ.get(
    "PAPERSCOUT_USER_AGENT",
    f"paperscout/{__version__} (research literature tool; "
    "+https://github.com/s-eun-young-g/paperscout)"
    + (f" mailto:{MAILTO}" if MAILTO else ""),
)


@dataclass(frozen=True)
class Settings:
    cache_dir: Path = DEFAULT_CACHE_DIR
    user_agent: str = USER_AGENT
    mailto: str = MAILTO
    min_request_interval: float = float(os.environ.get("PAPERSCOUT_RATE", "0.4"))
    cache_ttl_hours: float = float(os.environ.get("PAPERSCOUT_TTL_HOURS", "168"))  # 1 week
    request_timeout: float = float(os.environ.get("PAPERSCOUT_TIMEOUT", "45"))
    max_retries: int = int(os.environ.get("PAPERSCOUT_MAX_RETRIES", "4"))
    retry_backoff: float = float(os.environ.get("PAPERSCOUT_RETRY_BACKOFF", "1.0"))  # base secs, doubled per attempt
    anthropic_key: str | None = os.environ.get("ANTHROPIC_API_KEY") or None

    @property
    def db_path(self) -> Path:
        return self.cache_dir / "cache.sqlite"


settings = Settings()
