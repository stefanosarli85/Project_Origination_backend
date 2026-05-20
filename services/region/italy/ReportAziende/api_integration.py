import requests
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("REPOT_AZIENDE_TOKEN")


def get_company_details_form_reportaziende(cid: str):
    url = f"https://api.reportaziende.it/dettaglioazienda/visualizza/{cid}/05,10,20,30,40,70,85,ANA"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises HTTPError for bad responses

        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return None