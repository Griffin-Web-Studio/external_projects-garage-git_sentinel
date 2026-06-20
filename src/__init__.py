from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# ────────────────────────────────────────────────────────────────────| Meta |──

APP_VERSION = "0.1.0-beta.0"
APP_NAME = "git-sentinel"

# ──────────────────────────────────────────────────────────| Platform paths |──

if sys.platform == "win32":
    _appdata = Path(
        os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    )
    _localappdata = Path(
        os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
    )
    CONFIG_DIR = _appdata / APP_NAME
    STATE_DIR = _localappdata / APP_NAME
    # Temp dirs on Windows are already per-user, so no UID suffix needed.
    SSH_SOCK_DIR = Path(tempfile.gettempdir()) / APP_NAME
else:
    CONFIG_DIR = Path.home() / ".config" / APP_NAME
    STATE_DIR = Path.home() / ".local" / "share" / APP_NAME
    # UID suffix prevents socket name collisions between users on a shared /tmp.
    SSH_SOCK_DIR = Path(tempfile.gettempdir()) / f"{APP_NAME}-{os.getuid()}"

CONFIG_FILE = CONFIG_DIR / "settings.ini"
LOCK_FILE = STATE_DIR / "last-run-date"
