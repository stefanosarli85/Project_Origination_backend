import httpx

BASE_URL = "https://risk.openapi.com"
TOKEN = "YOUR_TOKEN_HERE"

GET_HEADERS = {"Authorization": f"Bearer {TOKEN}"}
POST_HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


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
    request_id = data["data"]["id"]
    state = data["data"]["state"]
    print(f"Submitted — ID: {request_id} — State: {state}")
    return request_id


def download_kyc_pdf(request_id: str, output_path: str = "kyc_report.pdf"):
    # Check state
    r = httpx.get(f"{BASE_URL}/IT-report-persona/{request_id}", headers=GET_HEADERS, timeout=30)
    r.raise_for_status()
    result = r.json()
    state = result["data"].get("state")
    print(f"State: {state}")

    if state != "complete":
        print(f"Not ready yet — current state: '{state}'. Try again later.")
        return None

    # Download PDF
    r = httpx.get(f"{BASE_URL}/IT-report-persona/{request_id}/pdf", headers=GET_HEADERS, timeout=60)
    r.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(r.content)
    print(f"PDF saved → {output_path}")
    return output_path


# ── Usage ──
# Step 1 — run once
request_id = submit_kyc_person("Stefano", "Sarli", "SRLSFN85P13L328V")
print(request_id)

# Step 2 — run after some time with the returned ID
# download_kyc_pdf("YOUR_REQUEST_ID", "stefano_sarli_kyc.pdf")