from __future__ import annotations

import shutil
import sys
from pathlib import Path

from . import APP_NAME, CONFIG_DIR, STATE_DIR

_LOCAL = Path.home() / ".local"
BIN_DIR = _LOCAL / "bin"
BINARY_DST = BIN_DIR / APP_NAME

AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / f"{APP_NAME}.desktop"

APPS_DIR = _LOCAL / "share" / "applications"
LAUNCHER_FILE = APPS_DIR / f"{APP_NAME}.desktop"

ICONS_DIR = _LOCAL / "share" / "icons" / "hicolor" / "scalable" / "apps"
ICON_FILE = ICONS_DIR / f"{APP_NAME}.svg"

# ───────────────────────────────────────────────────────────────| Resources |──


def _resource(name: str) -> Path:
    """Locate a bundled data file at runtime.

    Resolves to PyInstaller's `_MEIPASS` extraction directory when frozen,
    or src/data/ in the source tree during development.

    Args:
        name (str): File name relative to the data directory.

    Returns:
        Path: Absolute path to the requested data file.
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "data" / name

    return Path(__file__).parent / "data" / name


def _current_binary() -> Path:
    """get's either normalised binary location or (in development) script entry
    point

    Returns:
        Path: location of binary/script
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()

    return Path(sys.argv[0]).resolve()


def _render_desktop(exec_cmd: str, extra: str) -> str:
    """Fill the single .desktop template for either deployment target."""
    return (
        _resource(f"{APP_NAME}.desktop")
        .read_text()
        .replace("{exec}", exec_cmd)
        .replace("{extra}", extra)
    )


# ───────────────────────────────────────────────────────────────────| State |──


def is_installed() -> bool:
    """True when the running binary is already the installed copy."""
    try:
        return _current_binary().samefile(BINARY_DST)

    except OSError:
        return False


# ───────────────────────────────────────────────| Install steps (protected) |──


def _install_binary() -> None:
    """Copies the app binary into a destination location"""
    src = _current_binary()
    BIN_DIR.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(str(src), str(BINARY_DST))

    except shutil.SameFileError:
        pass

    BINARY_DST.chmod(0o755)
    print(f"Installed binary\t→ {BINARY_DST}")


def _install_config() -> None:
    """Create config folder, copy example config file into config folder, and
    create a copy of the example config file - renaming as actual config file
    """

    example_src = _resource("settings.example.ini")
    example_dst = CONFIG_DIR / "settings.example.ini"
    config = CONFIG_DIR / "settings.ini"

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)  # make config dir
    shutil.copy2(str(example_src), str(example_dst))  # copy example

    print(f"Installed example\t→ {example_dst}")

    if not config.exists():
        shutil.copy2(str(example_src), str(config))  # copy example into config
        print(f"Created config\t\t→ {config}  (edit to customise)")
        return

    print(f"Existing config\t\t→ {config}  (left unchanged)")


def _install_icon() -> None:
    """Create icons dir, and copy the icon inside."""
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(_resource(f"{APP_NAME}.svg")), str(ICON_FILE))

    print(f"Installed icon\t\t→ {ICON_FILE}")


def _install_autostart() -> None:
    """Create icons dir, and copy the icon inside."""
    AUTOSTART_DIR.mkdir(
        parents=True, exist_ok=True
    )  # create autostart dir (if missing)

    content = _render_desktop(str(BINARY_DST), "X-GNOME-Autostart-enabled=true")
    AUTOSTART_FILE.write_text(content)  # write autostart desktop entry

    print(f"Registered autostart\t→ {AUTOSTART_FILE}")


def _install_launcher() -> None:
    """add app launcher entry into launcher"""
    APPS_DIR.mkdir(parents=True, exist_ok=True)  # create apps dir (if missing)

    content = _render_desktop(f"{BINARY_DST} --force", "Categories=Utility;")
    LAUNCHER_FILE.write_text(content)  # write launcher desktop entry

    print(f"Registered launcher\t→ {LAUNCHER_FILE}")


# ─────────────────────────────────────────────────────────────| Public API  |──


def install(*, force: bool = False) -> None:
    """Public API to initialise application installation

    Args:
        force (bool, optional): force install flag. Defaults to False.
    """
    if sys.platform != "linux":
        print(
            f"ERROR: {APP_NAME} only supports Linux (for now).", file=sys.stderr
        )
        sys.exit(1)
    elif sys.platform == "linux":
        print(
            f"NOTICE: Linux detected {APP_NAME} will now install.",
            file=sys.stderr,
        )
    _install_binary()
    _install_config()
    _install_icon()
    _install_autostart()
    _install_launcher()

    print()  # add new line
    print(f"{APP_NAME} installed - will open automatically on next login.")

    if not force:
        print(f"To run immediately:\t{BINARY_DST} --force")
        print(f"To configure:\t\t$EDITOR {CONFIG_DIR / 'settings.ini'}")
