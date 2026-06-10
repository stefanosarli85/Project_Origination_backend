import httpx
import asyncio

BASE_URL = "https://risk.openapi.com"
TOKEN = "6a27c83e4a8c5078cb0aad85"

POST_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}
GET_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
}


async def kyc_person_italy(
    first_name: str,
    last_name: str,
    tax_code: str,              # codice fiscale — e.g. SRLSFN85P13L328V
    output_path: str = "kyc_report.pdf"
):
    # ── Step 1: Submit report request ──
    payload = {
        "name": first_name,
        "surname": last_name,
        "taxCode": tax_code,
        "titlePdf": f"KYC Report - {first_name} {last_name}",
        "textPdf": f"Know Your Customer report for {first_name} {last_name}",
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE_URL}/IT-report-persona",
            json=payload,
            headers=POST_HEADERS,
            timeout=30
        )
        r.raise_for_status()
        data = r.json()

    print(f"Full response: {data}")

    request_id = data["data"]["id"]
    print(f"Request submitted — ID: {request_id}")

    # ── Step 2: Poll until COMPLETED ──
    async with httpx.AsyncClient() as client:
        for attempt in range(15):
            await asyncio.sleep(15)
            r = await client.get(
                f"{BASE_URL}/IT-report-persona/{request_id}",
                headers=GET_HEADERS,
                timeout=30
            )
            r.raise_for_status()
            result = r.json()
            state = result["data"].get("state")
            print(f"Attempt {attempt + 1} — state: {state}")

            if state == "COMPLETED":
                break
        else:
            raise TimeoutError("Report did not complete in time")

    # ── Step 3: Download PDF ──
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BASE_URL}/IT-report-persona/{request_id}/pdf",
            headers=GET_HEADERS,
            timeout=60
        )
        print(f"PDF status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type')}")

        if r.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(r.content)
            print(f"PDF saved → {output_path}")
        else:
            print(f"Failed: {r.text[:300]}")

    return output_path


# ── Run ──
asyncio.run(kyc_person_italy(
    first_name="Stefano",
    last_name="Sarli",
    tax_code="SRLSFN85P13L328V",
    output_path="stefano_sarli_kyc.pdf"
))