"""Small deterministic state machine for ClaudeCat's visible behaviour."""
from __future__ import annotations

from enum import Enum


class PetState(str, Enum):
    IDLE = 'idle'
    LISTENING = 'listening'
    THINKING = 'thinking'
    STREAMING = 'streaming'
    SUCCESS = 'success'
    ERROR = 'error'


_ALLOWED: dict[PetState, set[PetState]] = {
    PetState.IDLE: {PetState.LISTENING, PetState.THINKING, PetState.ERROR},
    PetState.LISTENING: {PetState.IDLE, PetState.THINKING, PetState.ERROR},
    PetState.THINKING: {PetState.STREAMING, PetState.SUCCESS, PetState.ERROR},
    PetState.STREAMING: {PetState.SUCCESS, PetState.ERROR},
    PetState.SUCCESS: {PetState.IDLE, PetState.LISTENING, PetState.THINKING},
    PetState.ERROR: {PetState.IDLE, PetState.LISTENING, PetState.THINKING},
}


class PetStateMachine:
    """Validate visible state changes without coupling them to any GUI toolkit."""

    def __init__(self, initial: PetState = PetState.IDLE) -> None:
        self.current = initial

    def transition(self, target: PetState) -> bool:
        """Move to ``target`` when valid; same-state changes are harmless."""
        if target == self.current:
            return True
        if target not in _ALLOWED[self.current]:
            return False
        self.current = target
        return True

    def reset(self) -> None:
        self.current = PetState.IDLE
