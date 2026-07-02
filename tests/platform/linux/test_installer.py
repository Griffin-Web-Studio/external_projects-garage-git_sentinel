from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src import APP_NAME
from src.installer import _install_binary, install, uninstall
from src.platform.linux.installer import (
    install_autostart,
    install_icon,
    install_launcher,
    remove_autostart,
    remove_icon,
    remove_launcher,
)

# ────────────────────────────────────────────────────────────────| Fixtures |──


@pytest.fixture
def fake_binary(tmp_path: Path) -> Path:
    """A small executable-like file used as a stand-in for the app binary.

    Args:
        tmp_path (Path): Pytest fixture providing a temporary directory.

    Returns:
        Path: Path to the fake executable file.
    """

    b = tmp_path / "fake_bin"

    b.write_text("#!/bin/sh\necho hi")
    b.chmod(0o755)

    return b


@pytest.fixture
def paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Redirect all Linux installer path constants into tmp_path.

    Args:
        tmp_path (Path): Pytest fixture providing a temporary directory.
        monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect the
                                          installer path constants.

    Returns:
        dict[str, Path]: Mapping of logical path names to their tmp_path
                         locations.
    """

    bin_dir = tmp_path / "bin"
    binary_dst = bin_dir / APP_NAME
    autostart_dir = tmp_path / "autostart"
    autostart_file = autostart_dir / f"{APP_NAME}.desktop"
    apps_dir = tmp_path / "apps"
    launcher_file = apps_dir / f"{APP_NAME}.desktop"
    icons_dir = tmp_path / "icons"
    icon_file = icons_dir / f"{APP_NAME}.svg"

    monkeypatch.setattr("src.installer.BIN_DIR", bin_dir)
    monkeypatch.setattr("src.installer.BINARY_DST", binary_dst)
    monkeypatch.setattr("src.platform.linux.installer.BIN_DIR", bin_dir)
    monkeypatch.setattr("src.platform.linux.installer.BINARY_DST", binary_dst)
    monkeypatch.setattr(
        "src.platform.linux.installer.AUTOSTART_DIR", autostart_dir
    )
    monkeypatch.setattr(
        "src.platform.linux.installer.AUTOSTART_FILE", autostart_file
    )
    monkeypatch.setattr("src.platform.linux.installer.APPS_DIR", apps_dir)
    monkeypatch.setattr(
        "src.platform.linux.installer.LAUNCHER_FILE", launcher_file
    )
    monkeypatch.setattr("src.platform.linux.installer.ICONS_DIR", icons_dir)
    monkeypatch.setattr("src.platform.linux.installer.ICON_FILE", icon_file)

    return {
        "bin_dir": bin_dir,
        "binary_dst": binary_dst,
        "autostart_dir": autostart_dir,
        "autostart_file": autostart_file,
        "apps_dir": apps_dir,
        "launcher_file": launcher_file,
        "icons_dir": icons_dir,
        "icon_file": icon_file,
    }


# ─────────────────────────────────────────────────| _install_binary (Linux) |──


class TestInstallBinaryLinux:
    """Tests the installed binary has Linux executable permissions."""

    def test_sets_executable_permissions(
        self,
        paths: dict[str, Path],
        fake_binary: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The installed binary has mode 0o755.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
            fake_binary (Path): A temp file acting as the source binary.
            monkeypatch (pytest.MonkeyPatch): Makes _current_binary return
                                              fake_binary.
        """

        monkeypatch.setattr(
            "src.installer._current_binary", lambda: fake_binary
        )
        _install_binary()

        assert paths["binary_dst"].stat().st_mode & 0o755 == 0o755


# ───────────────────────────────────────────────────────────| install_icon |──


class TestInstallIcon:
    """Tests install_icon copies the SVG into the hicolor icon tree."""

    def test_copies_svg_to_icons_dir(
        self, paths: dict[str, Path], tmp_path: Path
    ) -> None:
        """The SVG is present at ICON_FILE with its original content after
        install.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
            tmp_path (Path): Provides space for the fake SVG source file.
        """

        svg = tmp_path / f"{APP_NAME}.svg"

        svg.write_text("<svg/>")
        install_icon(svg)

        assert paths["icon_file"].read_text() == "<svg/>"


# ──────────────────────────────────────────────────────| install_autostart |──


class TestInstallAutostart:
    """Tests install_autostart writes the autostart .desktop entry."""

    def test_creates_autostart_file(self, paths: dict[str, Path]) -> None:
        """The autostart .desktop file is created in AUTOSTART_DIR.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        install_autostart("[Desktop Entry]\nExec=/bin/x\n")

        assert paths["autostart_file"].exists()

    def test_includes_gnome_autostart_flag(
        self, paths: dict[str, Path]
    ) -> None:
        """The rendered autostart content is written verbatim, including the
        GNOME autostart enable flag composed by the caller.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        install_autostart("[Desktop Entry]\nX-GNOME-Autostart-enabled=true\n")

        assert (
            "X-GNOME-Autostart-enabled=true"
            in paths["autostart_file"].read_text()
        )


# ───────────────────────────────────────────────────────| install_launcher |──


class TestInstallLauncher:
    """Tests install_launcher writes the applications .desktop entry."""

    def test_creates_launcher_file(self, paths: dict[str, Path]) -> None:
        """The launcher .desktop file is created in APPS_DIR.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        install_launcher("[Desktop Entry]\nExec=/bin/x --force\n")

        assert paths["launcher_file"].exists()

    def test_exec_includes_force_flag(self, paths: dict[str, Path]) -> None:
        """The rendered launcher content is written verbatim, including the
        --force flag composed by the caller.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        install_launcher("[Desktop Entry]\nExec=/bin/x --force\n")

        assert "--force" in paths["launcher_file"].read_text()


# ────────────────────────────────────────────────────────────| Remove steps |──


class TestRemoveIcon:
    """Tests remove_icon deletes the SVG or skips when absent."""

    def test_removes_existing_icon(self, paths: dict[str, Path]) -> None:
        """The icon file is deleted when it exists.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        paths["icons_dir"].mkdir(parents=True, exist_ok=True)
        paths["icon_file"].write_text("<svg/>")
        remove_icon()

        assert not paths["icon_file"].exists()

    def test_noop_when_icon_missing(self, paths: dict[str, Path]) -> None:
        """No error is raised when the icon is already absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        remove_icon()  # must not raise


class TestRemoveAutostart:
    """Tests remove_autostart deletes the autostart entry or skips when
    absent."""

    def test_removes_existing_file(self, paths: dict[str, Path]) -> None:
        """The autostart .desktop file is deleted when it exists.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        paths["autostart_dir"].mkdir(parents=True, exist_ok=True)
        paths["autostart_file"].touch()
        remove_autostart()

        assert not paths["autostart_file"].exists()

    def test_noop_when_missing(self, paths: dict[str, Path]) -> None:
        """No error is raised when the autostart entry is already absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        remove_autostart()  # must not raise


class TestRemoveLauncher:
    """Tests remove_launcher deletes the launcher entry or skips when
    absent."""

    def test_removes_existing_file(self, paths: dict[str, Path]) -> None:
        """The launcher .desktop file is deleted when it exists.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        paths["apps_dir"].mkdir(parents=True, exist_ok=True)
        paths["launcher_file"].touch()
        remove_launcher()

        assert not paths["launcher_file"].exists()

    def test_noop_when_missing(self, paths: dict[str, Path]) -> None:
        """No error is raised when the launcher entry is already absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        remove_launcher()  # must not raise


# ──────────────────────────────────────────────────────────────| Public API |──


class TestInstall:
    """Tests install() dispatches to the Linux install steps."""

    def test_linux_calls_correct_install_steps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Linux, binary/config/icon/autostart/launcher are each called
        once, with --force and the GNOME autostart flag wired in.

        Args:
            monkeypatch (pytest.MonkeyPatch): Sets sys.platform to 'linux'.
        """

        monkeypatch.setattr(sys, "platform", "linux")

        mock_icon = MagicMock()
        mock_autostart = MagicMock()
        mock_launcher = MagicMock()

        monkeypatch.setattr(
            "src.platform.linux.installer.install_icon", mock_icon
        )
        monkeypatch.setattr(
            "src.platform.linux.installer.install_autostart", mock_autostart
        )
        monkeypatch.setattr(
            "src.platform.linux.installer.install_launcher", mock_launcher
        )

        with (
            patch("src.installer._install_binary") as mock_binary,
            patch("src.installer._install_config") as mock_config,
        ):
            install(force=True)

        mock_binary.assert_called_once()
        mock_config.assert_called_once()
        mock_icon.assert_called_once()
        mock_autostart.assert_called_once()
        mock_launcher.assert_called_once()

        assert (
            "X-GNOME-Autostart-enabled=true" in mock_autostart.call_args[0][0]
        )
        assert "--force" in mock_launcher.call_args[0][0]

    def test_force_false_prints_usage_hints(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When force=False, run-immediately and configure hints are printed.

        Args:
            monkeypatch (pytest.MonkeyPatch): Sets sys.platform to 'linux'.
            capsys (pytest.CaptureFixture[str]): Captures stdout.
        """

        monkeypatch.setattr(sys, "platform", "linux")

        with (
            patch("src.installer._install_binary"),
            patch("src.installer._install_config"),
            patch("src.platform.linux.installer.install_icon"),
            patch("src.platform.linux.installer.install_autostart"),
            patch("src.platform.linux.installer.install_launcher"),
        ):
            install(force=False)

        out = capsys.readouterr().out

        assert "To run immediately" in out
        assert "To configure" in out


class TestUninstall:
    """Tests uninstall() dispatches to the Linux removal steps."""

    def test_linux_purge_removes_config_and_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Linux with purge approved, config and state removal steps are
        called.

        Args:
            monkeypatch (pytest.MonkeyPatch): Makes _ask_purge return True.
        """

        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr("src.installer._ask_purge", lambda: True)

        with (
            patch("src.platform.linux.installer.remove_autostart"),
            patch("src.platform.linux.installer.remove_launcher"),
            patch("src.platform.linux.installer.remove_icon"),
            patch("src.installer._remove_config") as mock_config,
            patch("src.installer._remove_state") as mock_state,
            patch("src.installer._remove_binary"),
        ):
            uninstall()

        mock_config.assert_called_once()
        mock_state.assert_called_once()

    def test_linux_no_purge_skips_config_and_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Linux with purge declined, config and state are left on disk.

        Args:
            monkeypatch (pytest.MonkeyPatch): Makes _ask_purge return False.
        """

        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr("src.installer._ask_purge", lambda: False)

        with (
            patch("src.platform.linux.installer.remove_autostart"),
            patch("src.platform.linux.installer.remove_launcher"),
            patch("src.platform.linux.installer.remove_icon"),
            patch("src.installer._remove_config") as mock_config,
            patch("src.installer._remove_state") as mock_state,
            patch("src.installer._remove_binary"),
        ):
            uninstall()

        mock_config.assert_not_called()
        mock_state.assert_not_called()
