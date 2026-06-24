from __future__ import annotations

import configparser
from datetime import date, datetime
from pathlib import Path

import pytest

from src.models import (
    BranchIssue,
    BranchIssueReason,
    RemoteCheck,
    RemoteSkipReason,
    RepoResult,
    TagIssue,
)
from src.reports import (
    _fmt_branch_issue,
    _fmt_skip_reason,
    _fmt_stale_entry,
    collect_issue_keys,
    format_report,
    load_previous_issue_keys,
    manage_reports,
)

# ────────────────────────────────────────────────────────────────| Fixtures |──

NOW = datetime(2026, 6, 11, 12, 0, 0)
REPO_PATH = Path("/test/myrepo")


@pytest.fixture
def cfg() -> configparser.ConfigParser:
    """Minimal ConfigParser with the sections used by reports."""
    c = configparser.ConfigParser()
    c["staleness"] = {"stale_threshold_days": "90"}
    c["reports"] = {"report_extension": "log", "desktop_retention_days": "14"}
    return c


def _result(**kwargs: object) -> RepoResult:
    """RepoResult at REPO_PATH with caller-supplied field overrides."""
    r = RepoResult(path=REPO_PATH)
    for k, v in kwargs.items():
        setattr(r, k, v)
    return r


def _make_report(directory: Path, stem: str) -> Path:
    """Write a dummy report .log file and return the path."""
    f = directory / f"{stem}-git-status-report.log"
    f.write_text("content")
    return f


# ───────────────────────────────────────────────────────| _fmt_branch_issue |──


class TestFmtBranchIssue:
    """Unit tests for the private branch-issue line formatter."""

    def test_not_in_origin(self) -> None:
        """Branch absent from origin shows commit count."""
        bi = BranchIssue(
            branch="feat",
            remote="origin",
            reason=BranchIssueReason.NOT_IN_ORIGIN,
            commits=3,
        )
        line = _fmt_branch_issue(bi)
        assert "feat" in line
        assert "not in origin" in line
        assert "3 commit(s)" in line

    def test_ahead_of_origin(self) -> None:
        """Branch ahead of origin shows unpushed commit count."""
        bi = BranchIssue(
            branch="main",
            remote="origin",
            reason=BranchIssueReason.AHEAD_OF_ORIGIN,
            ahead=2,
        )
        line = _fmt_branch_issue(bi)
        assert "main" in line
        assert "origin" in line
        assert "+2 unpushed commit(s)" in line

    def test_ahead_of_remote(self) -> None:
        """Branch ahead of a non-origin remote shows that remote's name."""
        bi = BranchIssue(
            branch="dev",
            remote="upstream",
            reason=BranchIssueReason.AHEAD_OF_REMOTE,
            ahead=5,
        )
        line = _fmt_branch_issue(bi)
        assert "dev" in line
        assert "upstream" in line
        assert "+5 unpushed commit(s)" in line

    def test_not_in_any_remote(self) -> None:
        """Branch absent from all remotes shows commit count."""
        bi = BranchIssue(
            branch="local-only",
            remote=None,
            reason=BranchIssueReason.NOT_IN_ANY_REMOTE,
            commits=1,
        )
        line = _fmt_branch_issue(bi)
        assert "local-only" in line
        assert "not in any remote" in line
        assert "1 commit(s)" in line

    def test_indented_with_four_spaces(self) -> None:
        """Output line is indented with four spaces for report alignment."""
        bi = BranchIssue(
            branch="b",
            remote="origin",
            reason=BranchIssueReason.NOT_IN_ORIGIN,
            commits=1,
        )
        assert _fmt_branch_issue(bi).startswith("    ")


# ────────────────────────────────────────────────────────| _fmt_skip_reason |──


class TestFmtSkipReason:
    """Unit tests for the private skip-reason string formatter."""

    def test_ssh_declined_returns_value_string(self) -> None:
        """SSH_DECLINED maps to its enum value string."""
        rc = RemoteCheck(name="origin", url="git@github.com:u/r.git")
        rc.skip_reason = RemoteSkipReason.SSH_DECLINED
        assert _fmt_skip_reason(rc) == "ssh_declined"

    def test_fetch_failed_with_error_appends_detail(self) -> None:
        """FETCH_FAILED with skip_error includes the error in the output."""
        rc = RemoteCheck(name="origin", url="https://github.com/u/r.git")
        rc.skip_reason = RemoteSkipReason.FETCH_FAILED
        rc.skip_error = "Connection refused"
        assert _fmt_skip_reason(rc) == "fetch_failed: Connection refused"

    def test_fetch_failed_without_error_omits_colon(self) -> None:
        """FETCH_FAILED with empty skip_error does not append a colon."""
        rc = RemoteCheck(name="origin", url="https://github.com/u/r.git")
        rc.skip_reason = RemoteSkipReason.FETCH_FAILED
        assert _fmt_skip_reason(rc) == "fetch_failed"

    def test_none_skip_reason_returns_empty_string(self) -> None:
        """No skip reason (reachable remote) returns an empty string."""
        rc = RemoteCheck(name="origin", url="https://github.com/u/r.git")
        assert _fmt_skip_reason(rc) == ""


# ────────────────────────────────────────────────────────| _fmt_stale_entry |──


class TestFmtStaleEntry:
    """Unit tests for the private stale-entry line formatter."""

    def test_with_last_commit_date_shows_date_and_age(self) -> None:
        """Line includes the last commit date and a days-ago count."""
        r = _result(is_stale=True, last_commit_date=datetime(2026, 1, 1))
        line = _fmt_stale_entry(r)
        assert REPO_PATH.as_posix() in line
        assert "2026-01-01" in line
        assert "day(s) ago" in line

    def test_without_last_commit_date_shows_no_commits(self) -> None:
        """Line includes 'no commits found' when last_commit_date is None."""
        r = _result(is_stale=True, last_commit_date=None)
        line = _fmt_stale_entry(r)
        assert REPO_PATH.as_posix() in line
        assert "no commits found" in line

    def test_indented_with_two_spaces(self) -> None:
        """Output line is indented with two spaces for report alignment."""
        r = _result(is_stale=True, last_commit_date=None)
        assert _fmt_stale_entry(r).startswith("  ")


# ──────────────────────────────────────────────────────| collect_issue_keys |──


class TestCollectIssueKeys:
    """Tests for the canonical issue-key builder used for run comparison."""

    def test_empty_results_returns_empty_set(self) -> None:
        """No repositories produce no keys."""
        assert collect_issue_keys([]) == set()

    def test_no_remote_adds_no_remote_key(self) -> None:
        """A repo with no remote produces a 'no_remote' key."""
        r = _result(has_remote=False)
        keys = collect_issue_keys([r])
        assert f"{r.short_path()}|no_remote" in keys

    def test_uncommitted_file_key(self) -> None:
        """Each uncommitted file produces a distinct 'uncommitted' key."""
        r = _result(has_remote=True, uncommitted=["M  src/foo.py"])
        keys = collect_issue_keys([r])
        assert f"{r.short_path()}|uncommitted|M  src/foo.py" in keys

    def test_untracked_file_key(self) -> None:
        """Each untracked file produces a distinct 'untracked' key."""
        r = _result(has_remote=True, untracked=["notes.txt"])
        keys = collect_issue_keys([r])
        assert f"{r.short_path()}|untracked|notes.txt" in keys

    def test_stash_key(self) -> None:
        """Each stash entry produces a distinct 'stash' key."""
        r = _result(has_remote=True, stashes=["stash@{0}: WIP"])
        keys = collect_issue_keys([r])
        assert f"{r.short_path()}|stash|stash@{{0}}: WIP" in keys

    def test_branch_issue_key_uses_reason_value(self) -> None:
        """Branch issue keys use the enum .value string for stable
        comparison."""
        bi = BranchIssue(
            branch="feat",
            remote="origin",
            reason=BranchIssueReason.NOT_IN_ORIGIN,
            commits=1,
        )
        r = _result(has_remote=True, branch_issues=[bi])
        keys = collect_issue_keys([r])
        assert f"{r.short_path()}|branch|feat|origin|not_in_origin" in keys

    def test_branch_issue_none_remote_written_as_none_string(self) -> None:
        """None remote in a branch issue is serialised as the string 'none'."""
        bi = BranchIssue(
            branch="local",
            remote=None,
            reason=BranchIssueReason.NOT_IN_ANY_REMOTE,
            commits=1,
        )
        r = _result(has_remote=True, branch_issues=[bi])
        keys = collect_issue_keys([r])
        assert f"{r.short_path()}|branch|local|none|not_in_any_remote" in keys

    def test_tag_issue_key(self) -> None:
        """Each unpushed tag produces a distinct 'tag' key."""
        ti = TagIssue(tag="v1.0", remote="origin")
        r = _result(has_remote=True, tag_issues=[ti])
        keys = collect_issue_keys([r])
        assert f"{r.short_path()}|tag|v1.0|origin" in keys

    def test_multiple_repos_produce_independent_keys(self) -> None:
        """Keys from different repos do not collide."""
        r1 = RepoResult(path=Path("/test/repo1"))
        r1.has_remote = False
        r2 = RepoResult(path=Path("/test/repo2"))
        r2.has_remote = False
        keys = collect_issue_keys([r1, r2])
        assert f"{r1.short_path()}|no_remote" in keys
        assert f"{r2.short_path()}|no_remote" in keys


# ────────────────────────────────────────────────| load_previous_issue_keys |──


class TestLoadPreviousIssueKeys:
    """Tests for loading issue keys from prior report sidecar files."""

    def test_no_files_returns_empty_set(self, tmp_path: Path) -> None:
        """Returns an empty set when no .issues files exist."""
        assert load_previous_issue_keys(tmp_path / "reports") == set()

    def test_reads_issues_file(self, tmp_path: Path) -> None:
        """Reads and splits the most recent .issues file."""
        export_path = tmp_path / "reports"
        export_path.mkdir()
        (export_path / "20260101-00-00-00-git-status-report.issues").write_text(
            "key1\nkey2"
        )
        assert load_previous_issue_keys(export_path) == {"key1", "key2"}

    def test_picks_latest_by_filename(self, tmp_path: Path) -> None:
        """When multiple .issues files exist, the lexicographically latest is used."""
        export_path = tmp_path / "reports"
        export_path.mkdir()
        (export_path / "20260610-00-00-00-git-status-report.issues").write_text(
            "latest_key"
        )
        (export_path / "20260101-00-00-00-git-status-report.issues").write_text(
            "old_key"
        )
        result = load_previous_issue_keys(export_path)
        assert "latest_key" in result
        assert "old_key" not in result

    def test_oserror_on_read_returns_empty_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unreadable .issues file is silently treated as no prior keys."""
        export_path = tmp_path / "reports"
        export_path.mkdir()
        (export_path / "20260101-00-00-00-git-status-report.issues").write_text(
            "k"
        )

        def _boom(self: Path, **kwargs: object) -> str:
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "read_text", _boom)
        assert load_previous_issue_keys(export_path) == set()


# ───────────────────────────────────────────────────────────| format_report |──


class TestFormatReport:
    """Integration tests for the full report renderer."""

    def test_header_section_contains_metadata(
        self, cfg: configparser.ConfigParser
    ) -> None:
        """[report] section includes date, time, and repo counts."""
        output = format_report([], set(), set(), cfg, NOW)
        assert "[report]" in output
        assert "date              = 2026-06-11" in output
        assert "time              = 12:00:00" in output
        assert "total_repos       = 0" in output

    def test_repo_counts_in_header(
        self, cfg: configparser.ConfigParser
    ) -> None:
        """Header counts reflect clean vs issue repos correctly."""
        clean = _result(has_remote=True)
        issue = _result(has_remote=False)
        output = format_report([clean, issue], set(), set(), cfg, NOW)
        assert "total_repos       = 2" in output
        assert "repos_with_issues = 1" in output
        assert "repos_passed      = 1" in output

    def test_persistent_issues_section(
        self, cfg: configparser.ConfigParser
    ) -> None:
        """Keys present in both prev and curr appear under
        [persistent_issues]."""
        prev = {"repo|no_remote"}
        curr = {"repo|no_remote", "repo|uncommitted|file.py"}
        output = format_report([], prev, curr, cfg, NOW)
        assert "[persistent_issues]" in output
        assert "repo|no_remote" in output

    def test_new_issues_section(self, cfg: configparser.ConfigParser) -> None:
        """Keys in curr but not prev appear under [new_issues]."""
        output = format_report([], set(), {"repo|no_remote"}, cfg, NOW)
        assert "[new_issues]" in output
        assert "repo|no_remote" in output

    def test_no_remote_section(self, cfg: configparser.ConfigParser) -> None:
        """[no_remote] section lists repos without a configured remote."""
        r = _result(has_remote=False)
        output = format_report([r], set(), set(), cfg, NOW)
        assert "[no_remote]" in output
        assert REPO_PATH.as_posix() in output

    def test_uncommitted_section(self, cfg: configparser.ConfigParser) -> None:
        """[uncommitted] section lists repos and their modified files."""
        r = _result(has_remote=True, uncommitted=["M  file.py"])
        output = format_report([r], set(), set(), cfg, NOW)
        assert "[uncommitted]" in output
        assert "M  file.py" in output

    def test_untracked_section(self, cfg: configparser.ConfigParser) -> None:
        """[untracked] section lists repos and their untracked files."""
        r = _result(has_remote=True, untracked=["todo.txt"])
        output = format_report([r], set(), set(), cfg, NOW)
        assert "[untracked]" in output
        assert "todo.txt" in output

    def test_stashes_section(self, cfg: configparser.ConfigParser) -> None:
        """[stashes] section lists repos and their stash entries."""
        r = _result(has_remote=True, stashes=["stash@{0}: WIP on main"])
        output = format_report([r], set(), set(), cfg, NOW)
        assert "[stashes]" in output
        assert "stash@{0}: WIP on main" in output

    def test_unpushed_branches_section(
        self, cfg: configparser.ConfigParser
    ) -> None:
        """[unpushed_branches] section lists repos with unpushed branch work."""
        bi = BranchIssue(
            branch="feat",
            remote="origin",
            reason=BranchIssueReason.NOT_IN_ORIGIN,
            commits=2,
        )
        r = _result(has_remote=True, branch_issues=[bi])
        output = format_report([r], set(), set(), cfg, NOW)
        assert "[unpushed_branches]" in output
        assert "feat" in output
        assert "not in origin" in output

    def test_unpushed_tags_section(
        self, cfg: configparser.ConfigParser
    ) -> None:
        """[unpushed_tags] section lists repos with local-only tags."""
        ti = TagIssue(tag="v2.0", remote="origin")
        r = _result(has_remote=True, tag_issues=[ti])
        output = format_report([r], set(), set(), cfg, NOW)
        assert "[unpushed_tags]" in output
        assert "v2.0" in output

    def test_remote_checks_skipped_section(
        self, cfg: configparser.ConfigParser
    ) -> None:
        """[remote_checks_skipped] section appears when a remote was skipped."""
        rc = RemoteCheck(name="origin", url="git@github.com:u/r.git")
        rc.skip_reason = RemoteSkipReason.SSH_DECLINED
        r = _result(has_remote=True, remote_checks=[rc])
        output = format_report([r], set(), set(), cfg, NOW)
        assert "[remote_checks_skipped]" in output
        assert "origin" in output
        assert "ssh_declined" in output

    def test_stale_section(self, cfg: configparser.ConfigParser) -> None:
        """[stale] section lists repos and their last commit date."""
        r = _result(
            has_remote=True,
            is_stale=True,
            last_commit_date=datetime(2025, 1, 1),
        )
        output = format_report([r], set(), set(), cfg, NOW)
        assert "[stale]" in output
        assert REPO_PATH.as_posix() in output
        assert "2025-01-01" in output
        assert "90 day(s)" in output

    def test_passed_section(self, cfg: configparser.ConfigParser) -> None:
        """[passed] section lists repos with no issues detected."""
        r = _result(has_remote=True)
        output = format_report([r], set(), set(), cfg, NOW)
        assert "[passed]" in output
        assert REPO_PATH.as_posix() in output

    def test_empty_sections_omitted(
        self, cfg: configparser.ConfigParser
    ) -> None:
        """Sections with no data do not appear in the output."""
        r = _result(has_remote=True)
        output = format_report([r], set(), set(), cfg, NOW)
        assert "[uncommitted]" not in output
        assert "[untracked]" not in output
        assert "[unpushed_branches]" not in output
        assert "[stale]" not in output


# ──────────────────────────────────────────────────────────| manage_reports |──

_OLD_DATE = "20200101-00-00-00"  # guaranteed > any reasonable retention window


class TestManageReports:
    """Tests for age-based report cleanup in a single export directory."""

    def test_export_path_created_if_missing(self, tmp_path: Path) -> None:
        """manage_reports creates export_path if absent."""
        export_path = tmp_path / "reports" / "nested"
        manage_reports(export_path, retention_days=14)
        assert export_path.is_dir()

    def test_recent_report_kept(self, tmp_path: Path) -> None:
        """A report dated today is not deleted."""
        today = date.today().strftime("%Y%m%d")
        _make_report(tmp_path, f"{today}-00-00-00")
        manage_reports(tmp_path, retention_days=14)
        assert len(list(tmp_path.glob("*.log"))) == 1

    def test_old_report_deleted(self, tmp_path: Path) -> None:
        """A report dated years ago is deleted."""
        _make_report(tmp_path, _OLD_DATE)
        manage_reports(tmp_path, retention_days=14)
        assert not list(tmp_path.glob("*.log"))

    def test_sidecar_deleted_with_log(self, tmp_path: Path) -> None:
        """The .issues sidecar is deleted alongside its .log report."""
        report = _make_report(tmp_path, _OLD_DATE)
        sidecar = report.with_suffix(".issues")
        sidecar.write_text("key1")
        manage_reports(tmp_path, retention_days=14)
        assert not report.exists()
        assert not sidecar.exists()

    def test_unexpected_filename_skipped(self, tmp_path: Path) -> None:
        """Files whose names don't start with a parseable date are left alone."""
        bad = tmp_path / "not-a-date-git-status-report.log"
        bad.write_text("content")
        manage_reports(tmp_path, retention_days=0)
        assert bad.exists()
