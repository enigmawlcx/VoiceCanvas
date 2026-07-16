from datetime import datetime, timezone

from app.db import get_connection


def insert_project(*, title: str, source_text: str, annotated_text: str | None = None) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO projects (title, source_text, annotated_text, updated_at) VALUES (?, ?, ?, ?)",
            (title, source_text, annotated_text, datetime.now(timezone.utc).isoformat()),
        )
        return cursor.lastrowid


def list_projects() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [dict(row) for row in rows]


def get_project(project_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None


def update_project(
    project_id: int,
    *,
    title: str | None = None,
    source_text: str | None = None,
    annotated_text: str | None = None,
) -> bool:
    existing = get_project(project_id)
    if existing is None:
        return False

    with get_connection() as conn:
        conn.execute(
            "UPDATE projects SET title = ?, source_text = ?, annotated_text = ?, updated_at = ? WHERE id = ?",
            (
                title if title is not None else existing["title"],
                source_text if source_text is not None else existing["source_text"],
                annotated_text if annotated_text is not None else existing["annotated_text"],
                datetime.now(timezone.utc).isoformat(),
                project_id,
            ),
        )
        return True


def delete_project(project_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return cursor.rowcount > 0
