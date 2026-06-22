import requests

from dynamoDB.indian_region_service import is_cin_report_available, save_response, get_response

API_KEY = "eCpjtzNKNv"
API_SECRET = "ft8kO2beSGApOurC85fGliIIWlqVNvesFO12Ha7w"

HEADERS = {
    "X-API-KEY": API_KEY,
    "X-API-SECRET-KEY": API_SECRET,
}


def fetch_indian_company_report(cin: str) -> dict:
    url = (
        f"https://detail.finanvo.in/api/"
        f"detailed-report/company/json/{cin}?key=all"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def get_company_report(cin: str) -> dict:
    cin = cin.strip().upper()

    if not is_cin_report_available(cin):
        report = fetch_indian_company_report(cin)

        save_response(
            cin=cin,
            response=report,
        )

    return get_response(cin)["response"]
