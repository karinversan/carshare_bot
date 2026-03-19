from __future__ import annotations

import os

from fastapi import FastAPI, Request, Response
import httpx
import json


FRONTEND_BASE = os.getenv("MINIAPP_FRONTEND_BASE", "http://127.0.0.1:5173")
ADMIN_BASE = os.getenv("ADMIN_FRONTEND_BASE", "http://127.0.0.1:5174")
API_BASE = os.getenv("EDGE_API_BASE", "http://127.0.0.1:8100")
BOT_BASE = os.getenv("EDGE_BOT_BASE", "http://127.0.0.1:8001")

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
}

app = FastAPI(title="Local Edge Proxy")


def _target(path: str) -> tuple[str, str]:
    if path.startswith("/telegram/webhook"):
        return BOT_BASE, path
    if path.startswith("/api"):
        stripped = path[4:] or "/"
        return API_BASE, stripped
    if path.startswith("/admin"):
        # Keep "/admin" prefix for Vite base path routing and asset URLs.
        return ADMIN_BASE, path
    if path.startswith("/s3"):
        return API_BASE, path
    return FRONTEND_BASE, path


def _response_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy(path: str, request: Request) -> Response:
    path = f"/{path}"
    upstream, upstream_path = _target(path)
    query = request.url.query
    upstream_url = f"{upstream}{upstream_path}"
    if query:
        upstream_url = f"{upstream_url}?{query}"

    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            upstream_response = await client.request(
                request.method,
                upstream_url,
                content=body,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        payload = {
            "detail": {
                "code": "upstream_unavailable",
                "message": f"Upstream unavailable: {upstream}",
                "path": upstream_path,
            }
        }
        return Response(
            content=json.dumps(payload, ensure_ascii=False),
            status_code=503,
            media_type="application/json",
        )

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=_response_headers(upstream_response.headers),
    )
