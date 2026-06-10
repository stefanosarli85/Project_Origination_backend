import asyncio
from datetime import date
from typing import Optional
from fastapi import Form
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from enum import Enum

from dynamoDB.italy_region_services import get_company_schedule_status
from kyc.open_api_kyc_api import kyc_person, kyc_company, KYCPersonRequest, KYCCompanyRequest
from news.company_news import get_company_news
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


@router.post("/italy/company/{cid}")
def fetch_and_save_company(cid: str, schedules: list[str] = Query(default=["ANA"])):
    return get_and_save_company(cid, schedules)

@router.post("/fetch-financial-document/{cf_piva_id}")
def fetch_financial_document(cf_piva_id: str):
    return fetch_and_upload_balance_sheet(cf_piva_id)



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
    main_industry: str = "",
    sub_industry: str = "",
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
        main_industry=main_industry,
        sub_industry=sub_industry,
        page=page,
        limit=limit,
    )
    return result


@router.get("/fetch-news")
def fetch_news(company_name: str):
    return get_company_news(company_name)


class KYCType(str, Enum):
    person = "person"
    company = "company"

class KYCRequest(BaseModel):
    type: KYCType
    # Person fields
    firstName: str | None = None
    lastName: str | None = None
    birthDate: date | None = None
    # Company fields
    name: str | None = None

@router.post("/kyc-check")
async def kyc_check(body: KYCRequest):
    if body.type == KYCType.person:
        return await kyc_person(KYCPersonRequest(
            firstName=body.firstName,
            lastName=body.lastName,
            birthDate=body.birthDate
        ))
    else:
        return await kyc_company(KYCCompanyRequest(
            name=body.name
        ))


@router.get("/get-schedule-status/{company_code}")
def fetch_schedule_status(company_code: str):
    return get_company_schedule_status(company_code)