from datetime import date, datetime, timedelta, timezone

from app.db import get_connection


def insert_usage_log(
    *,
    feature: str,
    model: str | None = None,
    characters: int | None = None,
    tokens: int | None = None,
    voice_id: str | None = None,
    cost_estimate: float | None = None,
    status: str = "success",
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO usage_log (timestamp, feature, model, characters, tokens, voice_id, cost_estimate, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                feature,
                model,
                characters,
                tokens,
                voice_id,
                cost_estimate,
                status,
            ),
        )
        return cursor.lastrowid


def _end_exclusive_bound(end: str) -> str:
    # 时间戳存储为 ISO 格式，按字符串比较即可；取次日作为排他上界以覆盖当天全部时刻。
    return (date.fromisoformat(end) + timedelta(days=1)).isoformat()


def _date_range_conditions(start: str | None, end: str | None) -> tuple[list[str], list[str]]:
    conditions: list[str] = []
    params: list[str] = []
    if start:
        conditions.append("timestamp >= ?")
        params.append(start)
    if end:
        conditions.append("timestamp < ?")
        params.append(_end_exclusive_bound(end))
    return conditions, params


def get_usage_summary(
    start: str | None = None, end: str | None = None, *, granularity: str = "day"
) -> dict:
    conditions, params = _date_range_conditions(start, end)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    period_expr = (
        "strftime('%Y-W%W', timestamp)" if granularity == "week" else "substr(timestamp, 1, 10)"
    )

    with get_connection() as conn:
        by_period = conn.execute(
            f"""
            SELECT {period_expr} AS period,
                   COALESCE(SUM(characters), 0) AS characters,
                   COALESCE(SUM(tokens), 0) AS tokens,
                   COALESCE(SUM(cost_estimate), 0) AS cost_estimate
            FROM usage_log
            {where_clause}
            GROUP BY period
            ORDER BY period
            """,
            params,
        ).fetchall()
        by_feature = conn.execute(
            f"""
            SELECT feature,
                   COUNT(*) AS count,
                   COALESCE(SUM(characters), 0) AS characters,
                   COALESCE(SUM(tokens), 0) AS tokens,
                   COALESCE(SUM(cost_estimate), 0) AS cost_estimate
            FROM usage_log
            {where_clause}
            GROUP BY feature
            ORDER BY feature
            """,
            params,
        ).fetchall()
        totals = conn.execute(
            f"""
            SELECT COALESCE(SUM(characters), 0) AS characters,
                   COALESCE(SUM(tokens), 0) AS tokens,
                   COALESCE(SUM(cost_estimate), 0) AS cost_estimate
            FROM usage_log
            {where_clause}
            """,
            params,
        ).fetchone()

    period_key = "by_week" if granularity == "week" else "by_day"
    return {
        period_key: [dict(row) for row in by_period],
        "by_feature": [dict(row) for row in by_feature],
        "totals": dict(totals),
        "granularity": granularity,
    }


def list_usage_logs(
    start: str | None = None,
    end: str | None = None,
    feature: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    conditions, params = _date_range_conditions(start, end)
    if feature:
        conditions.append("feature = ?")
        params.append(feature)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS c FROM usage_log {where_clause}", params).fetchone()["c"]
        offset = max(page - 1, 0) * page_size
        rows = conn.execute(
            f"""
            SELECT * FROM usage_log
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [dict(row) for row in rows],
    }
