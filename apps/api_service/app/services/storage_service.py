import logging
from urllib.parse import quote

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from apps.api_service.app.core.config import settings

logger = logging.getLogger(__name__)


class StorageServiceError(Exception):
    """Raised when S3/MinIO operations fail."""


class StorageService:
    def __init__(self) -> None:
        common = dict(
            service_name="s3",
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self.client = boto3.client(endpoint_url=settings.s3_endpoint_url, **common)
        self._ensured_buckets: set[str] = set()

    def _ensure_bucket_once(self, bucket: str) -> None:
        if bucket in self._ensured_buckets:
            return
        self.ensure_bucket(bucket)
        self._ensured_buckets.add(bucket)

    def ensure_bucket(self, bucket: str) -> None:
        try:
            self.client.head_bucket(Bucket=bucket)
        except ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", ""))
            status_code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if error_code in {"404", "NoSuchBucket", "NotFound"} or status_code == 404:
                logger.info("Creating bucket: %s", bucket)
                self.client.create_bucket(Bucket=bucket)
            else:
                raise StorageServiceError(f"Cannot verify bucket {bucket}: {e}") from e
        except EndpointConnectionError as e:
            logger.error("Cannot connect to S3/MinIO: %s", e)
            raise StorageServiceError(f"Storage service unavailable: {e}") from e

    def put_bytes(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        self._ensure_bucket_once(bucket)
        try:
            self.client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
        except ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", ""))
            if error_code == "NoSuchBucket":
                logger.warning("Bucket %s missing on upload, creating and retrying", bucket)
                self._ensured_buckets.discard(bucket)
                self._ensure_bucket_once(bucket)
                try:
                    self.client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
                    return
                except Exception as retry_exc:
                    logger.error("Retry upload failed for %s/%s: %s", bucket, key, retry_exc)
                    raise StorageServiceError(f"Upload failed for {bucket}/{key}: {retry_exc}") from retry_exc
            logger.error("Failed to upload %s/%s: %s", bucket, key, e)
            raise StorageServiceError(f"Upload failed for {bucket}/{key}: {e}") from e
        except EndpointConnectionError as e:
            logger.error("Cannot connect to S3/MinIO: %s", e)
            raise StorageServiceError(f"Storage service unavailable: {e}") from e

    def get_object(self, bucket: str, key: str) -> tuple[bytes, str | None]:
        self._ensure_bucket_once(bucket)
        try:
            resp = self.client.get_object(Bucket=bucket, Key=key)
            return resp["Body"].read(), resp.get("ContentType")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                logger.error("Object not found: %s/%s", bucket, key)
                raise StorageServiceError(f"Object not found: {bucket}/{key}") from e
            logger.error("Failed to get %s/%s: %s", bucket, key, e)
            raise StorageServiceError(f"Download failed for {bucket}/{key}: {e}") from e
        except EndpointConnectionError as e:
            logger.error("Cannot connect to S3/MinIO: %s", e)
            raise StorageServiceError(f"Storage service unavailable: {e}") from e

    def get_bytes(self, bucket: str, key: str) -> bytes:
        data, _ = self.get_object(bucket, key)
        return data

    def delete_object(self, bucket: str, key: str | None) -> None:
        if not key:
            return
        try:
            self.client.delete_object(Bucket=bucket, Key=key)
        except ClientError as e:
            logger.warning("Failed to delete %s/%s: %s", bucket, key, e)
        except EndpointConnectionError as e:
            logger.warning("Cannot connect to S3/MinIO during delete %s/%s: %s", bucket, key, e)

    def presigned_url(self, bucket: str, key: str, expires: int = 3600) -> str:
        del expires
        endpoint = (settings.s3_external_endpoint_url or settings.s3_endpoint_url).rstrip("/")
        return f"{endpoint}/{bucket}/{quote(key, safe='/')}"


storage_service = StorageService()
