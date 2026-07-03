from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src import APP_NAME
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
def desktop_template(tmp_path: Path) -> Path:
    """A minimal .desktop template containing {exec} and {extra}
    placeholders.

    Args:
        tmp_path (Path): Pytest fixture providing a temporary directory.

    Returns:
        Path: Path to the fake .desktop template file.
    """

    t = tmp_path / f"{APP_NAME}.desktop"

    t.write_text("[Desktop Entry]\nExec={exec}\n{extra}\n")

    return t


@pytest.fixture
def paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Redirect the shared installer module-level path constants into
    tmp_path.

    BIN_DIR/BINARY_DST are also patched on the current platform's
    src.platform.{linux,windows}.installer module, since that's where the
    actual install/remove steps for the binary now live - the two copies
    must point at the same tmp_path for the shared tests to be consistent.

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
    CONF_DIR = tmp_path / "config"
    state_dir = tmp_path / "state"

    monkeypatch.setattr("src.installer.BIN_DIR", bin_dir)
    monkeypatch.setattr("src.installer.BINARY_DST", binary_dst)
    monkeypatch.setattr("src.installer.CONF_DIR", CONF_DIR)
    monkeypatch.setattr("src.installer.STATE_DIR", state_dir)

    if sys.platform == "win32":
        monkeypatch.setattr("src.platform.windows.installer.BIN_DIR", bin_dir)
        monkeypatch.setattr(
            "src.platform.windows.installer.BINARY_DST", binary_dst
        )
    else:
        monkeypatch.setattr("src.platform.linux.installer.BIN_DIR", bin_dir)
        monkeypatch.setattr(
            "src.platform.linux.installer.BINARY_DST", binary_dst
        )

    return {
        "bin_dir": bin_dir,
        "binary_dst": binary_dst,
        "CONF_DIR": CONF_DIR,
        "state_dir": state_dir,
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
        other = tmp_path / "other"
        binary.touch()
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
        """settings.example.ini is always written to CONF_DIR.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        _install_config()

        assert (paths["CONF_DIR"] / "settings.example.ini").exists()

    def test_example_file_contains_expected_sections(
        self, paths: dict[str, Path]
    ) -> None:
        """The generated settings.example.ini contains all standard sections.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        _install_config()

        content = (paths["CONF_DIR"] / "settings.example.ini").read_text()

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

        assert (paths["CONF_DIR"] / "settings.ini").exists()

    def test_leaves_existing_config_intact(
        self, paths: dict[str, Path]
    ) -> None:
        """An existing settings.ini is not overwritten on reinstall.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        config = paths["CONF_DIR"] / "settings.ini"

        paths["CONF_DIR"].mkdir(parents=True, exist_ok=True)
        config.write_text("[paths]\ngit_root = custom\n")

        _install_config()

        assert config.read_text() == "[paths]\ngit_root = custom\n"


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

        paths["CONF_DIR"].mkdir(parents=True, exist_ok=True)
        _remove_config()

        assert not paths["CONF_DIR"].exists()

    def test_noop_when_config_missing(self, paths: dict[str, Path]) -> None:
        """No error is raised when the config directory is already absent.

        Args:
            paths (dict[str, Path]): Fixture redirecting all installer paths to
                                     tmp_path.
        """

        _remove_config()  # must not raise


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
