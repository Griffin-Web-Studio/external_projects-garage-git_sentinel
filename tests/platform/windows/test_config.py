from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.platform.windows.config import get_export_path

# ─────────────────────────────────────────────────────────| get_export_path |──


class TestGetExportPathWindows:
    """Tests get_export_path reads the default export path from the Windows
    registry (Shell Folders → Desktop)."""

    def test_reads_desktop_path_from_shell_folders(self) -> None:
        """Returns the path stored in the Shell Folders registry key."""

        desktop = r"C:\Users\Alice\Desktop"

        with patch("src.platform.windows.config._winreg") as mock_reg:
            mock_reg.OpenKey.return_value = MagicMock()
            mock_reg.QueryValueEx.return_value = (desktop, 1)
            result = get_export_path()

        assert result == Path(desktop)

    def test_oserror_falls_back_to_home_desktop(self) -> None:
        """OSError from a missing or inaccessible key falls back to
        ~/Desktop."""

        with patch("src.platform.windows.config._winreg") as mock_reg:
            mock_reg.OpenKey.side_effect = OSError
            result = get_export_path()

        assert result == Path.home() / "Desktop"
