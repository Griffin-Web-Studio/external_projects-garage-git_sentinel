from __future__ import annotations

import configparser
import sys
import warnings
from pathlib import Path

from src import CONF_FILE

# ──────────────────────────────────────────────────────────────────| Config |──

_DEFAULTS: dict[str, dict[str, str]] = {
    "paths": {
        "git_root": "git",
    },
    "reports": {
        "retention_days": "14",
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

    if CONF_FILE.exists():
        cfg.read(CONF_FILE)  # update with user values

    return cfg


def get_export_path(cfg: configparser.ConfigParser) -> Path:
    """Resolves the export directory for reports.

    Args:
        cfg (configparser.ConfigParser): config parser

    Returns:
        Path: location of export dir
    """

    try:
        override = cfg.get("paths", "export_path").strip()

        if override:
            return Path.home() / override

    except configparser.NoOptionError, configparser.NoSectionError:
        pass

    # Deprecated key - kept as a fallback so existing configs still work.
    try:
        override = cfg.get("paths", "desktop_override").strip()

        if override:
            warnings.warn(
                "settings.ini: 'desktop_override' is deprecated; rename it to"
                " 'export_path' to silence this warning.",
                DeprecationWarning,
                stacklevel=2,
            )

            return Path.home() / override

    except configparser.NoOptionError, configparser.NoSectionError:
        pass

    if sys.platform == "win32":
        from src.platform.windows.config import get_export_path as _platform_gep

    else:
        from src.platform.linux.config import get_export_path as _platform_gep

    return _platform_gep()
