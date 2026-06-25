from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.migrations import _move_legacy_reports, apply_migrations, chain

# ───────────────────────────────────────────────────────────────────| chain |──


class TestMigrationsChain:
    """Tests the module-level chain discovers the expected migrations."""

    def test_chain_has_v0001_step(self) -> None:
        """The module-level chain contains the step that goes from v0 to v1."""
        assert 0 in chain._steps
        assert chain._steps[0].to_version == 1


# ────────────────────────────────────────────────────| _move_legacy_reports |──

# Report filenames that the function recognises
_LOG = "20240101-12-00-00-git-status-report.log"
_ISSUES = "20240101-12-00-00-git-status-report.issues"
_OTHER = "unrelated.txt"


class TestMoveLegacyReports:
    """Tests _move_legacy_reports moves .log/.issues files and nothing else."""

    def test_moves_log_file(self, tmp_path: Path) -> None:
        """A .log report file is moved from src to dst.

        Args:
            tmp_path (Path): Temporary directory for src and dst.
        """
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / _LOG).write_text("report")

        _move_legacy_reports(src, dst)

        assert (dst / _LOG).exists()
        assert not (src / _LOG).exists()

    def test_moves_issues_file(self, tmp_path: Path) -> None:
        """.issues sidecar files are moved alongside .log files.

        Args:
            tmp_path (Path): Temporary directory for src and dst.
        """
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / _ISSUES).write_text("keys")

        _move_legacy_reports(src, dst)

        assert (dst / _ISSUES).exists()
        assert not (src / _ISSUES).exists()

    def test_creates_dst_when_absent(self, tmp_path: Path) -> None:
        """dst is created automatically when it does not yet exist.

        Args:
            tmp_path (Path): Temporary directory for src.
        """
        src = tmp_path / "src"
        dst = tmp_path / "nested" / "dst"
        src.mkdir()
        (src / _LOG).write_text("report")

        _move_legacy_reports(src, dst)

        assert dst.exists()
        assert (dst / _LOG).exists()

    def test_skips_file_already_in_dst(self, tmp_path: Path) -> None:
        """An existing file at dst is not overwritten.

        Args:
            tmp_path (Path): Temporary directory for src and dst.
        """
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / _LOG).write_text("new")
        (dst / _LOG).write_text("original")

        _move_legacy_reports(src, dst)

        assert (dst / _LOG).read_text() == "original"

    def test_noop_when_src_equals_dst(self, tmp_path: Path) -> None:
        """No files are touched when src and dst are the same path.

        Args:
            tmp_path (Path): Temporary directory used as both src and dst.
        """
        (tmp_path / _LOG).write_text("report")

        _move_legacy_reports(tmp_path, tmp_path)

        assert (tmp_path / _LOG).exists()

    def test_noop_when_src_absent(self, tmp_path: Path) -> None:
        """Nothing happens when src does not exist.

        Args:
            tmp_path (Path): Temporary directory used as dst.
        """
        src = tmp_path / "nonexistent"
        dst = tmp_path / "dst"

        _move_legacy_reports(src, dst)

        assert not dst.exists()

    def test_does_not_move_non_report_files(self, tmp_path: Path) -> None:
        """Files that do not match the report glob patterns are left in src.

        Args:
            tmp_path (Path): Temporary directory for src and dst.
        """
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / _OTHER).write_text("unrelated")

        _move_legacy_reports(src, dst)

        assert (src / _OTHER).exists()
        assert not (dst / _OTHER).exists()


# ────────────────────────────────────────────────────────| apply_migrations |──

# A v0.1.0-style config: reports_archive set, no desktop_override, no version.
_V010_INI = """\
[paths]
git_root = git
reports_archive = git/reports

[reports]
desktop_retention_days = 14
"""


class TestApplyMigrations:
    """Tests apply_migrations moves desktop reports to export_path after
    upgrade."""

    def _setup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[Path, Path]:
        """Write a v0.1.0 config and wire all path patches.

        Returns:
            tuple[Path, Path]: (old_desktop, new_export_path) directories.
        """
        config_file = tmp_path / "settings.ini"
        config_file.write_text(_V010_INI, encoding="utf-8")
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Point both module namespaces at the temp config / dir.
        monkeypatch.setattr("src.migrations.CONFIG_FILE", config_file)
        monkeypatch.setattr("src.migrations.CONFIG_DIR", config_dir)
        monkeypatch.setattr("src.config.CONFIG_FILE", config_file)

        # Stub the example-config writer to avoid running the full installer.
        monkeypatch.setattr(
            "src.installer._render_example_config", lambda: "# example"
        )

        old_desktop = tmp_path / "Desktop"
        new_export = tmp_path / "git" / "reports"
        return old_desktop, new_export

    def test_moves_desktop_reports_to_export_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Report files on the desktop are relocated to export_path after
        migration.

        Args:
            tmp_path (Path): Temporary home directory used for all paths.
            monkeypatch (pytest.MonkeyPatch): Patches CONFIG_FILE, home,
                platform.
        """
        old_desktop, new_export = self._setup(tmp_path, monkeypatch)

        old_desktop.mkdir(parents=True)
        (old_desktop / _LOG).write_text("report")
        (old_desktop / _ISSUES).write_text("keys")

        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("sys.platform", "linux"),
        ):
            result = apply_migrations()

        assert result is None
        assert (new_export / _LOG).exists()
        assert (new_export / _ISSUES).exists()
        assert not (old_desktop / _LOG).exists()
        assert not (old_desktop / _ISSUES).exists()

    def test_returns_none_on_success_with_no_reports(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """apply_migrations succeeds and returns None when there are no files to
        move.

        Args:
            tmp_path (Path): Temporary home directory.
            monkeypatch (pytest.MonkeyPatch): Patches CONFIG_FILE, home,
                platform.
        """
        self._setup(tmp_path, monkeypatch)

        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("sys.platform", "linux"),
        ):
            result = apply_migrations()

        assert result is None
