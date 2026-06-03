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