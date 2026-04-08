from __future__ import annotations

import asyncio
import hmac
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request

from apps.bot_service.app import telegram_api as tg
from apps.bot_service.app.api_client import api_client
from apps.bot_service.app.core.config import settings
from apps.bot_service.app.model_quality import (
    format_quality_report_message,
    load_latest_quality_report,
    refresh_quality_report,
)
from apps.bot_service.app.state import get_state, reset_state
from apps.bot_service.app.ui import (
    back_keyboard,
    inspection_keyboard,
    model_quality_keyboard,
    rental_message,
    restore_previous_panel,
    set_default_menu_button,
    sync_context_menu,
    sync_welcome_message,
    trip_keyboard,
    upsert_panel_message,
    vehicle_keyboard,
    web_app_button,
    inline_keyboard,
)

logger = logging.getLogger(__name__)

_polling_task: asyncio.Task | None = None
_EPHEMERAL_TEXTS = {
    "Найти авто",
    "Моя поездка",
    "Качество моделей",
    "Админка",
    "Помощь",
    "Открыть осмотр",
    "Сдать машину",
    "/status",
    "/help",
    "/admin",
    "/cancel",
}


def _is_ephemeral_user_text(text: str) -> bool:
    if not text:
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    if any(line == "/start" for line in lines):
        return False
    return all(line in _EPHEMERAL_TEXTS for line in lines)


def _with_home_button(inline_markup: dict | None) -> dict:
    rows = list((inline_markup or {}).get("inline_keyboard") or [])
    rows.append([{"text": "Вернуться в главное меню", "callback_data": "return_home"}])
    return inline_keyboard(rows)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _polling_task
    if settings.telegram_bot_token:
        await tg.set_chat_menu_button(menu_button={"type": "commands"})
    if settings.telegram_polling_enabled and settings.telegram_bot_token:
        polling_allowed = True
        webhook_info = await tg.get_webhook_info()
        webhook_url = str((webhook_info.get("result") or {}).get("url") or "").strip()
        if webhook_url:
            polling_allowed = False
            logger.warning("Webhook is active (%s) — polling disabled to avoid duplicate updates.", webhook_url)
        if polling_allowed:
            _polling_task = asyncio.create_task(_poll_updates_loop())
    yield
    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
    await tg.close_client()
    await api_client.aclose()


app = FastAPI(title="Car Inspection Bot Service", version="0.2.0", lifespan=lifespan)


async def _send_dashboard(chat_id: int, user: dict, with_photo: bool = False, notice: str | None = None, force_welcome: bool = False) -> None:
    dashboard = await api_client.get_dashboard(
        telegram_user_id=user.get("id", 0),
        username=user.get("username"),
        first_name=user.get("first_name"),
    )
    first_name = dashboard["user"]["first_name"]
    state = get_state(chat_id)
    await sync_welcome_message(chat_id, first_name, dashboard, with_photo, force_resend=force_welcome)

    active_rental = dashboard.get("active_rental")

    if active_rental:
        await sync_context_menu(chat_id, active_rental)
        state.rental_id = active_rental["rental_id"]
        state.inspection_id = active_rental.get("current_inspection_id")
        state.vehicle_id = active_rental["vehicle"]["vehicle_id"]
        text = rental_message(active_rental)
        if notice:
            text = f"{notice}\n\n{text}"
        await upsert_panel_message(chat_id, text, inline_markup=trip_keyboard(active_rental))
        return

    await set_default_menu_button(chat_id)
    state.rental_id = None
    state.inspection_id = None
    state.vehicle_id = None
    vehicle_lines = [
        f"• <b>{vehicle['title']}</b> · {vehicle['eta_min']} мин · {vehicle['subtitle']}"
        for vehicle in dashboard["available_vehicles"][:4]
    ]
    text = "Сейчас активной аренды нет.\n\nВыберите машину для начала поездки:\n" + "\n".join(vehicle_lines)
    if notice:
        text = f"{notice}\n\n{text}"
    await upsert_panel_message(chat_id, text, inline_markup=vehicle_keyboard(dashboard["available_vehicles"]))


async def _send_admin_entry(chat_id: int) -> None:
    await set_default_menu_button(chat_id)
    await upsert_panel_message(
        chat_id,
        "Админка доступна по кнопке ниже. Там можно брать кейсы в работу, смотреть совпадения pre/post и назначать ответственного.",
        inline_markup=inline_keyboard([[web_app_button("Открыть админку", settings.effective_admin_panel_url)]]),
    )


async def _send_model_quality(chat_id: int) -> None:
    report = load_latest_quality_report()
    if not report:
        ok, result_text = await refresh_quality_report()
        if not ok:
            await _show_error_panel(chat_id, result_text)
            return
        await upsert_panel_message(chat_id, result_text, inline_markup=model_quality_keyboard())
        return

    await upsert_panel_message(
        chat_id,
        format_quality_report_message(report),
        inline_markup=model_quality_keyboard(),
    )


async def _send_vehicle_picker(chat_id: int, user: dict, text: str) -> None:
    await set_default_menu_button(chat_id)
    dashboard = await api_client.get_dashboard(
        telegram_user_id=user.get("id", 0),
        username=user.get("username"),
        first_name=user.get("first_name"),
    )
    active_rental = dashboard.get("active_rental")
    if active_rental and active_rental.get("status") in {"active", "awaiting_return_inspection"}:
        await upsert_panel_message(
            chat_id,
            "Сейчас у вас уже есть активная поездка. Сначала завершите её через кнопку «Сдать машину»."
            + "\n\n"
            + rental_message(active_rental),
            inline_markup=trip_keyboard(active_rental),
        )
        return
    await upsert_panel_message(chat_id, text, inline_markup=vehicle_keyboard(dashboard["available_vehicles"]))


async def _show_error_panel(chat_id: int, text: str) -> None:
    state = get_state(chat_id)
    back_markup = back_keyboard()
    await upsert_panel_message(
        chat_id,
        text,
        inline_markup=back_markup,
        remember_previous=state.current_panel_markup != back_markup,
    )


async def _send_help_panel(chat_id: int) -> None:
    await upsert_panel_message(
        chat_id,
        "Доступные действия:\n"
        "• Найти авто — выбрать машину для поездки\n"
        "• Моя поездка — показать текущий статус аренды\n"
        "• Качество моделей — открыть сводку метрик\n"
        "• Админка — перейти в панель кейсов",
    )


async def _start_trip(chat_id: int, user: dict, vehicle_id: str) -> None:
    data = await api_client.start_trip(
        telegram_user_id=user.get("id", 0),
        username=user.get("username"),
        first_name=user.get("first_name"),
        vehicle_id=vehicle_id,
    )
    rental = data["rental"]
    state = get_state(chat_id)
    state.rental_id = rental["rental_id"]
    state.inspection_id = data.get("inspection_id")
    state.vehicle_id = vehicle_id
    created = bool(data.get("created"))
    rental_status = rental.get("status")

    if (not created) and rental_status in {"active", "awaiting_return_inspection"}:
        await upsert_panel_message(
            chat_id,
            "Сейчас у вас уже есть активная поездка. Новую машину выбрать нельзя, пока не завершите текущую аренду.\n\n"
            + rental_message(rental),
            inline_markup=trip_keyboard(rental),
        )
        return

    if data.get("inspection_id"):
        notice = "Машина выбрана. Сначала пройдите обязательный осмотр в Mini App."
        await upsert_panel_message(
            chat_id,
            notice + "\n\n" + rental_message(rental),
            inline_markup=inspection_keyboard(
                data["inspection_id"],
                "Выполнить осмотр",
                secondary_callback="choose_car",
                secondary_label="Выбрать другую машину",
            ),
        )
        return
    await upsert_panel_message(
        chat_id,
        "У вас уже есть активная поездка.\n\n" + rental_message(rental),
        inline_markup=trip_keyboard(rental),
    )


async def _start_return(chat_id: int, user: dict, rental_id: str) -> None:
    data = await api_client.start_return(
        trip_id=rental_id,
        telegram_user_id=user.get("id", 0),
        username=user.get("username"),
        first_name=user.get("first_name"),
    )
    rental = data["rental"]
    state = get_state(chat_id)
    state.rental_id = rental["rental_id"]
    state.inspection_id = data["inspection_id"]
    await upsert_panel_message(
        chat_id,
        "Чтобы завершить аренду, нужен финальный осмотр. Откройте Mini App и загрузите обязательные фото сдачи.",
        inline_markup=inspection_keyboard(
            data["inspection_id"],
            "Выполнить осмотр сдачи",
            secondary_callback="dashboard",
            secondary_label="Назад к поездке",
        ),
    )


async def _cancel_pending_trip(chat_id: int, rental_id: str) -> None:
    await api_client.cancel_trip(rental_id)
    reset_state(chat_id)
    await set_default_menu_button(chat_id)


async def _handle_web_app_data(chat_id: int, payload_raw: str) -> None:
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        await _show_error_panel(chat_id, "Данные из Mini App не удалось разобрать.")
        return

    if payload.get("action") != "inspection_finalized":
        return

    inspection_id = payload.get("inspection_id")
    if not inspection_id:
        return
    context = await api_client.get_inspection_context(inspection_id)
    rental = context.get("rental")
    if not rental:
        await _show_error_panel(chat_id, "Осмотр завершён. Данные сохранены.")
        return

    if rental["status"] == "active":
        await set_default_menu_button(chat_id)
        trip_vehicle = rental.get("vehicle", {}).get("title") or "машина"
        remaining_min = rental.get("planned_duration_min")
        route_label = rental.get("route_label")
        active_text = f"Осмотр завершён. Приятной поездки на {trip_vehicle}."
        if remaining_min:
            active_text += f"\nОсталось ехать: примерно {remaining_min} мин."
        if route_label:
            active_text += f"\nМаршрут: {route_label}."
        await upsert_panel_message(
            chat_id,
            active_text,
            inline_markup=_with_home_button(trip_keyboard(rental)),
        )
        return

    comparison_status = payload.get("comparison_status")
    vehicle = rental.get("vehicle", {}).get("title") or "машина"
    duration_min = rental.get("planned_duration_min")
    follow_up = f"Поездка на {vehicle} завершена."
    if duration_min:
        follow_up += f"\nПлановая длительность: {duration_min} мин."
    if comparison_status == "admin_case_created":
        follow_up += "\nОткрыт спор: кейс отправлен на админ-проверку."
    elif comparison_status == "possible_new_damage":
        follow_up += "\nОткрыта проверка: есть подозрение на новые повреждения."
    else:
        follow_up += "\nВсего доброго."
    await set_default_menu_button(chat_id)
    await upsert_panel_message(chat_id, follow_up, inline_markup=_with_home_button(None))


async def _handle_internal_finalize_event(chat_id: int, inspection_id: str, comparison_status: str | None = None) -> None:
    payload = {
        "action": "inspection_finalized",
        "inspection_id": inspection_id,
        "comparison_status": comparison_status,
    }
    await _handle_web_app_data(chat_id, json.dumps(payload))


async def _poll_updates_loop() -> None:
    offset: int | None = None
    while True:
        try:
            data = await tg.get_updates(offset=offset, timeout=settings.telegram_polling_timeout_sec)
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                await process_update(update)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Polling loop failed: %s", exc)
            await asyncio.sleep(2)


async def _delete_user_command_message(message: dict) -> None:
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    if not chat_id or not message_id:
        return
    try:
        await tg.delete_message(chat_id, message_id)
    except Exception:
        logger.debug("Unable to delete user command message chat=%s message=%s", chat_id, message_id)


async def _cleanup_stale_callback_message(callback_query: dict) -> None:
    message = callback_query.get("message") or {}
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    if not chat_id or not message_id:
        return
    state = get_state(chat_id)
    if message_id in {state.panel_message_id, state.welcome_message_id}:
        return
    await tg.delete_message(chat_id, message_id)


async def handle_callback(callback_query: dict) -> None:
    data = callback_query.get("data", "")
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    user = callback_query.get("from", {})
    cq_id = callback_query.get("id")
    if cq_id:
        await tg.answer_callback_query(cq_id)
    if not chat_id:
        return
    await _cleanup_stale_callback_message(callback_query)

    if data.startswith("rent:"):
        await _start_trip(chat_id, user, data.split(":", 1)[1])
        return
    if data.startswith("return:"):
        await _start_return(chat_id, user, data.split(":", 1)[1])
        return
    if data.startswith("cancel:"):
        await _cancel_pending_trip(chat_id, data.split(":", 1)[1])
        await _send_dashboard(chat_id, user, notice="Машина снята с выбора.")
        return
    if data == "choose_car":
        await _send_vehicle_picker(chat_id, user, "Выберите другую машину. Текущий незавершённый выбор будет заменён.")
        return
    if data == "dashboard":
        await _send_dashboard(chat_id, user)
        return
    if data == "model_quality_refresh":
        ok, result_text = await refresh_quality_report()
        if not ok:
            await _show_error_panel(chat_id, result_text)
            return
        await upsert_panel_message(chat_id, result_text, inline_markup=model_quality_keyboard())
        return
    if data == "panel_back":
        restored = await restore_previous_panel(chat_id)
        if not restored:
            await _send_dashboard(chat_id, user)
        return
    if data == "return_home":
        state = get_state(chat_id)
        old_panel = state.panel_message_id
        old_welcome = state.welcome_message_id
        if old_panel:
            await tg.delete_message(chat_id, old_panel)
        if old_welcome:
            await tg.delete_message(chat_id, old_welcome)
        reset_state(chat_id)
        state = get_state(chat_id)
        state.previous_panel_text = None
        state.previous_panel_markup = None
        await _send_dashboard(chat_id, user, with_photo=True, force_welcome=True)
        return


async def process_update(update: dict) -> None:
    if "callback_query" in update:
        await handle_callback(update["callback_query"])
        return

    message = update.get("message") or {}
    chat_id = message.get("chat", {}).get("id")
    user = message.get("from") or {}
    text = (message.get("text") or "").strip()
    if not chat_id:
        return

    if message.get("web_app_data", {}).get("data"):
        await _handle_web_app_data(chat_id, message["web_app_data"]["data"])
        return

    should_delete_user_message = True
    try:
        if text == "/start":
            await _send_dashboard(
                chat_id,
                user,
                with_photo=True,
                force_welcome=False,
            )
            return
        if text in {"/help", "Помощь"}:
            await _send_help_panel(chat_id)
            return
        if text in {"/status", "Моя поездка"}:
            await _send_dashboard(chat_id, user)
            return
        if text == "Найти авто":
            await _send_vehicle_picker(
                chat_id,
                user,
                "Выберите автомобиль. Если у вас уже есть незавершённый выбор, он будет заменён новым.",
            )
            return
        if text in {"Админка", "/admin"}:
            await _send_admin_entry(chat_id)
            return
        if text == "Качество моделей":
            await _send_model_quality(chat_id)
            return
        if text == "Открыть осмотр":
            await _show_error_panel(chat_id, "Открывать осмотр нужно кнопкой в карточке поездки.")
            return
        if text == "Сдать машину":
            await _show_error_panel(chat_id, "Сдача машины доступна кнопкой в карточке активной поездки.")
            return
        if text == "/cancel":
            reset_state(chat_id)
            await _show_error_panel(chat_id, "Локальное состояние бота очищено.")
            return

        await _show_error_panel(
            chat_id,
            "Используйте кнопки ниже: выбрать авто, посмотреть поездку или перейти в админку.",
        )
    except Exception:
        should_delete_user_message = False
        logger.exception("Failed to process update chat=%s text=%r", chat_id, text)
        try:
            await _show_error_panel(
                chat_id,
                "Не удалось обработать действие. Попробуйте ещё раз.",
            )
        except Exception:
            logger.exception("Failed to show fallback error panel chat=%s", chat_id)
    finally:
        if should_delete_user_message and _is_ephemeral_user_text(text):
            await _delete_user_command_message(message)


@app.get("/health")
def health():
    return {"ok": True, "service": "bot-service"}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if settings.telegram_webhook_secret:
        if not x_telegram_bot_api_secret_token:
            raise HTTPException(status_code=401, detail="Telegram webhook secret required")
        if not hmac.compare_digest(x_telegram_bot_api_secret_token, settings.telegram_webhook_secret):
            logger.warning("Rejected Telegram webhook with invalid secret.")
            raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    update = await request.json()
    await process_update(update)
    return {"ok": True}


@app.post("/internal/inspection-finalized")
async def internal_inspection_finalized(
    request: Request,
    x_internal_service_token: str | None = Header(default=None),
):
    if not x_internal_service_token:
        raise HTTPException(status_code=401, detail="Internal service token required")
    if not hmac.compare_digest(x_internal_service_token, settings.internal_service_token):
        raise HTTPException(status_code=403, detail="Invalid internal service token")
    body = await request.json()
    chat_id = int(body.get("chat_id") or 0)
    inspection_id = str(body.get("inspection_id") or "").strip()
    comparison_status = body.get("comparison_status")
    if not chat_id or not inspection_id:
        return {"ok": False, "error": "chat_id and inspection_id are required"}
    try:
        await _handle_internal_finalize_event(chat_id, inspection_id, comparison_status)
        return {"ok": True}
    except Exception as exc:
        logger.exception("Internal finalize event failed chat=%s inspection=%s", chat_id, inspection_id)
        return {"ok": False, "error": str(exc)}
