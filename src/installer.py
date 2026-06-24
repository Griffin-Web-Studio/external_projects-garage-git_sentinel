from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import APP_NAME, APP_VERSION, CONFIG_DIR, STATE_DIR
from .config_template import render_config, wrap_comment
from .models import ConfigEntry, ConfigSection

if sys.platform == "win32":
    import winreg as _winreg

    _localappdata = Path(
        os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
    )
    _appdata = Path(
        os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    )
    BIN_DIR = _localappdata / "Programs" / APP_NAME
    BINARY_DST = BIN_DIR / f"{APP_NAME}.exe"
    _RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    _UNINSTALL_KEY = (
        rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"
    )
    START_MENU_DIR = (
        _appdata
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / APP_NAME
    )
    START_MENU_SHORTCUT = START_MENU_DIR / f"{APP_NAME}.lnk"
    START_MENU_UNINSTALL = START_MENU_DIR / f"Uninstall {APP_NAME}.lnk"

    _SHELL_FOLDERS_KEY = r"Software\Microsoft\Windows\Shell\User Shell Folders"

    try:
        _hkey = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, _SHELL_FOLDERS_KEY)
        _desktop_val, _ = _winreg.QueryValueEx(_hkey, "Desktop")
        _winreg.CloseKey(_hkey)
        _desktop_dir = Path(os.path.expandvars(str(_desktop_val)))

    except OSError:
        _desktop_dir = Path.home() / "Desktop"

    DESKTOP_SHORTCUT = _desktop_dir / f"{APP_NAME}.lnk"

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
                        "reports_archive",
                        "git/reports",
                        "Directory where reports older than"
                        " desktop_retention_days are archived.",
                    ),
                    ConfigEntry(
                        "export_path",
                        "Desktop",
                        "Directory where reports are written. Accepts any path:"
                        " a Desktop folder, a shared network path, a CI"
                        " artefact directory, etc.\n"
                        + (
                            "By default git-sentinel reads the Desktop shell"
                            " folder from the Windows registry. Set this only"
                            " if you want reports in a non-standard location."
                            if win
                            else "By default git-sentinel reads XDG_DESKTOP_DIR"
                            " from ~/.config/user-dirs.dirs. Set this only if"
                            " you want reports in a non-standard location."
                        ),
                        enabled=False,
                    ),
                ],
            ),
            ConfigSection(
                "reports",
                [
                    ConfigEntry(
                        "desktop_retention_days",
                        "14",
                        "Number of dated report files to keep on the Desktop at"
                        " one time. Once this limit is exceeded the oldest"
                        " reports are moved to reports_archive.",
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
    example_dst = CONFIG_DIR / "settings.example.ini"
    config = CONFIG_DIR / "settings.ini"
    content = _render_example_config()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    example_dst.write_text(content, encoding="utf-8")
    print(f"Installed example\t→ {example_dst}")

    if not config.exists():
        config.write_text(content, encoding="utf-8")
        print(f"Created config\t\t→ {config}  (edit to customise)")
        return

    print(f"Existing config\t\t→ {config}  (left unchanged)")


if sys.platform == "linux":

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

        content = _render_desktop(
            str(BINARY_DST), "X-GNOME-Autostart-enabled=true"
        )
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

    def _create_lnk(
        lnk: Path, target: Path, args: str, description: str
    ) -> None:
        """Create a Windows Shell shortcut (.lnk) via PowerShell COM.

        Uses single-quoted PS strings so the paths are not expanded as
        variables. Windows paths do not contain single quotes so this is safe.
        """
        script = (
            f"$s = (New-Object -ComObject WScript.Shell)"
            f".CreateShortcut('{lnk}');"
            f" $s.TargetPath = '{target}';"
            f" $s.Arguments = '{args}';"
            f" $s.Description = '{description}';"
            f" $s.Save()"
        )

        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            check=True,
            capture_output=True,
        )

    def _install_start_menu() -> None:
        """Create a Start Menu shortcut so the app is discoverable from the
        Windows shell."""
        START_MENU_DIR.mkdir(parents=True, exist_ok=True)

        _create_lnk(
            START_MENU_SHORTCUT,
            BINARY_DST,
            "--force",
            "Daily git repository audit",
        )
        print(f"Registered Start Menu\t→ {START_MENU_SHORTCUT}")

    def _ask_desktop_shortcut() -> bool:
        """Prompt whether to add a Desktop shortcut; defaults to Yes."""
        if not sys.stdin.isatty():
            return True

        try:
            answer = (
                input("\nCreate a Desktop shortcut? [Y/n] ").strip().lower()
            )

            return answer not in ("n", "no")

        except EOFError:
            return True

    def _install_desktop_shortcut() -> None:
        """Create a Desktop shortcut alongside the Start Menu entry."""
        _create_lnk(
            DESKTOP_SHORTCUT,
            BINARY_DST,
            "--force",
            "Daily git repository audit",
        )
        print(f"Registered Desktop\t→ {DESKTOP_SHORTCUT}")

    def _install_start_menu_uninstall() -> None:
        """Create an Uninstall shortcut in the Start Menu subfolder."""
        _create_lnk(
            START_MENU_UNINSTALL,
            BINARY_DST,
            "--uninstall",
            f"Uninstall {APP_NAME}",
        )
        print(f"Registered uninstall entry\t→ {START_MENU_UNINSTALL}")

    def _install_programs_entry() -> None:
        """Register the app in Settings > Apps (Add/Remove Programs)."""
        key = _winreg.CreateKeyEx(
            _winreg.HKEY_CURRENT_USER,
            _UNINSTALL_KEY,
            0,
            _winreg.KEY_SET_VALUE,
        )
        _winreg.SetValueEx(key, "DisplayName", 0, _winreg.REG_SZ, APP_NAME)
        _winreg.SetValueEx(
            key,
            "UninstallString",
            0,
            _winreg.REG_SZ,
            f'"{BINARY_DST}" --uninstall',
        )
        _winreg.SetValueEx(
            key, "DisplayIcon", 0, _winreg.REG_SZ, str(BINARY_DST)
        )
        _winreg.SetValueEx(
            key, "InstallLocation", 0, _winreg.REG_SZ, str(BIN_DIR)
        )
        _winreg.SetValueEx(
            key, "DisplayVersion", 0, _winreg.REG_SZ, APP_VERSION
        )
        _winreg.SetValueEx(key, "NoModify", 0, _winreg.REG_DWORD, 1)
        _winreg.SetValueEx(key, "NoRepair", 0, _winreg.REG_DWORD, 1)
        _winreg.CloseKey(key)
        print(f"Registered Programs entry\t→ HKCU\\...\\Uninstall\\{APP_NAME}")

    def _remove_start_menu() -> None:
        """Remove the main Start Menu shortcut and prune the folder if empty."""
        if START_MENU_SHORTCUT.exists():
            START_MENU_SHORTCUT.unlink()
            print(f"Removed Start Menu\t→ {START_MENU_SHORTCUT}")
        else:
            print(f"Start Menu not found\t→ {START_MENU_SHORTCUT}  (skipping)")
        try:
            START_MENU_DIR.rmdir()
        except OSError:
            pass

    def _remove_start_menu_uninstall() -> None:
        """Remove the Uninstall shortcut and prune the folder if empty."""
        if START_MENU_UNINSTALL.exists():
            START_MENU_UNINSTALL.unlink()
            print(f"Removed uninstall entry\t→ {START_MENU_UNINSTALL}")
        else:
            print(
                f"Uninstall entry not found\t→ {START_MENU_UNINSTALL}"
                "  (skipping)"
            )
        try:
            START_MENU_DIR.rmdir()
        except OSError:
            pass

    def _remove_programs_entry() -> None:
        """Remove the app from Settings > Apps (Add/Remove Programs)."""
        try:
            _winreg.DeleteKey(_winreg.HKEY_CURRENT_USER, _UNINSTALL_KEY)
            print(f"Removed Programs entry\t→ HKCU\\...\\Uninstall\\{APP_NAME}")
        except FileNotFoundError:
            print(
                f"Programs entry not found\t→ HKCU\\...\\Uninstall\\{APP_NAME}"
                "  (skipping)"
            )

    def _remove_desktop_shortcut() -> None:
        """Remove the Desktop shortcut if present."""
        if DESKTOP_SHORTCUT.exists():
            DESKTOP_SHORTCUT.unlink()
            print(f"Removed Desktop\t\t→ {DESKTOP_SHORTCUT}")

        else:
            print(f"Desktop not found\t→ {DESKTOP_SHORTCUT}  (skipping)")


if sys.platform == "linux":

    def _install_launcher() -> None:
        """add app launcher entry into launcher"""
        APPS_DIR.mkdir(
            parents=True, exist_ok=True
        )  # create apps dir (if missing)

        content = _render_desktop(
            f"{BINARY_DST} --force", "Categories=Utility;"
        )
        LAUNCHER_FILE.write_text(content)  # write launcher desktop entry

        print(f"Registered launcher\t→ {LAUNCHER_FILE}")


# ─────────────────────────────────────────────────────────| Uninstall steps |──


def _remove_binary() -> None:
    """removes the binary"""
    if not BINARY_DST.exists():
        print(f"Binary not found\t→ {BINARY_DST}  (skipping)")
        return

    if sys.platform == "win32":
        # Windows locks a running EXE so it cannot be deleted directly.
        # Rename it first (allowed while running, frees the install path
        # immediately), then let a detached cmd script delete the renamed
        # copy and the now-empty directory once this process exits.
        pending = BINARY_DST.with_name(BINARY_DST.stem + ".uninstalling.exe")
        BINARY_DST.rename(pending)
        # PowerShell with -WindowStyle Hidden + CREATE_NO_WINDOW is fully
        # invisible. Start-Sleep gives this process ~2 s to exit before the
        # cleanup fires (no cmd / ping required).
        script = (
            f"Start-Sleep 2;"
            f" Remove-Item -Force -LiteralPath '{pending}';"
            f" Remove-Item -ErrorAction SilentlyContinue '{BIN_DIR}'"
        )
        subprocess.Popen(
            [
                "powershell",
                "-WindowStyle",
                "Hidden",
                "-NonInteractive",
                "-NoProfile",
                "-Command",
                script,
            ],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"Scheduled binary removal\t→ {BINARY_DST}")
    else:
        BINARY_DST.unlink()
        print(f"Removed binary\t\t→ {BINARY_DST}")


def _remove_config() -> None:
    """removes the config dir"""
    if CONFIG_DIR.exists():
        shutil.rmtree(CONFIG_DIR)
        print(f"Removed config\t\t→ {CONFIG_DIR}")

    else:
        print(f"Config not found\t→ {CONFIG_DIR}  (skipping)")


if sys.platform == "linux":

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
        _install_start_menu()
        _install_start_menu_uninstall()
        _install_programs_entry()

        if _ask_desktop_shortcut():
            _install_desktop_shortcut()

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
        _remove_programs_entry()
        _remove_start_menu_uninstall()
        _remove_start_menu()
        _remove_desktop_shortcut()

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
