from __future__ import annotations

from pathlib import Path

# ──────────────────────────────────────────────────────────────────| Config |──


def get_export_path() -> Path:
    """Resolves the default export directory via the XDG user-dirs.dirs file.

    Returns:
        Path: XDG desktop directory, or ~/Desktop when unavailable.
    """

    xdg_file = Path.home() / ".config" / "user-dirs.dirs"

    if xdg_file.exists():
        for line in xdg_file.read_text().splitlines():  # read lines
            if line.strip().startswith("XDG_DESKTOP_DIR"):  # find desktop loc
                val = line.split("=", 1)[1].strip().strip('"')  # get value

                # return User XDG desktop path
                return Path(val.replace("$HOME", str(Path.home())))

    return Path.home() / "Desktop"
