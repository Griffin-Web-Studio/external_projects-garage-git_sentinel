from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src import APP_NAME

linux_only = pytest.mark.skipif(
    sys.platform != "linux", reason="requires Linux"
)
windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="requires Windows"
)
import src.installer as _installer_module
from src.installer import (
    _ask_purge,
    _current_binary,
    _install_binary,
    _install_config,
    _render_desktop,
    _remove_binary,
    _remove_config,
    _remove_state,
    _resource,
    install,
    is_installed,
    uninstall,
)

# ────────────────────────────────────────────────────────────────| Fixtures |──


@pytest.fixture
def fake_binary(tmp_path: Path) -> Path:
    """A small executable-like file used as a stand-in for the app binary."""
    b = tmp_path / "fake_bin"
    b.write_text("#!/bin/sh\necho hi")
    b.chmod(0o755)

    return b


@pytest.fixture
def desktop_template(tmp_path: Path) -> Path:
    """A minimal .desktop template containing {exec} and {extra}
    placeholders."""
    t = tmp_path / f"{APP_NAME}.desktop"
    t.write_text("[Desktop Entry]\nExec={exec}\n{extra}\n")

    return t


@pytest.fixture
def example_ini(tmp_path: Path) -> Path:
    """A minimal settings.example.ini file acting as the bundled resource."""
    f = tmp_path / "settings.example.ini"
    f.write_text("[paths]\ngit_root = git\n")

    return f


@pytest.fixture
def paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Redirect all installer module-level path constants into tmp_path."""
    bin_dir = tmp_path / "bin"
    binary_dst = bin_dir / APP_NAME
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    autostart_dir = tmp_path / "autostart"
    autostart_file = autostart_dir / f"{APP_NAME}.desktop"
    apps_dir = tmp_path / "apps"
    launcher_file = apps_dir / f"{APP_NAME}.desktop"
    icons_dir = tmp_path / "icons"
    icon_file = icons_dir / f"{APP_NAME}.svg"

    monkeypatch.setattr("src.installer.BIN_DIR", bin_dir)
    monkeypatch.setattr("src.installer.BINARY_DST", binary_dst)
    monkeypatch.setattr("src.installer.CONFIG_DIR", config_dir)
    monkeypatch.setattr("src.installer.STATE_DIR", state_dir)
    # Linux-only constants: silently skip on Windows where they don't exist.
    monkeypatch.setattr(
        "src.installer.AUTOSTART_DIR", autostart_dir, raising=False
    )
    monkeypatch.setattr(
        "src.installer.AUTOSTART_FILE", autostart_file, raising=False
    )
    monkeypatch.setattr("src.installer.APPS_DIR", apps_dir, raising=False)
    monkeypatch.setattr(
        "src.installer.LAUNCHER_FILE", launcher_file, raising=False
    )
    monkeypatch.setattr("src.installer.ICONS_DIR", icons_dir, raising=False)
    monkeypatch.setattr("src.installer.ICON_FILE", icon_file, raising=False)

    return {
        "bin_dir": bin_dir,
        "binary_dst": binary_dst,
        "config_dir": config_dir,
        "state_dir": state_dir,
        "autostart_dir": autostart_dir,
        "autostart_file": autostart_file,
        "apps_dir": apps_dir,
        "launcher_file": launcher_file,
        "icons_dir": icons_dir,
        "icon_file": icon_file,
    }


# ───────────────────────────────────────────────────────────────| _resource |──


class TestResource:
    """Tests _resource resolves bundled data files in both dev and frozen
    modes."""

    def test_dev_mode_path_is_under_data_subdir(self) -> None:
        """In dev mode the path sits under the src/data/ directory."""
        result = _resource("settings.example.ini")

        assert result.name == "settings.example.ini"
        assert result.parent.name == "data"

    def test_frozen_mode_uses_meipass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In PyInstaller frozen mode returns _MEIPASS/data/<name>.

        Args:
            tmp_path (Path): Used as the fake _MEIPASS extraction directory.
            monkeypatch (pytest.MonkeyPatch): Injects _MEIPASS onto sys.
        """
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        result = _resource("settings.example.ini")

        assert result == tmp_path / "data" / "settings.example.ini"


# ─────────────────────────────────────────────────────────| _current_binary |──


class TestCurrentBinary:
    """Tests _current_binary returns the correct path in dev and frozen
    modes."""

    def test_frozen_returns_sys_executable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In frozen mode the resolved path of sys.executable is returned.

        Args:
            monkeypatch (pytest.MonkeyPatch): Sets sys.frozen and
                                              sys.executable.
        """
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", "/usr/bin/git-sentinel")
        result = _current_binary()

        assert result == Path("/usr/bin/git-sentinel").resolve()

    def test_dev_returns_argv0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """In dev mode the resolved path of sys.argv[0] is returned.

        Args:
            monkeypatch (pytest.MonkeyPatch): Removes sys.frozen and sets
                                              sys.argv.
        """
        if hasattr(sys, "frozen"):
            monkeypatch.delattr(sys, "frozen")

        monkeypatch.setattr(sys, "argv", ["/path/to/run.py"])
        result = _current_binary()

        assert result == Path("/path/to/run.py").resolve()


# ─────────────────────────────────────────────────────────| _render_desktop |──


class TestRenderDesktop:
    """Tests _render_desktop substitutes the template placeholders correctly."""

    def test_substitutes_exec_and_extra(
        self,
        desktop_template: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Both {exec} and {extra} placeholders are replaced; none remain.

        Args:
            desktop_template (Path): A temp .desktop file with {exec}/{extra}
                                     tokens.
            monkeypatch (pytest.MonkeyPatch): Redirects _resource to return the
                                              template.
        """
        monkeypatch.setattr(
            "src.installer._resource", lambda _name: desktop_template
        )
        result = _render_desktop("/usr/bin/git-sentinel", "Categories=Utility;")

        assert "Exec=/usr/bin/git-sentinel" in result
        assert "Categories=Utility;" in result
        assert "{exec}" not in result
        assert "{extra}" not in result


# ──────────────────────────────────────────────────────────────| _ask_purge |──


class TestAskPurge:
    """Tests _ask_purge returns the correct decision across all input
    scenarios."""

    def test_non_tty_returns_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-interactive stdin always returns False without prompting.

        Args:
            monkeypatch (pytest.MonkeyPatch): Makes sys.stdin report as non-TTY.
        """
        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: False))

        assert _ask_purge() is False

    def test_y_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Entering 'y' at the prompt returns True.

        Args:
            monkeypatch (pytest.MonkeyPatch): Makes stdin a TTY and patches
                                              input to 'y'.
        """
        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda _: "y")

        assert _ask_purge() is True

    def test_yes_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Entering the full word 'yes' also returns True.

        Args:
            monkeypatch (pytest.MonkeyPatch): Makes stdin a TTY and patches
                                              input to 'yes'.
        """
        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda _: "yes")

        assert _ask_purge() is True

    def test_other_input_returns_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Any answer other than y/yes defaults to keeping data.

        Args:
            monkeypatch (pytest.MonkeyPatch): Makes stdin a TTY and patches
                                              input to 'n'.
        """
        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda _: "n")

        assert _ask_purge() is False

    def test_eof_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """EOFError from a closed pipe is caught and returns False.

        Args:
            monkeypatch (pytest.MonkeyPatch): Makes stdin a TTY and patches
                                              input to raise EOFError.
        """
        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", MagicMock(side_effect=EOFError))

        assert _ask_purge() is False


# ────────────────────────────────────────────────────────────| is_installed |──


class TestIsInstalled:
    """Tests is_installed detects whether the running binary is the installed
    copy."""

    def test_same_file_returns_true(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns True when the current binary and BINARY_DST are the same
        file.

        Args:
            tmp_path (Path): Provides an isolated directory for the test binary.
            monkeypatch (pytest.MonkeyPatch): Redirects BINARY_DST and
                                              _current_binary.
        """
        binary = tmp_path / APP_NAME
        binary.touch()

        monkeypatch.setattr("src.installer.BINARY_DST", binary)
        monkeypatch.setattr("src.installer._current_binary", lambda: binary)

        assert is_installed() is True

    def test_different_files_returns_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns False when the current binary and BINARY_DST are different
        files.

        Args:
            tmp_path (Path): Provides an isolated directory for two distinct
                             files.
            monkeypatch (pytest.MonkeyPatch): Redirects BINARY_DST and
                                              _current_binary.
        """
        binary = tmp_path / APP_NAME
        binary.touch()
        other = tmp_path / "other"
        other.touch()

        monkeypatch.setattr("src.installer.BINARY_DST", binary)
        monkeypatch.setattr("src.installer._current_binary", lambda: other)

        assert is_installed() is False

    def test_oserror_returns_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns False when BINARY_DST does not exist and samefile raises
        OSError.

        Args:
            tmp_path (Path): Provides an isolated directory; BINARY_DST is not
                             created.
            monkeypatch (pytest.MonkeyPatch): Redirects BINARY_DST to a missing
                                              path.
        """
        binary_dst = tmp_path / APP_NAME  # intentionally not created
        current = tmp_path / "current"
        current.touch()

        monkeypatch.setattr("src.installer.BINARY_DST", binary_dst)
        monkeypatch.setattr("src.installer._current_binary", lambda: current)

        assert is_installed() is False


# ─────────────────────────────────────────────────────────| _install_binary |──


class TestInstallBinary:
    """Tests _install_binary copies the binary and sets executable
    permissions."""

    def test_copies_binary_to_dst(
        self,
        paths: dict[str, Path],
        fake_binary: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The binary is present at BINARY_DST after installation.

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

        assert paths["binary_dst"].exists()

    @linux_only
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

    def test_same_file_does_not_raise(
        self, paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SameFileError is swallowed when the source and destination are
        identical.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
            monkeypatch (pytest.MonkeyPatch): Makes _current_binary return the
                                              already-installed dst.
        """
        dst = paths["binary_dst"]
        paths["bin_dir"].mkdir(parents=True, exist_ok=True)
        dst.write_text("binary")
        monkeypatch.setattr("src.installer._current_binary", lambda: dst)
        _install_binary()  # must not raise


# ─────────────────────────────────────────────────────────| _install_config |──


class TestInstallConfig:
    """Tests _install_config generates and deploys config files correctly."""

    def test_writes_example_file(self, paths: dict[str, Path]) -> None:
        """settings.example.ini is always written to CONFIG_DIR.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        _install_config()

        assert (paths["config_dir"] / "settings.example.ini").exists()

    def test_example_file_contains_expected_sections(
        self, paths: dict[str, Path]
    ) -> None:
        """The generated settings.example.ini contains all standard sections.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        _install_config()

        content = (paths["config_dir"] / "settings.example.ini").read_text()
        for section in (
            "[paths]",
            "[reports]",
            "[staleness]",
            "[schedule]",
            "[ssh]",
        ):
            assert section in content

    def test_creates_config_when_absent(self, paths: dict[str, Path]) -> None:
        """settings.ini is seeded from generated content when absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        _install_config()

        assert (paths["config_dir"] / "settings.ini").exists()

    def test_leaves_existing_config_intact(
        self, paths: dict[str, Path]
    ) -> None:
        """An existing settings.ini is not overwritten on reinstall.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        config = paths["config_dir"] / "settings.ini"
        paths["config_dir"].mkdir(parents=True, exist_ok=True)
        config.write_text("[paths]\ngit_root = custom\n")

        _install_config()

        assert config.read_text() == "[paths]\ngit_root = custom\n"


# ───────────────────────────────────────────────────────────| _install_icon |──


@linux_only
class TestInstallIcon:
    """Tests _install_icon copies the SVG into the hicolor icon tree."""

    def test_copies_svg_to_icons_dir(
        self,
        paths: dict[str, Path],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The SVG is present at ICON_FILE with its original content after
        install.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
            tmp_path (Path): Provides space for the fake SVG source file.
            monkeypatch (pytest.MonkeyPatch): Redirects _resource to the fake
                                              SVG.
        """
        svg = tmp_path / f"{APP_NAME}.svg"
        svg.write_text("<svg/>")
        monkeypatch.setattr("src.installer._resource", lambda _name: svg)

        _installer_module._install_icon()

        assert paths["icon_file"].read_text() == "<svg/>"


# ──────────────────────────────────────────────────────| _install_autostart |──


@linux_only
class TestInstallAutostart:
    """Tests _install_autostart writes the autostart .desktop entry."""

    def test_creates_autostart_file(
        self,
        paths: dict[str, Path],
        desktop_template: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The autostart .desktop file is created in AUTOSTART_DIR.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
            desktop_template (Path): A temp .desktop template with
                                     {exec}/{extra} tokens.
            monkeypatch (pytest.MonkeyPatch): Redirects _resource to the
                                              template.
        """
        monkeypatch.setattr(
            "src.installer._resource", lambda _name: desktop_template
        )
        _installer_module._install_autostart()

        assert paths["autostart_file"].exists()

    def test_includes_gnome_autostart_flag(
        self,
        paths: dict[str, Path],
        desktop_template: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The autostart file contains the GNOME autostart enable flag.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
            desktop_template (Path): A temp .desktop template with
                                     {exec}/{extra} tokens.
            monkeypatch (pytest.MonkeyPatch): Redirects _resource to the
                                              template.
        """
        monkeypatch.setattr(
            "src.installer._resource", lambda _name: desktop_template
        )
        _installer_module._install_autostart()

        assert (
            "X-GNOME-Autostart-enabled=true"
            in paths["autostart_file"].read_text()
        )


# ───────────────────────────────────────────────────────| _install_launcher |──


@linux_only
class TestInstallLauncher:
    """Tests _install_launcher writes the applications .desktop entry."""

    def test_creates_launcher_file(
        self,
        paths: dict[str, Path],
        desktop_template: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The launcher .desktop file is created in APPS_DIR.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
            desktop_template (Path): A temp .desktop template with
                                     {exec}/{extra} tokens.
            monkeypatch (pytest.MonkeyPatch): Redirects _resource to the
                                              template.
        """
        monkeypatch.setattr(
            "src.installer._resource", lambda _name: desktop_template
        )

        _installer_module._install_launcher()

        assert paths["launcher_file"].exists()

    def test_exec_includes_force_flag(
        self,
        paths: dict[str, Path],
        desktop_template: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The launcher Exec line appends --force so it always runs when invoked
        manually.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
            desktop_template (Path): A temp .desktop template with
                                     {exec}/{extra} tokens.
            monkeypatch (pytest.MonkeyPatch): Redirects _resource to the
                                              template.
        """
        monkeypatch.setattr(
            "src.installer._resource", lambda _name: desktop_template
        )

        _installer_module._install_launcher()

        assert "--force" in paths["launcher_file"].read_text()


# ────────────────────────────────────────────────────────────| Remove steps |──


class TestRemoveBinary:
    """Tests _remove_binary deletes the binary or skips gracefully when
    absent."""

    def test_removes_existing_binary(self, paths: dict[str, Path]) -> None:
        """The binary file is deleted when it exists.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        paths["bin_dir"].mkdir(parents=True, exist_ok=True)
        paths["binary_dst"].touch()

        _remove_binary()

        assert not paths["binary_dst"].exists()

    def test_noop_when_binary_missing(self, paths: dict[str, Path]) -> None:
        """No error is raised when the binary is already absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        _remove_binary()  # must not raise


class TestRemoveConfig:
    """Tests _remove_config deletes the config directory or skips when
    absent."""

    def test_removes_existing_config_dir(self, paths: dict[str, Path]) -> None:
        """The config directory is removed when it exists.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        paths["config_dir"].mkdir(parents=True, exist_ok=True)
        _remove_config()

        assert not paths["config_dir"].exists()

    def test_noop_when_config_missing(self, paths: dict[str, Path]) -> None:
        """No error is raised when the config directory is already absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        _remove_config()  # must not raise


@linux_only
class TestRemoveIcon:
    """Tests _remove_icon deletes the SVG or skips when absent."""

    def test_removes_existing_icon(self, paths: dict[str, Path]) -> None:
        """The icon file is deleted when it exists.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        paths["icons_dir"].mkdir(parents=True, exist_ok=True)
        paths["icon_file"].write_text("<svg/>")

        _installer_module._remove_icon()

        assert not paths["icon_file"].exists()

    def test_noop_when_icon_missing(self, paths: dict[str, Path]) -> None:
        """No error is raised when the icon is already absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        _installer_module._remove_icon()  # must not raise


@linux_only
class TestRemoveAutostart:
    """Tests _remove_autostart deletes the autostart entry or skips when
    absent."""

    def test_removes_existing_file(self, paths: dict[str, Path]) -> None:
        """The autostart .desktop file is deleted when it exists.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        paths["autostart_dir"].mkdir(parents=True, exist_ok=True)
        paths["autostart_file"].touch()
        _installer_module._remove_autostart()

        assert not paths["autostart_file"].exists()

    def test_noop_when_missing(self, paths: dict[str, Path]) -> None:
        """No error is raised when the autostart entry is already absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        _installer_module._remove_autostart()  # must not raise


@linux_only
class TestRemoveLauncher:
    """Tests _remove_launcher deletes the launcher entry or skips when
    absent."""

    def test_removes_existing_file(self, paths: dict[str, Path]) -> None:
        """The launcher .desktop file is deleted when it exists.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        paths["apps_dir"].mkdir(parents=True, exist_ok=True)
        paths["launcher_file"].touch()
        _installer_module._remove_launcher()

        assert not paths["launcher_file"].exists()

    def test_noop_when_missing(self, paths: dict[str, Path]) -> None:
        """No error is raised when the launcher entry is already absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        _installer_module._remove_launcher()  # must not raise


class TestRemoveState:
    """Tests _remove_state deletes the state directory or skips when absent."""

    def test_removes_existing_state_dir(self, paths: dict[str, Path]) -> None:
        """The state directory is removed when it exists.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        paths["state_dir"].mkdir(parents=True, exist_ok=True)
        _remove_state()

        assert not paths["state_dir"].exists()

    def test_noop_when_state_missing(self, paths: dict[str, Path]) -> None:
        """No error is raised when the state directory is already absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """
        _remove_state()  # must not raise


# ──────────────────────────────────────────────────────────────| Public API |──


class TestInstall:
    """Tests the install() public entry point orchestrates all install steps."""

    def test_exits_on_unsupported_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """install() calls sys.exit(1) on platforms other than linux/win32.

        Args:
            monkeypatch (pytest.MonkeyPatch): Sets sys.platform to 'darwin'.
        """
        monkeypatch.setattr(sys, "platform", "darwin")

        with pytest.raises(SystemExit):
            install()

    def test_linux_calls_correct_install_steps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Linux, binary/config/icon/autostart/launcher are each called once.

        Args:
            monkeypatch (pytest.MonkeyPatch): Sets sys.platform to 'linux'.
        """
        monkeypatch.setattr(sys, "platform", "linux")

        with (
            patch("src.installer._install_binary") as mock_binary,
            patch("src.installer._install_config") as mock_config,
            patch("src.installer._install_icon", create=True) as mock_icon,
            patch(
                "src.installer._install_autostart", create=True
            ) as mock_autostart,
            patch(
                "src.installer._install_launcher", create=True
            ) as mock_launcher,
        ):
            install(force=True)

        mock_binary.assert_called_once()
        mock_config.assert_called_once()
        mock_icon.assert_called_once()
        mock_autostart.assert_called_once()
        mock_launcher.assert_called_once()

    def test_windows_calls_correct_install_steps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Windows, binary/config/windows-autostart are called; Linux-only
        steps (icon, .desktop launcher) are not.

        Args:
            monkeypatch (pytest.MonkeyPatch): Sets sys.platform to 'win32'
                and injects a stub for the Windows-only autostart function.
        """
        monkeypatch.setattr(sys, "platform", "win32")
        mock_win_autostart = MagicMock()
        monkeypatch.setattr(
            "src.installer._install_autostart_windows",
            mock_win_autostart,
            raising=False,
        )

        with (
            patch("src.installer._install_binary") as mock_binary,
            patch("src.installer._install_config") as mock_config,
            patch("src.installer._install_icon", create=True) as mock_icon,
            patch(
                "src.installer._install_autostart", create=True
            ) as mock_autostart,
            patch(
                "src.installer._install_launcher", create=True
            ) as mock_launcher,
        ):
            install(force=True)

        mock_binary.assert_called_once()
        mock_config.assert_called_once()
        mock_win_autostart.assert_called_once()
        mock_icon.assert_not_called()
        mock_autostart.assert_not_called()
        mock_launcher.assert_not_called()

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
            patch("src.installer._install_icon", create=True),
            patch("src.installer._install_autostart", create=True),
            patch("src.installer._install_launcher", create=True),
        ):
            install(force=False)

        out = capsys.readouterr().out
        assert "To run immediately" in out
        assert "To configure" in out


class TestUninstall:
    """Tests the uninstall() public entry point orchestrates all removal
    steps."""

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
            patch("src.installer._remove_autostart", create=True),
            patch("src.installer._remove_launcher", create=True),
            patch("src.installer._remove_icon", create=True),
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
            patch("src.installer._remove_autostart", create=True),
            patch("src.installer._remove_launcher", create=True),
            patch("src.installer._remove_icon", create=True),
            patch("src.installer._remove_config") as mock_config,
            patch("src.installer._remove_state") as mock_state,
            patch("src.installer._remove_binary"),
        ):
            uninstall()

        mock_config.assert_not_called()
        mock_state.assert_not_called()

    def test_windows_calls_windows_remove_autostart(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Windows, _remove_autostart_windows is called and Linux-only
        removal steps (icon, .desktop files) are not.

        Args:
            monkeypatch (pytest.MonkeyPatch): Sets sys.platform to 'win32'
                and injects a stub for the Windows-only remove function.
        """
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr("src.installer._ask_purge", lambda: False)
        mock_win_remove = MagicMock()
        monkeypatch.setattr(
            "src.installer._remove_autostart_windows",
            mock_win_remove,
            raising=False,
        )

        with (
            patch(
                "src.installer._remove_autostart", create=True
            ) as mock_autostart,
            patch(
                "src.installer._remove_launcher", create=True
            ) as mock_launcher,
            patch("src.installer._remove_icon", create=True) as mock_icon,
            patch("src.installer._remove_binary"),
        ):
            uninstall()

        mock_win_remove.assert_called_once()
        mock_autostart.assert_not_called()
        mock_launcher.assert_not_called()
        mock_icon.assert_not_called()


# ─────────────────────────────────────────────────────────| Windows (win32) |──


@windows_only
class TestInstallAutostartWindows:
    """Tests _install_autostart_windows registers a Run registry value.

    These tests are skipped on Linux (winreg is unavailable) and run only
    on the Windows CI runner.
    """

    def test_writes_run_value_with_app_name(self) -> None:
        """SetValueEx is called with APP_NAME as the registry value name."""
        import src.installer as _mod

        with patch("src.installer._winreg") as mock_reg:
            _mod._install_autostart_windows()

        call_args = mock_reg.SetValueEx.call_args[0]
        # SetValueEx(key, value_name, reserved, type, data)
        assert call_args[1] == APP_NAME

    def test_close_key_always_called(self) -> None:
        """CloseKey is called after the value is written."""
        import src.installer as _mod

        with patch("src.installer._winreg") as mock_reg:
            _mod._install_autostart_windows()

        mock_reg.CloseKey.assert_called_once()


@windows_only
class TestRemoveAutostartWindows:
    """Tests _remove_autostart_windows deletes the Run registry value.

    These tests are skipped on Linux (winreg is unavailable) and run only
    on the Windows CI runner.
    """

    def test_deletes_value_when_present(self) -> None:
        """DeleteValue is called with APP_NAME when the Run value exists."""
        import src.installer as _mod

        with patch("src.installer._winreg") as mock_reg:
            _mod._remove_autostart_windows()

        call_args = mock_reg.DeleteValue.call_args[0]
        assert call_args[1] == APP_NAME

    def test_file_not_found_does_not_raise(self) -> None:
        """FileNotFoundError from a missing Run value is swallowed
        gracefully."""
        import src.installer as _mod

        with patch("src.installer._winreg") as mock_reg:
            mock_reg.DeleteValue.side_effect = FileNotFoundError
            _mod._remove_autostart_windows()  # must not raise
