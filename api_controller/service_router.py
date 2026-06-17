import asyncio
from datetime import date
from io import BytesIO
from typing import Optional
from fastapi import Form
import json
from pathlib import Path
from fastapi.responses import JSONResponse
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Query
from pydantic import BaseModel
from enum import Enum
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from requests.exceptions import RequestException


from dynamoDB.italy_region_services import is_report_available, get_all_kyc_requests, get_company_kyc_request, \
    get_company_schedule_status
from kyc.kyc_global.global_kyc_api import kyc_person, kyc_company, KYCPersonRequest, KYCCompanyRequest
from kyc.kyc_italy.italy_company_kyc_api import get_company_kyc_pdf, request_kyc_for_italian_company
from kyc.kyc_italy.italy_individual_kyc_api import request_kyc_for_italian_individual, get_person_kyc_pdf
from news.company_news import get_company_news
from services.region.india.CMIE_Prowess.api_integration import create_and_run_pipeline
from services.region.italy.ReportAziende.italy_region_service import column_search_italy, get_all_records_italy, get_and_save_company
from services.region.italy.openapi.financial_documents import fetch_and_upload_balance_sheet, get_wallet, \
    get_wallet_transaction

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

## KYC GLOBAL

class KYCTypeGlobal(str, Enum):
    person = "person"
    company = "company"

class KYCRequestGlobal(BaseModel):
    type: KYCTypeGlobal
    # Person fields
    firstName: str | None = None
    lastName: str | None = None
    birthDate: date | None = None
    # Company fields
    name: str | None = None

@router.post("/global/kyc-check")
async def kyc_check(body: KYCRequestGlobal):
    if body.type == KYCTypeGlobal.person:
        return await kyc_person(KYCPersonRequest(
            firstName=body.firstName,
            lastName=body.lastName,
            birthDate=body.birthDate
        ))
    else:
        return await kyc_company(KYCCompanyRequest(
            name=body.name
        ))

class KYCRequestIndividualItaly(BaseModel):
    first_name: str
    last_name: str
    tax_code: str


## KYC ITALY PERSON

@router.post("/italy/individual/request-kyc")
def create_person_kyc_request(payload: KYCRequestIndividualItaly):
    try:
        return request_kyc_for_italian_individual(
            first_name=payload.first_name,
            last_name=payload.last_name,
            tax_code=payload.tax_code
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get("/italy/individual/retrieve-kyc-requests")
def fetch_all_person_kyc_requests():
    return get_all_kyc_requests()


@router.get("/italy/individual/download-kyc-pdf/{request_id}")
def download_person_kyc_pdf(request_id: str):
    try:
        result = get_person_kyc_pdf(request_id)

        # PDF ready
        if isinstance(result, BytesIO):
            return StreamingResponse(
                result,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="kyc_report_{request_id}.pdf"'
                }
            )

        # Still processing
        return JSONResponse(
            status_code=200,
            content=result
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


## KYC ITALY COMPANY
class KYCRequestCompanyItaly(BaseModel):
    company_name: str
    vat_code: str
    tax_code: Optional[str] = None


@router.post("/italy/comp/request-kyc")
def create_company_kyc_request(payload: KYCRequestCompanyItaly):
    try:
        return request_kyc_for_italian_company(
            company_name=payload.company_name,
            vat_code=payload.vat_code,
            tax_code=payload.tax_code or payload.vat_code
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get("/italy/comp/retrieve-kyc-requests")
def fetch_all_company_kyc_requests():
    return get_company_kyc_request()


@router.get("/italy/comp/download-kyc-pdf/{request_id}")
def download_company_kyc_pdf(request_id: str):
    try:
        result = get_company_kyc_pdf(request_id)

        # PDF is ready
        if isinstance(result, BytesIO):
            return StreamingResponse(
                result,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="company_kyc_report_{request_id}.pdf"'
                }
            )

        # Report still processing
        return JSONResponse(
            status_code=200,
            content=result
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/isDocumentAvailable/{companycode}")
def check_document(companycode: str):
    result = is_report_available(companycode)

    return {
        "companyCode": companycode,
        **result
    }

@router.get("/get-schedule-status/{company_code}")
def fetch_schedule_status(company_code: str):
    return get_company_schedule_status(company_code)


@router.get("/reportaziende/credit")
def get_ReportAziende_credit():
    try:
        credit_file = (
            Path.cwd()
            / "services"
            / "region"
            / "italy"
            / "ReportAziende"
            / "credit.json"
        )

        if not credit_file.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "credit file not found",
                    "debug_path": str(credit_file)
                }
            )

        with open(credit_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            "success": True,
            "available_credit": data.get("available_credit", 0)
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@router.get("/wallet")
def fetch_wallet():
    try:
        return get_wallet()

    except RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch wallet data: {str(exc)}"
        )


@router.get("/wallet/transactions")
def fetch_wallet_transactions():
    try:
        return get_wallet_transaction()

    except RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch wallet transactions: {str(exc)}"
        )