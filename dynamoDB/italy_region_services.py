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

NON_PERSISTENT_SCHEDULES = {"85"}

def check_schedules_availability(company_code: str, schedules: list[str]) -> list[dict]:
    table = dynamodb.Table("italy_companies")

    response = table.get_item(
        Key={"company_code": company_code}
    )

    item = response.get("Item", {})

    result = []

    for schedule in schedules:

        # Always fetch these from API
        if schedule in NON_PERSISTENT_SCHEDULES:
            result.append({
                "schedule": schedule,
                "is_data_available": False
            })
            continue

        col = SCHEDULE_KEY_MAP.get(schedule)

        result.append({
            "schedule": schedule,
            "is_data_available": (
                col in item and item[col] is not None
            )
        })

    return result


def save_company_schedules(data: dict, schedules: list[str]):
    table = dynamodb.Table("italy_companies")

    company_code = data.get("cf")
    schede = data.get("schede", {})

    update_parts = []
    expr_attr_names = {}
    expr_attr_values = {
        ":updated_at": _now()
    }

    for schedule in schedules:

        # Never persist restricted schedules
        if schedule in NON_PERSISTENT_SCHEDULES:
            print(
                f"⚠️ Schedule {schedule} is non-persistent. Skipping save."
            )
            continue

        col = SCHEDULE_KEY_MAP.get(schedule)

        if col is None:
            print(f"⚠️ Unknown schedule '{schedule}', skipping.")
            continue

        raw = schede.get(schedule)

        if raw is None:
            print(
                f"⚠️ Schedule '{schedule}' not found in API response."
            )
            continue

        attr_name = f"#col_{col}"
        attr_value = f":val_{col}"

        expr_attr_names[attr_name] = col
        expr_attr_values[attr_value] = _floats_to_decimal(
            raw.get("dati", raw)
        )

        update_parts.append(
            f"{attr_name} = {attr_value}"
        )

    if not update_parts:
        print("⚠️ Nothing to save.")
        return

    expr_attr_names["#updated_at"] = "updated_at"
    update_parts.append("#updated_at = :updated_at")

    table.update_item(
        Key={"company_code": company_code},
        UpdateExpression="SET " + ", ".join(update_parts),
        ExpressionAttributeNames=expr_attr_names,
        ExpressionAttributeValues=expr_attr_values,
    )

    print(
        f"✅ Saved schedules "
        f"{[s for s in schedules if s not in NON_PERSISTENT_SCHEDULES]} "
        f"for {company_code}"
    )


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


schedule_table = dynamodb.Table("italy_companies")


SCHEDULE_COLUMNS = ["ANA", "CR", "PROT", "S05", "S10", "S20", "S30", "S40", "S50", "S60", "S70"]


def get_company_schedule_status(company_code: str):
    """
    Returns whether each schedule column exists (non-null) for a given company_code.
    """

    response = schedule_table.get_item(
        Key={
            "company_code": company_code
        }
    )

    item = response.get("Item", {})

    if not item:
        return {company_code: {k: False for k in SCHEDULE_COLUMNS}}

    result = {}

    for col in SCHEDULE_COLUMNS:
        value = item.get(col)

        # True if data exists, False otherwise
        result[col] = value is not None

    return {
        company_code: result
    }


def is_report_available(company_code):
    try:
        response = table.scan(
            FilterExpression=Attr("company_id").eq(str(company_code))
        )

        return {
            "isReportAvailable": len(response.get("Items", [])) > 0
        }

    except Exception as e:
        print(f"Error checking report availability: {e}")
        return {"isReportAvailable": False}


kyc_request_table = dynamodb.Table("italy_kyc_request")


def save_kyc_request_person(request_id, first_name, last_name, tax_code):
    try:
        kyc_request_table.put_item(
            Item={
                "request_id": request_id,
                "first_name": first_name,
                "last_name": last_name,
                "tax_code": tax_code
            }
        )

        return {
            "success": True,
            "request_id": request_id
        }

    except Exception as e:
        print("Error saving KYC request:", str(e))
        return {
            "success": False,
            "error": str(e)
        }


def get_all_kyc_requests():
    try:
        items = []

        response = kyc_request_table.scan()
        items.extend(response.get("Items", []))

        while "LastEvaluatedKey" in response:
            response = kyc_request_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response.get("Items", []))

        return items

    except Exception as e:
        print("Error fetching KYC requests:", str(e))
        return []



company_kyc_request_table = dynamodb.Table("italy_company_kyc_request")


def create_company_kyc_request_table():
    try:
        table = dynamodb.create_table(
            TableName="italy_company_kyc_request",
            KeySchema=[
                {
                    "AttributeName": "request_id",
                    "KeyType": "HASH"
                }
            ],
            AttributeDefinitions=[
                {
                    "AttributeName": "request_id",
                    "AttributeType": "S"
                }
            ],
            BillingMode="PAY_PER_REQUEST"
        )

        table.wait_until_exists()
        print("Table created successfully")

    except Exception as e:
        print(f"Error creating table: {e}")


def save_company_kyc_request(
    request_id: str,
    company_name: str,
    vat_code: str,
    tax_code: str = None
):
    try:
        item = {
            "request_id": request_id,
            "company_name": company_name,
            "vat_code": vat_code,
            "tax_code": tax_code,
            "created_at": datetime.utcnow().isoformat()
        }

        company_kyc_request_table.put_item(Item=item)

        return {
            "success": True,
            "request_id": request_id
        }

    except Exception as e:
        print(f"Error saving request: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_company_kyc_request():
    try:
        response = company_kyc_request_table.scan()

        return response.get("Items", [])

    except Exception as e:
        print(f"Error fetching requests: {e}")
        return []

# Global kyc functions #

def create_global_kyc_request_individual_table():
    table_name = "global_kyc_request_individual"

    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    "AttributeName": "request_id",
                    "KeyType": "HASH",
                }
            ],
            AttributeDefinitions=[
                {
                    "AttributeName": "request_id",
                    "AttributeType": "S",
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        table.wait_until_exists()
        return table

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]

        if error_code == "ResourceInUseException":
            return dynamodb.Table(table_name)

        raise


def create_global_kyc_request_company_table():
    table_name = "global_kyc_request_company"

    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    "AttributeName": "request_id",
                    "KeyType": "HASH",
                }
            ],
            AttributeDefinitions=[
                {
                    "AttributeName": "request_id",
                    "AttributeType": "S",
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        table.wait_until_exists()
        return table

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]

        if error_code == "ResourceInUseException":
            return dynamodb.Table(table_name)

        raise

from decimal import Decimal


individual_table = dynamodb.Table("global_kyc_request_individual")
company_table = dynamodb.Table("global_kyc_request_company")


def _convert_to_dynamodb(value):
    if isinstance(value, float):
        return Decimal(str(value))

    if isinstance(value, dict):
        return {
            key: _convert_to_dynamodb(val)
            for key, val in value.items()
        }

    if isinstance(value, list):
        return [_convert_to_dynamodb(item) for item in value]

    return value


def save_global_kyc_request_individual_table(response: dict) -> dict:
    data = response["data"]

    item = {
        "request_id": data["id"],
        "entity_type": "I",
        "first_name": data["query"].get("firstName"),
        "last_name": data["query"].get("lastName"),
        "birth_date": data["query"].get("birthDate"),
        "state": data.get("state"),
        "creation_timestamp": data.get("creationTimestamp"),
        "last_update_timestamp": data.get("lastUpdateTimestamp"),
        "entities_count": len(data.get("entities", [])),
        "evidences_count": len(data.get("evidences", [])),
        "raw_response": _convert_to_dynamodb(data),
    }

    individual_table.put_item(Item=item)

    return item


def save_global_kyc_request_company_table(response: dict) -> dict:
    data = response["data"]

    item = {
        "request_id": data["id"],
        "entity_type": "L",
        "company_name": data["query"].get("name"),
        "state": data.get("state"),
        "creation_timestamp": data.get("creationTimestamp"),
        "last_update_timestamp": data.get("lastUpdateTimestamp"),
        "entities_count": len(data.get("entities", [])),
        "evidences_count": len(data.get("evidences", [])),
        "raw_response": _convert_to_dynamodb(data),
    }

    company_table.put_item(Item=item)

    return item

from decimal import Decimal


def update_global_kyc_request(
    response: dict,
    entity_type: str,
) -> dict:
    data = response["data"]

    table = (
        individual_table
        if entity_type == "I"
        else company_table
    )

    item = {
        ":state": data.get("state"),
        ":last_update_timestamp": data.get("lastUpdateTimestamp"),
        ":entities_count": len(data.get("entities", [])),
        ":evidences_count": len(data.get("evidences", [])),
        ":raw_response": _convert_to_dynamodb(data),
    }

    response = table.update_item(
        Key={
            "request_id": data["id"],
        },
        UpdateExpression="""
            SET
                #state = :state,
                last_update_timestamp = :last_update_timestamp,
                entities_count = :entities_count,
                evidences_count = :evidences_count,
                raw_response = :raw_response
        """,
        ExpressionAttributeNames={
            "#state": "state",
        },
        ExpressionAttributeValues=item,
        ReturnValues="ALL_NEW",
    )

    return response["Attributes"]