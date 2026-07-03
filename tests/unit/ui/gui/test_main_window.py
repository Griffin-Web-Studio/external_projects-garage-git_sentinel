from __future__ import annotations

from pathlib import Path
import tkinter as tk

import pytest

from src.models import MsgFinish
from src.ui.gui.views.main_window import MainWindow

# ─────────────────────────────────────────────────────────────────| Fixture |──


@pytest.fixture
def window(tk_root: tk.Tk) -> MainWindow:
    return MainWindow(tk_root, on_close=lambda: None)


# ────────────────────────────────────────────────────────────────────| Init |──


class TestMainWindowInit:
    """Widget states are correct immediately after construction."""

    def test_status_initial_value(self, window: MainWindow) -> None:
        """Status label starts with 'Initialising...'.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        _LABEL_STATUS = "Initialising..."

        assert window._status_var.get() == _LABEL_STATUS

    def test_progress_initial_value(self, window: MainWindow) -> None:
        """Progress bar starts at 0.0.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        assert window._prog_bar_var.get() == pytest.approx(0.0)

    def test_close_button_disabled(self, window: MainWindow) -> None:
        """Close button is disabled before a scan completes.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        assert str(window._close_btn["state"]) == "disabled"

    def test_close_button_initial_text(self, window: MainWindow) -> None:
        """Close button text starts as 'Please wait...'.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        assert window._close_btn["text"] == "Please wait..."

    def test_prompt_container_is_frame(self, window: MainWindow) -> None:
        """prompt_container property returns a tk.Frame instance.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        assert isinstance(window.prompt_container, tk.Frame)

    def test_colour_tags_registered(self, window: MainWindow) -> None:
        """error, warning, and info colour tags are registered on the log
        widget.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        names = window._log_text.tag_names()

        assert "error" in names
        assert "warning" in names
        assert "info" in names


# ───────────────────────────────────────────────────────────| update_status |──


class TestUpdateStatus:
    """update_status changes the status label text."""

    def test_sets_text(self, window: MainWindow) -> None:
        """update_status updates the StringVar used by the label.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        _STATUS_TEXT = "Stage 1 / 3 - Discovering repositories..."

        window.update_status(_STATUS_TEXT)

        assert window._status_var.get() == _STATUS_TEXT

    def test_overwrites_previous(self, window: MainWindow) -> None:
        """Calling update_status twice shows only the most recent value.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.update_status("first")
        window.update_status("second")

        assert window._status_var.get() == "second"


# ─────────────────────────────────────────────────────────| update_progress |──


class TestUpdateProgress:
    """update_progress changes the progress bar value."""

    def test_sets_value(self, window: MainWindow) -> None:
        """update_progress sets the DoubleVar driving the progress bar.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.update_progress(42.5)

        assert window._prog_bar_var.get() == pytest.approx(42.5)

    def test_accepts_100(self, window: MainWindow) -> None:
        """update_progress accepts 100.0 as a full value.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.update_progress(100.0)

        assert window._prog_bar_var.get() == pytest.approx(100.0)

    def test_accepts_zero(self, window: MainWindow) -> None:
        """update_progress accepts 0.0 to reset the bar.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.update_progress(55.0)
        window.update_progress(0.0)

        assert window._prog_bar_var.get() == pytest.approx(0.0)


# ──────────────────────────────────────────────────────────────| append_log |──


class TestAppendLog:
    """append_log inserts text into the log pane with optional colour tags."""

    def test_plain_text_appears(self, window: MainWindow) -> None:
        """Text appended without a tag is visible in the log widget.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.append_log("hello world")

        assert "hello world" in window._log_text.get("1.0", "end")

    def test_multiple_lines_preserved(self, window: MainWindow) -> None:
        """Each append_log call adds a distinct line.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.append_log("line one")
        window.append_log("line two")

        content = window._log_text.get("1.0", "end")

        assert "line one" in content
        assert "line two" in content

    def test_error_tag_applied(self, window: MainWindow) -> None:
        """Text appended with tag='error' has the error tag on its range.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.append_log("something failed", tag="error")

        assert len(window._log_text.tag_ranges("error")) > 0

    def test_warning_tag_applied(self, window: MainWindow) -> None:
        """Text appended with tag='warning' has the warning tag on its range.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.append_log("3 uncommitted", tag="warning")

        assert len(window._log_text.tag_ranges("warning")) > 0

    def test_info_tag_applied(self, window: MainWindow) -> None:
        """Text appended with tag='info' has the info tag on its range.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.append_log("=== Stage 1 ===", tag="info")

        assert len(window._log_text.tag_ranges("info")) > 0

    def test_untagged_text_has_no_error_tag(self, window: MainWindow) -> None:
        """Plain text does not receive the error tag.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.append_log("all fine")

        assert len(window._log_text.tag_ranges("error")) == 0

    def test_tags_are_independent(self, window: MainWindow) -> None:
        """Appending a warning line does not apply the error tag.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.append_log("a warning", tag="warning")

        assert len(window._log_text.tag_ranges("error")) == 0


# ──────────────────────────────────────────────────────────| handle_finish |──


class TestHandleFinishClean:
    """handle_finish with issue_count=0 reflects a clean run."""

    def test_progress_full(self, window: MainWindow) -> None:
        """Progress bar snaps to 100.0.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.handle_finish(MsgFinish(issue_count=0, report_path=None))

        assert window._prog_bar_var.get() == pytest.approx(100.0)

    def test_close_button_enabled(self, window: MainWindow) -> None:
        """Close button is enabled after a clean finish.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.handle_finish(MsgFinish(issue_count=0, report_path=None))
        assert str(window._close_btn["state"]) == "normal"

    def test_close_button_text(self, window: MainWindow) -> None:
        """Close button reads 'Close' on a clean finish.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.handle_finish(MsgFinish(issue_count=0, report_path=None))
        assert window._close_btn["text"] == "Close"

    def test_status_shows_all_clear(self, window: MainWindow) -> None:
        """Status label shows the all-clear message.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.handle_finish(MsgFinish(issue_count=0, report_path=None))
        assert "All clear" in window._status_var.get()

    def test_no_open_report_button(self, window: MainWindow) -> None:
        """No 'Open Report' button is added on a clean finish.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        btn_count_before = len(window._button_row.winfo_children())

        window.handle_finish(MsgFinish(issue_count=0, report_path=None))

        assert len(window._button_row.winfo_children()) == btn_count_before


class TestHandleFinishWithIssues:
    """handle_finish with issue_count > 0 reflects a run with findings."""

    def test_close_button_text(self, window: MainWindow) -> None:
        """Close button reads 'Acknowledge & Close' when issues were found.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.handle_finish(MsgFinish(issue_count=2, report_path=None))

        assert window._close_btn["text"] == "Acknowledge & Close"

    def test_close_button_enabled(self, window: MainWindow) -> None:
        """Close button is enabled even when issues are present.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.handle_finish(MsgFinish(issue_count=1, report_path=None))

        assert str(window._close_btn["state"]) == "normal"

    def test_status_shows_issue_count(self, window: MainWindow) -> None:
        """Status label includes the number of repos with issues.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.handle_finish(MsgFinish(issue_count=3, report_path=None))

        assert "3" in window._status_var.get()

    def test_status_shows_tilde_shortened_report_dir(
        self,
        window: MainWindow,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Status label shows the report's parent directory, tilde-shortened
        relative to home, instead of a hardcoded 'Desktop'.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
            monkeypatch (pytest.MonkeyPatch): Redirects Path.home() to
                tmp_path so the report path resolves under it.
            tmp_path (Path): Stand-in home directory.
        """

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        report = tmp_path / "git" / "reports" / "report.log"

        window.handle_finish(MsgFinish(issue_count=1, report_path=report))

        assert "~/git/reports" in window._status_var.get()
        assert "Desktop" not in window._status_var.get()

    def test_status_omits_location_when_report_path_none(
        self, window: MainWindow
    ) -> None:
        """Status label doesn't claim a location when report_path is None.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        window.handle_finish(MsgFinish(issue_count=1, report_path=None))

        assert "Desktop" not in window._status_var.get()

    def test_report_exists_adds_open_button(
        self, window: MainWindow, tmp_path: Path
    ) -> None:
        """An 'Open Report' button is injected into the button row when the
        report file exists.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        report = tmp_path / "report.log"
        btn_count_before = len(window._button_row.winfo_children())

        report.touch()
        window.handle_finish(MsgFinish(issue_count=1, report_path=report))

        assert len(window._button_row.winfo_children()) == btn_count_before + 1

    def test_report_missing_no_open_button(
        self, window: MainWindow, tmp_path: Path
    ) -> None:
        """No 'Open Report' button is added when the report file does not exist.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        report = tmp_path / "nonexistent.log"
        btn_count_before = len(window._button_row.winfo_children())

        window.handle_finish(MsgFinish(issue_count=1, report_path=report))

        assert len(window._button_row.winfo_children()) == btn_count_before

    def test_report_none_no_open_button(self, window: MainWindow) -> None:
        """No 'Open Report' button is added when report_path is None.

        Args:
            window (MainWindow): Main application frame containing all
                                 persistent UI elements.
        """

        btn_count_before = len(window._button_row.winfo_children())

        window.handle_finish(MsgFinish(issue_count=1, report_path=None))

        assert len(window._button_row.winfo_children()) == btn_count_before
