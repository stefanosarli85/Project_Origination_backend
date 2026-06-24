import boto3
import os
from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv()

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

TABLE_NAME = "UserAccounts"

dynamodb = boto3.resource(
    "dynamodb",
    region_name="ap-south-1",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

def create_table():
    try:
        existing_tables = dynamodb.meta.client.list_tables()["TableNames"]

        if TABLE_NAME in existing_tables:
            print(f"Table '{TABLE_NAME}' already exists")
            return

        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {
                    "AttributeName": "email",
                    "KeyType": "HASH"
                }
            ],
            AttributeDefinitions=[
                {
                    "AttributeName": "email",
                    "AttributeType": "S"
                }
            ],
            BillingMode="PAY_PER_REQUEST"
        )

        print("Creating table...")
        table.wait_until_exists()
        print(f"Table '{TABLE_NAME}' created successfully")

    except ClientError as e:
        print("Error creating table:", e)



from datetime import datetime


def get_table():
    return dynamodb.Table(TABLE_NAME)


def get_user_by_email(email: str):
    table = get_table()

    response = table.get_item(
        Key={
            "email": email
        }
    )

    return response.get("Item")


def create_user(
        email: str,
        name: str,
        password_hash: str
):
    table = get_table()

    item = {
        "email": email,
        "name": name,
        "password_hash": password_hash,
        "created_at": datetime.utcnow().isoformat(),
        "is_active": True
    }

    table.put_item(Item=item)

    return item


def update_password(
        email: str,
        password_hash: str
):
    table = get_table()

    table.update_item(
        Key={
            "email": email
        },
        UpdateExpression="SET password_hash = :p",
        ExpressionAttributeValues={
            ":p": password_hash
        }
    )


def delete_user(email: str):
    table = get_table()

    table.delete_item(
        Key={
            "email": email
        }
    )


def user_exists(email: str) -> bool:
    return get_user_by_email(email) is not None