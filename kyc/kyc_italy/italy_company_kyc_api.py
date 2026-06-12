import requests
import httpx
from io import BytesIO

from dynamoDB.italy_region_services import save_company_kyc_request

API_KEY = "6a27c83e4a8c5078cb0aad85"
BASE_URL = "https://risk.openapi.com"
TOKEN = "6a27c83e4a8c5078cb0aad85"

POST_HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
GET_HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def submit_kyc_company(
    company_name: str,
    vat_code: str,
    tax_code: str = None
) -> str:

    payload = {
        "companyName": company_name,
        "vatCode": vat_code,
        "taxCode": tax_code or vat_code
    }

    r = httpx.post(f"{BASE_URL}/IT-report-azienda", json=payload, headers=POST_HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    print("submit kyc response :  company")
    print(data)
    print("submit kyc response :  company")
    request_id = data["data"]["id"]
    state = data["data"]["state"]
    print(f"Submitted — ID: {request_id} — State: {state}")
    return request_id


def get_company_kyc_pdf(request_id: str):
    r = httpx.get(
        f"{BASE_URL}/IT-report-azienda/{request_id}",
        headers=GET_HEADERS,
        timeout=30
    )
    r.raise_for_status()

    state = r.json()["data"].get("state")

    if state != "completed":
        return {
            "status": "processing",
            "message": f"Report not ready. Current state: {state}",
            "request_id": request_id
        }

    r = httpx.get(
        f"{BASE_URL}/IT-report-azienda/{request_id}/download",
        headers=GET_HEADERS,
        timeout=60
    )
    r.raise_for_status()

    return BytesIO(r.content)


def request_kyc_for_italian_company(company_name: str,vat_code: str,tax_code: str):
    request_id = submit_kyc_company(company_name,vat_code,tax_code)
    print("request id - company")
    print(request_id)
    print("request id - company")
    response = save_company_kyc_request(request_id,company_name,vat_code,tax_code)
    print("table response - company")
    print(response)
    print("table response - company")
    return response
