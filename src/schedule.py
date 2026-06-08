from __future__ import annotations

import configparser
from datetime import date

from . import LOCK_FILE, STATE_DIR

# ─────────────────────────────────────────────────────────| Lock / Schedule |──


def should_run_today(
    cfg: configparser.ConfigParser, force: bool = False
) -> bool:
    """Return True when the script should proceed.

    Writes today's date to the lock file so subsequent logins are skipped.
    """
    if force or not cfg.getboolean("schedule", "once_per_day"):
        return True

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    if LOCK_FILE.exists() and LOCK_FILE.read_text().strip() == today:
        return False

    LOCK_FILE.write_text(today)

    return True
