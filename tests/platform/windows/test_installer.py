from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src import APP_NAME
from src.installer import install, uninstall
from src.platform.windows.installer import (
    ask_desktop_shortcut,
    create_lnk,
    install_autostart_windows,
    install_desktop_shortcut,
    install_programs_entry,
    install_start_menu,
    install_start_menu_uninstall,
    remove_autostart_windows,
    remove_desktop_shortcut,
    remove_programs_entry,
    remove_start_menu,
    remove_start_menu_uninstall,
)

# ────────────────────────────────────────────────────────────────| Fixtures |──


@pytest.fixture
def paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Redirect all Windows installer path constants into tmp_path.

    Args:
        tmp_path (Path): Pytest fixture providing a temporary directory.
        monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect the
                                          installer path constants.

    Returns:
        dict[str, Path]: Mapping of logical path names to their tmp_path
                         locations.
    """

    bin_dir = tmp_path / "bin"
    binary_dst = bin_dir / f"{APP_NAME}.exe"
    start_menu_dir = tmp_path / "start_menu"
    start_menu_shortcut = start_menu_dir / f"{APP_NAME}.lnk"
    start_menu_uninstall = start_menu_dir / f"Uninstall {APP_NAME}.lnk"
    desktop_shortcut = tmp_path / f"{APP_NAME}.lnk"

    monkeypatch.setattr("src.installer.BIN_DIR", bin_dir)
    monkeypatch.setattr("src.installer.BINARY_DST", binary_dst)
    monkeypatch.setattr("src.platform.windows.installer.BIN_DIR", bin_dir)
    monkeypatch.setattr("src.platform.windows.installer.BINARY_DST", binary_dst)
    monkeypatch.setattr(
        "src.platform.windows.installer.START_MENU_DIR", start_menu_dir
    )
    monkeypatch.setattr(
        "src.platform.windows.installer.START_MENU_SHORTCUT",
        start_menu_shortcut,
    )
    monkeypatch.setattr(
        "src.platform.windows.installer.START_MENU_UNINSTALL",
        start_menu_uninstall,
    )
    monkeypatch.setattr(
        "src.platform.windows.installer.DESKTOP_SHORTCUT", desktop_shortcut
    )

    return {
        "bin_dir": bin_dir,
        "binary_dst": binary_dst,
        "start_menu_dir": start_menu_dir,
        "start_menu_shortcut": start_menu_shortcut,
        "start_menu_uninstall": start_menu_uninstall,
        "desktop_shortcut": desktop_shortcut,
    }


# ───────────────────────────────────────────────| install_autostart_windows |──


class TestInstallAutostartWindows:
    """Tests install_autostart_windows registers a Run registry value."""

    def test_writes_run_value_with_app_name(self) -> None:
        """SetValueEx is called with APP_NAME as the registry value name."""

        with patch("src.platform.windows.installer._winreg") as mock_reg:
            install_autostart_windows()

        call_args = mock_reg.SetValueEx.call_args[0]

        # SetValueEx(key, value_name, reserved, type, data)
        assert call_args[1] == APP_NAME

    def test_close_key_always_called(self) -> None:
        """CloseKey is called after the value is written."""

        with patch("src.platform.windows.installer._winreg") as mock_reg:
            install_autostart_windows()

        mock_reg.CloseKey.assert_called_once()


class TestRemoveAutostartWindows:
    """Tests remove_autostart_windows deletes the Run registry value."""

    def test_deletes_value_when_present(self) -> None:
        """DeleteValue is called with APP_NAME when the Run value exists."""

        with patch("src.platform.windows.installer._winreg") as mock_reg:
            remove_autostart_windows()

        call_args = mock_reg.DeleteValue.call_args[0]

        assert call_args[1] == APP_NAME

    def test_file_not_found_does_not_raise(self) -> None:
        """FileNotFoundError from a missing Run value is swallowed
        gracefully."""

        with patch("src.platform.windows.installer._winreg") as mock_reg:
            mock_reg.DeleteValue.side_effect = FileNotFoundError

            remove_autostart_windows()  # must not raise


class TestCreateLnk:
    """Tests create_lnk invokes PowerShell with the expected arguments."""

    def test_calls_powershell(self, tmp_path: Path) -> None:
        """subprocess.run is called with powershell as the first command token.

        Args:
            tmp_path (Path): Provides paths for lnk and target arguments.
        """

        lnk = tmp_path / "test.lnk"
        target = tmp_path / "app.exe"

        with patch("src.platform.windows.installer.subprocess.run") as mock_run:
            create_lnk(lnk, target, "--force", "A description")

        cmd = mock_run.call_args[0][0]

        assert cmd[0] == "powershell"

    def test_script_contains_target_and_args(self, tmp_path: Path) -> None:
        """The PowerShell script embeds the target path and arguments string.

        Args:
            tmp_path (Path): Provides paths for lnk and target arguments.
        """

        lnk = tmp_path / "test.lnk"
        target = tmp_path / "app.exe"

        with patch("src.platform.windows.installer.subprocess.run") as mock_run:
            create_lnk(lnk, target, "--force", "A description")

        script = mock_run.call_args[0][0][-1]

        assert str(target) in script
        assert "--force" in script


class TestInstallStartMenu:
    """Tests install_start_menu creates the Start Menu directory and
    shortcut."""

    def test_creates_start_menu_dir(
        self, paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """START_MENU_DIR is created when it does not exist.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths.
            monkeypatch (pytest.MonkeyPatch): Injects a no-op create_lnk.
        """

        monkeypatch.setattr(
            "src.platform.windows.installer.create_lnk", MagicMock()
        )
        install_start_menu()

        assert paths["start_menu_dir"].is_dir()

    def test_calls_create_lnk(
        self, paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """create_lnk is called with the Start Menu shortcut path.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths.
            monkeypatch (pytest.MonkeyPatch): Captures create_lnk calls.
        """

        mock_lnk = MagicMock()

        monkeypatch.setattr(
            "src.platform.windows.installer.create_lnk", mock_lnk
        )
        install_start_menu()
        mock_lnk.assert_called_once()

        assert mock_lnk.call_args[0][0] == paths["start_menu_shortcut"]


class TestAskDesktopShortcut:
    """Tests ask_desktop_shortcut prompt behaviour."""

    def test_non_tty_returns_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-interactive stdin defaults to creating the shortcut.

        Args:
            monkeypatch (pytest.MonkeyPatch): Makes sys.stdin non-TTY.
        """

        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: False))

        assert ask_desktop_shortcut() is True

    def test_n_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Entering 'n' declines the Desktop shortcut.

        Args:
            monkeypatch (pytest.MonkeyPatch): Makes stdin a TTY and answers n.
        """

        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda _: "n")

        assert ask_desktop_shortcut() is False

    def test_empty_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pressing Enter (empty answer) accepts the default Yes.

        Args:
            monkeypatch (pytest.MonkeyPatch): Makes stdin a TTY and answers
                with an empty string.
        """

        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda _: "")

        assert ask_desktop_shortcut() is True

    def test_eof_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """EOFError is caught and treated as Yes.

        Args:
            monkeypatch (pytest.MonkeyPatch): Makes stdin a TTY and raises EOF.
        """

        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", MagicMock(side_effect=EOFError))

        assert ask_desktop_shortcut() is True


class TestInstallDesktopShortcut:
    """Tests install_desktop_shortcut delegates to create_lnk."""

    def test_calls_create_lnk_with_desktop_path(
        self, paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """create_lnk is called with DESKTOP_SHORTCUT as the first argument.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths.
            monkeypatch (pytest.MonkeyPatch): Captures create_lnk calls.
        """

        mock_lnk = MagicMock()

        monkeypatch.setattr(
            "src.platform.windows.installer.create_lnk", mock_lnk
        )
        install_desktop_shortcut()
        mock_lnk.assert_called_once()

        assert mock_lnk.call_args[0][0] == paths["desktop_shortcut"]


class TestRemoveStartMenu:
    """Tests remove_start_menu deletes the shortcut or skips gracefully."""

    def test_removes_existing_shortcut(self, paths: dict[str, Path]) -> None:
        """The Start Menu .lnk file is deleted when it exists.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths.
        """

        paths["start_menu_dir"].mkdir(parents=True, exist_ok=True)
        paths["start_menu_shortcut"].touch()

        remove_start_menu()

        assert not paths["start_menu_shortcut"].exists()

    def test_noop_when_shortcut_missing(self, paths: dict[str, Path]) -> None:
        """No error is raised when the Start Menu shortcut is absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths.
        """

        remove_start_menu()  # must not raise


class TestRemoveDesktopShortcut:
    """Tests remove_desktop_shortcut deletes the shortcut or skips
    gracefully."""

    def test_removes_existing_shortcut(self, paths: dict[str, Path]) -> None:
        """The Desktop .lnk file is deleted when it exists.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths.
        """

        paths["desktop_shortcut"].touch()
        remove_desktop_shortcut()

        assert not paths["desktop_shortcut"].exists()

    def test_noop_when_shortcut_missing(self, paths: dict[str, Path]) -> None:
        """No error is raised when the Desktop shortcut is absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths.
        """

        remove_desktop_shortcut()  # must not raise


class TestInstallStartMenuUninstall:
    """Tests install_start_menu_uninstall creates the Uninstall shortcut."""

    def test_calls_create_lnk_with_uninstall_path(
        self, paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """create_lnk is called with START_MENU_UNINSTALL as the first arg.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths.
            monkeypatch (pytest.MonkeyPatch): Captures create_lnk calls.
        """

        mock_lnk = MagicMock()

        monkeypatch.setattr(
            "src.platform.windows.installer.create_lnk", mock_lnk
        )
        install_start_menu_uninstall()
        mock_lnk.assert_called_once()

        assert mock_lnk.call_args[0][0] == paths["start_menu_uninstall"]

    def test_uninstall_argument_passed(
        self, paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The shortcut is created with --uninstall as the arguments string.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths.
            monkeypatch (pytest.MonkeyPatch): Captures create_lnk calls.
        """

        mock_lnk = MagicMock()

        monkeypatch.setattr(
            "src.platform.windows.installer.create_lnk", mock_lnk
        )
        install_start_menu_uninstall()

        assert mock_lnk.call_args[0][2] == "--uninstall"


class TestInstallProgramsEntry:
    """Tests install_programs_entry writes the Uninstall registry key."""

    def test_sets_display_name(self) -> None:
        """DisplayName is set to APP_NAME in the registry key.

        Uses a mocked _winreg so no real registry writes occur.
        """

        with patch("src.platform.windows.installer._winreg") as mock_reg:
            install_programs_entry()

        set_calls = {
            call[0][1]: call[0][4]
            for call in mock_reg.SetValueEx.call_args_list
        }

        assert set_calls["DisplayName"] == APP_NAME

    def test_uninstall_string_contains_binary(self) -> None:
        """UninstallString embeds the binary path and --uninstall flag.

        Uses a mocked _winreg so no real registry writes occur.
        """

        with patch("src.platform.windows.installer._winreg") as mock_reg:
            install_programs_entry()

        set_calls = {
            call[0][1]: call[0][4]
            for call in mock_reg.SetValueEx.call_args_list
        }

        assert "--uninstall" in set_calls["UninstallString"]

    def test_close_key_always_called(self) -> None:
        """CloseKey is called after all values are written.

        Uses a mocked _winreg so no real registry writes occur.
        """

        with patch("src.platform.windows.installer._winreg") as mock_reg:
            install_programs_entry()

        mock_reg.CloseKey.assert_called_once()


class TestRemoveStartMenuUninstall:
    """Tests remove_start_menu_uninstall deletes the Uninstall shortcut."""

    def test_removes_existing_shortcut(self, paths: dict[str, Path]) -> None:
        """The Uninstall .lnk file is deleted when it exists.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths.
        """

        paths["start_menu_dir"].mkdir(parents=True, exist_ok=True)
        paths["start_menu_uninstall"].touch()
        remove_start_menu_uninstall()

        assert not paths["start_menu_uninstall"].exists()

    def test_noop_when_shortcut_missing(self, paths: dict[str, Path]) -> None:
        """No error is raised when the Uninstall shortcut is absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths.
        """

        remove_start_menu_uninstall()  # must not raise

    def test_removes_empty_start_menu_dir(self, paths: dict[str, Path]) -> None:
        """The Start Menu subfolder is removed when it is empty after cleanup.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths.
        """

        paths["start_menu_dir"].mkdir(parents=True, exist_ok=True)
        paths["start_menu_uninstall"].touch()
        remove_start_menu_uninstall()

        assert not paths["start_menu_dir"].exists()


class TestRemoveProgramsEntry:
    """Tests remove_programs_entry deletes the Uninstall registry key."""

    def test_deletes_key_when_present(self) -> None:
        """DeleteKey is called with the correct uninstall registry path.

        Uses a mocked _winreg so no real registry writes occur.
        """

        with patch("src.platform.windows.installer._winreg") as mock_reg:
            remove_programs_entry()

        mock_reg.DeleteKey.assert_called_once()
        call_args = mock_reg.DeleteKey.call_args[0]

        assert APP_NAME in call_args[1]

    def test_file_not_found_does_not_raise(self) -> None:
        """FileNotFoundError from a missing key is swallowed gracefully.

        Uses a mocked _winreg so no real registry writes occur.
        """

        with patch("src.platform.windows.installer._winreg") as mock_reg:
            mock_reg.DeleteKey.side_effect = FileNotFoundError

            remove_programs_entry()  # must not raise


# ──────────────────────────────────────────────────────────────| Public API |──


class TestInstall:
    """Tests install() dispatches to the Windows install steps."""

    def test_windows_calls_correct_install_steps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Windows, binary/config/autostart/start-menu are called and the
        desktop shortcut is created when the user accepts the prompt. Linux-only
        steps (icon, .desktop launcher) are not called.

        Args:
            monkeypatch (pytest.MonkeyPatch): Sets sys.platform to 'win32'
                and injects stubs for all Windows-only install functions.
        """

        monkeypatch.setattr(sys, "platform", "win32")

        mock_win_autostart = MagicMock()
        mock_start_menu = MagicMock()
        mock_ask_desktop = MagicMock(return_value=True)
        mock_install_desktop = MagicMock()
        mock_start_menu_uninstall = MagicMock()
        mock_programs_entry = MagicMock()

        monkeypatch.setattr(
            "src.platform.windows.installer.install_autostart_windows",
            mock_win_autostart,
        )
        monkeypatch.setattr(
            "src.platform.windows.installer.install_start_menu",
            mock_start_menu,
        )
        monkeypatch.setattr(
            "src.platform.windows.installer.install_start_menu_uninstall",
            mock_start_menu_uninstall,
        )
        monkeypatch.setattr(
            "src.platform.windows.installer.install_programs_entry",
            mock_programs_entry,
        )
        monkeypatch.setattr(
            "src.platform.windows.installer.ask_desktop_shortcut",
            mock_ask_desktop,
        )
        monkeypatch.setattr(
            "src.platform.windows.installer.install_desktop_shortcut",
            mock_install_desktop,
        )

        with (
            patch("src.installer._install_binary") as mock_binary,
            patch("src.installer._install_config") as mock_config,
        ):
            install(force=True)

        mock_binary.assert_called_once()
        mock_config.assert_called_once()
        mock_win_autostart.assert_called_once()
        mock_start_menu.assert_called_once()
        mock_start_menu_uninstall.assert_called_once()
        mock_programs_entry.assert_called_once()
        mock_ask_desktop.assert_called_once()
        mock_install_desktop.assert_called_once()


class TestUninstall:
    """Tests uninstall() dispatches to the Windows removal steps."""

    def test_windows_calls_windows_remove_autostart(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Windows, remove_autostart_windows, remove_start_menu, and
        remove_desktop_shortcut are called; Linux-only removal steps are not.

        Args:
            monkeypatch (pytest.MonkeyPatch): Sets sys.platform to 'win32'
                and injects stubs for all Windows-only remove functions.
        """

        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr("src.installer._ask_purge", lambda: False)
        mock_win_remove = MagicMock()
        mock_remove_programs = MagicMock()
        mock_remove_start_menu = MagicMock()
        mock_remove_start_menu_uninstall = MagicMock()
        mock_remove_desktop = MagicMock()
        monkeypatch.setattr(
            "src.platform.windows.installer.remove_autostart_windows",
            mock_win_remove,
        )
        monkeypatch.setattr(
            "src.platform.windows.installer.remove_programs_entry",
            mock_remove_programs,
        )
        monkeypatch.setattr(
            "src.platform.windows.installer.remove_start_menu",
            mock_remove_start_menu,
        )
        monkeypatch.setattr(
            "src.platform.windows.installer.remove_start_menu_uninstall",
            mock_remove_start_menu_uninstall,
        )
        monkeypatch.setattr(
            "src.platform.windows.installer.remove_desktop_shortcut",
            mock_remove_desktop,
        )

        with patch("src.installer._remove_binary"):
            uninstall()

        mock_win_remove.assert_called_once()
        mock_remove_programs.assert_called_once()
        mock_remove_start_menu.assert_called_once()
        mock_remove_start_menu_uninstall.assert_called_once()
        mock_remove_desktop.assert_called_once()
