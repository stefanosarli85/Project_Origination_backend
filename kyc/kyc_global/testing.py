from datetime import date
from typing import Literal

import httpx
from pydantic import BaseModel

from dynamoDB.italy_region_services import save_global_kyc_request_individual_table, \
    save_global_kyc_request_company_table, individual_table, company_table

BASE_URL = "https://risk.openapi.com"
TOKEN = "6a27c83e4a8c5078cb0aad85"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }


class KYCPersonQuery(BaseModel):
    firstName: str
    lastName: str
    birthDate: date
    entityType: Literal["I"] = "I"


class KYCCompanyQuery(BaseModel):
    name: str
    entityType: Literal["L"] = "L"


class KYCRequestPayloadGlobal(BaseModel):
    query: KYCPersonQuery | KYCCompanyQuery


async def create_kyc_request(payload: KYCRequestPayloadGlobal) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{BASE_URL}/WW-kyc-full",
            json=payload.model_dump(mode="json"),
            headers=_headers(),
        )

        response.raise_for_status()

        result = response.json()

    if isinstance(payload.query, KYCPersonQuery):
        save_global_kyc_request_individual_table(result)

    elif isinstance(payload.query, KYCCompanyQuery):
        save_global_kyc_request_company_table(result)

    return result


async def get_kyc_evidence(request_id: str) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(
            f"{BASE_URL}/WW-kyc-evidences/{request_id}",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def download_kyc_pdf(request_id: str, entity_id: str) -> bytes:
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/pdf",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.get(
            f"{BASE_URL}/WW-kyc-evidences/{request_id}/{entity_id}",
            headers=headers,
        )
        response.raise_for_status()
        return response.content

def get_all_global_kyc_request_individual() -> list[dict]:
    response = individual_table.scan()

    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = individual_table.scan(
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        items.extend(response.get("Items", []))

    return items


def get_all_global_kyc_request_company() -> list[dict]:
    response = company_table.scan()

    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = company_table.scan(
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        items.extend(response.get("Items", []))

    return items


