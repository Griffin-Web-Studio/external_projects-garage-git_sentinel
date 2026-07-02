from __future__ import annotations

import os
from pathlib import Path

# ──────────────────────────────────────────────────────────| Platform paths |──


def conf_dir(home_dir: Path, app_name: str) -> Path:
    """Config directory for the current user.

    Args:
        home_dir (Path): User home directory.
        app_name (str): Application name.

    Returns:
        Path: Roaming AppData directory for the app.
    """

    appdata_dir = home_dir / "AppData"
    ad = Path(os.environ.get("APPDATA") or (appdata_dir / "Roaming"))

    return ad / app_name


def state_dir(home_dir: Path, app_name: str) -> Path:
    """State directory for the current user.

    Args:
        home_dir (Path): User home directory.
        app_name (str): Application name.

    Returns:
        Path: Local AppData directory for the app.
    """

    appdata_dir = home_dir / "AppData"
    lad = Path(os.environ.get("LOCALAPPDATA") or (appdata_dir / "Local"))

    return lad / app_name


def ssh_sock_dir(tmp_dir: Path, app_name: str) -> Path:
    """SSH ControlMaster socket directory for the current user.

    Args:
        tmp_dir (Path): System temp directory.
        app_name (str): Application name.

    Returns:
        Path: Socket directory. Temp dirs on Windows are already per-user, so
              no UID suffix is needed.
    """

    return tmp_dir / app_name
