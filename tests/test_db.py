from app.db import get_connection, init_db
from app.db.usage_repo import insert_usage_log


def test_init_db_creates_all_tables(db):
    with get_connection() as conn:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

    assert {"usage_log", "voices", "projects"}.issubset(tables)


def test_insert_usage_log_stores_row(db):
    row_id = insert_usage_log(feature="synthesize", model="speech-2.8-hd", characters=120, voice_id="voice-1")

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM usage_log WHERE id = ?", (row_id,)).fetchone()

    assert row["feature"] == "synthesize"
    assert row["characters"] == 120
    assert row["status"] == "success"


def test_insert_usage_log_defaults_status_success(db):
    insert_usage_log(feature="polish", model="abab-chat")

    with get_connection() as conn:
        row = conn.execute("SELECT status FROM usage_log ORDER BY id DESC LIMIT 1").fetchone()

    assert row["status"] == "success"


def test_init_db_is_idempotent(db):
    init_db()
    init_db()

    with get_connection() as conn:
        tables = [
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usage_log'")
        ]

    assert tables == ["usage_log"]
