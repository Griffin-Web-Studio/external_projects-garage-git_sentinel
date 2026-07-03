from __future__ import annotations

import tkinter as tk
from unittest.mock import MagicMock

import pytest

from src.config.migrate import MigrationStep
from src.ui.gui.views.migration_dialog import show_migration_dialog

# ─────────────────────────────────────────────────────────────────| Helpers |──


def _step(
    from_version: int = 0, to_version: int = 1, description: str = ""
) -> MigrationStep:
    """Build a MigrationStep for use in tests.

    Args:
        from_version (int): Version the step upgrades from.
        to_version (int): Version the step upgrades to.
        description (str): Human-readable summary shown in the dialog.

    Returns:
        MigrationStep: A step with a no-op upgrade function.
    """

    return MigrationStep(
        from_version=from_version,
        to_version=to_version,
        description=description,
        fn=lambda cfg: None,
    )


def _dialog(root: tk.Tk) -> tk.Toplevel:
    """Return the single Toplevel child spawned under *root*.

    Args:
        root (tk.Tk): Parent window the dialog was created under.

    Returns:
        tk.Toplevel: The single Toplevel dialog found under root.
    """

    toplevels: list[tk.Toplevel] = []

    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            toplevels.append(w)

    assert len(toplevels) == 1
    return toplevels[0]


def _button(dialog: tk.Toplevel, text: str) -> tk.Button:
    """Find a button labelled *text* inside the dialog's button row.

    Args:
        dialog (tk.Toplevel): Dialog to search for the button in.
        text (str): Exact button label to match.

    Returns:
        tk.Button: The matching button widget.
    """

    for child in dialog.winfo_children():
        if not isinstance(child, tk.Frame):
            continue

        for grandchild in child.winfo_children():
            if isinstance(grandchild, tk.Frame):
                for btn in grandchild.winfo_children():
                    if isinstance(btn, tk.Button) and btn["text"] == text:
                        return btn

    raise AssertionError(f"button {text!r} not found")


# ───────────────────────────────────────────────────| show_migration_dialog |──


class TestShowMigrationDialog:
    """Tests the modal migration dialog's content and button behaviour."""

    def test_creates_a_toplevel(self, tk_root: tk.Tk) -> None:
        """A single Toplevel dialog is created under the parent.

        Args:
            tk_root (tk.Tk): Root window the dialog is made transient to.
        """

        show_migration_dialog(tk_root, [_step()], lambda: None)

        _dialog(tk_root)  # raises if not exactly one

    def test_lists_each_step_version_range(self, tk_root: tk.Tk) -> None:
        """Each pending step's from/to version appears in the dialog body.

        Args:
            tk_root (tk.Tk): Root window the dialog is made transient to.
        """

        steps = [
            _step(0, 1, "first change"),
            _step(1, 2, "second change"),
        ]
        show_migration_dialog(tk_root, steps, lambda: None)

        dialog = _dialog(tk_root)
        label = next(
            w
            for w in dialog.winfo_children()[0].winfo_children()
            if isinstance(w, tk.Label)
        )
        text = label["text"]

        assert "v0 to v1" in text
        assert "first change" in text
        assert "v1 to v2" in text
        assert "second change" in text

    def test_step_without_description_omits_colon(self, tk_root: tk.Tk) -> None:
        """A step with an empty description shows no trailing ': ...'.

        Args:
            tk_root (tk.Tk): Root window the dialog is made transient to.
        """

        show_migration_dialog(tk_root, [_step(0, 1, "")], lambda: None)

        dialog = _dialog(tk_root)
        label = next(
            w
            for w in dialog.winfo_children()[0].winfo_children()
            if isinstance(w, tk.Label)
        )

        assert "v0 to v1\n" in label["text"]

    def test_dismiss_destroys_dialog_and_calls_on_close(
        self, tk_root: tk.Tk
    ) -> None:
        """Clicking Dismiss destroys the dialog and invokes on_close.

        Args:
            tk_root (tk.Tk): Root window the dialog is made transient to.
        """

        on_close = MagicMock()

        show_migration_dialog(
            tk_root, [_step()], lambda: None, on_close=on_close
        )

        dialog = _dialog(tk_root)
        _button(dialog, "Dismiss").invoke()

        on_close.assert_called_once()

        assert not dialog.winfo_exists()

    def test_dismiss_without_on_close_does_not_raise(
        self, tk_root: tk.Tk
    ) -> None:
        """Dismissing is safe when on_close is None (the default).

        Args:
            tk_root (tk.Tk): Root window the dialog is made transient to.
        """

        show_migration_dialog(tk_root, [_step()], lambda: None)

        dialog = _dialog(tk_root)
        _button(dialog, "Dismiss").invoke()  # must not raise

        assert not dialog.winfo_exists()

    def test_update_success_destroys_dialog_and_calls_on_close(
        self, tk_root: tk.Tk
    ) -> None:
        """A successful update (on_update returns None) dismisses the
        dialog and calls on_close.

        Args:
            tk_root (tk.Tk): Root window the dialog is made transient to.
        """

        on_close = MagicMock()
        on_update = MagicMock(return_value=None)

        show_migration_dialog(tk_root, [_step()], on_update, on_close=on_close)

        dialog = _dialog(tk_root)
        _button(dialog, "Update").invoke()

        on_update.assert_called_once()
        on_close.assert_called_once()

        assert not dialog.winfo_exists()

    def test_update_failure_shows_error_and_keeps_dialog_open(
        self, tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed update (on_update returns an OSError) shows an error
        dialog and leaves the migration dialog open.

        Args:
            tk_root (tk.Tk): Root window the dialog is made transient to.
            monkeypatch (pytest.MonkeyPatch): Replaces messagebox.showerror
                with a spy so no real modal dialog is shown.
        """

        showerror = MagicMock()

        monkeypatch.setattr(
            "src.ui.gui.views.migration_dialog.messagebox.showerror",
            showerror,
        )

        on_close = MagicMock()
        on_update = MagicMock(return_value=OSError("disk full"))
        show_migration_dialog(tk_root, [_step()], on_update, on_close=on_close)

        dialog = _dialog(tk_root)
        _button(dialog, "Update").invoke()

        showerror.assert_called_once()

        assert "disk full" in showerror.call_args[0][1]

        on_close.assert_not_called()

        assert dialog.winfo_exists()
