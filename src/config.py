from __future__ import annotations

import configparser
from pathlib import Path

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


def get_desktop_path(cfg: configparser.ConfigParser) -> Path:
    """Detects user desktop path

    Args:
        cfg (configparser.ConfigParser): config parser

    Returns:
        Path: location of desktop dir
    """
    try:
        override = cfg.get("paths", "desktop_override").strip()

        if override:
            return Path.home() / override  # override exists

    except configparser.NoOptionError, configparser.NoSectionError:
        pass  # config parser error assume value not set

    # get xdg user-dirs.dirs file path
    xdg_file = Path.home() / ".config" / "user-dirs.dirs"

    if xdg_file.exists():
        for line in xdg_file.read_text().splitlines():  # read lines
            if line.strip().startswith("XDG_DESKTOP_DIR"):  # find desktop loc
                val = line.split("=", 1)[1].strip().strip('"')  # get value

                # return User XDG desktop path
                return Path(val.replace("$HOME", str(Path.home())))

    # Make an ass of U and Ming by assuming desktop is where it should be
    return Path.home() / "Desktop"
