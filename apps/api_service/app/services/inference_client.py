import logging

import httpx

from apps.api_service.app.core.config import settings

logger = logging.getLogger(__name__)


class InferenceServiceError(Exception):
    """Raised when the inference service returns an error or is unreachable."""


class InferenceClient:
    def __init__(self):
        self.base_url = settings.inference_service_url.rstrip("/")

    def _base_candidates(self) -> list[str]:
        candidates: list[str] = []
        if settings.app_env == "dev":
            candidates.extend(
                [
                    "http://host.docker.internal:8011",
                    "http://127.0.0.1:8011",
                    "http://localhost:8011",
                ]
            )
        candidates.extend(
            [
                self.base_url,
                "http://inference-service:8010",
                "http://infra-inference-service-1:8010",
            ]
        )
        unique: list[str] = []
        for base in candidates:
            base = base.rstrip("/")
            if base and base not in unique:
                unique.append(base)
        return unique

    def _post_with_fallback(self, path: str, *, files: dict, data: dict) -> dict:
        last_connect_exc: Exception | None = None
        last_http_error: Exception | None = None
        with httpx.Client(timeout=60.0) as client:
            for base in self._base_candidates():
                url = f"{base}{path}"
                try:
                    resp = client.post(url, files=files, data=data)
                    if resp.status_code >= 500:
                        logger.warning(
                            "Inference upstream %s returned %s, trying fallback",
                            base,
                            resp.status_code,
                        )
                        last_http_error = httpx.HTTPStatusError(
                            f"Server error from {base}: {resp.status_code}",
                            request=resp.request,
                            response=resp,
                        )
                        continue
                    resp.raise_for_status()
                    if base != self.base_url:
                        logger.warning("Inference base URL fallback: %s -> %s", self.base_url, base)
                        self.base_url = base
                    return resp.json()
                except (httpx.ConnectError, httpx.TimeoutException) as exc:
                    logger.warning("Inference connect/timeout via %s: %s", base, exc)
                    last_connect_exc = exc
                    continue
                except httpx.HTTPStatusError as exc:
                    logger.error("Inference service HTTP error %s from %s: %s", exc.response.status_code, base, exc.response.text[:500])
                    raise InferenceServiceError(
                        f"Inference service returned HTTP {exc.response.status_code}"
                    ) from exc

        if last_http_error:
            raise InferenceServiceError(str(last_http_error)) from last_http_error
        if last_connect_exc:
            raise InferenceServiceError(f"Inference service unavailable: {last_connect_exc}") from last_connect_exc
        raise InferenceServiceError("Inference service unavailable")

    def quality_view_predict(self, image_bytes: bytes, filename: str, expected_slot: str) -> dict:
        files = {"file": (filename, image_bytes, "image/jpeg")}
        data = {"expected_slot": expected_slot}
        try:
            return self._post_with_fallback("/v1/quality-view/predict", files=files, data=data)
        except InferenceServiceError:
            raise

    def damage_seg_predict(self, image_bytes: bytes, filename: str, slot_code: str) -> dict:
        files = {"file": (filename, image_bytes, "image/jpeg")}
        data = {"slot_code": slot_code}
        try:
            return self._post_with_fallback("/v1/damage-seg/predict", files=files, data=data)
        except InferenceServiceError:
            raise


inference_client = InferenceClient()
