from __future__ import annotations

import configparser
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import get_desktop_path, load_config

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


# ────────────────────────────────────────────────────────| get_desktop_path |──


class TestGetDesktopPath:
    """Tests that get_desktop_path resolves the user's desktop directory
    correctly."""

    def test_desktop_override_used_when_set(self) -> None:
        """A desktop_override in config overrides XDG/fallback detection."""
        cfg = configparser.ConfigParser()
        cfg["paths"] = {"desktop_override": "MyDesktop"}
        result = get_desktop_path(cfg)

        assert result == Path.home() / "MyDesktop"

    def test_empty_override_falls_through(self, tmp_path: Path) -> None:
        """An empty desktop_override string does not short-circuit; detection
        continues.

        Args:
            tmp_path (Path): Temporary home directory with no XDG config,
                             ensuring the fallback path is reached.
        """
        cfg = configparser.ConfigParser()
        cfg["paths"] = {"desktop_override": ""}

        # empty override must not be returned; function should fall through to
        # XDG/fallback
        with patch.object(Path, "home", return_value=tmp_path):
            result = get_desktop_path(cfg)

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

        with patch.object(Path, "home", return_value=tmp_path):
            result = get_desktop_path(cfg)

        assert result == tmp_path / "XDGDesktop"

    def test_fallback_to_desktop_dir(self, tmp_path: Path) -> None:
        """Falls back to ~/Desktop when no override or XDG config is present.

        Args:
            tmp_path (Path): Temporary home directory with no XDG config.
        """
        cfg = configparser.ConfigParser()

        with patch.object(Path, "home", return_value=tmp_path):
            result = get_desktop_path(cfg)

        assert result == tmp_path / "Desktop"
