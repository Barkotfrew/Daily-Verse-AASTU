"""Environment-backed application configuration."""

from dataclasses import dataclass
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_path: Path


def load_settings() -> Settings:
    """Load local .env values and return settings, without exposing secrets."""
    env_file = PROJECT_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        database_path=Path(os.getenv("DATABASE_PATH", "data/daily_verse.sqlite3")),
    )
