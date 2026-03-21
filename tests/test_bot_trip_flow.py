import asyncio
import json


def _rental_payload(status: str) -> dict:
    return {
        "rental_id": "rental-1",
        "status": status,
        "vehicle": {
            "vehicle_id": "VEH-001",
            "title": "Volkswagen Polo",
            "subtitle": "Sedan • White",
            "license_plate": "A123AA77",
        },
        "route_label": "Tverskaya -> Цветной бульвар",
        "pickup_title": "Pickup: Tverskaya 18",
        "dropoff_title": "Drop-off zone: Цветной бульвар",
        "planned_duration_min": 32,
        "current_inspection_id": "insp-1" if status in {"awaiting_pickup_inspection", "awaiting_return_inspection"} else None,
        "next_action": "complete_return_inspection" if status == "awaiting_return_inspection" else None,
        "next_action_label": "Открыть осмотр сдачи" if status == "awaiting_return_inspection" else "Открыть осмотр",
    }


def test_start_trip_does_not_switch_vehicle_when_return_inspection_exists(monkeypatch):
    from apps.bot_service.app import main as bot_main

    called = {}

    async def fake_start_trip(**kwargs):
        return {
            "created": False,
            "inspection_id": "post-insp-1",
            "rental": _rental_payload("awaiting_return_inspection"),
        }

    async def fake_upsert(chat_id, text, inline_markup=None, **kwargs):
        called["chat_id"] = chat_id
        called["text"] = text
        called["inline_markup"] = inline_markup

    monkeypatch.setattr(bot_main.api_client, "start_trip", fake_start_trip)
    monkeypatch.setattr(bot_main, "upsert_panel_message", fake_upsert)

    asyncio.run(bot_main._start_trip(123, {"id": 77, "username": "karin"}, "VEH-002"))

    assert called["chat_id"] == 123
    assert "Новую машину выбрать нельзя" in called["text"]
    assert "Машина выбрана" not in called["text"]
    assert called["inline_markup"] is not None


def test_start_trip_for_new_pickup_keeps_inspection_entry(monkeypatch):
    from apps.bot_service.app import main as bot_main

    called = {}

    async def fake_start_trip(**kwargs):
        return {
            "created": True,
            "inspection_id": "pre-insp-1",
            "rental": _rental_payload("awaiting_pickup_inspection"),
        }

    async def fake_upsert(chat_id, text, inline_markup=None, **kwargs):
        called["chat_id"] = chat_id
        called["text"] = text
        called["inline_markup"] = inline_markup

    monkeypatch.setattr(bot_main.api_client, "start_trip", fake_start_trip)
    monkeypatch.setattr(bot_main, "upsert_panel_message", fake_upsert)

    asyncio.run(bot_main._start_trip(456, {"id": 88, "username": "karin"}, "VEH-001"))

    assert called["chat_id"] == 456
    assert "Машина выбрана" in called["text"]
    assert called["inline_markup"] is not None


def test_web_app_finalize_switches_bot_to_active_trip(monkeypatch):
    from apps.bot_service.app import main as bot_main

    calls = {}

    async def fake_get_inspection_context(inspection_id):
        return {
            "rental": {
                **_rental_payload("active"),
                "current_inspection_id": None,
                "next_action": "start_return",
                "next_action_label": "Сдать машину",
            }
        }

    async def fake_set_default_menu_button(chat_id):
        calls["menu_chat_id"] = chat_id

    async def fake_upsert(chat_id, text, inline_markup=None, **kwargs):
        calls["chat_id"] = chat_id
        calls["text"] = text
        calls["inline_markup"] = inline_markup

    monkeypatch.setattr(bot_main.api_client, "get_inspection_context", fake_get_inspection_context)
    monkeypatch.setattr(bot_main, "set_default_menu_button", fake_set_default_menu_button)
    monkeypatch.setattr(bot_main, "upsert_panel_message", fake_upsert)

    asyncio.run(
        bot_main._handle_web_app_data(
            101,
            json.dumps({"action": "inspection_finalized", "inspection_id": "pre-insp-1"}),
        )
    )

    assert calls["chat_id"] == 101
    assert "Приятной поездки" in calls["text"]
    assert "Осталось ехать" in calls["text"]
    assert calls["inline_markup"] is not None
    buttons = calls["inline_markup"]["inline_keyboard"]
    assert any(button["text"] == "Сдать машину" for row in buttons for button in row)
    assert any(button["text"] == "Вернуться в главное меню" for row in buttons for button in row)


def test_web_app_finalize_after_return_clears_conflicting_buttons(monkeypatch):
    from apps.bot_service.app import main as bot_main

    calls = {}

    async def fake_get_inspection_context(inspection_id):
        return {
            "rental": {
                **_rental_payload("completed"),
                "current_inspection_id": None,
                "next_action": None,
                "next_action_label": None,
            }
        }

    async def fake_set_default_menu_button(chat_id):
        calls["menu_chat_id"] = chat_id

    async def fake_upsert(chat_id, text, inline_markup=None, **kwargs):
        calls["chat_id"] = chat_id
        calls["text"] = text
        calls["inline_markup"] = inline_markup

    monkeypatch.setattr(bot_main.api_client, "get_inspection_context", fake_get_inspection_context)
    monkeypatch.setattr(bot_main, "set_default_menu_button", fake_set_default_menu_button)
    monkeypatch.setattr(bot_main, "upsert_panel_message", fake_upsert)

    asyncio.run(
        bot_main._handle_web_app_data(
            202,
            json.dumps(
                {
                    "action": "inspection_finalized",
                    "inspection_id": "post-insp-1",
                    "comparison_status": "admin_case_created",
                }
            ),
        )
    )

    assert calls["chat_id"] == 202
    assert "Открыт спор" in calls["text"]
    assert calls["inline_markup"] is not None
    buttons = calls["inline_markup"]["inline_keyboard"]
    assert any(button["text"] == "Вернуться в главное меню" for row in buttons for button in row)
