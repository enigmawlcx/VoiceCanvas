import pytest
from fastapi.testclient import TestClient

from app.db import get_connection
from app.main import create_app


@pytest.fixture
def client(db):
    return TestClient(create_app())


def _insert_raw(*, timestamp, feature, characters=0, tokens=0):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO usage_log (timestamp, feature, model, characters, tokens, voice_id, cost_estimate, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, feature, "speech-2.8-hd", characters, tokens, None, None, "success"),
        )


def test_summary_endpoint_returns_grouped_data(client):
    _insert_raw(timestamp="2026-07-01T00:00:00+00:00", feature="synthesize", characters=100)
    _insert_raw(timestamp="2026-07-02T00:00:00+00:00", feature="polish", tokens=20)

    response = client.get("/api/usage/summary")

    assert response.status_code == 200
    body = response.json()
    assert len(body["by_day"]) == 2
    assert len(body["by_feature"]) == 2


def test_logs_endpoint_supports_pagination_and_feature_filter(client):
    for i in range(5):
        _insert_raw(timestamp=f"2026-07-01T0{i}:00:00+00:00", feature="synthesize")
    _insert_raw(timestamp="2026-07-01T09:00:00+00:00", feature="polish")

    response = client.get("/api/usage/logs", params={"feature": "synthesize", "page": 1, "page_size": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_export_endpoint_returns_csv(client):
    _insert_raw(timestamp="2026-07-01T00:00:00+00:00", feature="synthesize", characters=42)

    response = client.get("/api/usage/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert "id,timestamp,feature" in body
    assert "synthesize" in body
    assert "42" in body
