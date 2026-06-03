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


def create_italy_companies_table():
    table = dynamodb.create_table(
        TableName="italy_companies",
        KeySchema=[
            {"AttributeName": "company_code", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "company_code", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    print("✅ Table created")
    return table



SCHEDULE_KEY_MAP = {
    "ANA":  "ANA",
    "05":   "S05",
    "10":   "S10",
    "20":   "S20",
    "30":   "S30",
    "40":   "S40",
    "50":   "S50",
    "60":   "S60",
    "70":   "S70",
    "85":   "S85",
    "PROT": "PROT",
    "CR":   "CR",
}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _floats_to_decimal(obj):
    from decimal import Decimal
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _floats_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_floats_to_decimal(i) for i in obj]
    return obj


def check_schedules_availability(company_code: str, schedules: list[str]) -> list[dict]:
    table = dynamodb.Table("italy_companies")

    response = table.get_item(
        Key={"company_code": company_code}
    )

    item = response.get("Item", {})

    result = []
    for schedule in schedules:
        col = SCHEDULE_KEY_MAP.get(schedule)
        result.append({
            "schedule": schedule,
            "is_data_available": col in item and item[col] is not None
        })

    return result



def save_company_schedules(data: dict, schedules: list[str]):
    table = dynamodb.Table("italy_companies")

    company_code = data.get("cf")
    schede = data.get("schede", {})

    update_parts = []
    expr_attr_names = {}
    expr_attr_values = {":updated_at": _now()}

    for schedule in schedules:
        col = SCHEDULE_KEY_MAP.get(schedule)
        if col is None:
            print(f"⚠️  Unknown schedule '{schedule}', skipping.")
            continue

        raw = schede.get(schedule)
        if raw is None:
            print(f"⚠️  Schedule '{schedule}' not in response, skipping.")
            continue

        attr_name  = f"#col_{col}"
        attr_value = f":val_{col}"

        expr_attr_names[attr_name]   = col
        expr_attr_values[attr_value] = _floats_to_decimal(raw.get("dati", raw))

        update_parts.append(f"{attr_name} = {attr_value}")

    if not update_parts:
        print("⚠️  Nothing to save.")
        return

    expr_attr_names["#updated_at"] = "updated_at"
    update_parts.append("#updated_at = :updated_at")

    table.update_item(
        Key={"company_code": company_code},
        UpdateExpression="SET " + ", ".join(update_parts),
        ExpressionAttributeNames=expr_attr_names,
        ExpressionAttributeValues=expr_attr_values,
    )

    print(f"✅ Saved schedules {schedules} for {company_code}")


def get_company_schedules(company_code: str, schedules: list[str]) -> dict:
    print("free return")
    table = dynamodb.Table("italy_companies")

    response = table.get_item(
        Key={"company_code": company_code}
    )

    item = response.get("Item", {})
    if not item:
        return {"success": False, "message": f"No data found for {company_code}"}

    result = {"company_code": company_code}
    for schedule in schedules:
        col = SCHEDULE_KEY_MAP.get(schedule)
        result[schedule] = item.get(col)

    return {"success": True, "data": result}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()