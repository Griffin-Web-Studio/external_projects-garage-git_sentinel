from __future__ import annotations

import tkinter as tk

from src.services.git_ops import ssh_host_key
from src.models import GateHTTP, GateSSH

# ────────────────────────────────────────────────────────────| Gate prompts |──


class PromptArea:
    """Renders gate prompts into a container frame owned by MainWindow.

    Not a widget subclass - wraps a tk.Frame and replaces its contents whenever
    a gate fires. The resolve methods set the gate result field and call
    event.set() to unblock the worker thread.

    Args:
        container: The tk.Frame (owned by MainWindow) to render prompts into.
    """

    def __init__(self, container: tk.Frame) -> None:
        self._container = container

    # ── Public API ────────────────────────────────────────────────────────────

    def clear(self) -> None:
        """Remove all widgets from the prompt area."""
        # destroy rather than hide - reclaims widget IDs and avoids stale state
        # when the next prompt type has a different layout
        for w in self._container.winfo_children():
            w.destroy()

    def show_ssh(self, req: GateSSH) -> None:
        """Render the SSH approval prompt for *req*.

        Args:
            req: The GateSSH placed on the gate queue by the worker.
        """

        self.clear()

        host = ssh_host_key(req.url).split("@")[-1]

        message_banner = tk.LabelFrame(
            self._container,
            text=" SSH Authorisation Required ",
            padx=8,
            pady=6,
        )
        message_banner.pack(fill="x")
        contents = (
            f"Repository : {req.repo}\n"
            f"Remote URL : {req.url}\n"
            f"SSH host   : {host}\n\n"
            f"Approving will open an SSH connection to '{host}'.\n"
            f"Authentication will be needed once for this host; all further\n"
            f"connections this session will reuse the control socket."
        )
        tk.Label(
            message_banner,
            text=contents,
            anchor="w",
            justify="left",
            font=("monospace", 9),
        ).pack(fill="x")

        # button row
        button_row = tk.Frame(message_banner)
        button_row.pack(pady=(6, 0))

        tk.Button(
            button_row,
            text="Approve",
            width=16,
            command=lambda: self._resolve_ssh(req, True),
        ).pack(side="left", padx=4)
        tk.Button(
            button_row,
            text="Skip this host",
            width=16,
            command=lambda: self._resolve_ssh(req, False),
        ).pack(side="left", padx=4)

    def show_http(self, req: GateHTTP) -> None:
        """Render the HTTP retry prompt for *req*.

        Args:
            req: The GateHTTP placed on the gate queue by the worker.
        """

        self.clear()

        message_banner = tk.LabelFrame(
            self._container,
            text=" HTTP Remote Unreachable ",
            padx=8,
            pady=6,
        )
        message_banner.pack(fill="x")
        contents = (
            f"Repository : {req.repo}\n"
            f"Remote URL : {req.url}\n"
            f"Error      : {req.error}\n\n"
            f"Retry the connection, or skip this remote?"
        )
        tk.Label(
            message_banner,
            text=contents,
            anchor="w",
            justify="left",
            font=("monospace", 9),
        ).pack(fill="x")

        # Button Row
        row = tk.Frame(message_banner)
        row.pack(pady=(6, 0))

        tk.Button(
            row,
            text="Retry",
            width=16,
            command=lambda: self._resolve_http(req, True),
        ).pack(side="left", padx=4)
        tk.Button(
            row,
            text="Skip",
            width=16,
            command=lambda: self._resolve_http(req, False),
        ).pack(side="left", padx=4)

    # ── Resolvers ─────────────────────────────────────────────────────────────

    def _resolve_ssh(self, req: GateSSH, approved: bool) -> None:
        """Record the user's SSH decision and unblock the worker.

        Args:
            req: The gate being resolved.
            approved: True if the user approved the connection.
        """

        req.approved = approved
        self.clear()

        # unblocks the worker thread waiting in request_ssh
        req.event.set()

    def _resolve_http(self, req: GateHTTP, retry: bool) -> None:
        """Record the user's HTTP decision and unblock the worker.

        Args:
            req: The gate being resolved.
            retry: True if the user requested a retry.
        """
        req.retry = retry
        self.clear()

        # unblocks the worker thread waiting in request_http_retry
        req.event.set()
