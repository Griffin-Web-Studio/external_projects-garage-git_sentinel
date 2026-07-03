from __future__ import annotations

import os
import sys
from pathlib import Path

# ──────────────────────────────────────────────────────────| Platform paths |──


def conf_dir(home_dir: Path, app_name: str) -> Path:
    """Config directory for the current user.

    Args:
        home_dir (Path): User home directory.
        app_name (str): Application name.

    Returns:
        Path: XDG config directory for the app.
    """

    return home_dir / ".config" / app_name


def state_dir(home_dir: Path, app_name: str) -> Path:
    """State directory for the current user.

    Args:
        home_dir (Path): User home directory.
        app_name (str): Application name.

    Returns:
        Path: XDG state directory for the app.
    """

    return home_dir / ".local" / "share" / app_name


def ssh_sock_dir(tmp_dir: Path, app_name: str) -> Path:
    """SSH ControlMaster socket directory for the current user.

    Args:
        tmp_dir (Path): System temp directory.
        app_name (str): Application name.

    Returns:
        Path: UID-suffixed socket directory that prevents name collisions
              between users on a shared /tmp.
    """

    if sys.platform == "linux":
        return tmp_dir / f"{app_name}-{os.getuid()}"

    return tmp_dir / app_name
