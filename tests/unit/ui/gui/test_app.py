from __future__ import annotations

import configparser
import tkinter as tk
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from src import APP_NAME, APP_VERSION
from src.config.migrate import MigrationStep
from src.models import (
    GateHTTP,
    GateSSH,
    MsgFinish,
    MsgLog,
    MsgProgress,
    MsgStatus,
)
from src.ui.gui.app import GitSentinelApp

# ────────────────────────────────────────────────────────────────| Fixtures |──


@pytest.fixture(autouse=True)
def no_real_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent start_scan from spawning a real background scan worker.

    Args:
        monkeypatch (pytest.MonkeyPatch): Replaces ScanController.start_scan
            with a no-op for every test in this module.
    """

    monkeypatch.setattr(
        "src.controllers.scan.ScanController.start_scan", lambda self, cfg: None
    )


@pytest.fixture
def no_pending_migrations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the module-level migration chain report nothing pending.

    Args:
        monkeypatch (pytest.MonkeyPatch): Patches chain.pending().
    """

    monkeypatch.setattr("src.ui.gui.app.chain.pending", lambda adapter: [])
    monkeypatch.setattr("src.ui.gui.app.make_adapter", lambda: object())


@pytest.fixture
def app(
    no_pending_migrations: None,
) -> Generator[GitSentinelApp]:
    """Construct a GitSentinelApp with a withdrawn (invisible) window.

    Args:
        no_pending_migrations (None): Ensures construction doesn't trigger
            the migration dialog.

    Yields:
        GitSentinelApp: A freshly constructed, withdrawn app instance.
    """

    instance = GitSentinelApp(configparser.ConfigParser())
    instance.withdraw()

    yield instance

    try:
        instance.destroy()

    except tk.TclError:
        pass  # already destroyed by the test itself


def _ssh_req() -> GateSSH:
    """Build a minimal GateSSH request for use in tests.

    Returns:
        GateSSH: A GateSSH instance with a sample URL and local repo path.
    """

    return GateSSH(url="git@github.com:user/repo.git", repo="~/projects/repo")


def _http_req() -> GateHTTP:
    """Build a minimal GateHTTP request with a simulated error for use in
    tests.

    Returns:
        GateHTTP: A GateHTTP instance with a sample URL, repo path, and error
                 message.
    """

    return GateHTTP(
        url="https://example.com/repo.git", repo="~/projects/repo", error="boom"
    )


def _is_destroyed(app: GitSentinelApp) -> bool:
    """True if *app*'s underlying Tk window no longer exists.

    destroy() on a Tk root tears down the interpreter, so winfo_exists()
    raises TclError afterwards rather than returning False.

    Args:
        app (GitSentinelApp): App instance to check.

    Returns:
        bool: True if the window has been destroyed.
    """

    try:
        return not app.winfo_exists()

    except tk.TclError:
        return True


# ────────────────────────────────────────────────────────────────────| Init |──


class TestInit:
    """GitSentinelApp construction wires up window chrome and components."""

    def test_title_contains_app_name_and_version(
        self, app: GitSentinelApp
    ) -> None:
        """Window title shows APP_NAME and APP_VERSION.

        Args:
            app (GitSentinelApp): App under test.
        """

        assert APP_NAME in app.title()
        assert APP_VERSION in app.title()

    def test_starts_scan_when_no_pending_migrations(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When chain.pending() is empty, construction starts the scan
        directly without showing a migration dialog.

        Args:
            monkeypatch (pytest.MonkeyPatch): Patches chain.pending() and
                records start_scan calls.
        """

        monkeypatch.setattr("src.ui.gui.app.chain.pending", lambda adapter: [])
        monkeypatch.setattr("src.ui.gui.app.make_adapter", lambda: object())

        calls: list[object] = []
        monkeypatch.setattr(
            "src.controllers.scan.ScanController.start_scan",
            lambda self, cfg: calls.append(cfg),
        )

        cfg = configparser.ConfigParser()
        instance = GitSentinelApp(cfg)
        instance.withdraw()

        try:
            instance._begin()

            assert calls == [cfg]

        finally:
            instance.destroy()


# ──────────────────────────────────────────────────────────────────| _begin |──


class TestBegin:
    """_begin() dispatches to the migration dialog or starts the scan."""

    def test_shows_migration_dialog_when_pending(
        self, app: GitSentinelApp, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When migrations are pending, show_migration_dialog is invoked
        instead of starting the scan immediately.

        Args:
            app (GitSentinelApp): App under test.
            monkeypatch (pytest.MonkeyPatch): Patches chain.pending() to
                report one pending step, and records dialog invocations.
        """

        step = MigrationStep(
            from_version=0,
            to_version=1,
            description="test",
            fn=lambda cfg: None,
        )
        monkeypatch.setattr(
            "src.ui.gui.app.chain.pending", lambda adapter: [step]
        )

        dialog_calls: list[tuple[object, object, object, object]] = []
        monkeypatch.setattr(
            "src.ui.gui.app.show_migration_dialog",
            lambda parent, pending, on_update, on_close=None: dialog_calls.append(
                (parent, pending, on_update, on_close)
            ),
        )

        scan_calls: list[object] = []
        monkeypatch.setattr(
            "src.controllers.scan.ScanController.start_scan",
            lambda self, cfg: scan_calls.append(cfg),
        )

        app._begin()

        assert len(dialog_calls) == 1

        parent, pending, on_update, on_close = dialog_calls[0]

        assert parent is app
        assert pending == [step]
        assert on_close == app._start_after_migration
        assert scan_calls == []


# ──────────────────────────────────────────────────| _start_after_migration |──


class TestStartAfterMigration:
    """_start_after_migration reloads config from disk then starts the scan."""

    def test_reloads_config_and_starts_scan(
        self, app: GitSentinelApp, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The reloaded config (not the pre-migration one) is passed to
        start_scan.

        Args:
            app (GitSentinelApp): App under test.
            monkeypatch (pytest.MonkeyPatch): Replaces load_config() with a
                sentinel and records start_scan calls.
        """

        new_cfg = configparser.ConfigParser()
        new_cfg["marker"] = {"reloaded": "yes"}

        monkeypatch.setattr("src.ui.gui.app.load_config", lambda: new_cfg)

        calls: list[object] = []
        monkeypatch.setattr(
            "src.controllers.scan.ScanController.start_scan",
            lambda self, cfg: calls.append(cfg),
        )

        app._start_after_migration()

        assert app._cfg is new_cfg
        assert calls == [new_cfg]


# ───────────────────────────────────────────────────| Event handlers |──


class TestEventHandlers:
    """Bus event handlers forward messages to the owned MainWindow."""

    def test_on_log_appends_to_window(self, app: GitSentinelApp) -> None:
        """_on_log appends the message text/tag to the log pane.

        Args:
            app (GitSentinelApp): App under test.
        """

        app._on_log(MsgLog("hello", "info"))

        assert "hello" in app._window._log_text.get("1.0", "end")

    def test_on_status_updates_window(self, app: GitSentinelApp) -> None:
        """_on_status updates the status label.

        Args:
            app (GitSentinelApp): App under test.
        """

        app._on_status(MsgStatus("scanning..."))

        assert app._window._status_var.get() == "scanning..."

    def test_on_progress_updates_window(self, app: GitSentinelApp) -> None:
        """_on_progress updates the progress bar value.

        Args:
            app (GitSentinelApp): App under test.
        """

        app._on_progress(MsgProgress(42.0))

        assert app._window._prog_bar_var.get() == pytest.approx(42.0)

    def test_on_finish_updates_window(self, app: GitSentinelApp) -> None:
        """_on_finish forwards to the window's handle_finish.

        Args:
            app (GitSentinelApp): App under test.
        """

        app._on_finish(MsgFinish(issue_count=0, report_path=None))

        assert str(app._window._close_btn["state"]) == "normal"

    def test_on_gate_ssh_shows_ssh_prompt(
        self, app: GitSentinelApp, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_on_gate with a GateSSH renders the SSH prompt.

        Args:
            app (GitSentinelApp): App under test.
            monkeypatch (pytest.MonkeyPatch): Replaces PromptArea.show_ssh
                with a spy.
        """

        show_ssh = MagicMock()

        monkeypatch.setattr(app._prompts, "show_ssh", show_ssh)

        req = _ssh_req()
        app._on_gate(req)

        show_ssh.assert_called_once_with(req)

    def test_on_gate_http_shows_http_prompt(
        self, app: GitSentinelApp, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_on_gate with a GateHTTP renders the HTTP retry prompt.

        Args:
            app (GitSentinelApp): App under test.
            monkeypatch (pytest.MonkeyPatch): Replaces PromptArea.show_http
                with a spy.
        """

        show_http = MagicMock()

        monkeypatch.setattr(app._prompts, "show_http", show_http)

        req = _http_req()
        app._on_gate(req)

        show_http.assert_called_once_with(req)

    def test_bus_emit_reaches_window_after_update(
        self, app: GitSentinelApp
    ) -> None:
        """Emitting on the bus reaches the window once pending after()
        callbacks are flushed via update().

        Args:
            app (GitSentinelApp): App under test.
        """

        app._bus.emit("scan.status", MsgStatus("via bus"))
        app.update()

        assert app._window._status_var.get() == "via bus"


# ───────────────────────────────────────────────────────────| Close guards |──


class TestGuardClose:
    """_guard_close only destroys the window once the scan is closable."""

    def test_ignored_while_not_closable(self, app: GitSentinelApp) -> None:
        """The window survives a close attempt while the scan is running.

        Args:
            app (GitSentinelApp): App under test.
        """

        app._guard_close()

        assert not _is_destroyed(app)

    def test_destroys_when_closable(self, app: GitSentinelApp) -> None:
        """The window is destroyed once the controller reports closable.

        Args:
            app (GitSentinelApp): App under test.
        """

        app._controller.finish(0, None)
        app._guard_close()

        assert _is_destroyed(app)


class TestOnCloseBtn:
    """_on_close_btn always destroys the window."""

    def test_destroys_window(self, app: GitSentinelApp) -> None:
        """Clicking Close/Acknowledge destroys the window unconditionally.

        Args:
            app (GitSentinelApp): App under test.
        """

        app._on_close_btn()

        assert _is_destroyed(app)
