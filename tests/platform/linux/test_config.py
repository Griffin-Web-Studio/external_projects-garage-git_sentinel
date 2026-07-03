from __future__ import annotations

import configparser
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import get_export_path

# ─────────────────────────────────────────────────────────| get_export_path |──


class TestGetExportPathLinux:
    """Tests get_export_path Linux-specific resolution paths (XDG and fallback).

    These tests patch sys.platform to 'linux' to exercise the XDG and
    ~/Desktop fallback branches, which are meaningless on Windows.
    """

    def test_empty_override_falls_through(self, tmp_path: Path) -> None:
        """An empty export_path string does not short-circuit; detection
        continues.

        Args:
            tmp_path (Path): Temporary home directory with no XDG config,
                             ensuring the fallback path is reached.
        """

        cfg = configparser.ConfigParser()
        cfg["paths"] = {"export_path": ""}

        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("sys.platform", "linux"),
        ):
            result = get_export_path(cfg)

        assert result == tmp_path / "Desktop"

    def test_xdg_user_dirs(self, tmp_path: Path) -> None:
        """XDG_DESKTOP_DIR from user-dirs.dirs is parsed and returned.

        Args:
            tmp_path (Path): Temporary home directory containing a populated
                             user-dirs.dirs file.
        """

        cfg = configparser.ConfigParser()
        CONF_DIR = tmp_path / ".config"

        CONF_DIR.mkdir()
        (CONF_DIR / "user-dirs.dirs").write_text(
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
