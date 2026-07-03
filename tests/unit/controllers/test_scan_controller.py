from __future__ import annotations

import configparser
import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from src.controllers.events import EventBus
from src.controllers.scan import ScanController
from src.models import (
    GateHTTP,
    GateSSH,
    MsgFinish,
    MsgLog,
    MsgProgress,
    MsgStatus,
)

# ────────────────────────────────────────────────────────────────| Fixtures |──


@pytest.fixture
def bus() -> EventBus:
    """Reusable Event Bus fixture

    Returns:
        EventBus: Application Event Bus Controller
    """

    return EventBus()


@pytest.fixture
def ctrl(bus: EventBus) -> ScanController:
    """Reusable scan controller fixture

    Returns:
        EventBus: Application Scan Controller
    """

    return ScanController(bus)


# ───────────────────────────────────────────────────────────────────| log() |──


class TestLog:
    """log() emits a MsgLog on scan.log."""

    def test_emits_msg_log(self, ctrl: ScanController, bus: EventBus) -> None:
        """log() emits a MsgLog carrying the text."""

        received: list[MsgLog] = []

        bus.subscribe("scan.log", received.append)
        ctrl.log("hello")

        assert len(received) == 1 and isinstance(received[0], MsgLog)
        assert received[0].text == "hello"

    def test_default_tag_is_empty(
        self, ctrl: ScanController, bus: EventBus
    ) -> None:
        """log() without a tag emits MsgLog with an empty tag."""

        received: list[MsgLog] = []

        bus.subscribe("scan.log", received.append)
        ctrl.log("msg")

        assert received[0].tag == ""

    def test_tag_forwarded(self, ctrl: ScanController, bus: EventBus) -> None:
        """log() with a tag emits MsgLog with that tag."""

        received: list[MsgLog] = []

        bus.subscribe("scan.log", received.append)
        ctrl.log("err", tag="error")

        assert received[0].tag == "error"


# ────────────────────────────────────────────────────────────| set_status() |──


class TestSetStatus:
    """set_status() emits a MsgStatus on scan.status."""

    def test_emits_msg_status(
        self, ctrl: ScanController, bus: EventBus
    ) -> None:
        """set_status() emits MsgStatus with the given text."""

        received: list[MsgStatus] = []

        bus.subscribe("scan.status", received.append)
        ctrl.set_status("scanning...")

        assert isinstance(received[0], MsgStatus)
        assert received[0].text == "scanning..."


# ──────────────────────────────────────────────────────────| set_progress() |──


class TestSetProgress:
    """set_progress() emits a MsgProgress on scan.progress."""

    def test_emits_msg_progress(
        self, ctrl: ScanController, bus: EventBus
    ) -> None:
        """set_progress() emits MsgProgress with the given percentage."""

        received: list[MsgProgress] = []

        bus.subscribe("scan.progress", received.append)
        ctrl.set_progress(42.5)

        assert isinstance(received[0], MsgProgress)
        assert received[0].pct == pytest.approx(42.5)


# ────────────────────────────────────────────────────────────────| finish() |──


class TestFinish:
    """finish() sets closable and emits MsgFinish on scan.finish."""

    def test_closable_starts_false(self, ctrl: ScanController) -> None:
        """closable is False before finish() is called."""

        assert ctrl.closable is False

    def test_finish_sets_closable(self, ctrl: ScanController) -> None:
        """finish() flips closable to True."""

        ctrl.finish(0, None)

        assert ctrl.closable is True

    def test_emits_msg_finish(
        self, ctrl: ScanController, bus: EventBus
    ) -> None:
        """finish() emits a MsgFinish with the correct issue count."""

        received: list[MsgFinish] = []

        bus.subscribe("scan.finish", received.append)
        ctrl.finish(3, None)

        assert isinstance(received[0], MsgFinish)
        assert received[0].issue_count == 3

    def test_emits_report_path(
        self, ctrl: ScanController, bus: EventBus, tmp_path: Path
    ) -> None:
        """finish() includes the report path in the emitted MsgFinish."""

        received: list[MsgFinish] = []

        bus.subscribe("scan.finish", received.append)
        report = tmp_path / "report.log"
        ctrl.finish(1, report)

        assert received[0].report_path == report


# ───────────────────────────────────────────────────────────────────| Gates |──


class TestRequestSSH:
    """request_ssh() emits a GateSSH and blocks until the event is set."""

    def _auto_approve(self, approved: bool) -> Callable[[GateSSH], None]:
        """Return a gate handler that immediately resolves the request."""

        def handler(req: GateSSH) -> None:
            req.approved = approved
            req.event.set()

        return handler

    def test_emits_gate_ssh(self, ctrl: ScanController, bus: EventBus) -> None:
        """request_ssh() emits a GateSSH on scan.gate."""

        received: list[object] = []

        def handler(req: GateSSH) -> None:
            received.append(req)
            req.event.set()

        bus.subscribe("scan.gate", handler)
        ctrl.request_ssh("git@github.com:u/r.git", "~/repo")

        assert len(received) == 1 and isinstance(received[0], GateSSH)

    def test_returns_true_when_approved(
        self, ctrl: ScanController, bus: EventBus
    ) -> None:
        """request_ssh() returns True when the gate is resolved approved."""

        bus.subscribe("scan.gate", self._auto_approve(True))

        assert ctrl.request_ssh("git@github.com:u/r.git", "~/repo") is True

    def test_returns_false_when_declined(
        self, ctrl: ScanController, bus: EventBus
    ) -> None:
        """request_ssh() returns False when the gate is resolved declined."""

        bus.subscribe("scan.gate", self._auto_approve(False))

        assert ctrl.request_ssh("git@github.com:u/r.git", "~/repo") is False


class TestRequestHTTPRetry:
    """request_http_retry() emits a GateHTTP and blocks until the event is
    set."""

    def _auto_resolve(self, retry: bool) -> Callable[[GateHTTP], None]:
        def handler(req: GateHTTP) -> None:
            req.retry = retry
            req.event.set()

        return handler

    def test_emits_gate_http(self, ctrl: ScanController, bus: EventBus) -> None:
        """request_http_retry() emits a GateHTTP on scan.gate."""

        received: list[object] = []

        def handler(req: GateHTTP) -> None:
            received.append(req)
            req.event.set()

        bus.subscribe("scan.gate", handler)
        ctrl.request_http_retry(
            "https://griffin-web.studio/r.git", "~/repo", "err"
        )

        assert len(received) == 1 and isinstance(received[0], GateHTTP)

    def test_returns_true_when_retry(
        self, ctrl: ScanController, bus: EventBus
    ) -> None:
        """request_http_retry() returns True when the user chose Retry."""

        bus.subscribe("scan.gate", self._auto_resolve(True))

        assert (
            ctrl.request_http_retry(
                "https://griffin-web.studio/r.git", "~/repo", "err"
            )
            is True
        )

    def test_returns_false_when_skip(
        self, ctrl: ScanController, bus: EventBus
    ) -> None:
        """request_http_retry() returns False when the user chose Skip."""

        bus.subscribe("scan.gate", self._auto_resolve(False))

        assert (
            ctrl.request_http_retry(
                "https://griffin-web.studio/r.git", "~/repo", "err"
            )
            is False
        )


# ──────────────────────────────────────────────────────────────| start_scan |──


class TestStartScan:
    """start_scan() runs the scan worker on a background daemon thread."""

    @pytest.fixture
    def spawned(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> list[threading.Thread]:
        """Capture every thread started via src.controllers.scan.threading.

        Args:
            monkeypatch (pytest.MonkeyPatch): Wraps threading.Thread so each
                created instance is recorded before being returned as-is.

        Returns:
            list[threading.Thread]: Threads created by start_scan, appended
                to as they are constructed.
        """

        threads: list[threading.Thread] = []
        real_thread = threading.Thread

        def spy_thread(*args: object, **kwargs: object) -> threading.Thread:
            t = real_thread(*args, **kwargs)  # type: ignore[arg-type]
            threads.append(t)
            return t

        monkeypatch.setattr("src.controllers.scan.threading.Thread", spy_thread)

        return threads

    def test_spawns_daemon_thread(
        self,
        ctrl: ScanController,
        spawned: list[threading.Thread],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The worker thread created by start_scan is marked daemon.

        Args:
            ctrl (ScanController): Controller under test.
            spawned (list[threading.Thread]): Threads captured by the
                spawned fixture.
            monkeypatch (pytest.MonkeyPatch): Stubs out the real scan
                worker so no filesystem/git access happens.
        """

        monkeypatch.setattr("src.services.scan.scan", lambda app, cfg: None)

        ctrl.start_scan(configparser.ConfigParser())

        assert len(spawned) == 1
        assert spawned[0].daemon is True

        spawned[0].join(timeout=2)

    def test_worker_calls_scan_with_controller_and_cfg(
        self,
        ctrl: ScanController,
        spawned: list[threading.Thread],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The background worker invokes scan(self, cfg) with the exact
        controller and config passed to start_scan.

        Args:
            ctrl (ScanController): Controller under test.
            spawned (list[threading.Thread]): Threads captured by the
                spawned fixture.
            monkeypatch (pytest.MonkeyPatch): Replaces scan() with a
                recording stub.
        """

        calls: list[tuple[object, object]] = []

        def fake_scan(app: object, cfg: object) -> None:
            calls.append((app, cfg))

        monkeypatch.setattr("src.services.scan.scan", fake_scan)

        cfg = configparser.ConfigParser()
        ctrl.start_scan(cfg)

        spawned[0].join(timeout=2)

        assert calls == [(ctrl, cfg)]
