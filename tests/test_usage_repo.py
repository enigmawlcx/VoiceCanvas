from app.db import get_connection
from app.db.usage_repo import get_usage_summary, list_usage_logs


def _insert_raw(*, timestamp, feature, characters=0, tokens=0, voice_id=None, status="success"):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO usage_log (timestamp, feature, model, characters, tokens, voice_id, cost_estimate, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, feature, "speech-2.8-hd", characters, tokens, voice_id, None, status),
        )


def test_get_usage_summary_groups_by_day_and_feature(db):
    _insert_raw(timestamp="2026-07-01T10:00:00+00:00", feature="synthesize", characters=100)
    _insert_raw(timestamp="2026-07-01T12:00:00+00:00", feature="synthesize", characters=50)
    _insert_raw(timestamp="2026-07-02T08:00:00+00:00", feature="polish", tokens=30)

    summary = get_usage_summary()

    by_day = {row["period"]: row for row in summary["by_day"]}
    assert by_day["2026-07-01"]["characters"] == 150
    assert by_day["2026-07-02"]["tokens"] == 30

    by_feature = {row["feature"]: row for row in summary["by_feature"]}
    assert by_feature["synthesize"]["count"] == 2
    assert by_feature["synthesize"]["characters"] == 150
    assert by_feature["polish"]["count"] == 1


def test_get_usage_summary_filters_by_date_range(db):
    _insert_raw(timestamp="2026-07-01T10:00:00+00:00", feature="synthesize", characters=10)
    _insert_raw(timestamp="2026-07-05T10:00:00+00:00", feature="synthesize", characters=20)
    _insert_raw(timestamp="2026-07-10T10:00:00+00:00", feature="synthesize", characters=40)

    summary = get_usage_summary(start="2026-07-02", end="2026-07-06")

    assert [row["period"] for row in summary["by_day"]] == ["2026-07-05"]


def test_get_usage_summary_end_date_is_inclusive_of_whole_day(db):
    _insert_raw(timestamp="2026-07-05T23:59:59.999999+00:00", feature="synthesize", characters=5)

    summary = get_usage_summary(start="2026-07-05", end="2026-07-05")

    assert summary["by_day"][0]["characters"] == 5


def test_list_usage_logs_paginates_and_orders_desc(db):
    for i in range(3):
        _insert_raw(timestamp=f"2026-07-0{i + 1}T00:00:00+00:00", feature="synthesize", characters=i)

    page1 = list_usage_logs(page=1, page_size=2)
    page2 = list_usage_logs(page=2, page_size=2)

    assert page1["total"] == 3
    assert len(page1["items"]) == 2
    assert page1["items"][0]["timestamp"].startswith("2026-07-03")
    assert len(page2["items"]) == 1


def test_get_usage_summary_groups_by_week(db):
    _insert_raw(timestamp="2026-07-01T10:00:00+00:00", feature="synthesize", characters=10)
    _insert_raw(timestamp="2026-07-08T10:00:00+00:00", feature="synthesize", characters=20)

    summary = get_usage_summary(granularity="week")

    assert summary["granularity"] == "week"
    assert len(summary["by_week"]) >= 1
    _insert_raw(timestamp="2026-07-01T00:00:00+00:00", feature="synthesize")
    _insert_raw(timestamp="2026-07-01T01:00:00+00:00", feature="polish")

    result = list_usage_logs(feature="polish")

    assert result["total"] == 1
    assert result["items"][0]["feature"] == "polish"
