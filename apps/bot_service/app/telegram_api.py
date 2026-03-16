"""Thin wrapper around the Telegram Bot API (HTTP calls)."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from apps.bot_service.app.core.config import settings

logger = logging.getLogger(__name__)

_BOT_API = "https://api.telegram.org/bot{token}/{method}"
_CLIENT: httpx.AsyncClient | None = None


async def _client() -> httpx.AsyncClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = httpx.AsyncClient(timeout=30.0)
    return _CLIENT


async def close_client() -> None:
    global _CLIENT
    if _CLIENT is not None:
        await _CLIENT.aclose()
        _CLIENT = None


async def _call(method: str, payload: dict[str, Any]) -> dict:
    if not settings.telegram_bot_token:
        logger.warning("Telegram bot token not configured — skipping API call")
        return {}
    url = _BOT_API.format(token=settings.telegram_bot_token, method=method)
    try:
        client = await _client()
        resp = await client.post(url, json=payload)
        data = resp.json()
        if not data.get("ok"):
            logger.error("Telegram API error for %s: %s", method, data)
        return data
    except Exception as exc:
        logger.error("Telegram API call %s failed: %s", method, exc)
        return {}


async def send_message(
    chat_id: int,
    text: str,
    reply_markup: dict | None = None,
    parse_mode: str = "HTML",
) -> dict:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _call("sendMessage", payload)


async def edit_message_text(
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: dict | None = None,
    parse_mode: str = "HTML",
) -> dict:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _call("editMessageText", payload)


async def edit_message_caption(
    chat_id: int,
    message_id: int,
    caption: str,
    reply_markup: dict | None = None,
    parse_mode: str = "HTML",
) -> dict:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "caption": caption,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _call("editMessageCaption", payload)


async def answer_callback_query(callback_query_id: str, text: str = "") -> dict:
    return await _call("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})


async def delete_message(chat_id: int, message_id: int) -> dict:
    return await _call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})


async def get_file(file_id: str) -> dict:
    return await _call("getFile", {"file_id": file_id})


async def download_file(file_path: str) -> bytes:
    """Download a file from Telegram servers."""
    url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
    client = await _client()
    resp = await client.get(url, timeout=60.0)
    resp.raise_for_status()
    return resp.content


async def send_photo(
    chat_id: int,
    photo: bytes | str,
    caption: str,
    reply_markup: dict | None = None,
    parse_mode: str = "HTML",
    filename: str = "card.png",
) -> dict:
    if not settings.telegram_bot_token:
        return {}
    url = _BOT_API.format(token=settings.telegram_bot_token, method="sendPhoto")
    client = await _client()
    data: dict[str, Any] = {
        "chat_id": str(chat_id),
        "caption": caption,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    if isinstance(photo, bytes):
        files = {"photo": (filename, photo, "image/png")}
        resp = await client.post(url, data=data, files=files)
    else:
        data["photo"] = photo
        resp = await client.post(url, data=data)
    body = resp.json()
    if not body.get("ok"):
        logger.error("Telegram API error for sendPhoto: %s", body)
    return body


async def get_updates(offset: int | None = None, timeout: int = 20) -> dict:
    payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
    if offset is not None:
        payload["offset"] = offset
    return await _call("getUpdates", payload)


async def set_chat_menu_button(chat_id: int | None = None, menu_button: dict[str, Any] | None = None) -> dict:
    payload: dict[str, Any] = {}
    if chat_id is not None:
        payload["chat_id"] = chat_id
    if menu_button is not None:
        payload["menu_button"] = menu_button
    return await _call("setChatMenuButton", payload)
