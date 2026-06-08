import asyncio
from typing import Optional
from fastapi import Form
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel


from nlp_search.ollama_services import _ask_ollama, search
from services.region.india.CMIE_Prowess.api_integration import create_and_run_pipeline
from services.region.italy.ReportAziende.italy_region_service import check_if_data_available_in_db, \
    get_company_full_data, column_search_italy, get_all_records_italy, get_and_save_company
from services.region.italy.openapi.financial_documents import fetch_and_upload_balance_sheet


router = APIRouter(prefix="/api")



class SearchRequest(BaseModel):
    search: str



# INDIA
@router.post("/india/get-report")
async def run_italian_pipeline(company_code: str = Form(...)):
    company_codes = [company_code]
    response = await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: create_and_run_pipeline(company_codes)
    )
    return response

# ITALY

# @router.get("/italy/check_db/{cid}")
# def check_db(cid: str):
#     return {"available": check_if_data_available_in_db(cid)}
#
#
# @router.get("/italy/company/{company_id}")
# def get_company(company_id: str):
#     return get_company_full_data(company_id)


@router.post("/italy/company/{cid}")
def fetch_and_save_company(cid: str, schedules: list[str] = Query(default=["ANA"])):
    return get_and_save_company(cid, schedules)

@router.post("/fetch-financial-document/{cf_piva_id}")
def fetch_financial_document(cf_piva_id: str):
    return fetch_and_upload_balance_sheet(cf_piva_id)


@router.post("/italy-search_query")
async def search_query_endpoint(request: SearchRequest):
    try:
        company_ids = search(request.search)
        return {
            "query": request.search,
            "total": len(company_ids),
            "company_ids": company_ids
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/italy-get-all-records")
def get_master_data_of_italy(page: int = 1):
    records = get_all_records_italy(page=page)
    return {"page": page, "data": records}


def parse_numeric_input(value: str) -> Optional[float]:
    if value is None:
        return None

    value = value.strip().upper()

    if not value:
        return None

    # Remove commas (e.g. "50,000,000" -> "50000000")
    value = value.replace(",", "")

    try:
        if value.endswith("M"):
            return float(value[:-1]) * 1_000_000
        elif value.endswith("K"):
            return float(value[:-1]) * 1_000
        else:
            return float(value)
    except ValueError:
        return None


@router.get("/italy-search-columns")
def search_italy_by_columns(
    company_code: str = "",
    company_name: str = "",
    city: str = "",
    industry_code: str = "",
    revenue_min: str = "",
    revenue_max: str = "",
    ebit_min: str = "",
    ebit_max: str = "",
    employees_min: float = None,
    employees_max: float = None,
    sort_by: str = "id",          # e.g. "revenue", "ebit", "employees"
    sort_order: str = "asc",      # "asc" or "desc"
    page: int = 1,
    limit: int = 100,
):
    result = column_search_italy(
        company_code=company_code,
        company_name=company_name,
        city=city,
        industry_code=industry_code,
        revenue_min=parse_numeric_input(revenue_min),
        revenue_max=parse_numeric_input(revenue_max),
        ebit_min=parse_numeric_input(ebit_min),
        ebit_max=parse_numeric_input(ebit_max),
        employees_min=employees_min,
        employees_max=employees_max,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=limit,
    )
    return result