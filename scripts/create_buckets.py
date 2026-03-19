import os
import boto3
from botocore.client import Config

endpoint = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
client = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=os.getenv("S3_ACCESS_KEY", "minioadmin"),
    aws_secret_access_key=os.getenv("S3_SECRET_KEY", "minioadmin"),
    region_name=os.getenv("S3_REGION", "us-east-1"),
    config=Config(signature_version="s3v4"),
)

buckets = [
    os.getenv("S3_BUCKET_RAW_IMAGES", "raw-images"),
    os.getenv("S3_BUCKET_PROCESSED_IMAGES", "processed-images"),
    os.getenv("S3_BUCKET_OVERLAYS", "overlays"),
    os.getenv("S3_BUCKET_CLOSEUPS", "closeups"),
    os.getenv("S3_BUCKET_REPORTS", "reports"),
    os.getenv("S3_BUCKET_ML_ARTIFACTS", "ml-artifacts"),
]

for bucket in buckets:
    try:
        client.head_bucket(Bucket=bucket)
        print("exists", bucket)
    except Exception:
        client.create_bucket(Bucket=bucket)
        print("created", bucket)
