import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import get_app_dir
from app.db.schema import SCHEMA_STATEMENTS


def get_db_path() -> Path:
    return get_app_dir() / "voicemax.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
