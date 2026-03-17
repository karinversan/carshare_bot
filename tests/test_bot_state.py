"""Tests for bot conversation state management."""
from apps.bot_service.app.state import (
    get_state, reset_state, reset_ui_state, has_active_inspection,
    ConversationState, REQUIRED_SLOTS, SLOT_LABELS,
)


def test_get_state_creates_new():
    reset_state(99999)
    st = get_state(99999)
    assert isinstance(st, ConversationState)
    assert st.inspection_id is None
    reset_state(99999)


def test_get_state_returns_same():
    reset_state(88888)
    st1 = get_state(88888)
    st1.inspection_id = "abc"
    st2 = get_state(88888)
    assert st2.inspection_id == "abc"
    reset_state(88888)


def test_reset_state():
    st = get_state(77777)
    st.inspection_id = "xyz"
    reset_state(77777)
    st2 = get_state(77777)
    assert st2.inspection_id is None
    reset_state(77777)


def test_has_active_inspection():
    reset_state(66666)
    assert has_active_inspection(66666) is False
    st = get_state(66666)
    st.inspection_id = "test-id"
    assert has_active_inspection(66666) is True
    reset_state(66666)


def test_reset_ui_state_keeps_flow_but_drops_message_refs():
    reset_state(55555)
    st = get_state(55555)
    st.inspection_id = "inspection-1"
    st.rental_id = "rental-1"
    st.panel_message_id = 101
    st.welcome_message_id = 202
    st.welcome_sent = True
    st.current_panel_text = "panel"
    reset_ui_state(55555)
    st2 = get_state(55555)
    assert st2.inspection_id == "inspection-1"
    assert st2.rental_id == "rental-1"
    assert st2.panel_message_id is None
    assert st2.welcome_message_id is None
    assert st2.welcome_sent is False
    assert st2.current_panel_text is None
    reset_state(55555)


def test_required_slots():
    assert len(REQUIRED_SLOTS) == 4
    for slot in REQUIRED_SLOTS:
        assert slot in SLOT_LABELS


def test_ephemeral_multiline_text_is_detected():
    from apps.bot_service.app.main import _is_ephemeral_user_text

    text = "Найти авто\n\nМоя поездка\nОткрыть осмотр"
    assert _is_ephemeral_user_text(text) is True


def test_mixed_multiline_text_is_not_ephemeral():
    from apps.bot_service.app.main import _is_ephemeral_user_text

    text = "Найти авто\nкакой-то свой текст"
    assert _is_ephemeral_user_text(text) is False


def test_start_is_not_ephemeral():
    from apps.bot_service.app.main import _is_ephemeral_user_text

    assert _is_ephemeral_user_text("/start") is False


def test_reply_keyboard_has_no_open_or_return_actions():
    from apps.bot_service.app.ui import reply_keyboard

    keyboard = reply_keyboard()
    labels = [button["text"] for row in keyboard["keyboard"] for button in row]
    assert "Открыть осмотр" not in labels
    assert "Сдать машину" not in labels
    assert "Качество моделей" in labels
