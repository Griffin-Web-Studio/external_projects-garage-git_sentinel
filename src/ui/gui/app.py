from __future__ import annotations

import configparser
from collections.abc import Callable
from typing import Any
import tkinter as tk

from src import APP_NAME, APP_VERSION
from src.config import load_config
from src.controllers.events import EventBus
from src.controllers.scan import ScanController
from src.migrations import apply_migrations, chain, make_adapter
from src.models import (
    GateHTTP,
    GateSSH,
    MsgFinish,
    MsgLog,
    MsgProgress,
    MsgStatus,
)
from .views.migration_dialog import show_migration_dialog
from .views.main_window import MainWindow
from .views.prompt_area import PromptArea

# ─────────────────────────────────────────────────────────────| Coordinator |──


class GitSentinelApp(tk.Tk):
    """Application root window.

    Owns the EventBus and ScanController, wires bus events to the Tkinter views
    via thread-safe after() adapters, and manages window lifecycle. All widget
    work is delegated to MainWindow; gate prompt rendering to PromptArea.

    Args:
        cfg: Loaded application config parser.
    """

    def __init__(self, cfg: configparser.ConfigParser) -> None:
        super().__init__()

        self._cfg = cfg

        # window chrome
        self.title(f"{APP_NAME}  v{APP_VERSION}")
        self.minsize(680, 480)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._guard_close)

        # views
        self._window = MainWindow(self, on_close=self._on_close_btn)
        self._prompts = PromptArea(self._window.prompt_container)

        # controller + bus
        self._bus = EventBus()
        self._controller = ScanController(self._bus)
        self._subscribe()

        # defer startup so the window renders before any dialog or scan begins
        self.after(0, self._begin)

    # ── Startup sequencing ────────────────────────────────────────────────────

    def _begin(self) -> None:
        """Apply pending migrations (if any), then start the scan.

        Migrations are resolved first; the scan only starts after the dialog
        is dismissed so the two cannot race.
        """
        pending = chain.pending(make_adapter())

        if pending:
            show_migration_dialog(
                self,
                pending,
                apply_migrations,
                on_close=self._start_after_migration,
            )

        else:
            self._controller.start_scan(self._cfg)

    def _start_after_migration(self) -> None:
        """Reload config from disk after migrations are applied, then scan.

        The in-memory config predates the migration; reloading ensures the scan
        runs against the updated values and no DEPRECATED warnings are emitted.
        """
        self._cfg = load_config()
        self._controller.start_scan(self._cfg)

    # ── Bus subscriptions ─────────────────────────────────────────────────────

    def _subscribe(self) -> None:
        """Wire bus events to views via thread-safe Tkinter after() adapters."""

        def thread_safe(fn: Callable[[Any], None]) -> Callable[[Any], None]:
            def wrapper(data: Any) -> None:
                self.after(0, lambda: fn(data))

            return wrapper

        self._bus.subscribe("scan.log", thread_safe(self._on_log))
        self._bus.subscribe("scan.status", thread_safe(self._on_status))
        self._bus.subscribe("scan.progress", thread_safe(self._on_progress))
        self._bus.subscribe("scan.finish", thread_safe(self._on_finish))
        self._bus.subscribe("scan.gate", thread_safe(self._on_gate))

    # ── Event handlers (main thread) ──────────────────────────────────────────

    def _on_log(self, msg: MsgLog) -> None:
        """On log handler

        Args:
            msg (MsgLog): Message Log Object
        """

        self._window.append_log(msg.text, msg.tag)

    def _on_status(self, msg: MsgStatus) -> None:
        """On status handler

        Args:
            msg (MsgStatus): Message Status Object
        """

        self._window.update_status(msg.text)

    def _on_progress(self, msg: MsgProgress) -> None:
        """On progress handler

        Args:
            msg (MsgProgress): Message Progress Object
        """

        self._window.update_progress(msg.pct)

    def _on_finish(self, msg: MsgFinish) -> None:
        """On finish handler

        Args:
            msg (MsgFinish): Message Finish Object
        """

        self._window.handle_finish(msg)

    def _on_gate(self, req: GateSSH | GateHTTP) -> None:
        """On gate handler

        Args:
            req (GateSSH | GateHTTP): Gate Type (SSH/HTTP) Object
        """

        self.bell()  # Alert the user

        if isinstance(req, GateSSH):
            self._prompts.show_ssh(req)

        elif isinstance(req, GateHTTP):
            self._prompts.show_http(req)

    # ── Close guards ──────────────────────────────────────────────────────────

    def _guard_close(self) -> None:
        """Handle WM close button; ignored while scan is running."""

        if self._controller.closable:
            self.destroy()

    def _on_close_btn(self) -> None:
        """Handle the Close / Acknowledge button."""

        self.destroy()
