import httpx
import asyncio

BASE_URL = "https://risk.openapi.com"
TOKEN = "6a27c83e4a8c5078cb0aad85"

async def submit_kyc_person(first_name, last_name, tax_code):
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE_URL}/IT-report-persona",
            json={
                "name": first_name,
                "surname": last_name,
                "taxCode": tax_code,
                "titlePdf": f"KYC Report - {first_name} {last_name}",
            },
            headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
            timeout=30
        )
        r.raise_for_status()
        data = r.json()
        print(f"Request ID: {data['data']['id']}")
        print(f"State: {data['data']['state']}")

asyncio.run(submit_kyc_person("Stefano", "Sarli", "SRLSFN85P13L328V"))