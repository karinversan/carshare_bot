"""Smoke tests for Telegram bot message lifecycle (anti-chat-clutter behavior)."""

import asyncio

from apps.bot_service.app.state import get_state, reset_state


def test_upsert_panel_message_edits_existing_instead_of_sending_new(monkeypatch):
    from apps.bot_service.app.ui import upsert_panel_message
    from apps.bot_service.app import ui as bot_ui

    chat_id = 401001
    reset_state(chat_id, preserve_ui=False)
    state = get_state(chat_id)
    state.panel_message_id = 777
    state.current_panel_text = "старый текст"
    state.current_panel_markup = {"inline_keyboard": [[{"text": "A", "callback_data": "a"}]]}

    calls = {"edit": 0, "send": 0}

    async def fake_edit_message_text(chat_id_arg, message_id_arg, text, reply_markup=None, parse_mode="HTML"):
        calls["edit"] += 1
        assert chat_id_arg == chat_id
        assert message_id_arg == 777
        return {"ok": True, "result": {"message_id": 777}}

    async def fake_send_message(chat_id_arg, text, reply_markup=None, parse_mode="HTML"):
        calls["send"] += 1
        return {"ok": True, "result": {"message_id": 999}}

    monkeypatch.setattr(bot_ui.tg, "edit_message_text", fake_edit_message_text)
    monkeypatch.setattr(bot_ui.tg, "send_message", fake_send_message)

    asyncio.run(
        upsert_panel_message(
            chat_id,
            "новый текст",
            inline_markup={"inline_keyboard": [[{"text": "B", "callback_data": "b"}]]},
        )
    )

    assert calls["edit"] == 1
    assert calls["send"] == 0
    assert state.panel_message_id == 777
    assert state.current_panel_text == "новый текст"

    reset_state(chat_id, preserve_ui=False)


def test_upsert_panel_message_recreates_when_edit_target_missing(monkeypatch):
    from apps.bot_service.app.ui import upsert_panel_message
    from apps.bot_service.app import ui as bot_ui

    chat_id = 401002
    reset_state(chat_id, preserve_ui=False)
    state = get_state(chat_id)
    state.panel_message_id = 123
    state.current_panel_text = "старый"

    async def fake_edit_message_text(chat_id_arg, message_id_arg, text, reply_markup=None, parse_mode="HTML"):
        assert chat_id_arg == chat_id
        assert message_id_arg == 123
        return {"ok": False, "description": "Bad Request: message to edit not found"}

    async def fake_send_message(chat_id_arg, text, reply_markup=None, parse_mode="HTML"):
        assert chat_id_arg == chat_id
        return {"ok": True, "result": {"message_id": 456}}

    monkeypatch.setattr(bot_ui.tg, "edit_message_text", fake_edit_message_text)
    monkeypatch.setattr(bot_ui.tg, "send_message", fake_send_message)

    asyncio.run(upsert_panel_message(chat_id, "новый текст"))

    assert state.panel_message_id == 456
    assert state.current_panel_text == "новый текст"
    reset_state(chat_id, preserve_ui=False)


def test_sync_welcome_message_resends_after_chat_cleanup(monkeypatch):
    from apps.bot_service.app.ui import sync_welcome_message
    from apps.bot_service.app import ui as bot_ui

    chat_id = 401003
    reset_state(chat_id, preserve_ui=False)
    state = get_state(chat_id)
    state.welcome_message_id = 777
    state.welcome_sent = True

    async def fake_edit_message_caption(chat_id_arg, message_id_arg, caption, reply_markup=None, parse_mode="HTML"):
        assert chat_id_arg == chat_id
        assert message_id_arg == 777
        return {"ok": False, "description": "Bad Request: message to edit not found"}

    async def fake_send_photo(chat_id_arg, photo, caption, reply_markup=None, parse_mode="HTML", filename="card.png"):
        assert chat_id_arg == chat_id
        return {"ok": True, "result": {"message_id": 888}}

    monkeypatch.setattr(bot_ui.tg, "edit_message_caption", fake_edit_message_caption)
    monkeypatch.setattr(bot_ui.tg, "send_photo", fake_send_photo)

    asyncio.run(
        sync_welcome_message(
            chat_id,
            "Karin",
            {"active_rental": None},
            with_photo=True,
        )
    )

    assert state.welcome_message_id == 888
    assert state.welcome_sent is True
    reset_state(chat_id, preserve_ui=False)


def test_process_update_deletes_ephemeral_commands_but_not_start(monkeypatch):
    from apps.bot_service.app import main as bot_main

    deleted_message_ids: list[int] = []

    async def fake_send_dashboard(chat_id, user, with_photo=False, notice=None, force_welcome=False):
        return None

    async def fake_send_vehicle_picker(chat_id, user, text):
        return None

    async def fake_show_error_panel(chat_id, text):
        return None

    async def fake_delete_user_command_message(message):
        deleted_message_ids.append(message["message_id"])

    monkeypatch.setattr(bot_main, "_send_dashboard", fake_send_dashboard)
    monkeypatch.setattr(bot_main, "_send_vehicle_picker", fake_send_vehicle_picker)
    monkeypatch.setattr(bot_main, "_show_error_panel", fake_show_error_panel)
    monkeypatch.setattr(bot_main, "_delete_user_command_message", fake_delete_user_command_message)

    start_update = {
        "message": {
            "chat": {"id": 501001},
            "from": {"id": 77, "username": "karin"},
            "text": "/start",
            "message_id": 11,
        }
    }
    find_car_update = {
        "message": {
            "chat": {"id": 501001},
            "from": {"id": 77, "username": "karin"},
            "text": "Найти авто",
            "message_id": 12,
        }
    }

    asyncio.run(bot_main.process_update(start_update))
    asyncio.run(bot_main.process_update(find_car_update))

    assert 11 not in deleted_message_ids
    assert 12 in deleted_message_ids


def test_handle_callback_deletes_stale_message_not_bound_to_panel(monkeypatch):
    from apps.bot_service.app import main as bot_main

    chat_id = 601001
    reset_state(chat_id, preserve_ui=False)
    state = get_state(chat_id)
    state.panel_message_id = 101
    state.welcome_message_id = 202

    deleted: list[tuple[int, int]] = []
    answered: list[str] = []

    async def fake_delete_message(chat_id_arg, message_id_arg):
        deleted.append((chat_id_arg, message_id_arg))
        return {"ok": True}

    async def fake_answer_callback_query(cq_id, text=""):
        answered.append(cq_id)
        return {"ok": True}

    async def fake_send_dashboard(chat_id_arg, user, with_photo=False, notice=None, force_welcome=False):
        return None

    monkeypatch.setattr(bot_main.tg, "delete_message", fake_delete_message)
    monkeypatch.setattr(bot_main.tg, "answer_callback_query", fake_answer_callback_query)
    monkeypatch.setattr(bot_main, "_send_dashboard", fake_send_dashboard)

    update = {
        "id": "cq-1",
        "from": {"id": 77, "username": "karin"},
        "data": "dashboard",
        "message": {"chat": {"id": chat_id}, "message_id": 999},
    }

    asyncio.run(bot_main.handle_callback(update))

    assert answered == ["cq-1"]
    assert deleted == [(chat_id, 999)]
    reset_state(chat_id, preserve_ui=False)


def test_handle_callback_keeps_current_panel_message(monkeypatch):
    from apps.bot_service.app import main as bot_main

    chat_id = 701001
    reset_state(chat_id, preserve_ui=False)
    state = get_state(chat_id)
    state.panel_message_id = 909
    state.welcome_message_id = 808

    deleted: list[tuple[int, int]] = []

    async def fake_delete_message(chat_id_arg, message_id_arg):
        deleted.append((chat_id_arg, message_id_arg))
        return {"ok": True}

    async def fake_answer_callback_query(cq_id, text=""):
        return {"ok": True}

    async def fake_send_dashboard(chat_id_arg, user, with_photo=False, notice=None, force_welcome=False):
        return None

    monkeypatch.setattr(bot_main.tg, "delete_message", fake_delete_message)
    monkeypatch.setattr(bot_main.tg, "answer_callback_query", fake_answer_callback_query)
    monkeypatch.setattr(bot_main, "_send_dashboard", fake_send_dashboard)

    update = {
        "id": "cq-2",
        "from": {"id": 77, "username": "karin"},
        "data": "dashboard",
        "message": {"chat": {"id": chat_id}, "message_id": 909},
    }

    asyncio.run(bot_main.handle_callback(update))

    assert deleted == []
    reset_state(chat_id, preserve_ui=False)
