import httpx
from pydantic import BaseModel
from datetime import date

BASE_URL = "https://risk.openapi.com"
TOKEN = "6a27c83e4a8c5078cb0aad85"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}


class KYCPersonRequest(BaseModel):
    firstName: str
    lastName: str
    birthDate: date


class KYCCompanyRequest(BaseModel):
    name: str


async def kyc_person(body: KYCPersonRequest) -> dict:
    payload = {
        "query": {
            "firstName": body.firstName,
            "lastName": body.lastName,
            "birthDate": str(body.birthDate),
            "entityType": "I",
        }
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}/WW-kyc-full", json=payload, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()


async def kyc_company(body: KYCCompanyRequest) -> dict:
    payload = {
        "query": {
            "name": body.name,
            "entityType": "L",
        }
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}/WW-kyc-full", json=payload, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()