from __future__ import annotations

import os
import subprocess
import sys
import winreg as _winreg
from pathlib import Path

from src import APP_NAME, APP_VERSION

# ───────────────────────────────────────────────────────────────────| Paths |──

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
    _appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME
)
START_MENU_SHORTCUT = START_MENU_DIR / f"{APP_NAME}.lnk"
START_MENU_UNINSTALL = START_MENU_DIR / f"Uninstall {APP_NAME}.lnk"

_SHELL_FOLDERS_KEY = r"Software\Microsoft\Windows\Shell\User Shell Folders"


def _desktop_dir() -> Path:
    if sys.platform == "win32":
        try:
            _hkey = _winreg.OpenKey(
                _winreg.HKEY_CURRENT_USER, _SHELL_FOLDERS_KEY
            )
            _desktop_val, _ = _winreg.QueryValueEx(_hkey, "Desktop")
            _winreg.CloseKey(_hkey)

            return Path(os.path.expandvars(str(_desktop_val)))

        except OSError:
            pass

    return Path.home() / "Desktop"


DESKTOP_SHORTCUT = _desktop_dir() / f"{APP_NAME}.lnk"

# ───────────────────────────────────────────────| Install steps (protected) |──


def install_autostart_windows() -> None:
    """Add a Run registry value so the app launches at Windows login."""

    if sys.platform != "win32":
        return

    key = _winreg.OpenKey(
        _winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, _winreg.KEY_SET_VALUE
    )

    _winreg.SetValueEx(key, APP_NAME, 0, _winreg.REG_SZ, str(BINARY_DST))
    _winreg.CloseKey(key)

    print(f"Registered autostart\t→ HKCU\\...\\Run\\{APP_NAME}")


def remove_autostart_windows() -> None:
    """Remove the Run registry value added by install_autostart_windows."""

    if sys.platform != "win32":
        return

    try:
        key = _winreg.OpenKey(
            _winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, _winreg.KEY_SET_VALUE
        )
        _winreg.DeleteValue(key, APP_NAME)
        _winreg.CloseKey(key)

        print(f"Removed autostart\t→ HKCU\\...\\Run\\{APP_NAME}")

    except FileNotFoundError:
        print(f"Autostart not found\t→ HKCU\\...\\Run\\{APP_NAME}  (skipping)")


def create_lnk(lnk: Path, target: Path, args: str, description: str) -> None:
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
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True,
        capture_output=True,
    )


def install_start_menu() -> None:
    """Create a Start Menu shortcut so the app is discoverable from the
    Windows shell."""

    START_MENU_DIR.mkdir(parents=True, exist_ok=True)

    create_lnk(
        START_MENU_SHORTCUT, BINARY_DST, "--force", "Daily git repository audit"
    )
    print(f"Registered Start Menu\t→ {START_MENU_SHORTCUT}")


def ask_desktop_shortcut() -> bool:
    """Prompt whether to add a Desktop shortcut; defaults to Yes."""

    if not sys.stdin.isatty():
        return True

    try:
        answer = input("\nCreate a Desktop shortcut? [Y/n] ").strip().lower()

        return answer not in ("n", "no")

    except EOFError:
        return True


def install_desktop_shortcut() -> None:
    """Create a Desktop shortcut alongside the Start Menu entry."""

    create_lnk(
        DESKTOP_SHORTCUT, BINARY_DST, "--force", "Daily git repository audit"
    )
    print(f"Registered Desktop\t→ {DESKTOP_SHORTCUT}")


def install_start_menu_uninstall() -> None:
    """Create an Uninstall shortcut in the Start Menu subfolder."""

    create_lnk(
        START_MENU_UNINSTALL, BINARY_DST, "--uninstall", f"Uninstall {APP_NAME}"
    )
    print(f"Registered uninstall entry\t→ {START_MENU_UNINSTALL}")


def install_programs_entry() -> None:
    """Register the app in Settings > Apps (Add/Remove Programs)."""

    if sys.platform != "win32":
        return

    key = _winreg.CreateKeyEx(
        _winreg.HKEY_CURRENT_USER, _UNINSTALL_KEY, 0, _winreg.KEY_SET_VALUE
    )
    _winreg.SetValueEx(key, "DisplayName", 0, _winreg.REG_SZ, APP_NAME)
    _winreg.SetValueEx(
        key, "UninstallString", 0, _winreg.REG_SZ, f'"{BINARY_DST}" --uninstall'
    )
    _winreg.SetValueEx(key, "DisplayIcon", 0, _winreg.REG_SZ, str(BINARY_DST))
    _winreg.SetValueEx(key, "InstallLocation", 0, _winreg.REG_SZ, str(BIN_DIR))
    _winreg.SetValueEx(key, "DisplayVersion", 0, _winreg.REG_SZ, APP_VERSION)
    _winreg.SetValueEx(key, "NoModify", 0, _winreg.REG_DWORD, 1)
    _winreg.SetValueEx(key, "NoRepair", 0, _winreg.REG_DWORD, 1)
    _winreg.CloseKey(key)
    print(f"Registered Programs entry\t→ HKCU\\...\\Uninstall\\{APP_NAME}")


# ─────────────────────────────────────────────────────────| Uninstall steps |──


def remove_binary() -> None:
    """removes the binary"""

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
    creationflags = 0

    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

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
        creationflags=creationflags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"Scheduled binary removal\t→ {BINARY_DST}")


def remove_start_menu() -> None:
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


def remove_start_menu_uninstall() -> None:
    """Remove the Uninstall shortcut and prune the folder if empty."""

    if START_MENU_UNINSTALL.exists():
        START_MENU_UNINSTALL.unlink()
        print(f"Removed uninstall entry\t→ {START_MENU_UNINSTALL}")

    else:
        print(
            f"Uninstall entry not found\t→ {START_MENU_UNINSTALL}  (skipping)"
        )

    try:
        START_MENU_DIR.rmdir()

    except OSError:
        pass


def remove_programs_entry() -> None:
    """Remove the app from Settings > Apps (Add/Remove Programs)."""

    if sys.platform != "win32":
        return

    try:
        _winreg.DeleteKey(_winreg.HKEY_CURRENT_USER, _UNINSTALL_KEY)
        print(f"Removed Programs entry\t→ HKCU\\...\\Uninstall\\{APP_NAME}")

    except FileNotFoundError:
        print(
            f"Programs entry not found\t→ HKCU\\...\\Uninstall\\{APP_NAME}"
            "  (skipping)"
        )


def remove_desktop_shortcut() -> None:
    """Remove the Desktop shortcut if present."""

    if DESKTOP_SHORTCUT.exists():
        DESKTOP_SHORTCUT.unlink()
        print(f"Removed Desktop\t\t→ {DESKTOP_SHORTCUT}")

    else:
        print(f"Desktop not found\t→ {DESKTOP_SHORTCUT}  (skipping)")
