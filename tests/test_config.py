from __future__ import annotations

import configparser
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import get_export_path, load_config

windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="requires Windows"
)

# ─────────────────────────────────────────────────────────────| load_config |──


class TestLoadConfig:
    """Tests load_config returns a ConfigParser with correct defaults and user
    overrides."""

    def test_defaults_applied_without_config_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All expected default values are present when no config file exists.

        Args:
            tmp_path (Path): Temporary directory used as parent for a missing
                             config path.
            monkeypatch (pytest.MonkeyPatch): Redirects CONFIG_FILE to the
                                              missing path in tmp_path.
        """
        monkeypatch.setattr(
            "src.config.CONFIG_FILE", tmp_path / "non-existent.ini"
        )
        cfg = load_config()

        assert cfg.get("paths", "git_root") == "git"
        assert cfg.get("paths", "reports_archive") == "git/reports"
        assert cfg.get("schedule", "once_per_day") == "true"
        assert cfg.get("ssh", "control_persist_seconds") == "300"

    def test_user_values_override_defaults(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A value set in the user config file takes precedence over the
        built-in default.

        Args:
            tmp_path (Path): Temporary directory containing a settings.ini with
                             a custom git_root.
            monkeypatch (pytest.MonkeyPatch): Redirects CONFIG_FILE to the
                                              settings.ini in tmp_path.
        """
        config_file = tmp_path / "settings.ini"
        config_file.write_text("[paths]\ngit_root = /custom/git\n")

        monkeypatch.setattr("src.config.CONFIG_FILE", config_file)

        cfg = load_config()

        assert cfg.get("paths", "git_root") == "/custom/git"

    def test_unoverridden_defaults_survive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Keys not present in the user config file retain their default values.

        Args:
            tmp_path (Path): Temporary directory containing a settings.ini that
                             overrides only git_root.
            monkeypatch (pytest.MonkeyPatch): Redirects CONFIG_FILE to the
                                              settings.ini in tmp_path.
        """
        cfg = load_config()
        config_file = tmp_path / "settings.ini"
        config_file.write_text("[paths]\ngit_root = /custom/git\n")

        monkeypatch.setattr("src.config.CONFIG_FILE", config_file)

        # default for a different key still present
        assert cfg.get("paths", "reports_archive") == "git/reports"

    def test_returns_config_parser(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The return type is a ConfigParser instance, not a plain dict or
        namespace.

        Args:
            tmp_path (Path): Parent for a config path that does not exist.
            monkeypatch (pytest.MonkeyPatch): Redirects CONFIG_FILE into
                                              tmp_path.
        """
        cfg = load_config()

        monkeypatch.setattr(
            "src.config.CONFIG_FILE", tmp_path / "non-existent.ini"
        )

        assert isinstance(cfg, configparser.ConfigParser)


# ─────────────────────────────────────────────────────────| get_export_path |──


class TestGetExportPath:
    """Tests that get_export_path resolves the report export directory
    correctly."""

    def test_export_path_used_when_set(self) -> None:
        """An export_path in config overrides XDG/fallback detection."""
        cfg = configparser.ConfigParser()
        cfg["paths"] = {"export_path": "MyReports"}
        result = get_export_path(cfg)

        assert result == Path.home() / "MyReports"

    def test_empty_override_falls_through(self, tmp_path: Path) -> None:
        """An empty export_path string does not short-circuit; detection
        continues.

        Args:
            tmp_path (Path): Temporary home directory with no XDG config,
                             ensuring the fallback path is reached.
        """
        cfg = configparser.ConfigParser()
        cfg["paths"] = {"export_path": ""}

        # empty override must not be returned; function should fall through to
        # XDG/fallback
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("sys.platform", "linux"),
        ):
            result = get_export_path(cfg)

        # no XDG file under tmp_path, so falls back to Desktop
        assert result == tmp_path / "Desktop"

    def test_xdg_user_dirs(self, tmp_path: Path) -> None:
        """XDG_DESKTOP_DIR from user-dirs.dirs is parsed and returned.

        Args:
            tmp_path (Path): Temporary home directory containing a populated
                             user-dirs.dirs file.
        """
        cfg = configparser.ConfigParser()
        config_dir = tmp_path / ".config"
        config_dir.mkdir()
        (config_dir / "user-dirs.dirs").write_text(
            'XDG_DESKTOP_DIR="$HOME/XDGDesktop"\n'
        )

        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("sys.platform", "linux"),
        ):
            result = get_export_path(cfg)

        assert result == tmp_path / "XDGDesktop"

    def test_fallback_to_desktop_dir(self, tmp_path: Path) -> None:
        """Falls back to ~/Desktop when no override or XDG config is present.

        Args:
            tmp_path (Path): Temporary home directory with no XDG config.
        """
        cfg = configparser.ConfigParser()

        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("sys.platform", "linux"),
        ):
            result = get_export_path(cfg)

        assert result == tmp_path / "Desktop"


# ─────────────────────────────────────────────────────────| Windows (win32) |──


@windows_only
class TestGetExportPathWindows:
    """Tests _get_export_path_windows reads the default export path from the
    Windows registry (Shell Folders → Desktop).

    These tests are skipped on Linux (winreg is unavailable) and run only
    on the Windows CI runner.
    """

    def test_reads_desktop_path_from_shell_folders(self) -> None:
        """Returns the path stored in the Shell Folders registry key."""
        import src.config as _mod

        desktop = r"C:\Users\Alice\Desktop"
        with patch("src.config._winreg") as mock_reg:
            mock_reg.OpenKey.return_value = MagicMock()
            mock_reg.QueryValueEx.return_value = (desktop, 1)
            result = _mod._get_export_path_windows()

        assert result == Path(desktop)

    def test_oserror_falls_back_to_home_desktop(self) -> None:
        """OSError from a missing or inaccessible key falls back to
        ~/Desktop."""
        import src.config as _mod

        with patch("src.config._winreg") as mock_reg:
            mock_reg.OpenKey.side_effect = OSError
            result = _mod._get_export_path_windows()

        assert result == Path.home() / "Desktop"
