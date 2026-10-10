# src/backend/events.py
"""
NEW EMPIRE v1.5.5 — Backend Agent.
Простая шина событий (v1.5.5, п.2).
Без pygame.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

Callback = Callable[[Dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._subs: Dict[str, List[Callback]] = {}

    def subscribe(self, event_type: str, callback: Callback) -> None:
        self._subs.setdefault(event_type, []).append(callback)

    def unsubscribe(self, event_type: str, callback: Callback) -> None:
        if event_type not in self._subs:
            return
        try:
            self._subs[event_type].remove(callback)
        except ValueError:
            pass

    def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        for cb in list(self._subs.get(event_type, [])):
            cb(payload)

    def clear(self) -> None:
        self._subs.clear()

    def subscriber_count(self, event_type: str) -> int:
        return len(self._subs.get(event_type, []))