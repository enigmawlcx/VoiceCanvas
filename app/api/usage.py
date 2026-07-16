import csv
import io

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.db.usage_repo import get_usage_summary, list_usage_logs

router = APIRouter(prefix="/api/usage", tags=["usage"])

CSV_COLUMNS = ["id", "timestamp", "feature", "model", "characters", "tokens", "voice_id", "cost_estimate", "status"]


@router.get("/summary")
def summary(
    start: str | None = None,
    end: str | None = None,
    granularity: str = Query("day", pattern="^(day|week)$"),
) -> dict:
    return get_usage_summary(start=start, end=end, granularity=granularity)


@router.get("/logs")
def logs(
    start: str | None = None,
    end: str | None = None,
    feature: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> dict:
    return list_usage_logs(start=start, end=end, feature=feature, page=page, page_size=page_size)


@router.get("/export")
def export(start: str | None = None, end: str | None = None, feature: str | None = None) -> StreamingResponse:
    result = list_usage_logs(start=start, end=end, feature=feature, page=1, page_size=1_000_000)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for item in result["items"]:
        writer.writerow([item.get(column) for column in CSV_COLUMNS])

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=usage_export.csv"},
    )
