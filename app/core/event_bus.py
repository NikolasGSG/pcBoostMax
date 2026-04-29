"""Minimal publish/subscribe bus used to keep modules loosely coupled.

Every module emits or consumes events via this bus rather than importing
each other. The bus is thread-safe and deliberately dependency-free so it
can be used by background workers.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Callable, DefaultDict, List


Listener = Callable[..., None]


class EventBus:
    """Simple thread-safe pub/sub.

    Keys are short ``"domain.topic"`` strings (e.g. ``"monitor.sample"``,
    ``"opt.plan_ready"``). Listeners are called synchronously on the emitting
    thread — if you need to touch Qt widgets, connect a Qt signal to a slot
    that forwards via this bus, never the other way around.
    """

    def __init__(self) -> None:
        self._listeners: DefaultDict[str, List[Listener]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, topic: str, listener: Listener) -> Callable[[], None]:
        with self._lock:
            self._listeners[topic].append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                try:
                    self._listeners[topic].remove(listener)
                except ValueError:
                    pass

        return _unsubscribe

    def publish(self, topic: str, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            listeners = list(self._listeners.get(topic, ()))
        for listener in listeners:
            try:
                listener(*args, **kwargs)
            except Exception:  # pragma: no cover - listeners should never break the bus
                import logging

                logging.getLogger("gameboostapex.event_bus").exception("Listener failed for %s", topic)

    def clear(self) -> None:
        with self._lock:
            self._listeners.clear()
