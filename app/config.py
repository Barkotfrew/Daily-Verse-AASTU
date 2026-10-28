"""Environment-backed application configuration."""

from dataclasses import dataclass
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_path: Path
    mini_app_url: str = ""


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
    mini_app_url = os.getenv("MINI_APP_URL", "").strip().rstrip("/")
    if mini_app_url:
        from urllib.parse import urlsplit

        parsed_url = urlsplit(mini_app_url)
        if parsed_url.scheme != "https" or not parsed_url.netloc or parsed_url.query or parsed_url.fragment:
            raise ValueError("MINI_APP_URL must be an HTTPS site URL without query or fragment")
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        database_path=Path(os.getenv("DATABASE_PATH", "data/daily_verse.sqlite3")),
        mini_app_url=mini_app_url,
    )
