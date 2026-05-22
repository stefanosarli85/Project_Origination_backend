import boto3
import os
import json

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

print("DYNAMO KEY LOADED:", bool(AWS_ACCESS_KEY_ID), bool(AWS_SECRET_ACCESS_KEY))

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


def print_all_records():
    response = table.scan()
    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    print(f"\n📦 Total records: {len(items)}\n")
    print(json.dumps(items, indent=2, default=str))