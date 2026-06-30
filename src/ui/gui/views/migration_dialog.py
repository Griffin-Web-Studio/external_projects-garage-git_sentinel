from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable

from src import CONF_FILE
from src.configmigrate import MigrationStep


def show_migration_dialog(
    parent: tk.Misc,
    pending: list[MigrationStep],
    on_update: Callable[[], OSError | None],
    on_close: Callable[[], None] | None = None,
) -> None:
    """Show a modal dialog listing pending config migrations.

    Offers to apply them automatically or dismiss for manual handling.
    `on_close` is called after the dialog is dismissed via either button so
    callers can sequence work that must not start until migrations are resolved.

    Args:
        parent (tk.Misc): Parent widget the dialog is transient to.
        pending (list[MigrationStep]): Steps to display and optionally apply.
        on_update (Callable[[], OSError | None]): Called when the user clicks
            Update; returns an OSError on failure, None on success.
        on_close (Callable[[], None] | None): Optional callback invoked after
            the dialog is dismissed (both Update success and Dismiss paths).
    """

    # Dialog Box
    dialog = tk.Toplevel(parent)
    dialog.title("Config update available")
    dialog.resizable(False, False)
    dialog.grab_set()

    # Message Box body
    body = tk.Frame(dialog, padx=16, pady=12)
    body.pack(fill="both", expand=True)

    contents = "settings.ini has pending updates.\n\n"

    for step in pending:
        contents += f"  v{step.from_version} to v{step.to_version}"

        if step.description:
            contents += f": {step.description}"

        contents += "\n"

    contents += (
        "\nClick Update to apply automatically,\n"
        "or Dismiss to handle it manually.\n\n"
        f"Settings file:\n{CONF_FILE}"
    )

    # Contents printout
    tk.Label(
        body,
        text=contents,
        justify="left",
        anchor="w",
        font=("monospace", 9),
    ).pack(fill="x")

    # Buttons row
    button_row = tk.Frame(body)
    button_row.pack(pady=(12, 0))

    def _dismiss() -> None:
        dialog.destroy()
        if on_close:
            on_close()

    def _do_update() -> None:
        exception = on_update()  # returns None on success

        if exception:
            messagebox.showerror(
                "Update failed", f"Could not update settings.ini:\n{exception}"
            )

            return

        _dismiss()

    tk.Button(button_row, text="Update", width=14, command=_do_update).pack(
        side="left", padx=6
    )
    tk.Button(button_row, text="Dismiss", width=14, command=_dismiss).pack(
        side="left", padx=6
    )
