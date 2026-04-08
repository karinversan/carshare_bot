import hashlib
import hmac
import mimetypes
import time
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query, Response

from apps.api_service.app.core.config import settings
from apps.api_service.app.services.storage_service import StorageService, StorageServiceError

router = APIRouter(tags=["assets"])

ALLOWED_BUCKETS = {
    settings.s3_bucket_raw_images,
    settings.s3_bucket_processed_images,
    settings.s3_bucket_overlays,
    settings.s3_bucket_closeups,
    settings.s3_bucket_reports,
    settings.s3_bucket_ml_artifacts,
}


@router.api_route("/s3/{bucket}/{object_key:path}", methods=["GET", "HEAD"])
def serve_object(
    bucket: str,
    object_key: str,
    exp: int = Query(..., description="Unix timestamp when signed URL expires."),
    sig: str = Query(..., description="HMAC signature for the signed asset URL."),
):
    bucket = bucket.strip("/")
    if bucket not in ALLOWED_BUCKETS:
        raise HTTPException(status_code=404, detail="bucket not found")

    normalized_key = unquote(object_key).lstrip("/")
    if exp < int(time.time()):
        raise HTTPException(status_code=403, detail="asset URL expired")

    secret = (settings.asset_url_secret or settings.jwt_secret).encode("utf-8")
    payload = f"{bucket}\n{normalized_key}\n{exp}".encode("utf-8")
    expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        raise HTTPException(status_code=403, detail="invalid asset signature")

    try:
        payload, content_type = StorageService().get_object(bucket, normalized_key)
    except StorageServiceError as exc:
        message = str(exc).lower()
        if "not found" in message:
            raise HTTPException(status_code=404, detail="object not found") from exc
        raise HTTPException(status_code=502, detail="storage unavailable") from exc

    guessed_media_type = mimetypes.guess_type(normalized_key)[0]
    if guessed_media_type is None and "." in normalized_key:
        ext = normalized_key.rsplit(".", 1)[-1].lower()
        guessed_media_type = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
            "bmp": "image/bmp",
            "svg": "image/svg+xml",
            "avif": "image/avif",
        }.get(ext)
    return Response(
        content=payload,
        media_type=guessed_media_type or content_type or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=300"},
    )
