from __future__ import annotations
from pathlib import Path

# ────────────────────────────────────────────────────────────────────| Meta |──

APP_VERSION = "1.0.0"
APP_NAME = "git-sentinel"
CONFIG_DIR = Path.home() / ".config" / APP_NAME
STATE_DIR = Path.home() / ".local" / "share" / APP_NAME
