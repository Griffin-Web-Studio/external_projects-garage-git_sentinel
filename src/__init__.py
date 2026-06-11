from __future__ import annotations

import os
import tempfile
from pathlib import Path

# ────────────────────────────────────────────────────────────────────| Meta |──

APP_VERSION = "0.1.0-beta.0"
APP_NAME = "git-sentinel"

CONFIG_DIR = Path.home() / ".config" / APP_NAME
CONFIG_FILE = CONFIG_DIR / "settings.ini"

STATE_DIR = Path.home() / ".local" / "share" / APP_NAME
LOCK_FILE = STATE_DIR / "last-run-date"

# Per-user directory for SSH ControlMaster socket files.
# Including the UID prevents one user's sockets from being visible to another.
SSH_SOCK_DIR = Path(tempfile.gettempdir()) / f"{APP_NAME}-{os.getuid()}"
