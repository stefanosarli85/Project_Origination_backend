import requests
import time
import zipfile
import io
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv

# =========================
# LOAD .ENV (project root)
# =========================
BASE_DIR = Path(__file__).resolve().parents[4]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

# =========================
# CONFIG FROM ENV
# =========================
API_KEY        = os.getenv("API_KEY")
SEND_BATCH_URL = os.getenv("SEND_BATCH_URL")
GET_BATCH_URL  = os.getenv("GET_BATCH_URL")
OUTPUT_FORMAT  = "json"
POLL_INTERVAL  = 25  # seconds

# =========================
# LOCAL BT TEMPLATE FILE
# =========================
TEMPLATE_BT_FILE = (
    Path(__file__).resolve().parent /
    "my_batch_file" /
    "3cos_detailed_data_batch2.bt"
)

if not TEMPLATE_BT_FILE.exists():
    raise FileNotFoundError(f"BT file not found: {TEMPLATE_BT_FILE}")


# =========================
# HELPERS
# =========================

def _build_bt_bytes(company_codes: list) -> bytes:
    """
    Read the BT template, inject company codes, return as bytes.
    Nothing is written to disk.
    """
    content = TEMPLATE_BT_FILE.read_text(encoding="utf-8")
    codes_string = "|".join(map(str, company_codes))
    updated = re.sub(r"codes\{.*?\}", f"codes{{{codes_string}}}", content)
    return updated.encode("utf-8")


def _parse_data_file(name: str, obj: dict) -> dict:
    """
    Parse one data JSON file (e.g. W9.json, W10.json).
    Returns a structured dict with periods and per-metric records.
    """
    meta      = obj.get("meta", {})
    head_rows = obj.get("head", [])
    data_rows = obj.get("data", [])

    # head[3] -> [' ', ' ', ' ', ' ', ' ', 'Mar 2023', 'Mar 2024', ...]
    # head[4] -> [' ', '', 'Info Type', 'Unit', 'Expression', 'Company A', ...]
    years     = [c.strip() for c in head_rows[3][5:] if c.strip()] if len(head_rows) > 3 else []
    companies = [c.strip() for c in head_rows[4][5:] if c.strip()] if len(head_rows) > 4 else []

    # Period label: "Axis Bank Ltd. | Mar 2023"
    periods = [f"{co} | {yr}" for co, yr in zip(companies, years)]

    report_name = next(
        (c.strip() for row in head_rows for c in row
         if c.strip() and not c.strip().startswith("Output")),
        name,
    )

    records = []
    for row in data_rows:
        if len(row) < 6:
            continue
        expression = row[4].strip()
        if not expression:
            continue  # skip blank / section-header rows

        values = {}
        for period, val in zip(periods, row[5:]):
            val_str = str(val).strip()
            values[period] = float(val_str) if val_str else None

        records.append({
            "expression": expression,
            "info_type":  row[2].strip(),
            "unit":       row[3].strip(),
            "expr_type":  row[0].strip(),
            "values":     values,
        })

    return {
        "file":        name,
        "report_name": report_name,
        "periods":     periods,
        "errno":       meta.get("errno"),
        "errmsg":      meta.get("errmsg"),
        "server_time": meta.get("servertime"),
        "records":     records,
    }


def _parse_zip_bytes(zip_bytes: bytes) -> dict:
    """
    Parse an in-memory ZIP into a structured dict.
    Files are classified by their *content*, not filename,
    so any naming convention the API uses is handled correctly.
    """
    result = {
        "company_info": {},  # code -> company name
        "data_files":   {},  # file key -> parsed records
    }

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".json"):
                continue  # skip .lst and other non-JSON files

            try:
                obj = json.loads(zf.read(name).decode("utf-8"))
            except Exception:
                continue

            meta      = obj.get("meta", {})
            head_rows = obj.get("head", [])
            ncol      = meta.get("ncol", 0)

            # Company-lookup files: 2 columns, header mentions "Company Code"
            is_lookup = (
                ncol == 2
                and any("Company Code" in str(row) for row in head_rows)
            )

            if is_lookup:
                for row in obj.get("data", []):
                    if len(row) >= 2:
                        result["company_info"][row[0]] = row[1]

            elif ncol >= 6:
                key = name.replace(".json", "")
                try:
                    result["data_files"][key] = _parse_data_file(name, obj)
                except Exception as exc:
                    result["data_files"][key] = {"error": str(exc)}

    return result


# =========================
# STEP 1: SEND BATCH
# =========================

def _send_batch(bt_bytes: bytes) -> str | None:
    """Upload the BT content in-memory and return the batch token."""
    print("Uploading batch file ...")

    response = requests.post(
        "https://prowess.cmie.com/api/sendbatch",
        data={"apikey": API_KEY, "format": OUTPUT_FORMAT},
        files={"batchfile": ("batch.bt", bt_bytes)},
    )

    body = response.json()
    print("SendBatch response:", body)

    if body.get("errcode") != 0:
        print("Batch submission failed.")
        return None

    token = body.get("token")
    print(f"Batch token: {token}")
    return token


# =========================
# STEP 2: POLL STATUS
# =========================

PENDING_STATUSES = {
    "IN_QUEUE",
    "PROCESSING",
    "PROCESSED",
    "ZIP WAITING TO BE QUEUED",
    "ZIP INQUEUE",
    "ZIP PROCESSING",
}


def _poll_until_ready(token: str) -> bytes | None:
    """Poll the API until the ZIP is ready; return its raw bytes in memory."""
    while True:
        print("Checking batch status ...")

        response = requests.post("https://prowess.cmie.com/api/getbatch", data={"apikey": API_KEY, "token": token})
        content_type = response.headers.get("Content-Type", "")

        # ZIP arrived (non-JSON content type)
        if "application/json" not in content_type:
            print("ZIP received.")
            return response.content

        status  = response.json()
        message = status.get("message", "")
        print(f"Status: {message}")

        if message in PENDING_STATUSES:
            print(f"Waiting {POLL_INTERVAL} seconds ...\n")
            time.sleep(POLL_INTERVAL)
        else:
            print("Unexpected response:", status)
            return None


# =========================
# STEP 3: PIPELINE
# =========================

def run_pipeline(company_codes: list) -> dict:
    """
    Full pipeline - nothing written to disk at any step.

    Returns a frontend-ready JSON-serialisable dict:

    {
        "success": true,
        "token": "20260514_1218885",
        "company_codes": [256066],
        "companies": {
            "256066": "Axis Bank Ltd."
        },
        "reports": [
            {
                "report_key":  "W9",
                "report_name": "Standardised Annual Finance",
                "server_time": "2026-05-14 17:50:38",
                "errno":       0,
                "errmsg":      "Success",
                "periods":     ["Axis Bank Ltd. | Mar 2023", "Axis Bank Ltd. | Mar 2024", ...],
                "data": [
                    {
                        "expression": "Total income",
                        "info_type":  "Standardised Annual Finance Standalone",
                        "unit":       "Rs. Crore",
                        "expr_type":  "CMIE Expr",
                        "values": {
                            "Axis Bank Ltd. | Mar 2023": 105788.58,
                            "Axis Bank Ltd. | Mar 2024": 134866.89,
                            "Axis Bank Ltd. | Mar 2025": 152144.97
                        }
                    },
                    ...
                ]
            }
        ]
    }

    On failure returns: {"success": false, "error": "<reason>"}
    """
    bt_bytes = _build_bt_bytes(company_codes)

    token = _send_batch(bt_bytes)
    if not token:
        return {"success": False, "error": "Batch submission failed."}

    zip_bytes = _poll_until_ready(token)
    if not zip_bytes:
        return {"success": False, "error": "Did not receive ZIP from API."}

    raw     = _parse_zip_bytes(zip_bytes)
    reports = []

    for report_key, file_data in raw.get("data_files", {}).items():
        if "error" in file_data:
            reports.append({"report_key": report_key, "error": file_data["error"]})
            continue

        reports.append({
            "report_key":  report_key,
            "report_name": file_data.get("report_name", ""),
            "server_time": file_data.get("server_time", ""),
            "errno":       file_data.get("errno"),
            "errmsg":      file_data.get("errmsg", ""),
            "periods":     file_data.get("periods", []),
            "data":        file_data.get("records", []),
        })

    return {
        "success":       True,
        "token":         token,
        "company_codes": company_codes,
        "companies":     raw.get("company_info", {}),
        "reports":       reports,
    }


# =========================
# MAIN
# =========================

# if __name__ == "__main__":
#     company_codes = [256066]
#     response = run_pipeline(company_codes)
#     print(json.dumps(response, indent=2, ensure_ascii=False))

def create_and_run_pipeline(company_codes: list[int]):
    return run_pipeline(company_codes)