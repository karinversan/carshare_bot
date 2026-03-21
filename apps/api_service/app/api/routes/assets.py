import mimetypes
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Response

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
def serve_object(bucket: str, object_key: str):
    bucket = bucket.strip("/")
    if bucket not in ALLOWED_BUCKETS:
        raise HTTPException(status_code=404, detail="bucket not found")

    normalized_key = unquote(object_key).lstrip("/")
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
