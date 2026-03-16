"""In-memory conversation state for the Telegram bot.

In production this should be backed by Redis, but for the MVP
an in-memory dict is sufficient (state is lost on restart).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from packages.shared_py.car_inspection.enums import REQUIRED_SLOTS, SLOT_LABELS

logger = logging.getLogger(__name__)


@dataclass
class ConversationState:
    """Tracks a single user's active inspection flow."""
    inspection_id: str | None = None
    vehicle_id: str | None = None
    rental_id: str | None = None
    menu_mode: str = "home"
    panel_message_id: int | None = None
    welcome_message_id: int | None = None
    welcome_sent: bool = False
    current_panel_text: str | None = None
    current_panel_markup: dict | None = None
    previous_panel_text: str | None = None
    previous_panel_markup: dict | None = None


# chat_id -> ConversationState
_states: dict[int, ConversationState] = {}


def get_state(chat_id: int) -> ConversationState:
    if chat_id not in _states:
        _states[chat_id] = ConversationState()
    return _states[chat_id]


def reset_state(chat_id: int, preserve_ui: bool = True) -> None:
    current = _states.get(chat_id)
    if not current:
        return
    if not preserve_ui:
        _states.pop(chat_id, None)
        return
    _states[chat_id] = ConversationState(
        panel_message_id=current.panel_message_id,
        welcome_message_id=current.welcome_message_id,
        welcome_sent=current.welcome_sent,
        current_panel_text=current.current_panel_text,
        current_panel_markup=current.current_panel_markup,
        previous_panel_text=current.previous_panel_text,
        previous_panel_markup=current.previous_panel_markup,
    )


def reset_ui_state(chat_id: int) -> None:
    current = _states.get(chat_id)
    if not current:
        return
    current.panel_message_id = None
    current.welcome_message_id = None
    current.welcome_sent = False
    current.current_panel_text = None
    current.current_panel_markup = None
    current.previous_panel_text = None
    current.previous_panel_markup = None


def has_active_inspection(chat_id: int) -> bool:
    st = _states.get(chat_id)
    return st is not None and st.inspection_id is not None
