from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

from apps.bot_service.app import telegram_api as tg
from apps.bot_service.app.core.config import settings
from apps.bot_service.app.state import get_state


def reply_keyboard() -> dict:
    return {
        "keyboard": [
            [{"text": "Найти авто"}, {"text": "Моя поездка"}],
            [{"text": "Качество моделей"}],
            [{"text": "Админка"}, {"text": "Помощь"}],
        ],
        "resize_keyboard": True,
    }


def inline_keyboard(rows: list[list[dict]]) -> dict:
    return {"inline_keyboard": rows}


def web_app_button(text: str, url: str) -> dict:
    return {"text": text, "web_app": {"url": url}}


def callback_button(text: str, callback_data: str) -> dict:
    return {"text": text, "callback_data": callback_data}


def vehicle_keyboard(vehicles: list[dict]) -> dict:
    rows = [
        [{"text": f"{vehicle['title']} · {vehicle['eta_min']} мин", "callback_data": f"rent:{vehicle['vehicle_id']}"}]
        for vehicle in vehicles[:4]
    ]
    return inline_keyboard(rows)


def inspection_keyboard(
    inspection_id: str,
    button_text: str,
    secondary_callback: str | None = None,
    secondary_label: str | None = None,
) -> dict:
    rows = [[web_app_button(button_text, f"{settings.miniapp_base_url}?inspection_id={inspection_id}")]]
    if secondary_callback and secondary_label:
        rows.append([callback_button(secondary_label, secondary_callback)])
    return inline_keyboard(rows)


def trip_keyboard(rental: dict) -> dict:
    rows: list[list[dict]] = []
    if rental.get("current_inspection_id"):
        rows.append([web_app_button(rental.get("next_action_label", "Открыть осмотр"), f"{settings.miniapp_base_url}?inspection_id={rental['current_inspection_id']}")])
        if rental.get("status") == "awaiting_pickup_inspection":
            rows.append([callback_button("Выбрать другую машину", "choose_car")])
            rows.append([callback_button("Отменить выбор", f"cancel:{rental['rental_id']}")])
    elif rental.get("next_action") == "start_return":
        rows.append([callback_button("Сдать машину", f"return:{rental['rental_id']}")])
    return inline_keyboard(rows)


def back_keyboard() -> dict:
    return inline_keyboard([[callback_button("Назад", "panel_back")]])


def model_quality_keyboard() -> dict:
    return inline_keyboard([[callback_button("Обновить оценку", "model_quality_refresh")]])


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = (
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def welcome_card(first_name: str) -> bytes:
    image = Image.new("RGB", (1080, 1350), "#A8FF2A")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((76, 120, 1004, 1220), radius=56, fill="#EEF2F5")

    for x in (204, 400, 596, 792):
        draw.line((x, 120, x, 1220), fill="#B9F0BA", width=8)
    for y in (282, 444, 606, 768, 930):
        draw.line((76, y, 1004, y), fill="#FFFFFF", width=6)

    draw.ellipse((644, 188, 928, 472), fill="#2ACB59")
    draw.ellipse((714, 258, 858, 402), fill="#EBF2FF")
    draw.ellipse((770, 314, 802, 346), fill="#4D6BFE")

    for coords in ((154, 386, 218, 450), (286, 812, 350, 876), (846, 716, 910, 780), (470, 220, 534, 284)):
        draw.ellipse(coords, fill="#2ACB59")

    for x, y in ((258, 528), (720, 640), (442, 1002)):
        draw.rounded_rectangle((x, y, x + 74, y + 118), radius=24, fill="#FFFFFF", outline="#D4DBE2", width=5)
        draw.rounded_rectangle((x + 8, y + 18, x + 66, y + 100), radius=18, fill="#232B34")

    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def user_name(user: dict) -> str:
    return user.get("first_name") or user.get("username") or "Driver"


def dashboard_caption(first_name: str, dashboard: dict) -> str:
    active = dashboard.get("active_rental")
    if active:
        vehicle = active["vehicle"]
        return (
            f"<b>{first_name}, ваша аренда под рукой.</b>\n"
            f"{vehicle['title']} · {vehicle.get('license_plate') or ''}\n"
            f"{active.get('route_label') or 'Маршрут готов'}\n\n"
            f"Следующий шаг: <b>{active.get('next_action_label') or 'Открыть поездку'}</b>."
        )
    return (
        f"<b>{first_name}, готовы поехать?</b>\n"
        "Сначала выберите машину, затем откроется Mini App для обязательных фото: "
        "перед, левая сторона, правая сторона и задняя часть."
    )


def rental_message(rental: dict) -> str:
    vehicle = rental["vehicle"]
    lines = [
        f"<b>{vehicle['title']}</b> · {vehicle.get('license_plate') or 'plate pending'}",
        vehicle.get("subtitle") or "",
        rental.get("route_label") or "",
    ]
    if rental.get("pickup_title"):
        lines.append(rental["pickup_title"])
    if rental.get("dropoff_title"):
        lines.append(rental["dropoff_title"])
    if rental.get("planned_duration_min"):
        lines.append(f"Плановая поездка: {rental['planned_duration_min']} мин")
    lines = [line for line in lines if line]

    if rental["status"] == "awaiting_pickup_inspection":
        lines.append("")
        lines.append("Пройдите обязательный осмотр в Mini App. До подтверждения можно сменить машину или отменить выбор.")
    elif rental["status"] == "active":
        lines.append("")
        lines.append("Поездка активна. Когда будете завершать аренду, нажмите «Сдать машину».")
    elif rental["status"] == "awaiting_return_inspection":
        lines.append("")
        lines.append("Перед завершением аренды откройте осмотр сдачи и загрузите обязательные фото.")
    elif rental["status"] == "completed":
        lines.append("")
        lines.append("Аренда завершена.")
    return "\n".join(lines)


async def set_default_menu_button(chat_id: int) -> None:
    await tg.set_chat_menu_button(chat_id=chat_id, menu_button={"type": "commands"})


async def set_inspection_menu_button(chat_id: int, inspection_id: str, button_text: str) -> None:
    await tg.set_chat_menu_button(
        chat_id=chat_id,
        menu_button={
            "type": "web_app",
            "text": button_text,
            "web_app": {"url": f"{settings.miniapp_base_url}?inspection_id={inspection_id}"},
        },
    )


async def sync_context_menu(chat_id: int, rental: dict | None) -> None:
    await set_default_menu_button(chat_id)


def _markup_equal(left: dict | None, right: dict | None) -> bool:
    return left == right


def _is_not_modified(response: dict | None) -> bool:
    if not response:
        return False
    description = str(response.get("description") or "").lower()
    return "message is not modified" in description


def _is_message_missing(response: dict | None) -> bool:
    if not response:
        return False
    description = str(response.get("description") or "").lower()
    return "message to edit not found" in description or "message can't be edited" in description


async def upsert_panel_message(
    chat_id: int,
    text: str,
    inline_markup: dict | None = None,
    use_reply_keyboard_on_create: bool = False,
    force_new: bool = False,
    remember_previous: bool = True,
) -> None:
    state = get_state(chat_id)

    if remember_previous and state.current_panel_text is not None:
        state.previous_panel_text = state.current_panel_text
        state.previous_panel_markup = state.current_panel_markup

    if state.panel_message_id and not force_new:
        response = await tg.edit_message_text(
            chat_id,
            state.panel_message_id,
            text,
            reply_markup=inline_markup,
        )
        if response.get("ok") or _is_not_modified(response):
            state.current_panel_text = text
            state.current_panel_markup = inline_markup
            return
        state.panel_message_id = None

    reply_markup = inline_markup
    if reply_markup is None and use_reply_keyboard_on_create:
        reply_markup = reply_keyboard()
    response = await tg.send_message(chat_id, text, reply_markup=reply_markup)
    result = response.get("result") or {}
    message_id = result.get("message_id")
    if message_id:
        state.panel_message_id = message_id
        state.current_panel_text = text
        state.current_panel_markup = inline_markup


async def sync_welcome_message(chat_id: int, first_name: str, dashboard: dict, with_photo: bool, force_resend: bool = False) -> None:
    state = get_state(chat_id)
    if not with_photo:
        return

    caption = dashboard_caption(first_name, dashboard)

    if force_resend:
        state.welcome_message_id = None
        state.welcome_sent = False

    # Приветственный блок должен быть стабильным и не плодиться.
    # Если сообщение уже есть, пробуем мягко обновить caption.
    # Если пользователь удалил его вручную — переотправляем.
    if state.welcome_message_id and state.welcome_sent:
        edited = await tg.edit_message_caption(
            chat_id,
            state.welcome_message_id,
            caption,
            reply_markup=reply_keyboard(),
        )
        if edited.get("ok") or _is_not_modified(edited):
            return
        if _is_message_missing(edited):
            state.welcome_message_id = None
            state.welcome_sent = False
        else:
            # Для остальных Telegram-ошибок не плодим новое приветствие.
            return

    response = await tg.send_photo(
        chat_id,
        welcome_card(first_name),
        caption=caption,
        reply_markup=reply_keyboard(),
    )
    if response.get("ok"):
        result = response.get("result") or {}
        state.welcome_message_id = result.get("message_id")
        state.welcome_sent = state.welcome_message_id is not None
        return

    # Fallback, если отправка картинки не удалась
    fallback = await tg.send_message(chat_id, caption, reply_markup=reply_keyboard())
    result = fallback.get("result") or {}
    state.welcome_message_id = result.get("message_id")
    state.welcome_sent = state.welcome_message_id is not None


async def restore_previous_panel(chat_id: int) -> bool:
    state = get_state(chat_id)
    if not state.previous_panel_text:
        return False
    await upsert_panel_message(
        chat_id,
        state.previous_panel_text,
        inline_markup=state.previous_panel_markup,
        remember_previous=False,
    )
    return True
