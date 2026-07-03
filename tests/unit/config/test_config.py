from __future__ import annotations

import configparser
from pathlib import Path

import pytest

from src.config import get_export_path, load_config

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
            monkeypatch (pytest.MonkeyPatch): Redirects CONF_FILE to the
                                              missing path in tmp_path.
        """

        monkeypatch.setattr(
            "src.config.CONF_FILE", tmp_path / "non-existent.ini"
        )
        cfg = load_config()

        assert cfg.get("paths", "git_root") == "git"
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
            monkeypatch (pytest.MonkeyPatch): Redirects CONF_FILE to the
                                              settings.ini in tmp_path.
        """

        CONF_FILE = tmp_path / "settings.ini"
        CONF_FILE.write_text("[paths]\ngit_root = /custom/git\n")

        monkeypatch.setattr("src.config.CONF_FILE", CONF_FILE)

        cfg = load_config()

        assert cfg.get("paths", "git_root") == "/custom/git"

    def test_unoverridden_defaults_survive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Keys not present in the user config file retain their default values.

        Args:
            tmp_path (Path): Temporary directory containing a settings.ini that
                             overrides only git_root.
            monkeypatch (pytest.MonkeyPatch): Redirects CONF_FILE to the
                                              settings.ini in tmp_path.
        """

        CONF_FILE = tmp_path / "settings.ini"

        CONF_FILE.write_text("[paths]\ngit_root = /custom/git\n")
        monkeypatch.setattr("src.config.CONF_FILE", CONF_FILE)
        cfg = load_config()

        assert cfg.get("reports", "retention_days") == "14"

    def test_returns_config_parser(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The return type is a ConfigParser instance, not a plain dict or
        namespace.

        Args:
            tmp_path (Path): Parent for a config path that does not exist.
            monkeypatch (pytest.MonkeyPatch): Redirects CONF_FILE into
                                              tmp_path.
        """

        monkeypatch.setattr(
            "src.config.CONF_FILE", tmp_path / "non-existent.ini"
        )

        cfg = load_config()

        assert isinstance(cfg, configparser.ConfigParser)


# ─────────────────────────────────────────────────────────| get_export_path |──


class TestGetExportPath:
    """Tests that get_export_path resolves the report export directory
    correctly for shared (non-platform-specific) cases."""

    def test_export_path_used_when_set(self) -> None:
        """An export_path in config overrides XDG/fallback detection."""

        cfg = configparser.ConfigParser()
        cfg["paths"] = {"export_path": "MyReports"}
        result = get_export_path(cfg)

        assert result == Path.home() / "MyReports"

    def test_deprecated_desktop_override_still_works(self) -> None:
        """A legacy desktop_override key is honoured but emits
        DeprecationWarning."""

        cfg = configparser.ConfigParser()
        cfg["paths"] = {"desktop_override": "OldDesktop"}

        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = get_export_path(cfg)

        assert result == Path.home() / "OldDesktop"
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)
