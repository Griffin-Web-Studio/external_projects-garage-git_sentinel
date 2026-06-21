from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from . import APP_NAME, CONFIG_DIR, STATE_DIR

if sys.platform == "win32":
    import winreg as _winreg

    _localappdata = Path(
        os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
    )
    BIN_DIR = _localappdata / "Programs" / APP_NAME
    BINARY_DST = BIN_DIR / f"{APP_NAME}.exe"
    _RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

else:
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


def _wrap_comment(text: str, width: int = 80) -> str:
    """Wrap *text* into '; '-prefixed comment lines of at most *width* chars.

    Splits on whitespace. A word with punctuation directly attached (no space
    between the word and the mark) is treated as one atomic token - it moves to
    the next line as a unit rather than leaving the mark behind. A word longer
    than the available content width is placed on its own line.
    """
    prefix = "; "
    max_content = width - len(prefix)
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    current_len = 0

    for word in words:
        needed = len(word) if not current else current_len + 1 + len(word)

        if needed <= max_content:
            current.append(word)
            current_len = needed

        else:
            if current:
                lines.append(prefix + " ".join(current))

            current = [word]
            current_len = len(word)

    if current:
        lines.append(prefix + " ".join(current))

    return "\n".join(lines)


def _render_example_config() -> str:
    """Generate the settings.example.ini content for the current platform."""
    win = sys.platform == "win32"
    sep = "; " + "─" * 78  # less by 2 due to comment prefix

    config_path = (
        r"%APPDATA%\git-sentinel\settings.ini"
        if win
        else "~/.config/git-sentinel/settings.ini"
    )

    desktop_note = _wrap_comment(
        "By default git-sentinel reads the Desktop shell folder from the"
        " Windows registry. Set this only if your Desktop location is"
        " non-standard."
        if win
        else "By default git-sentinel reads XDG_DESKTOP_DIR from"
        " ~/.config/user-dirs.dirs. Set this only if your Desktop location is"
        " non-standard."
    )

    if win:
        ssh_block = "\n".join(
            [
                _wrap_comment(
                    "SSH ControlMaster multiplexing is not supported on"
                    " Windows. This setting has no effect and is always treated"
                    " as false."
                ),
                "use_control_master = false",
                "",
                _wrap_comment(
                    "How long (in seconds) to keep a control socket alive"
                    " (Linux only)."
                ),
                "control_persist_seconds = 300",
            ]
        )

    else:
        ssh_block = "\n".join(
            [
                _wrap_comment(
                    "Use SSH ControlMaster multiplexing so that each SSH host"
                    " requires only one FIDO key authentication per scan"
                    " session. After you approve a host in the GUI and enter"
                    " your PIN once, all further git ls-remote calls to that"
                    " host will reuse the established control socket"
                    " automatically. It is RECOMMENDED to keep this on because"
                    " from experience more than 2 requests in a short time will"
                    " inevitably get annoying and will be habitually approved"
                    " without checking. If you are working in a high security"
                    " environment, set this to false."
                ),
                ";",
                _wrap_comment(
                    "Set to false to disable. Note: with ControlMaster"
                    " disabled, every SSH remote check may prompt for your FIDO"
                    " key separately."
                ),
                "use_control_master = true",
                "",
                _wrap_comment(
                    "How long (in seconds) to keep a control socket alive after"
                    " the last connection to that host finishes. The socket is"
                    " also explicitly closed at the end of the scan regardless"
                    " of this value."
                ),
                "control_persist_seconds = 300",
            ]
        )

    return "\n".join(
        [
            "; git-sentinel - settings.example.ini",
            sep,
            _wrap_comment(
                f"Copy this file to {config_path} and edit as needed."
                " The executable does this automatically on first start."
            ),
            ";",
            _wrap_comment(
                "All path values are relative to your home directory unless"
                " absolute."
            ),
            sep,
            "",
            "[paths]",
            "",
            _wrap_comment(
                "Git root directory scanned recursively for git repositories."
            ),
            "git_root = git",
            "",
            _wrap_comment(
                "Directory where reports older than desktop_retention_days are"
                " archived."
            ),
            "reports_archive = git/reports",
            "",
            _wrap_comment(
                "Override the Desktop path where reports are written."
            ),
            desktop_note,
            "; desktop_override = Desktop",
            "",
            "",
            "[reports]",
            "",
            _wrap_comment(
                "Number of dated report files to keep on the Desktop at one"
                " time. Once this limit is exceeded the oldest reports are"
                " moved to reports_archive."
            ),
            "desktop_retention_days = 14",
            "",
            _wrap_comment(
                "File extension written on report files."
                ' "log" is conventional and opens well in most text editors.'
            ),
            "report_extension = log",
            "",
            "",
            "[staleness]",
            "",
            _wrap_comment(
                "A repository is flagged as stale when its most recent commit"
                " across all local branches is older than this many days."
            ),
            "stale_threshold_days = 90",
            "",
            "",
            "[schedule]",
            "",
            _wrap_comment(
                "When true, the script runs at most once per calendar day."
                " Subsequent logins on the same day exit silently. Run with"
                " --force to bypass."
            ),
            "once_per_day = true",
            "",
            "",
            "[ssh]",
            "",
            ssh_block,
            "",
        ]
    )


def _ask_purge() -> bool:
    """Prompt interactively; default to keeping data when non-interactive."""
    if not sys.stdin.isatty():
        return False

    try:
        answer = input("\nRemove config and state data? [y/N] ").strip().lower()
        return answer in ("y", "yes")

    except EOFError:
        return False


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
    """Create config dir, write the platform-specific example, and seed the live
    settings.ini from it on first install.
    """
    example_dst = CONFIG_DIR / "settings.example.ini"
    config = CONFIG_DIR / "settings.ini"
    content = _render_example_config()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    example_dst.write_text(content)
    print(f"Installed example\t→ {example_dst}")

    if not config.exists():
        config.write_text(content)
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


if sys.platform == "win32":

    def _install_autostart_windows() -> None:
        """Add a Run registry value so the app launches at Windows login."""
        key = _winreg.OpenKey(
            _winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, _winreg.KEY_SET_VALUE
        )
        _winreg.SetValueEx(key, APP_NAME, 0, _winreg.REG_SZ, str(BINARY_DST))
        _winreg.CloseKey(key)

        print(f"Registered autostart\t→ HKCU\\...\\Run\\{APP_NAME}")

    def _remove_autostart_windows() -> None:
        """Remove the Run registry value added by _install_autostart_windows."""
        try:
            key = _winreg.OpenKey(
                _winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, _winreg.KEY_SET_VALUE
            )
            _winreg.DeleteValue(key, APP_NAME)
            _winreg.CloseKey(key)

            print(f"Removed autostart\t→ HKCU\\...\\Run\\{APP_NAME}")

        except FileNotFoundError:
            print(
                f"Autostart not found\t→ HKCU\\...\\Run\\{APP_NAME}  (skipping)"
            )


def _install_launcher() -> None:
    """add app launcher entry into launcher"""
    APPS_DIR.mkdir(parents=True, exist_ok=True)  # create apps dir (if missing)

    content = _render_desktop(f"{BINARY_DST} --force", "Categories=Utility;")
    LAUNCHER_FILE.write_text(content)  # write launcher desktop entry

    print(f"Registered launcher\t→ {LAUNCHER_FILE}")


# ─────────────────────────────────────────────────────────| Uninstall steps |──


def _remove_binary() -> None:
    """removes the binary"""
    if BINARY_DST.exists():
        BINARY_DST.unlink()
        print(f"Removed binary\t\t→ {BINARY_DST}")

    else:
        print(f"Binary not found\t→ {BINARY_DST}  (skipping)")


def _remove_config() -> None:
    """removes the config dir"""
    if CONFIG_DIR.exists():
        shutil.rmtree(CONFIG_DIR)
        print(f"Removed config\t\t→ {CONFIG_DIR}")

    else:
        print(f"Config not found\t→ {CONFIG_DIR}  (skipping)")


def _remove_icon() -> None:
    """remove icon"""
    if ICON_FILE.exists():
        ICON_FILE.unlink()
        print(f"Removed icon\t\t→ {ICON_FILE}")

    else:
        print(f"Icon not found\t\t→ {ICON_FILE}  (skipping)")


def _remove_autostart() -> None:
    """remove autostart entry"""
    if AUTOSTART_FILE.exists():
        AUTOSTART_FILE.unlink()
        print(f"Removed autostart\t→ {AUTOSTART_FILE}")

    else:
        print(f"Autostart not found\t→ {AUTOSTART_FILE}  (skipping)")


def _remove_launcher() -> None:
    """remove launcher entry"""
    if LAUNCHER_FILE.exists():
        LAUNCHER_FILE.unlink()
        print(f"Removed launcher\t→ {LAUNCHER_FILE}")

    else:
        print(f"Launcher not found\t→ {LAUNCHER_FILE}  (skipping)")


def _remove_state() -> None:
    """remove state dir"""
    if STATE_DIR.exists():
        shutil.rmtree(STATE_DIR)
        print(f"Removed state\t\t→ {STATE_DIR}")

    else:
        print(f"State not found\t\t→ {STATE_DIR}  (skipping)")


# ─────────────────────────────────────────────────────────────| Public API  |──


def install(*, force: bool = False) -> None:
    """Public API to initialise application installation

    Args:
        force (bool, optional): force install flag. Defaults to False.
    """
    if sys.platform not in ("linux", "win32"):
        print(
            f"ERROR: {APP_NAME} supports Linux and Windows only.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"NOTICE: {sys.platform} detected, installing {APP_NAME}...",
        file=sys.stderr,
    )

    _install_binary()
    _install_config()

    if sys.platform == "linux":
        _install_icon()
        _install_autostart()
        _install_launcher()

    else:
        _install_autostart_windows()

    print()
    print(f"{APP_NAME} installed - will open automatically on next login.")

    if not force:
        print(f"To run immediately:\t{BINARY_DST} --force")
        print(f"To configure:\t\t{CONFIG_DIR / 'settings.ini'}")


def uninstall() -> None:
    """Public API to initialise application uninstallation"""

    if sys.platform == "linux":
        _remove_autostart()
        _remove_launcher()
        _remove_icon()

    else:
        _remove_autostart_windows()

    purge = _ask_purge()

    if purge:
        _remove_config()
        _remove_state()

    else:
        print()
        print("Config and run-state left intact:")
        print(f"  {CONFIG_DIR}")
        print(f"  {STATE_DIR}")

    _remove_binary()

    print()
    print("Uninstallation complete.")
