from __future__ import annotations

import shutil
import sys
from pathlib import Path

from . import APP_NAME, CONF_DIR, STATE_DIR
from src.config.template import render_config, wrap_comment
from .models import ConfigEntry, ConfigSection

if sys.platform == "win32":
    from src.platform.windows.installer import BIN_DIR, BINARY_DST

else:
    from src.platform.linux.installer import BIN_DIR, BINARY_DST

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


def _render_example_config() -> str:
    """Generate the settings.example.ini content for the current platform."""

    win = sys.platform == "win32"
    sep = "; " + "─" * 78

    config_path = (
        r"%APPDATA%\git-sentinel\settings.ini"
        if win
        else "~/.config/git-sentinel/settings.ini"
    )

    header = "\n".join(
        [
            "; git-sentinel - settings.example.ini",
            sep,
            wrap_comment(
                f"Copy this file to {config_path} and edit as needed."
                " The executable does this automatically on first start."
            ),
            ";",
            wrap_comment(
                "All path values are relative to your home directory unless"
                " absolute."
            ),
            sep,
        ]
    )

    return render_config(
        header=header,
        sections=[
            ConfigSection(
                "paths",
                [
                    ConfigEntry(
                        "git_root",
                        "git",
                        "Git root directory scanned recursively for git"
                        " repositories.",
                    ),
                    ConfigEntry(
                        "export_path",
                        "git/reports",
                        "Directory where reports are written. Accepts any path:"
                        " a Desktop folder, a shared network path, a CI"
                        " artefact directory, etc.\n By default git-sentinel "
                        "will store the file inside the git/reports dir.",
                        enabled=True,
                    ),
                ],
            ),
            ConfigSection(
                "reports",
                [
                    ConfigEntry(
                        "retention_days",
                        "14",
                        "Number of days to keep report files locally."
                        " Reports older than this are removed.",
                    ),
                    ConfigEntry(
                        "report_extension",
                        "log",
                        'File extension written on report files. "log" is'
                        " conventional and opens well in most text editors.",
                    ),
                ],
            ),
            ConfigSection(
                "staleness",
                [
                    ConfigEntry(
                        "stale_threshold_days",
                        "90",
                        "A repository is flagged as stale when its most recent"
                        " commit across all local branches is older than this"
                        " many days.",
                    ),
                ],
            ),
            ConfigSection(
                "schedule",
                [
                    ConfigEntry(
                        "once_per_day",
                        "true",
                        "When true, the script runs at most once per calendar"
                        " day. Subsequent logins on the same day exit silently."
                        " Run with --force to bypass.",
                    ),
                ],
            ),
            ConfigSection(
                "ssh",
                [
                    ConfigEntry(
                        "use_control_master",
                        "false" if win else "true",
                        (
                            "SSH ControlMaster multiplexing is not supported on"
                            " Windows. This setting has no effect and is always"
                            " treated as false."
                            if win
                            else "Use SSH ControlMaster multiplexing so that"
                            " each SSH host requires only one FIDO key"
                            " authentication per scan session. After you"
                            " approve a host in the GUI and enter your PINe"
                            " once, all further git ls-remote calls to that"
                            " host will reuse the established control socket"
                            " automatically. It is RECOMMENDED to keep this on."
                            " From experience, more than 2 requests in a short"
                            " time will inevitably get annoying and will be"
                            " habitually approved without checking. If you are"
                            " working in a high security environment, set this"
                            " to false.\n"
                            "Set to false to disable. Note: with ControlMaster"
                            " disabled, every SSH remote check may prompt for"
                            " your authentication or FIDO key separately."
                        ),
                    ),
                    ConfigEntry(
                        "control_persist_seconds",
                        "300",
                        (
                            "How long (in seconds) to keep a control socket"
                            " alive (Linux only)."
                            if win
                            else "How long (in seconds) to keep a control"
                            " socket alive after the last connection to that"
                            " host finishes. The socket is also explicitly"
                            " closed at the end of the scan regardless of this"
                            " value."
                        ),
                    ),
                ],
            ),
            ConfigSection(
                "meta",
                [
                    ConfigEntry(
                        "version",
                        "1",
                        "DO NOT REMOVE!\nUsed to determine the migration"
                        " version of this config file",
                    ),
                ],
            ),
        ],
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

    except shutil.SameFileError, PermissionError:
        pass

    BINARY_DST.chmod(0o755)
    print(f"Installed binary\t→ {BINARY_DST}")


def _install_config() -> None:
    """Create config dir, write the platform-specific example, and seed the live
    settings.ini from it on first install.
    """

    example_dst = CONF_DIR / "settings.example.ini"
    config = CONF_DIR / "settings.ini"
    content = _render_example_config()

    CONF_DIR.mkdir(parents=True, exist_ok=True)
    example_dst.write_text(content, encoding="utf-8")
    print(f"Installed example\t→ {example_dst}")

    if not config.exists():
        config.write_text(content, encoding="utf-8")
        print(f"Created config\t\t→ {config}  (edit to customise)")

        return

    print(f"Existing config\t\t→ {config}  (left unchanged)")


# ─────────────────────────────────────────────────────────| Uninstall steps |──


def _remove_binary() -> None:
    """removes the binary"""

    if not BINARY_DST.exists():
        print(f"Binary not found\t→ {BINARY_DST}  (skipping)")

        return

    if sys.platform == "win32":
        from src.platform.windows.installer import remove_binary

    else:
        from src.platform.linux.installer import remove_binary

    remove_binary()


def _remove_config() -> None:
    """removes the config dir"""

    if CONF_DIR.exists():
        shutil.rmtree(CONF_DIR)
        print(f"Removed config\t\t→ {CONF_DIR}")

    else:
        print(f"Config not found\t→ {CONF_DIR}  (skipping)")


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
        from src.platform.linux.installer import (
            install_autostart,
            install_icon,
            install_launcher,
        )

        install_icon(_resource(f"{APP_NAME}.svg"))
        install_autostart(
            _render_desktop(str(BINARY_DST), "X-GNOME-Autostart-enabled=true")
        )
        install_launcher(
            _render_desktop(f"{BINARY_DST} --force", "Categories=Utility;")
        )

    else:
        from src.platform.windows.installer import (
            ask_desktop_shortcut,
            install_autostart_windows,
            install_desktop_shortcut,
            install_programs_entry,
            install_start_menu,
            install_start_menu_uninstall,
        )

        install_autostart_windows()
        install_start_menu()
        install_start_menu_uninstall()
        install_programs_entry()

        if ask_desktop_shortcut():
            install_desktop_shortcut()

    print()
    print(f"{APP_NAME} installed - will open automatically on next login.")

    if not force:
        print(f"To run immediately:\t{BINARY_DST} --force")
        print(f"To configure:\t\t{CONF_DIR / 'settings.ini'}")


def uninstall() -> None:
    """Public API to initialise application uninstallation"""

    if sys.platform == "linux":
        from src.platform.linux.installer import (
            remove_autostart,
            remove_icon,
            remove_launcher,
        )

        remove_autostart()
        remove_launcher()
        remove_icon()

    else:
        from src.platform.windows.installer import (
            remove_autostart_windows,
            remove_desktop_shortcut,
            remove_programs_entry,
            remove_start_menu,
            remove_start_menu_uninstall,
        )

        remove_autostart_windows()
        remove_programs_entry()
        remove_start_menu_uninstall()
        remove_start_menu()
        remove_desktop_shortcut()

    purge = _ask_purge()

    if purge:
        _remove_config()
        _remove_state()

    else:
        print()
        print("Config and run-state left intact:")
        print(f"  {CONF_DIR}")
        print(f"  {STATE_DIR}")

    _remove_binary()

    print()
    print("Uninstallation complete.")
