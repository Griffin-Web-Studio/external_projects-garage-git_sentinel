from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
import tkinter as tk

from .. import APP_NAME, APP_VERSION
from ..models import MsgFinish

# ─────────────────────────────────────────────────────────────────| Helpers |──


def _open_file(path: Path) -> None:
    """Open *path* with the default application, cross-platform."""
    if sys.platform == "win32":
        os.startfile(path)

    else:
        subprocess.Popen(["xdg-open", str(path)])


# ───────────────────────────────────────────────────────────────| Main view |──


class MainWindow(tk.Frame):
    """Main application frame containing all persistent UI elements.

    Packed to fill the tk.Tk root owned by GitSentinelApp. All public
    methods must be called from the main thread only; the drain loop in
    app.py is the sole caller.

    Layout (top to bottom):
        - Bold status label
        - Progress bar
        - Scrollable monospace log pane (expands to fill available space)
        - Prompt container (empty until a gate fires; managed by PromptArea)
        - Close / Acknowledge button

    Args:
        master: The tk.Tk root window.
        on_close: Callback invoked when the close button is pressed or the
            scan completes and the user clicks Acknowledge.
    """

    def __init__(self, master: tk.Tk, on_close: Callable[[], None]) -> None:
        super().__init__(master)
        self._on_close = on_close
        self.pack(fill="both", expand=True)
        self._build_ui()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Construct and grid all child widgets."""
        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=(10, 2))
        self._status_var = tk.StringVar(value="Initialising...")
        tk.Label(
            top,
            textvariable=self._status_var,
            anchor="w",
            font=("sans-serif", 10, "bold"),
        ).pack(fill="x")

        self._prog_bar_var = tk.DoubleVar(value=0.0)
        ttk.Progressbar(self, variable=self._prog_bar_var, maximum=100.0).pack(
            fill="x",
            padx=10,
            pady=4,
        )

        log_outer = tk.Frame(self)
        log_outer.pack(fill="both", expand=True, padx=10, pady=2)

        # Scrollbars must be packed before the Text widget so the pack
        # geometry manager anchors them to the edges first; the Text then
        # fills whatever space remains.
        vsb = ttk.Scrollbar(log_outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(log_outer, orient="horizontal")
        hsb.pack(side="bottom", fill="x")
        self._log_text = tk.Text(
            log_outer,
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            font=("monospace", 9),
            state="disabled",  # re-enabled momentarily on each append_log call
            wrap="none",
        )
        self._log_text.pack(fill="both", expand=True)
        vsb.config(command=self._log_text.yview)
        hsb.config(command=self._log_text.xview)

        self._prompt_area = tk.Frame(self)
        self._prompt_area.pack(fill="x", padx=10, pady=2)

        self._close_btn = tk.Button(
            self,
            text="Please wait...",
            state="disabled",
            command=self._on_close,
        )
        self._close_btn.pack(pady=(4, 10))

    @property
    def prompt_container(self) -> tk.Frame:
        """The frame that PromptArea renders gate prompts into."""
        return self._prompt_area

    # ── Update methods (main-thread only) ─────────────────────────────────────

    def update_status(self, text: str) -> None:
        """Set the bold status label text.

        Args:
            text: New status string.
        """
        self._status_var.set(text)

    def update_progress(self, pct: float) -> None:
        """Set the progress bar value.

        Args:
            pct: Percentage between 0.0 and 100.0.
        """
        self._prog_bar_var.set(pct)

    def append_log(self, text: str) -> None:
        """Append *text* as a new line in the log pane.

        Args:
            text: Line to append; a newline is added automatically.
        """
        self._log_text.config(state="normal")
        self._log_text.insert("end", text + "\n")
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    # ── Finish ────────────────────────────────────────────────────────────────

    def handle_finish(self, msg: MsgFinish) -> None:
        """Update the UI to reflect scan completion.

        Snaps the progress bar to 100, updates the status label, and enables
        the close button. When a report file exists an 'Open Report' button is
        injected above the close button.

        Args:
            msg: The finish message from the worker.
        """
        self._prog_bar_var.set(100.0)
        if msg.issue_count == 0:
            self._status_var.set("✔️  All clear - no issues found.")
            self._close_btn.config(text="Close", state="normal")
        else:
            self._status_var.set(
                f"⚠️  {msg.issue_count} repo(s) with issues"
                f" - report saved to Desktop."
            )

            if msg.report_path and msg.report_path.exists():
                report_path = msg.report_path
                row = tk.Frame(self)
                # pack(before=) inserts the row above the close button
                # without rebuilding the whole layout
                row.pack(before=self._close_btn, pady=(0, 4))
                tk.Button(
                    row,
                    text="Open Report",
                    command=lambda: _open_file(report_path),
                ).pack(side="left", padx=4)

            self._close_btn.config(text="Acknowledge & Close", state="normal")
