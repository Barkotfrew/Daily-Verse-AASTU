"""Environment-backed application configuration."""

from dataclasses import dataclass
from datetime import time
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_path: Path
    mini_app_url: str = ""
    reminder_scheduler_enabled: bool = False
    reminder_time: time = time(hour=7)


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
    reminder_time_text = os.getenv("REMINDER_TIME", "07:00").strip()
    try:
        reminder_hour, reminder_minute = (int(part) for part in reminder_time_text.split(":"))
        reminder_time = time(hour=reminder_hour, minute=reminder_minute)
    except (ValueError, TypeError) as error:
        raise ValueError("REMINDER_TIME must use 24-hour HH:MM format, for example 07:00") from error
    if mini_app_url:
        from urllib.parse import urlsplit

        parsed_url = urlsplit(mini_app_url)
        if parsed_url.scheme != "https" or not parsed_url.netloc or parsed_url.query or parsed_url.fragment:
            raise ValueError("MINI_APP_URL must be an HTTPS site URL without query or fragment")
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        database_path=Path(os.getenv("DATABASE_PATH", "data/daily_verse.sqlite3")),
        mini_app_url=mini_app_url,
        reminder_scheduler_enabled=os.getenv("REMINDER_SCHEDULER_ENABLED", "false").strip().lower()
        in {"1", "true", "yes", "on"},
        reminder_time=reminder_time,
    )
