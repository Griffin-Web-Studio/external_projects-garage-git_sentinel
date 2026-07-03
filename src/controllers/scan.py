from __future__ import annotations

import configparser
import threading
from pathlib import Path

from src.controllers.events import EventBus
from src.models import (
    AppProtocol,
    GateHTTP,
    GateSSH,
    MsgFinish,
    MsgLog,
    MsgProgress,
    MsgStatus,
)

# ──────────────────────────────────────────────────────────| ScanController |──


class ScanController(AppProtocol):
    """Implements AppProtocol; bridges the scan worker and the EventBus.

    Emits typed Msg* events on the bus for fire-and-forget updates (log, status,
    progress, finish). Gate requests (SSH approval, HTTP retry) emit a gate
    event then block the worker thread on a threading.Event until the UI
    resolves them.

    Args:
        bus (EventBus): Shared EventBus that UI adapters subscribe to.
    """

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._closable = False

    # ── AppProtocol ───────────────────────────────────────────────────────────

    def log(self, text: str, tag: str = "") -> None:
        """Emit a log line on the bus.

        Args:
            text (str): Line to append; a newline is added by the view.
            tag (str): Optional colour tag ("error", "warning", "info").
        """

        self._bus.emit("scan.log", MsgLog(text, tag))

    def set_status(self, text: str) -> None:
        """Emit a status update on the bus.

        Args:
            text (str): New status string.
        """

        self._bus.emit("scan.status", MsgStatus(text))

    def set_progress(self, pct: float) -> None:
        """Emit a progress update on the bus.

        Args:
            pct (float): Percentage between 0.0 and 100.0.
        """

        self._bus.emit("scan.progress", MsgProgress(pct))

    def finish(self, issue_count: int, report_path: Path | None) -> None:
        """Mark the scan as closable and emit a finish event on the bus.

        Args:
            issue_count (int): Number of repositories with at least one issue.
            report_path (Path | None): Path to the written report, or None for a
                clean run.
        """

        self._closable = True

        self._bus.emit("scan.finish", MsgFinish(issue_count, report_path))

    def request_ssh(self, url: str, repo_short: str) -> bool:
        """Emit a gate event for SSH approval and block until resolved.

        Args:
            url (str): SSH remote URL requiring approval.
            repo_short (str): Tilde-prefixed repo path shown in the prompt.

        Returns:
            bool: True if the user approved, False if declined.
        """

        req = GateSSH(url, repo_short)

        self._bus.emit("scan.gate", req)
        req.event.wait()

        return req.approved

    def request_http_retry(self, url: str, repo_short: str, error: str) -> bool:
        """Emit a gate event for an HTTP retry decision and block until
        resolved.

        Args:
            url (str): HTTP remote URL that failed.
            repo_short (str): Tilde-prefixed repo path shown in the prompt.
            error (str): Error string from the failed fetch.

        Returns:
            bool: True if the user requested a retry, False to skip.
        """

        req = GateHTTP(url, repo_short, error)

        self._bus.emit("scan.gate", req)
        req.event.wait()

        return req.retry

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start_scan(self, cfg: configparser.ConfigParser) -> None:
        """Start the scan worker in a background daemon thread.

        Args:
            cfg (configparser.ConfigParser): Loaded application configuration.
        """

        from src.services.scan import scan

        worker = threading.Thread(target=scan, args=(self, cfg), daemon=True)

        worker.start()

    @property
    def closable(self) -> bool:
        """True once finish() has been called; gates the close button and WM."""

        return self._closable
