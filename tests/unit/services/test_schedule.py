from __future__ import annotations

import configparser
from datetime import date
from pathlib import Path

import pytest

from src.services.schedule import should_run_today

# ────────────────────────────────────────────────────────| should_run_today |──


def _cfg(once_per_day: bool = True) -> configparser.ConfigParser:
    """Build a minimal ConfigParser for schedule tests.

    Args:
        once_per_day (bool, optional): Whether once_per_day is enabled in the schedule section. Defaults to True.

    Returns:
        configparser.ConfigParser: Config with only the schedule section populated.
    """
    cfg = configparser.ConfigParser()
    cfg["schedule"] = {"once_per_day": "true" if once_per_day else "false"}

    return cfg


class TestShouldRunToday:
    """Tests that should_run_today correctly gates execution to once per day."""

    def test_force_bypasses_lock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The --force flag causes should_run_today to return True regardless of the lock file.

        Args:
            tmp_path (Path): Isolated temporary directory used as STATE_DIR and parent of the lock file.
            monkeypatch (pytest.MonkeyPatch): Redirects STATE_DIR and LOCK_FILE to tmp_path.
        """
        monkeypatch.setattr("src.services.schedule.STATE_DIR", tmp_path)
        monkeypatch.setattr(
            "src.services.schedule.LOCK_FILE", tmp_path / "lock"
        )

        assert should_run_today(_cfg(), force=True) is True

    def test_once_per_day_false_always_runs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """once_per_day=false in config causes the function to always return True.

        Args:
            tmp_path (Path): Isolated temporary directory used as STATE_DIR and parent of the lock file.
            monkeypatch (pytest.MonkeyPatch): Redirects STATE_DIR and LOCK_FILE to tmp_path.
        """
        monkeypatch.setattr("src.services.schedule.STATE_DIR", tmp_path)
        monkeypatch.setattr(
            "src.services.schedule.LOCK_FILE", tmp_path / "lock"
        )

        assert should_run_today(_cfg(once_per_day=False)) is True

    def test_first_run_returns_true(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """First run of the day (no lock file present) returns True.

        Args:
            tmp_path (Path): Isolated temporary directory used as STATE_DIR; no lock file exists yet.
            monkeypatch (pytest.MonkeyPatch): Redirects STATE_DIR and LOCK_FILE to tmp_path.
        """
        lock = tmp_path / "lock"
        monkeypatch.setattr("src.services.schedule.STATE_DIR", tmp_path)
        monkeypatch.setattr("src.services.schedule.LOCK_FILE", lock)

        assert should_run_today(_cfg()) is True

    def test_first_run_writes_lock_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """First run writes today's ISO date to the lock file.

        Args:
            tmp_path (Path): Isolated temporary directory; lock is expected to appear here after the call.
            monkeypatch (pytest.MonkeyPatch): Redirects STATE_DIR and LOCK_FILE to tmp_path.
        """
        lock = tmp_path / "lock"
        monkeypatch.setattr("src.services.schedule.STATE_DIR", tmp_path)
        monkeypatch.setattr("src.services.schedule.LOCK_FILE", lock)

        should_run_today(_cfg())

        assert lock.read_text().strip() == date.today().isoformat()

    def test_second_run_same_day_skips(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A second run on the same day finds a matching lock and returns False.

        Args:
            tmp_path (Path): Isolated temporary directory containing a lock file pre-written with today's date.
            monkeypatch (pytest.MonkeyPatch): Redirects STATE_DIR and LOCK_FILE to tmp_path.
        """
        lock = tmp_path / "lock"
        lock.write_text(date.today().isoformat())
        monkeypatch.setattr("src.services.schedule.STATE_DIR", tmp_path)
        monkeypatch.setattr("src.services.schedule.LOCK_FILE", lock)

        assert should_run_today(_cfg()) is False

    def test_stale_lock_from_previous_day_runs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A lock file containing a past date allows the run.

        Args:
            tmp_path (Path): Isolated temporary directory containing a lock file pre-written with an old date.
            monkeypatch (pytest.MonkeyPatch): Redirects STATE_DIR and LOCK_FILE to tmp_path.
        """
        lock = tmp_path / "lock"
        lock.write_text("2000-01-01")
        monkeypatch.setattr("src.services.schedule.STATE_DIR", tmp_path)
        monkeypatch.setattr("src.services.schedule.LOCK_FILE", lock)

        assert should_run_today(_cfg()) is True

    def test_stale_lock_updated_to_today(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After running with a stale lock, the lock is updated to today's date.

        Args:
            tmp_path (Path): Isolated temporary directory containing a lock file pre-written with an old date.
            monkeypatch (pytest.MonkeyPatch): Redirects STATE_DIR and LOCK_FILE to tmp_path.
        """
        lock = tmp_path / "lock"
        lock.write_text("2000-01-01")
        monkeypatch.setattr("src.services.schedule.STATE_DIR", tmp_path)
        monkeypatch.setattr("src.services.schedule.LOCK_FILE", lock)

        should_run_today(_cfg())

        assert lock.read_text().strip() == date.today().isoformat()
