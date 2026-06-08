from __future__ import annotations

import configparser

from . import CONFIG_FILE

# ──────────────────────────────────────────────────────────────────| Config |──

_DEFAULTS: dict[str, dict[str, str]] = {
    "paths": {
        "git_root": "git",
        "reports_archive": "git/reports",
    },
    "reports": {
        "desktop_retention_days": "14",
        "report_extension": "log",
    },
    "staleness": {
        "stale_threshold_days": "90",
    },
    "schedule": {
        "once_per_day": "true",
    },
    "ssh": {
        "use_control_master": "true",
        "control_persist_seconds": "300",
    },
}


def load_config() -> configparser.ConfigParser:
    """Wrapper for config file parser. Loads the config parser and applies
    default values if not set

    Returns:
        configparser.ConfigParser: return config values
    """
    cfg = configparser.ConfigParser()

    for section, values in _DEFAULTS.items():
        cfg[section] = values  # build config of defaults

    if CONFIG_FILE.exists():
        cfg.read(CONFIG_FILE)  # update with user values

    return cfg
