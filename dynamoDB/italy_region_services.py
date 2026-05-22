import boto3
from pathlib import Path
from dotenv import dotenv_values
import os

# =========================
# Load .env
# =========================
BASE_DIR = Path(__file__).resolve().parents[1]  # dynamoDB/ → project_originate/
ENV_PATH = BASE_DIR / ".env"

env = dotenv_values(ENV_PATH)

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

print("KEY LOADED:", bool(AWS_ACCESS_KEY_ID), bool(AWS_SECRET_ACCESS_KEY))  # must be True True now

# =========================
# DynamoDB Connection
# =========================
dynamodb = boto3.resource(
    "dynamodb",
    region_name="ap-south-1",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

table = dynamodb.Table("italy_company_documents")


def add_record(company_id: str, asset_id: str, s3_url: str):
    response = table.put_item(
        Item={
            "company_id": company_id,
            "asset_id": asset_id,
            "s3_url": s3_url
        }
    )
    return response


def get_records_by_company(company_id: str):
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("company_id").eq(company_id)
    )
    return response.get("Items", [])

import json

# =========================
# SCAN FULL TABLE
# =========================
def print_all_records():
    response = table.scan()
    items = response.get("Items", [])

    # Handle pagination (if table has more than 1MB of data)
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    print(f"\n📦 Total records: {len(items)}\n")
    print(json.dumps(items, indent=2, default=str))

