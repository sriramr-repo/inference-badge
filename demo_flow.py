"""Session-only state helpers for the five-step Inference Badge demo."""
from __future__ import annotations

from typing import Any


STEP_COUNT = 5


def new_demo_state() -> dict[str, Any]:
    return {
        "step": 1,
        "dave_sharing": False,
        "walked_to_sarah": False,
        "collision_stopped": False,
        "talk_logged": False,
        "done": False,
    }


def advance_demo(state: dict[str, Any]) -> dict[str, Any]:
    """Advance the demo and complete skipped interactions safely."""
    next_state = dict(state)
    current_step = int(next_state.get("step", 1))
    if current_step < STEP_COUNT:
        next_state["step"] = current_step + 1
        if next_state["step"] >= 2:
            next_state["walked_to_sarah"] = True
        if next_state["step"] >= 3:
            next_state["collision_stopped"] = True
    elif current_step == STEP_COUNT:
        next_state["talk_logged"] = True
        next_state["done"] = True
    return next_state


def log_demo_talk(state: dict[str, Any]) -> dict[str, Any]:
    next_state = dict(state)
    if int(next_state.get("step", 1)) == STEP_COUNT:
        next_state["talk_logged"] = True
        next_state["done"] = True
    return next_state


def set_dave_sharing(state: dict[str, Any], sharing: bool) -> dict[str, Any]:
    next_state = dict(state)
    next_state["dave_sharing"] = bool(sharing)
    return next_state
