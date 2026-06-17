import requests
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("REPOT_AZIENDE_TOKEN")


def get_company_details_form_reportaziende(cid: str, schedules: list[str]):
    schedules_str = ",".join(schedules)
    url = f"https://api.reportaziende.it/dettaglioazienda/visualizza/{cid}/{schedules_str}"

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return None

import json
from pathlib import Path

def update_credit_file(new_credit: int):
    # go to: services/region/italy/ReportAziende/
    base_dir = Path(__file__).resolve().parent
    file_path = base_dir / "credit.json"

    data = {"available_credit": new_credit}

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)