"""Initial application entry point."""

from pathlib import Path

from app.config import load_settings
from app.database import initialize_database


def main() -> None:
    settings = load_settings()
    database_path = settings.database_path
    if not database_path.is_absolute():
        database_path = Path(__file__).resolve().parent.parent / database_path
    initialize_database(database_path)
    print(f"Daily Verse foundation ready. Database: {database_path}")
    if not settings.bot_token:
        print("BOT_TOKEN is not set; Telegram polling is not configured yet.")


if __name__ == "__main__":
    main()
