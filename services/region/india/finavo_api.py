import requests
import json
from dynamoDB.indian_region_service import is_cin_report_available, save_indian_companies_reports, get_company_report_cin_number

API_KEY = "eCpjtzNKNv"
API_SECRET = "ft8kO2beSGApOurC85fGliIIWlqVNvesFO12Ha7w"

HEADERS = {
    "X-API-KEY": API_KEY,
    "X-API-SECRET-KEY": API_SECRET,
}


def fetch_indian_company_report(cin: str):
    url = f"https://detail.finanvo.in/api/detailed-report/company/json/{cin}?key=all"
    resp = requests.get(url, headers=HEADERS)
    print(f"Status: {resp.status_code}")
    if resp.ok:
        data = resp.json()
        with open("detailed_report_response.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("Full response saved to detailed_report_response.json")
    else:
        print(resp.text)
    return resp


def fetch_and_save_indian_company_report(cin: str) -> dict:
    cin = cin.strip().upper()

    if not is_cin_report_available(cin):
        print("here")
        report = fetch_indian_company_report(cin)

        save_indian_companies_reports(
            cin=cin,
            response=report,
        )

    return get_company_report_cin_number(cin)["response"]
