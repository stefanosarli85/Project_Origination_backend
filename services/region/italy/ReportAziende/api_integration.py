import requests


def     get_company_details_form_reportaziende(cid: str):
    url = f"https://api.reportaziende.it/dettaglioazienda/visualizza/{cid}/05,10,20,30,40,70,85,ANA"

    headers = {
        "Authorization": "Bearer 49da9d58db14ad65747ac3b90d80f8a7f8ada6b59645a86f8fd1a26c2a16070c"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises HTTPError for bad responses

        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return None