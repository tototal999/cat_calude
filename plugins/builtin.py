"""Safe plugin-style actions inspired by OpenPets' optional behaviours."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BuiltinAction:
    action_id: str
    label: str


ACTIONS = (
    BuiltinAction('quick_question', '快速提問'),
    BuiltinAction('documents', '文件助手'),
)


def actions() -> tuple[BuiltinAction, ...]:
    """Return fixed local actions; no executable code is loaded dynamically."""
    return ACTIONS
