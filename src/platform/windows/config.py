from __future__ import annotations

import sys
import winreg as _winreg
from pathlib import Path

# ──────────────────────────────────────────────────────────────────| Config |──


def get_export_path() -> Path:
    """Resolve the Desktop folder via the Windows Shell Folders registry key,
    falling back to ~/Desktop when the key is missing.

    Returns:
        Path: Desktop directory from the registry, or ~/Desktop when
              unavailable.
    """

    if sys.platform == "win32":
        try:
            key = _winreg.OpenKey(
                _winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows"
                r"\CurrentVersion\Explorer\Shell Folders",
            )
            desktop, _ = _winreg.QueryValueEx(key, "Desktop")
            _winreg.CloseKey(key)

            return Path(desktop)

        except OSError:
            pass

    return Path.home() / "Desktop"
