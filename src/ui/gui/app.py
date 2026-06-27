from __future__ import annotations

import configparser
import queue
from pathlib import Path
import tkinter as tk

from src import APP_NAME, APP_VERSION
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
from .views.prompt_area import PromptArea
from .views.main_window import MainWindow

# ─────────────────────────────────────────────────────────────| Coordinator |──


class GitSentinelApp(tk.Tk):
    """Application root window and AppProtocol implementer.

    Owns the two inter-thread queues, runs the drain timers on the Tk event
    loop, and exposes the worker-callable surface that scan.py uses via
    AppProtocol. All widget work is delegated to MainWindow; gate prompt
    rendering to PromptArea.

    Args:
        cfg: Loaded application config parser.
    """

    def __init__(self, cfg: configparser.ConfigParser) -> None:
        super().__init__()

        # scan.py reads repo paths and thresholds from cfg at runtime
        self.cfg = cfg

        # window chrome
        self.title(f"{APP_NAME}  v{APP_VERSION}")
        self.minsize(680, 480)
        self.resizable(True, True)

        # intercept the x button so users can't close the window mid-scan
        self.protocol("WM_DELETE_WINDOW", self._guard_close)

        # flipped to True by MsgFinish; gates both the x button and close button
        self._closable = False

        # _ui_queue: fire-and-forget - worker puts Msg* objects, main thread
        # drains them every 80 ms. Keeps all Tkinter calls on the main thread
        # because Tk is not thread-safe.
        self._ui_queue: queue.Queue[
            MsgLog | MsgStatus | MsgProgress | MsgFinish
        ] = queue.Queue()

        # _gate_queue: blocking - worker puts a Gate* then waits on gate.event
        # until the user responds and the main thread calls event.set()
        self._gate_queue: queue.Queue[GateSSH | GateHTTP] = queue.Queue()

        self._window = MainWindow(self, on_close=self._on_close_btn)
        self._prompts = PromptArea(self._window.prompt_container)

        # kick off the polling loops; each reschedules itself indefinitely
        self.after(80, self._drain_ui_queue)
        self.after(80, self._check_gate_queue)

        pending = chain.pending(make_adapter())
        if pending:

            def _show_migration() -> None:
                show_migration_dialog(self, pending, apply_migrations)

            self.after(0, _show_migration)

    # ── Queue drains (main thread) ────────────────────────────────────────────

    def _drain_ui_queue(self) -> None:
        """Process all pending UI messages then reschedule itself."""
        try:
            # Loop until the queue is empty so the full backlog is flushed in
            # one tick - avoids visible lag when the worker emits a burst.
            while True:
                msg = self._ui_queue.get_nowait()

                if isinstance(msg, MsgLog):
                    self._window.append_log(msg.text, msg.tag)

                elif isinstance(msg, MsgStatus):
                    self._window.update_status(msg.text)

                elif isinstance(msg, MsgProgress):
                    self._window.update_progress(msg.pct)

                elif isinstance(msg, MsgFinish):
                    # Unlock close before handle_finish so the button is
                    # immediately active when it becomes visible.
                    self._closable = True
                    self._window.handle_finish(msg)

        except queue.Empty:
            pass  # normal exit - queue exhausted for this tick

        self.after(80, self._drain_ui_queue)

    def _check_gate_queue(self) -> None:
        """Check for a pending gate request and render its prompt if present."""
        try:
            # Only one gate is processed per tick. The worker blocks on
            # gate.event until the user responds, so a second gate cannot
            # arrive until the first is resolved.
            req = self._gate_queue.get_nowait()
            self.bell()  # audible alert so the user notices the prompt

            if isinstance(req, GateSSH):
                self._prompts.show_ssh(req)

            elif isinstance(req, GateHTTP):
                self._prompts.show_http(req)

        except queue.Empty:
            pass

        self.after(150, self._check_gate_queue)

    # ── Worker-callable helpers (thread-safe) ─────────────────────────────────

    def log(self, text: str, tag: str = "") -> None:
        """Append a line to the log pane from any thread.

        Args:
            text: Line to append; a newline is added automatically.
            tag: Optional colour tag ("error", "warning", "info").
        """
        self._ui_queue.put(MsgLog(text, tag))

    def set_status(self, text: str) -> None:
        """Update the status label from any thread.

        Args:
            text: New status string.
        """
        self._ui_queue.put(MsgStatus(text))

    def set_progress(self, pct: float) -> None:
        """Set the progress bar value from any thread.

        Args:
            pct: Percentage between 0.0 and 100.0.
        """
        self._ui_queue.put(MsgProgress(pct))

    def finish(self, issue_count: int, report_path: Path | None) -> None:
        """Signal scan completion from the worker thread.

        Args:
            issue_count: Number of repositories with at least one issue.
            report_path: Path to the written report, or None for a clean run.
        """
        self._ui_queue.put(MsgFinish(issue_count, report_path))

    def request_ssh(self, url: str, repo_short: str) -> bool:
        """Block the worker until the user approves or declines SSH for this
        host.

        Places a GateSSH on the gate queue and waits on its event. The main
        thread renders the prompt and sets the event when the user responds.

        Args:
            url: SSH remote URL requiring approval.
            repo_short: Tilde-prefixed repo path shown in the prompt.

        Returns:
            bool: True if the user approved, False if declined.
        """
        req = GateSSH(url, repo_short)
        self._gate_queue.put(req)

        # blocks the worker thread here until _resolve_ssh sets the event
        req.event.wait()
        return req.approved

    def request_http_retry(self, url: str, repo_short: str, error: str) -> bool:
        """Block the worker until the user chooses to retry or skip an HTTP
        remote.

        Args:
            url: HTTP remote URL that failed.
            repo_short: Tilde-prefixed repo path shown in the prompt.
            error: Error string from the failed fetch.

        Returns:
            bool: True if the user requested a retry, False to skip.
        """
        req = GateHTTP(url, repo_short, error)
        self._gate_queue.put(req)
        # blocks the worker thread here until _resolve_http sets the event
        req.event.wait()
        return req.retry

    # ── Close guards ──────────────────────────────────────────────────────────

    def _guard_close(self) -> None:
        """Handle WM close button; ignored while scan is running."""
        if self._closable:
            self.destroy()

    def _on_close_btn(self) -> None:
        """Handle the Close / Acknowledge button."""
        self.destroy()
