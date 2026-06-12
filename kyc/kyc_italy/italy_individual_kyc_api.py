import httpx
from io import BytesIO

from dynamoDB.italy_region_services import save_kyc_request_person

BASE_URL = "https://risk.openapi.com"
TOKEN = "6a27c83e4a8c5078cb0aad85"

POST_HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
GET_HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def submit_kyc_person(first_name: str, last_name: str, tax_code: str) -> str:
    payload = {
        "name": first_name,
        "surname": last_name,
        "taxCode": tax_code,
        "titlePdf": f"KYC Report - {first_name} {last_name}",
        "textPdf": f"Know Your Customer report for {first_name} {last_name}",
    }
    r = httpx.post(f"{BASE_URL}/IT-report-persona", json=payload, headers=POST_HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    print("submit kyc response")
    print(data)
    print("submit kyc response")
    request_id = data["data"]["id"]
    state = data["data"]["state"]
    print(f"Submitted — ID: {request_id} — State: {state}")
    return request_id


def get_person_kyc_pdf(request_id: str):
    r = httpx.get(
        f"{BASE_URL}/IT-report-persona/{request_id}",
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
        f"{BASE_URL}/IT-report-persona/{request_id}/download",
        headers=GET_HEADERS,
        timeout=60
    )
    r.raise_for_status()

    return BytesIO(r.content)


def request_kyc_for_italian_individual(first_name: str, last_name: str, tax_code: str):
    request_id = submit_kyc_person(first_name, last_name, tax_code)
    print("request id - person")
    print(request_id)
    print("request id - person")
    response = save_kyc_request_person(request_id, first_name, last_name, tax_code)
    print("save response - person")
    print(response)
    print("save response - person")
    return response
