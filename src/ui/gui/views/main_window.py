from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
import tkinter as tk

from src.models import MsgFinish

# ─────────────────────────────────────────────────────────────────| Helpers |──


def _open_file(path: Path) -> None:  # pragma: no cover - no custom logic
    """Open *path* with the default MIME application.

    Args:
        path (Path): file (like report) path
    """

    if sys.platform == "win32":
        from src.platform.windows.gui import open_file

    else:
        from src.platform.linux.gui import open_file

    open_file(path)


# ───────────────────────────────────────────────────────────────| Main view |──


class MainWindow(tk.Frame):
    """Main application frame containing all persistent UI elements.

    Packed to fill the tk.Tk root owned by GitSentinelApp. All public methods
    must be called from the main thread only; the drain loop in app.py is the
    sole caller.

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

        # Header
        header = tk.Frame(self)
        header.pack(fill="x", padx=10, pady=(10, 2))

        # Current Status Label
        self._status_var = tk.StringVar(value="Initialising...")
        tk.Label(
            header,
            textvariable=self._status_var,
            anchor="w",
            font=("sans-serif", 10, "bold"),
        ).pack(fill="x")

        # Progress Bar
        self._prog_bar_var = tk.DoubleVar(value=0.0)
        ttk.Progressbar(self, variable=self._prog_bar_var, maximum=100.0).pack(
            fill="x",
            padx=10,
            pady=4,
        )

        # Body
        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=2)

        # Scrollbars must be packed before the Text widget so the pack
        # geometry manager anchors them to the edges first; the Text then
        # fills whatever space remains.
        y_scroll = ttk.Scrollbar(body, orient="vertical")
        y_scroll.pack(side="right", fill="y")

        x_scroll = ttk.Scrollbar(body, orient="horizontal")
        x_scroll.pack(side="bottom", fill="x")

        self._log_text = tk.Text(
            body,
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
            font=("monospace", 9),
            state="disabled",  # re-enabled momentarily on each append_log call
            wrap="none",
        )
        self._log_text.pack(fill="both", expand=True)

        ## Register Text colour tags
        self._log_text.tag_config("error", foreground="red")
        self._log_text.tag_config("warning", foreground="orange")
        self._log_text.tag_config("info", foreground="blue")

        y_scroll.config(command=self._log_text.yview)
        x_scroll.config(command=self._log_text.xview)

        # Footer
        self._prompt_area = tk.Frame(self)
        self._prompt_area.pack(fill="x", padx=10, pady=2)

        # Buttons - right-aligned row
        self._button_row = tk.Frame(self)
        self._button_row.pack(fill="x", padx=10, pady=(4, 10))

        self._close_btn = tk.Button(
            self._button_row,
            text="Please wait...",
            state="disabled",
            command=self._on_close,
        )
        self._close_btn.pack(side="right")

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

    def append_log(self, text: str, tag: str = "") -> None:
        """Append *text* as a new line in the log pane.

        Args:
            text: Line to append; a newline is added automatically.
            tag: Optional colour tag ("error", "warning", "info").
        """

        self._log_text.config(state="normal")

        if tag:
            self._log_text.insert("end", text + "\n", tag)

        else:
            self._log_text.insert("end", text + "\n")

        self._log_text.see("end")
        self._log_text.config(state="disabled")

    # ── Finish ────────────────────────────────────────────────────────────────

    def handle_finish(self, msg: MsgFinish) -> None:
        """Update the UI to reflect scan completion.

        Snaps the progress bar to 100, updates the status label, and enables the
        close button. When a report file exists an 'Open Report' button is
        injected above the close button.

        Args:
            msg: The finish message from the worker.
        """

        self._prog_bar_var.set(100.0)

        if msg.issue_count == 0:
            self._status_var.set("✔️  All clear - no issues found.")
            self._close_btn.config(text="Close", state="normal")

        else:
            location = ""

            if msg.report_path:
                try:
                    location = (
                        " ~/"
                        + msg.report_path.parent.relative_to(
                            Path.home()
                        ).as_posix()
                    )

                except ValueError:
                    location = f" {msg.report_path.parent}"

            self._status_var.set(
                f"⚠️  {msg.issue_count} repo(s) with issues"
                f" - report saved to{location}."
            )

            if msg.report_path and msg.report_path.exists():
                report_path = msg.report_path
                tk.Button(
                    self._button_row,
                    text="Open Report",
                    command=lambda: _open_file(report_path),
                ).pack(side="right", padx=(0, 8))

            self._close_btn.config(text="Acknowledge & Close", state="normal")
