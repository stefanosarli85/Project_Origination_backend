import httpx

TOKEN = "6a27c83e4a8c5078cb0aad85"
REQUEST_ID = "6a2820cb31ec2f19cc068455"

def download_kyc_pdf(request_id: str, output_path: str = "kyc_report.pdf"):
    r = httpx.get(
        f"https://risk.openapi.com/IT-report-persona/{request_id}/download",
        headers={"Authorization": f"Bearer {TOKEN}"},
        timeout=60
    )
    print(f"Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type')}")

    if r.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(r.content)
        print(f"PDF saved → {output_path}")
    else:
        print(f"Failed: {r.text[:300]}")


download_kyc_pdf(REQUEST_ID, "stefano_sarli_kyc.pdf")