from __future__ import annotations

import pytest

from src.controllers.events import EventBus

# ─────────────────────────────────────────────────────────────────| Fixture |──


@pytest.fixture
def bus() -> EventBus:
    """Reusable Event Bus fixture

    Returns:
        EventBus: Application Event Bus Controller
    """

    return EventBus()


# ────────────────────────────────────────────────────────| Subscribe / Emit |──


class TestSubscribeEmit:
    """Basic subscribe/emit contract."""

    def test_subscriber_called_on_emit(self, bus: EventBus) -> None:
        """A subscribed handler receives the emitted payload."""

        received: list[object] = []

        bus.subscribe("ev", received.append)
        bus.emit("ev", "hello")

        assert received == ["hello"]

    def test_multiple_subscribers_all_called(self, bus: EventBus) -> None:
        """All handlers registered for the same event are called."""

        a: list[object] = []
        b: list[object] = []

        bus.subscribe("ev", a.append)
        bus.subscribe("ev", b.append)
        bus.emit("ev", 1)

        assert a == [1] and b == [1]

    def test_emit_with_no_data_passes_none(self, bus: EventBus) -> None:
        """Emitting without data passes None to handlers."""

        received: list[object] = []
        bus.subscribe("ev", received.append)
        bus.emit("ev")

        assert received == [None]

    def test_emit_unknown_event_does_not_raise(self, bus: EventBus) -> None:
        """Emitting to an event with no subscribers is a no-op."""

        bus.emit("noop", "data")

    def test_different_events_are_isolated(self, bus: EventBus) -> None:
        """Subscribing to 'a' does not receive emissions on 'b'."""

        a: list[object] = []
        b: list[object] = []

        bus.subscribe("a", a.append)
        bus.subscribe("b", b.append)
        bus.emit("a", 1)

        assert a == [1] and b == []

    def test_handler_called_in_order(self, bus: EventBus) -> None:
        """Handlers are called in subscription order."""

        order: list[str] = []

        bus.subscribe("ev", lambda _: order.append("first"))
        bus.subscribe("ev", lambda _: order.append("second"))
        bus.emit("ev", None)

        assert order == ["first", "second"]


# ─────────────────────────────────────────────────────────────| Unsubscribe |──


class TestUnsubscribe:
    """unsubscribe() removes a specific handler."""

    def test_unsubscribe_stops_calls(self, bus: EventBus) -> None:
        """Handler is not called after unsubscribing."""

        received: list[object] = []

        bus.subscribe("ev", received.append)
        bus.unsubscribe("ev", received.append)
        bus.emit("ev", "x")

        assert received == []

    def test_unsubscribe_only_removes_target(self, bus: EventBus) -> None:
        """Unsubscribing one handler leaves others intact."""

        a: list[object] = []
        b: list[object] = []

        bus.subscribe("ev", a.append)
        bus.subscribe("ev", b.append)
        bus.unsubscribe("ev", a.append)
        bus.emit("ev", 99)

        assert a == [] and b == [99]
