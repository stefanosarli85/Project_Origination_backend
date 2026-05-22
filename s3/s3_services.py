import boto3
import os
import json
import uuid

# =========================
# ENV VARS (works locally + Docker)
# =========================
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
REGION = os.environ.get("AWS_REGION", "ap-south-1")

print("S3 KEY LOADED:", bool(AWS_ACCESS_KEY_ID), bool(AWS_SECRET_ACCESS_KEY), "REGION:", REGION)

# =========================
# S3 CLIENT
# =========================
s3 = boto3.client(
    "s3",
    region_name=REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

BUCKET_NAME = "italy-companies-financial-documents"


# =========================
# CREATE BUCKET (SAFE)
# =========================
def create_bucket_if_not_exists():
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        print("✅ Bucket already exists")
        return
    except Exception:
        pass

    try:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={"LocationConstraint": REGION}
            )
        print("✅ Bucket created")
    except Exception as e:
        print("❌ Bucket error:", e)


# =========================
# MAKE BUCKET PUBLIC
# =========================
def make_bucket_public():
    try:
        s3.put_public_access_block(
            Bucket=BUCKET_NAME,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False
            }
        )

        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "PublicRead",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{BUCKET_NAME}/*"
            }]
        }

        s3.put_bucket_policy(
            Bucket=BUCKET_NAME,
            Policy=json.dumps(policy)
        )
        print("✅ Bucket made public")
    except Exception as e:
        print("❌ Policy error:", e)


# =========================
# UPLOAD FILE
# =========================
def upload_bytes_to_s3(
    file_bytes: bytes,
    bucket_name: str,
    folder: str = "uploads",
    file_name: str = None,
    content_type: str = "application/zip"
):
    if not file_name:
        file_name = f"{uuid.uuid4()}.zip"

    s3_key = f"{folder}/{file_name}"

    s3.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=file_bytes,
        ContentType=content_type
    )

    url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"

    return {
        "file_name": file_name,
        "s3_key": s3_key,
        "url": url
    }