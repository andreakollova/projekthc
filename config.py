from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    BASE_URL: str = "https://www.hckosice.sk"

    # Stránky
    NOVINKY_URL: str = "https://www.hckosice.sk/novinky"
    ZAPASY_URL: str = "https://www.hckosice.sk/a-muzstvo/zapasy"  # page
    ROBOTS_URL: str = "https://www.hckosice.sk/robots.txt"

    # API (zápasy sa načítavajú cez XHR)
    ZAPASY_API_URL: str = "https://www.hckosice.sk/api/matches?league=extraliga&season=2025-2026"

    # Low footprint
    MIN_SLEEP: float = 2.0
    MAX_SLEEP: float = 6.0
    DETAIL_EXTRA_SLEEP_MIN: float = 3.0
    DETAIL_EXTRA_SLEEP_MAX: float = 8.0

    TIMEOUT: float = 20.0
    MAX_RETRIES: int = 4
    BACKOFF_BASE: float = 1.7
    BACKOFF_JITTER_MIN: float = 0.2
    BACKOFF_JITTER_MAX: float = 1.0

    # Incremental limits
    NOVINKY_LIMIT: int = 30
    MAX_REQUESTS_PER_RUN: int = 120

    # Identification (uprav si kontakt)
    USER_AGENT: str = "HCKosiceLowFootprintScraper/1.0 (kontakt: example@email.com)"

    # Paths
    PROJECT_ROOT: Path = Path(__file__).resolve().parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    LOG_DIR: Path = PROJECT_ROOT / "logs"

    # (už nepoužívaš pri Storage() na Postgres, ale nechávam ako fallback)
    DB_PATH: Path = DATA_DIR / "hckosice.sqlite3"
