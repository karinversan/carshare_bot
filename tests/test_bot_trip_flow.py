import asyncio


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
