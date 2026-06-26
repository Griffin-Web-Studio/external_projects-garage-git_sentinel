from __future__ import annotations

import configparser
import sys
import warnings
from pathlib import Path

from . import CONF_FILE

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
        return _get_export_path_windows()

    # get xdg user-dirs.dirs file path
    xdg_file = Path.home() / ".config" / "user-dirs.dirs"

    if xdg_file.exists():
        for line in xdg_file.read_text().splitlines():  # read lines
            if line.strip().startswith("XDG_DESKTOP_DIR"):  # find desktop loc
                val = line.split("=", 1)[1].strip().strip('"')  # get value

                # return User XDG desktop path
                return Path(val.replace("$HOME", str(Path.home())))

    return Path.home() / "Desktop"


if sys.platform == "win32":
    import winreg as _winreg

    def _get_export_path_windows() -> Path:
        """Resolve the Desktop folder via the Windows Shell Folders registry
        key, falling back to ~/Desktop when the key is missing.
        """
        try:
            key = _winreg.OpenKey(
                _winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows"
                r"\CurrentVersion\Explorer\Shell Folders",
            )
            desktop, _ = _winreg.QueryValueEx(key, "Desktop")
            _winreg.CloseKey(key)
            return Path(desktop)
        except OSError:
            return Path.home() / "Desktop"
