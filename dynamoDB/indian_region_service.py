from datetime import datetime

import boto3
import os
import json
from boto3.dynamodb.conditions import Attr

from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv()

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

print("DYNAMO KEY LOADED:", bool(AWS_ACCESS_KEY_ID), bool(AWS_SECRET_ACCESS_KEY))

TABLE_NAME = "indian_company_reports"


dynamodb = boto3.resource(
    "dynamodb",
    region_name="ap-south-1",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)


def create_table():
    try:
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "cin", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "cin", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        table.wait_until_exists()
        return table

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            return dynamodb.Table(TABLE_NAME)
        raise


def save_indian_companies_reports(cin: str, response: dict):
    table = dynamodb.Table(TABLE_NAME)

    table.put_item(
        Item={
            "cin": cin,
            "response": response,
        }
    )


def get_company_report_cin_number(cin: str):
    table = dynamodb.Table(TABLE_NAME)

    result = table.get_item(Key={"cin": cin})
    return result.get("Item")


def is_cin_report_available(cin: str) -> bool:
    table = dynamodb.Table(TABLE_NAME)

    response = table.get_item(
        Key={"cin": cin},
        ProjectionExpression="cin"
    )

    return "Item" in response


def list_company_reports(limit: int = 100, last_evaluated_key: dict | None = None):
    table = dynamodb.Table(TABLE_NAME)

    scan_kwargs = {
        "Limit": limit,
        "ProjectionExpression": "cin, #r.company_name, #r.company_status, #r.incorporation_date",
        "ExpressionAttributeNames": {
            "#r": "response",
        },
    }

    if last_evaluated_key:
        scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

    response = table.scan(**scan_kwargs)

    records = []

    for item in response.get("Items", []):
        report = item.get("response", {})

        records.append({
            "cin": item.get("cin"),
            "company_name": report.get("company_name"),
            "company_status": report.get("company_status"),
            "incorporation_date": report.get("incorporation_date"),
        })

    return {
        "items": records,
        "count": len(records),
        "next_page_token": response.get("LastEvaluatedKey"),
    }