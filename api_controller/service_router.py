from fastapi import APIRouter, Form, UploadFile, Body

from services.region.india.CMIE_Prowess.api_integration import create_and_run_pipeline

router = APIRouter(prefix="/api")


@router.post("/itly/get-report")
def run_italian_pipeline(company_code: str = Form(...)):
    company_codes = [company_code]
    response = create_and_run_pipeline(company_codes)
    return response
