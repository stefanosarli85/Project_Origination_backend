import asyncio

from fastapi import APIRouter, Form, UploadFile, Body
from fastapi.concurrency import run_in_threadpool

from services.region.india.CMIE_Prowess.api_integration import create_and_run_pipeline
from services.region.italy.ReportAziende.italy_region_service import check_if_data_available_in_db, get_company_full_data, \
    get_and_save_italy_company
from services.region.italy.openapi.financial_documents import fetch_and_upload_balance_sheet

router = APIRouter(prefix="/api")

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

@router.get("/italy/check_db/{cid}")
def check_db(cid: str):
    return {"available": check_if_data_available_in_db(cid)}


@router.get("/italy/company/{company_id}")
def get_company(company_id: str):
    return get_company_full_data(company_id)


@router.post("/italy/company/{cid}")
def fetch_and_save_company(cid: str):
    return get_and_save_italy_company(cid)

@router.post("/fetch-financial-document/{cf_piva_id}")
def fetch_financial_document(cf_piva_id: str):
    return fetch_and_upload_balance_sheet(cf_piva_id)