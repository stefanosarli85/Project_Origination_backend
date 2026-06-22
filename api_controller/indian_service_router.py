from fastapi import APIRouter, HTTPException, Query


from dynamoDB.indian_region_service import list_company_reports, get_company_report_cin_number
from services.region.india.finavo_api import fetch_and_save_indian_company_report

router = APIRouter(prefix="/api/india", tags=["India"])


@router.get("/reports")
async def get_company_reports(
    limit: int = Query(default=100, ge=1, le=100),
    last_evaluated_key: str | None = None,
):
    import json

    decoded_key = (
        json.loads(last_evaluated_key)
        if last_evaluated_key
        else None
    )

    data = list_company_reports(
        limit=limit,
        last_evaluated_key=decoded_key,
    )

    return {
        "items": data["items"],
        "count": data["count"],
        "next_page_token": (
            json.dumps(data["next_page_token"])
            if data["next_page_token"]
            else None
        ),
    }


@router.get("/reports/{cin}")
async def get_saved_indian_companies_report(cin: str):
    data = get_company_report_cin_number(cin.strip().upper())

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Report not found for CIN: {cin}",
        )

    return data["response"]


@router.post("/reports/{cin}")
async def fetch_and_save_indian_companies_report_by_cin_number(cin: str):
    try:
        return fetch_and_save_indian_company_report(cin)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get company report: {str(exc)}",
        )