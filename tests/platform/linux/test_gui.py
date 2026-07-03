from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.platform.linux.gui import open_file

# ─────────────────────────────────────────────────────────────| open_file |──


class TestOpenFile:
    """Tests open_file dispatches to xdg-open."""

    def test_invokes_xdg_open_with_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """open_file spawns xdg-open with the given path as its sole argument.

        Args:
            monkeypatch (pytest.MonkeyPatch): Replaces subprocess.Popen with a
                recording stub so no real process is spawned.
            tmp_path (Path): Stand-in report file path.
        """

        popen = MagicMock()
        monkeypatch.setattr("src.platform.linux.gui.subprocess.Popen", popen)

        report = tmp_path / "report.log"
        open_file(report)

        popen.assert_called_once_with(["xdg-open", str(report)])
