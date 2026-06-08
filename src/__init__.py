from __future__ import annotations
from pathlib import Path

# ────────────────────────────────────────────────────────────────────| Meta |──

APP_VERSION = "1.0.0"
APP_NAME = "git-sentinel"
CONFIG_DIR = Path.home() / ".config" / APP_NAME
CONFIG_FILE = CONFIG_DIR / "settings.ini"
STATE_DIR = Path.home() / ".local" / "share" / APP_NAME
LOCK_FILE = STATE_DIR / "last-run-date"
