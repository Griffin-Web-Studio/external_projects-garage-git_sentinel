from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

# ────────────────────────────────────────────────────────────────| EventBus |──


class EventBus:
    """Lightweight synchronous event bus.

    Subscribers are called in the emitting thread. Marshalling to a UI
    thread (e.g. Tkinter's root.after(), Textual's app.call_from_thread()) is
    the subscriber's responsibility.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[Any], None]]] = defaultdict(
            list
        )

    def subscribe(self, event: str, handler: Callable[[Any], None]) -> None:
        """Register *handler* to be called whenever *event* is emitted.

        Args:
            event (str): Event name string.
            handler (Callable[[Any], None]): Callable that receives the
                emitted data.
        """

        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable[[Any], None]) -> None:
        """Remove a previously registered *handler* for *event*.

        Args:
            event (str): Event name string.
            handler (Callable[[Any], None]): The exact callable that was passed
                to subscribe().
        """

        self._handlers[event].remove(handler)

    def emit(self, event: str, data: Any = None) -> None:
        """Call all handlers registered for *event* with *data*.

        Args:
            event (str): Event name string.
            data (Any): Payload passed verbatim to each handler.
        """

        for handler in self._handlers[event]:
            handler(data)
