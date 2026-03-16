"""HTTP client for the main API service."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.bot_service.app.core.config import settings

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self):
        self.base_url = settings.effective_api_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=45.0)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        client = await self._get_client()
        tried: list[str] = []
        base_candidates: list[str] = [
            self.base_url,
            "http://api:8000",
            "http://api-service:8000",
            "http://infra-api-1:8000",
            "http://127.0.0.1:8100",
            "http://localhost:8100",
            "http://host.docker.internal:8100",
        ]

        for base in base_candidates:
            base = base.rstrip("/")
            if base in tried:
                continue
            tried.append(base)
            try:
                resp = await client.request(method, f"{base}{path}", **kwargs)
                resp.raise_for_status()
                body = resp.json()
                if base != self.base_url:
                    logger.warning("API base URL fallback: %s -> %s", self.base_url, base)
                    self.base_url = base
                return body.get("data", body)
            except httpx.ConnectError:
                logger.warning("API connect failed via %s", base)
                continue

        # Если дошли сюда — все варианты недоступны. Повторяем исходное поведение:
        # бросаем исключение последней попытки через исходный URL.
        resp = await client.request(method, f"{self.base_url}{path}", **kwargs)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def create_inspection(
        self,
        vehicle_id: str,
        inspection_type: str,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/inspections",
            json={
                "vehicle_id": vehicle_id,
                "inspection_type": inspection_type,
                "user_telegram_id": telegram_user_id,
                "username": username,
                "first_name": first_name,
            },
        )

    async def upload_image(
        self,
        inspection_id: str,
        file_bytes: bytes,
        filename: str,
        image_type: str,
        slot_code: str,
        capture_order: int = 1,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/inspections/{inspection_id}/images",
            files={"file": (filename, file_bytes, "image/jpeg")},
            data={
                "image_type": image_type,
                "slot_code": slot_code,
                "capture_order": str(capture_order),
            },
        )

    async def run_initial_checks(
        self, inspection_id: str, image_id: str, expected_slot: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/inspections/{inspection_id}/run-initial-checks",
            json={"image_id": image_id, "expected_slot": expected_slot},
        )

    async def run_damage_inference(self, inspection_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/inspections/{inspection_id}/run-damage-inference")

    async def finalize_inspection(self, inspection_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/inspections/{inspection_id}/finalize",
            json={"photos_review_confirmed": True},
        )

    async def get_inspection(self, inspection_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/inspections/{inspection_id}")

    async def get_dashboard(self, telegram_user_id: int, username: str | None, first_name: str | None) -> dict[str, Any]:
        params = {"telegram_user_id": telegram_user_id}
        if username:
            params["username"] = username
        if first_name:
            params["first_name"] = first_name
        return await self._request("GET", "/mobile/dashboard", params=params)

    async def start_trip(self, telegram_user_id: int, username: str | None, first_name: str | None, vehicle_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/mobile/trips/start",
            json={
                "telegram_user_id": telegram_user_id,
                "username": username,
                "first_name": first_name,
                "vehicle_id": vehicle_id,
            },
        )

    async def start_return(self, trip_id: str, telegram_user_id: int, username: str | None, first_name: str | None) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/mobile/trips/{trip_id}/return",
            json={
                "telegram_user_id": telegram_user_id,
                "username": username,
                "first_name": first_name,
            },
        )

    async def cancel_trip(self, trip_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/mobile/trips/{trip_id}/cancel")

    async def get_inspection_context(self, inspection_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/mobile/inspections/{inspection_id}/context")


api_client = APIClient()
