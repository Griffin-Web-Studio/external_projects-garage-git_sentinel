from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# ────────────────────────────────────────────────────────────────────| Meta |──

APP_VERSION = "0.2.1"
APP_NAME = "git-sentinel"

# ──────────────────────────────────────────────────────────| Platform paths |──

TMP_DIR = Path(tempfile.gettempdir())
HOME_DIR = Path.home()

if sys.platform == "win32":  # pragma: no cover - Windows only
    from src.platform.windows.paths import conf_dir, ssh_sock_dir, state_dir

else:
    from src.platform.linux.paths import conf_dir, ssh_sock_dir, state_dir

CONF_DIR = conf_dir(HOME_DIR, APP_NAME)
STATE_DIR = state_dir(HOME_DIR, APP_NAME)
SSH_SOCK_DIR = ssh_sock_dir(TMP_DIR, APP_NAME)

CONF_FILE = CONF_DIR / "settings.ini"
LOCK_FILE = STATE_DIR / "last-run-date"
