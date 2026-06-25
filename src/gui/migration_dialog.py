from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable

from .. import CONFIG_FILE
from ..configmigrate import MigrationStep


def show_migration_dialog(
    parent: tk.Misc,
    pending: list[MigrationStep],
    on_update: Callable[[], OSError | None],
) -> None:
    """Show a modal dialog listing pending config migrations.

    Offers to apply them automatically or dismiss for manual handling.

    Args:
        parent (tk.Misc): Parent widget the dialog is transient to.
        pending (list[MigrationStep]): Steps to display and optionally apply.
        on_update (Callable[[], OSError | None]): Called when the user clicks
            Update; returns an OSError on failure, None on success.
    """
    dlg = tk.Toplevel(parent)
    dlg.title("Config update available")
    dlg.resizable(False, False)
    dlg.grab_set()

    frame = tk.Frame(dlg, padx=16, pady=12)
    frame.pack(fill="both", expand=True)

    body = "settings.ini has pending updates.\n\n"

    for step in pending:
        body += f"  v{step.from_version} → v{step.to_version}"

        if step.description:
            body += f": {step.description}"

        body += "\n"

    body += (
        "\nClick Update to apply automatically,\n"
        "or Dismiss to handle it manually.\n\n"
        f"Settings file:\n{CONFIG_FILE}"
    )

    tk.Label(
        frame,
        text=body,
        justify="left",
        anchor="w",
        font=("monospace", 9),
    ).pack(fill="x")

    btn_row = tk.Frame(frame)
    btn_row.pack(pady=(12, 0))

    def _do_update() -> None:
        exc = on_update()

        if exc:
            messagebox.showerror(
                "Update failed", f"Could not update settings.ini:\n{exc}"
            )
            return

        dlg.destroy()

    tk.Button(btn_row, text="Update", width=14, command=_do_update).pack(
        side="left", padx=6
    )
    tk.Button(btn_row, text="Dismiss", width=14, command=dlg.destroy).pack(
        side="left", padx=6
    )
