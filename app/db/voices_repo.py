from datetime import datetime, timezone

from app.db import get_connection


def insert_voice(
    *,
    voice_id: str,
    type: str,
    name: str | None = None,
    note: str | None = None,
    sample_path: str | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO voices (voice_id, type, name, note, sample_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (voice_id, type, name, note, sample_path, datetime.now(timezone.utc).isoformat()),
        )


def list_voices(type: str | None = None) -> list[dict]:
    with get_connection() as conn:
        if type is not None:
            rows = conn.execute(
                "SELECT * FROM voices WHERE type = ? ORDER BY created_at DESC", (type,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM voices ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def get_voice(voice_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM voices WHERE voice_id = ?", (voice_id,)).fetchone()
        return dict(row) if row else None


def update_note(voice_id: str, note: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("UPDATE voices SET note = ? WHERE voice_id = ?", (note, voice_id))
        return cursor.rowcount > 0


def delete_voice(voice_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM voices WHERE voice_id = ?", (voice_id,))
        return cursor.rowcount > 0
