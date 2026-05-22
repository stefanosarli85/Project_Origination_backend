import requests
import base64
import os
from pathlib import Path
from dotenv import load_dotenv, dotenv_values
import time


from dynamoDB.italy_region_services import add_record, get_records_by_company
from s3.s3_services import upload_bytes_to_s3

BASE_DIR = Path(__file__).resolve().parents[4]
ENV_PATH = BASE_DIR / ".env"

print("ENV PATH:", ENV_PATH)

# =========================
# LOAD ENV
# =========================
load_dotenv(dotenv_path=ENV_PATH, override=True)

# 🔥 DIRECT SAFE READ (no os.getenv confusion)
env = dotenv_values(ENV_PATH)

OPENAI_TOKEN = os.environ.get("OPENAI_TOKEN")


def request_document(cf_piva_id: str):
    url = "https://visurecamerali.openapi.it/bilancio-ottico"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_TOKEN}"
    }

    payload = {
        "cf_piva_id": cf_piva_id
    }

    response = requests.post(url, json=payload, headers=headers)

    try:
        return response.json()
    except Exception:
        return response.text

def check_requested_document_status(request_id: str):
    url = f"https://visurecamerali.openapi.it/bilancio-ottico/{request_id}"

    headers = {
        "Authorization": f"Bearer {OPENAI_TOKEN}"
    }

    response = requests.get(url, headers=headers)

    try:
        return response.json()
    except Exception:
        return response.text


def fetch_balance_sheet_zip_bytes(request_id: str) -> bytes:
    url = f"https://visurecamerali.openapi.it/bilancio-ottico/{request_id}/allegati"
    HEADERS = {"Authorization": f"Bearer {OPENAI_TOKEN}"}

    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()

    resp = r.json()
    data = resp["data"]

    # Decode base64 ZIP
    zip_bytes = base64.b64decode(data["file"])

    print(f"✅ ZIP fetched in memory: {len(zip_bytes):,} bytes")

    return zip_bytes



def fetch_and_upload_balance_sheet(cf_piva_id: str,folder: str = "uploads") -> dict:
    bucket_name="italy-companies-financial-documents"

    # ── Step 0: Check if document already exists in DynamoDB ──────────────────
    print(f"🔍 Checking DynamoDB for existing records — company_id: {cf_piva_id}")
    existing_records = get_records_by_company(company_id=cf_piva_id)

    if existing_records:
        print(f"✅ Document already exists for company {cf_piva_id}, skipping request.")
        record = existing_records[0]
        return {
            "success": True,
            "cached": True,
            "cf_piva_id": cf_piva_id,
            "asset_id": record.get("asset_id"),
            "s3_url": record.get("s3_url")
        }

    print(f"📭 No existing record found, proceeding with fresh request...")

    # ── Step 1: Request the document ──────────────────────────────────────────
    print(f"📤 Requesting document for cf_piva_id: {cf_piva_id}")
    request_response = request_document(cf_piva_id)

    if not request_response.get("success"):
        raise Exception(f"❌ Failed to request document: {request_response}")

    request_id = request_response["data"]["id"]
    print(f"📋 Request ID: {request_id}")

    # ── Step 2: Poll until ready ───────────────────────────────────────────────
    MAX_ATTEMPTS = 20  # 20 × 15s = 5 minutes max wait
    attempt = 0
    stato = None

    while attempt < MAX_ATTEMPTS:
        attempt += 1
        print(f"⏳ Waiting 15 seconds before checking status (attempt {attempt}/{MAX_ATTEMPTS})...")
        time.sleep(15)

        status_response = check_requested_document_status(request_id)

        if not status_response.get("success"):
            raise Exception(f"❌ Failed to check status: {status_response}")

        stato = status_response["data"].get("stato_richiesta")
        print(f"📊 Status: {stato}")

        if stato == "Dati disponibili":
            print("✅ Document is ready!")
            break

        elif stato == "In ricerca":
            print("🔄 Still processing, waiting 15 more seconds...")
            continue

        else:
            raise Exception(f"❌ Unexpected status received: {stato}. Full response: {status_response}")

    else:
        raise TimeoutError(f"⏰ Document not ready after {MAX_ATTEMPTS * 15} seconds. Last status: {stato}")

    # ── Step 3: Fetch the ZIP bytes ────────────────────────────────────────────
    print(f"📥 Fetching balance sheet ZIP for request ID: {request_id}")
    zip_bytes = fetch_balance_sheet_zip_bytes(request_id)

    # ── Step 4: Upload to S3 ───────────────────────────────────────────────────
    file_name = f"bilancio_{cf_piva_id}_{request_id}.zip"
    print(f"☁️  Uploading to S3 bucket: {bucket_name}/{folder}/{file_name}")

    s3_result = upload_bytes_to_s3(
        file_bytes=zip_bytes,
        bucket_name=bucket_name,
        folder=folder,
        file_name=file_name,
        content_type="application/zip"
    )

    # ── Step 5: Save record to DynamoDB ───────────────────────────────────────
    print(f"🗄️  Saving record to DynamoDB — company_id: {cf_piva_id}, asset_id: {request_id}")
    add_record(
        company_id=cf_piva_id,
        asset_id=request_id,
        s3_url=s3_result["url"]
    )
    print("✅ Record saved to DynamoDB!")

    # ── Step 6: Return result ──────────────────────────────────────────────────
    return {
        "success": True,
        "cached": False,
        "cf_piva_id": cf_piva_id,
        "request_id": request_id,
        "file_name": s3_result["file_name"],
        "s3_key": s3_result["s3_key"],
        "s3_url": s3_result["url"],
        "size_bytes": len(zip_bytes)
    }

# fetch_and_upload_balance_sheet("05962420963")