from __future__ import annotations

import threading
from pathlib import Path

import pytest

from src.models import (
    BranchIssue,
    BranchIssueReason,
    GateHTTP,
    GateSSH,
    MsgFinish,
    MsgLog,
    MsgProgress,
    MsgStatus,
    RemoteCheck,
    RemoteSkipReason,
    RepoResult,
    TagIssue,
    TagIssueReason,
)

# ───────────────────────────────────────────────────────────────────| Enums |──


class TestEnums:
    """Enum string values are stable contracts; changes would break serialised
    data."""

    def test_branch_issue_reason_values(self) -> None:
        """All BranchIssueReason members have their expected serialisation
        values."""
        assert BranchIssueReason.NOT_IN_ORIGIN.value == "not_in_origin"
        assert BranchIssueReason.AHEAD_OF_ORIGIN.value == "ahead_of_origin"
        assert BranchIssueReason.NOT_IN_ANY_REMOTE.value == "not_in_any_remote"
        assert BranchIssueReason.AHEAD_OF_REMOTE.value == "ahead_of_remote"

    def test_tag_issue_reason_values(self) -> None:
        """TagIssueReason.NOT_IN_REMOTE has the expected serialisation value."""
        assert TagIssueReason.NOT_IN_REMOTE.value == "not_in_remote"

    def test_remote_skip_reason_values(self) -> None:
        """All RemoteSkipReason members have their expected serialisation
        values."""
        assert RemoteSkipReason.SSH_DECLINED.value == "ssh_declined"
        assert RemoteSkipReason.FETCH_FAILED.value == "fetch_failed"


# ────────────────────────────────────────────────────────────| Data classes |──


class TestRemoteCheck:
    """Tests RemoteCheck dataclass defaults and field construction."""

    def test_defaults(self) -> None:
        """reachable defaults to False, skip_reason to None, skip_error to empty
        string."""
        rc = RemoteCheck(name="origin", url="git@github.com:user/repo.git")

        assert rc.reachable is False
        assert rc.skip_reason is None
        assert rc.skip_error == ""

    def test_skip_reason_set(self) -> None:
        """skip_reason accepts a RemoteSkipReason enum member."""
        rc = RemoteCheck(
            name="origin",
            url="git@github.com:user/repo.git",
            skip_reason=RemoteSkipReason.SSH_DECLINED,
        )

        assert rc.skip_reason is RemoteSkipReason.SSH_DECLINED


class TestBranchIssue:
    """Tests BranchIssue dataclass defaults and optional fields."""

    def test_defaults(self) -> None:
        """ahead and commits default to zero when not provided."""
        bi = BranchIssue(
            branch="main",
            remote="origin",
            reason=BranchIssueReason.AHEAD_OF_ORIGIN,
        )

        assert bi.ahead == 0
        assert bi.commits == 0

    def test_no_remote(self) -> None:
        """remote can be None for branches with no configured remote."""
        bi = BranchIssue(
            branch="feature",
            remote=None,
            reason=BranchIssueReason.NOT_IN_ANY_REMOTE,
        )

        assert bi.remote is None


class TestTagIssue:
    """Tests TagIssue dataclass defaults."""

    def test_default_reason(self) -> None:
        """reason defaults to NOT_IN_REMOTE when omitted."""
        ti = TagIssue(tag="v1.0.0", remote="origin")

        assert ti.reason is TagIssueReason.NOT_IN_REMOTE


# ──────────────────────────────────────────────────────────────| RepoResult |──


class TestRepoResult:
    """Tests RepoResult issue detection and path display helpers."""

    def test_has_issues_no_remote(self) -> None:
        """A repo with no remote is always flagged regardless of working-tree
        state."""
        result = RepoResult(path=Path("/repo"), has_remote=False)

        assert result.has_issues() is True

    def test_has_issues_uncommitted(self) -> None:
        """Uncommitted changes are counted as issues."""
        result = RepoResult(
            path=Path("/repo"),
            has_remote=True,
            uncommitted=["M  file.py"],
        )

        assert result.has_issues() is True

    def test_has_issues_untracked(self) -> None:
        """Untracked files are counted as issues."""
        result = RepoResult(
            path=Path("/repo"),
            has_remote=True,
            untracked=["new_file.py"],
        )

        assert result.has_issues() is True

    def test_has_issues_stash(self) -> None:
        """Stashed changes are counted as issues."""
        result = RepoResult(
            path=Path("/repo"),
            has_remote=True,
            stashes=["stash@{0}: WIP on main"],
        )

        assert result.has_issues() is True

    def test_has_issues_clean(self) -> None:
        """A remote-backed repo with a clean working tree has no issues."""
        result = RepoResult(path=Path("/repo"), has_remote=True)

        assert result.has_issues() is False

    def test_short_path_inside_home(self) -> None:
        """Paths under the home directory are rendered with a ~ prefix."""
        home = Path.home()
        result = RepoResult(path=home / "projects" / "myrepo", has_remote=True)

        assert result.short_path() == "~/projects/myrepo"

    def test_short_path_outside_home(self) -> None:
        """Paths outside the home directory are rendered as absolute strings."""
        result = RepoResult(path=Path("/opt/repos/myrepo"), has_remote=True)

        assert result.short_path() == "/opt/repos/myrepo"


# ───────────────────────────────────────────────────────────────────| Gates |──


class TestGates:
    """Tests Gate event initialisation, field defaults, and instance
    isolation."""

    def test_gate_event_is_threading_event(self) -> None:
        """event is initialised as a threading.Event by __post_init__."""
        req = GateSSH(
            url="git@github.com:user/repo.git", repo="~/projects/repo"
        )

        assert isinstance(req.event, threading.Event)

    def test_gate_event_starts_unset(self) -> None:
        """event starts unset so the worker blocks on first wait."""
        req = GateSSH(
            url="git@github.com:user/repo.git", repo="~/projects/repo"
        )

        assert not req.event.is_set()

    def test_gate_ssh_approved_defaults_false(self) -> None:
        """approved defaults to False until the UI resolves the gate."""
        req = GateSSH(
            url="git@github.com:user/repo.git", repo="~/projects/repo"
        )

        assert req.approved is False

    def test_gate_http_stores_error(self) -> None:
        """error is stored verbatim and retry defaults to False."""
        req = GateHTTP(
            url="https://github.com/user/repo.git",
            repo="~/projects/repo",
            error="Connection refused",
        )

        assert req.error == "Connection refused"
        assert req.retry is False

    def test_gate_event_excluded_from_repr(self) -> None:
        """event is excluded from repr to keep log output readable."""
        req = GateSSH(url="git@github.com:user/repo.git", repo="~/repo")

        assert "event" not in repr(req)

    def test_each_gate_gets_independent_event(self) -> None:
        """Each gate instance gets its own event; setting one does not affect
        another."""
        a = GateSSH(url="git@github.com:user/repo.git", repo="~/a")
        b = GateSSH(url="git@github.com:user/repo.git", repo="~/b")
        a.event.set()

        assert not b.event.is_set()


# ────────────────────────────────────────────────────────────────| Messages |──


class TestMessages:
    """Tests NamedTuple message construction and field access."""

    def test_msg_log(self) -> None:
        """MsgLog stores its line in the text field."""
        assert MsgLog("hello").text == "hello"

    def test_msg_status(self) -> None:
        """MsgStatus stores its status string in the text field."""
        assert MsgStatus("Scanning...").text == "Scanning..."

    def test_msg_progress(self) -> None:
        """MsgProgress stores the percentage in the pct field."""
        assert MsgProgress(pct=42.5).pct == pytest.approx(42.5)

    def test_msg_finish_clean(self) -> None:
        """MsgFinish with zero issues has report_path set to None."""
        msg = MsgFinish(issue_count=0, report_path=None)

        assert msg.issue_count == 0
        assert msg.report_path is None

    def test_msg_finish_with_report(self, tmp_path: Path) -> None:
        """MsgFinish stores issue count and report path.

        Args:
            tmp_path (Path): Pytest fixture used to construct a plausible report
                             file path.
        """
        report = tmp_path / "report.log"
        msg = MsgFinish(issue_count=3, report_path=report)

        assert msg.issue_count == 3
        assert msg.report_path == report
