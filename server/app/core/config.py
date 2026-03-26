import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


def get_database_url() -> str | None:
    url = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
    if not url:
        return None
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url

