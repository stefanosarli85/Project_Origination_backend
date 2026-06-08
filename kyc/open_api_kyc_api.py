import httpx
from pydantic import BaseModel
from datetime import date

BASE_URL = "https://risk.openapi.com"
TOKEN = "6a2666eae9b723c3bb05fcf6"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}


# ── Pydantic Models ──────────────────────────────────────────────

class KYCPersonRequest(BaseModel):
    firstName: str
    lastName: str
    birthDate: date                 # yyyy-mm-dd


class KYCCompanyRequest(BaseModel):
    name: str


# ── Functions ────────────────────────────────────────────────────

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


# ── Usage ────────────────────────────────────────────────────────

# result = await kyc_person(KYCPersonRequest(firstName="Mario", lastName="Rossi", birthDate="1980-05-14"))
# result = await kyc_company(KYCCompanyRequest(name="Acme S.r.l."))

import asyncio

result = asyncio.run(kyc_person(KYCPersonRequest(
    firstName="Stefano",
    lastName="Sarli",
    birthDate="1985-09-13"
)))

print(result)