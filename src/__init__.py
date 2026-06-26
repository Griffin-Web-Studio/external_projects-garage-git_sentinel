from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# ────────────────────────────────────────────────────────────────────| Meta |──

APP_VERSION = "0.2.0"
APP_NAME = "git-sentinel"

# ──────────────────────────────────────────────────────────| Platform paths |──

TMP_DIR = Path(tempfile.gettempdir())
HOME_DIR = Path.home()

if sys.platform == "win32":
    APPDATA_DIR = HOME_DIR / "AppData"

    _ad = Path(os.environ.get("APPDATA") or (APPDATA_DIR / "Roaming"))
    _lad = Path(os.environ.get("LOCALAPPDATA") or (APPDATA_DIR / "Local"))
    CONF_DIR = _ad / APP_NAME
    STATE_DIR = _lad / APP_NAME

    # Temp dirs on Windows are already per-user, so no UID suffix needed.
    SSH_SOCK_DIR = TMP_DIR / APP_NAME

if sys.platform == "linux":
    CONF_DIR = HOME_DIR / ".config" / APP_NAME
    STATE_DIR = HOME_DIR / ".local" / "share" / APP_NAME

    # UID suffix prevents socket name collisions between users on a shared /tmp.
    SSH_SOCK_DIR = TMP_DIR / f"{APP_NAME}-{os.getuid()}"

CONF_FILE = CONF_DIR / "settings.ini"
LOCK_FILE = STATE_DIR / "last-run-date"
