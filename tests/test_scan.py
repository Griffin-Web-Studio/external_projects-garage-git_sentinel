from __future__ import annotations

import configparser
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from src.models import (
    BranchIssue,
    BranchIssueReason,
    RemoteSkipReason,
    RepoResult,
    TagIssue,
)
from src.scan import _check_remotes, _gate_ssh, _scan_repo, scan

# ─────────────────────────────────────────────────────────────────| Helpers |──


class FakeApp:
    """Minimal AppProtocol stub that records all interactions."""

    def __init__(
        self,
        ssh_response: bool = True,
        http_retry_response: bool = False,
    ) -> None:
        self.logs: list[str] = []
        self.statuses: list[str] = []
        self.progresses: list[float] = []
        self.finish_call: tuple[int, Path | None] | None = None
        self.ssh_response = ssh_response
        self.http_retry_response = http_retry_response

    def log(self, text: str) -> None:
        self.logs.append(text)

    def set_status(self, text: str) -> None:
        self.statuses.append(text)

    def set_progress(self, pct: float) -> None:
        self.progresses.append(pct)

    def finish(self, issue_count: int, report_path: Path | None) -> None:
        self.finish_call = (issue_count, report_path)

    def request_ssh(self, url: str, repo_short: str) -> bool:
        return self.ssh_response

    def request_http_retry(self, url: str, repo_short: str, error: str) -> bool:
        return self.http_retry_response


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect Path.home() to tmp_path (HOME on Linux, USERPROFILE on
    Windows)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


@pytest.fixture
def cfg() -> configparser.ConfigParser:
    """Minimal ConfigParser matching the sections consumed by scan()."""
    c = configparser.ConfigParser()
    c["paths"] = {
        "git_root": "git",
        "reports_archive": "git/reports",
        "desktop_override": "Desktop",
    }
    c["reports"] = {
        "desktop_retention_days": "14",
        "report_extension": "log",
    }
    c["staleness"] = {"stale_threshold_days": "90"}
    c["ssh"] = {
        "use_control_master": "false",
        "control_persist_seconds": "300",
    }
    return c


# ───────────────────────────────────────────────────────────────| _gate_ssh |──


class TestGateSSH:
    """Tests for the per-host SSH approval gate."""

    SSH_URL = "git@github.com:u/r.git"
    HOST_KEY = "git@github.com"

    def test_already_declined_returns_false_without_prompting(self) -> None:
        """A host already in ssh_declined is rejected with no prompt."""
        app = FakeApp(ssh_response=True)  # would approve if prompted
        approved: set[str] = set()
        declined = {self.HOST_KEY}
        result = _gate_ssh(
            app,
            "origin",
            self.SSH_URL,
            "~/repo",
            self.HOST_KEY,
            approved,
            declined,
            use_cm=False,
        )
        assert result is False
        assert any("declined" in m for m in app.logs)

    def test_already_approved_returns_true_without_prompting(self) -> None:
        """A host already in ssh_approved is accepted with no prompt."""
        app = FakeApp(ssh_response=False)  # would decline if prompted
        approved = {self.HOST_KEY}
        declined: set[str] = set()
        result = _gate_ssh(
            app,
            "origin",
            self.SSH_URL,
            "~/repo",
            self.HOST_KEY,
            approved,
            declined,
            use_cm=False,
        )
        assert result is True

    def test_new_host_user_approves_adds_to_approved(self) -> None:
        """An approved new host is added to ssh_approved."""
        app = FakeApp(ssh_response=True)
        approved: set[str] = set()
        declined: set[str] = set()
        result = _gate_ssh(
            app,
            "origin",
            self.SSH_URL,
            "~/repo",
            self.HOST_KEY,
            approved,
            declined,
            use_cm=False,
        )
        assert result is True
        assert self.HOST_KEY in approved
        assert self.HOST_KEY not in declined

    def test_new_host_user_declines_adds_to_declined_and_returns_false(
        self,
    ) -> None:
        """A declined new host is added to ssh_declined and False returned."""
        app = FakeApp(ssh_response=False)
        approved: set[str] = set()
        declined: set[str] = set()
        result = _gate_ssh(
            app,
            "origin",
            self.SSH_URL,
            "~/repo",
            self.HOST_KEY,
            approved,
            declined,
            use_cm=False,
        )
        assert result is False
        assert self.HOST_KEY in declined
        assert self.HOST_KEY not in approved

    def test_approve_with_control_master_logs_fido_hint(self) -> None:
        """Approving with ControlMaster enabled logs the FIDO key hint."""
        app = FakeApp(ssh_response=True)
        _gate_ssh(
            app,
            "origin",
            self.SSH_URL,
            "~/repo",
            self.HOST_KEY,
            set(),
            set(),
            use_cm=True,
        )
        assert any("FIDO" in m for m in app.logs)

    def test_approve_without_control_master_logs_cm_disabled(self) -> None:
        """Approving with ControlMaster disabled logs the disabled note."""
        app = FakeApp(ssh_response=True)
        _gate_ssh(
            app,
            "origin",
            self.SSH_URL,
            "~/repo",
            self.HOST_KEY,
            set(),
            set(),
            use_cm=False,
        )
        assert any("ControlMaster disabled" in m for m in app.logs)


# ──────────────────────────────────────────────────────────| _check_remotes |──


class TestCheckRemotes:
    """Tests for the per-repository remote-checking loop."""

    REPO = Path("/test/repo")
    HTTPS_URL = "https://github.com/u/r.git"
    SSH_URL = "git@github.com:u/r.git"

    def _result(self, url: str) -> RepoResult:
        r = RepoResult(path=self.REPO)
        r.remotes = {"origin": url}
        r.has_remote = True
        return r

    def test_https_success_marks_remote_reachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A successful ls-remote marks the RemoteCheck as reachable."""
        monkeypatch.setattr(
            "src.scan.fetch_remote_refs",
            lambda *a, **kw: (True, {"main": "abc"}, {"v1.0"}, ""),
        )
        app = FakeApp()
        result = self._result(self.HTTPS_URL)
        heads, tags = _check_remotes(
            app, self.REPO, result, "~/repo", set(), set(), None, False
        )
        assert "origin" in heads
        assert "v1.0" in tags["origin"]
        assert result.remote_checks[0].reachable is True

    def test_https_failure_no_retry_sets_fetch_failed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed fetch with no retry sets FETCH_FAILED on the check."""
        monkeypatch.setattr(
            "src.scan.fetch_remote_refs",
            lambda *a, **kw: (False, {}, set(), "connection refused"),
        )
        app = FakeApp(http_retry_response=False)
        result = self._result(self.HTTPS_URL)
        _check_remotes(
            app, self.REPO, result, "~/repo", set(), set(), None, False
        )
        rc = result.remote_checks[0]
        assert rc.skip_reason == RemoteSkipReason.FETCH_FAILED
        assert "connection refused" in rc.skip_error

    def test_https_failure_retry_succeeds_marks_reachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed fetch that succeeds on retry marks the remote reachable."""
        responses: Iterator[tuple[bool, dict[str, str], set[str], str]] = iter(
            [
                (False, {}, set(), "timeout"),
                (True, {"main": "abc"}, set(), ""),
            ]
        )
        monkeypatch.setattr(
            "src.scan.fetch_remote_refs",
            lambda *a, **kw: next(responses),
        )
        app = FakeApp(http_retry_response=True)
        result = self._result(self.HTTPS_URL)
        _check_remotes(
            app, self.REPO, result, "~/repo", set(), set(), None, False
        )
        assert result.remote_checks[0].reachable is True

    def test_ssh_user_declines_sets_ssh_declined_and_skips_fetch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Declining SSH approval sets SSH_DECLINED and skips ls-remote."""
        fetch_called: list[bool] = []

        def _fake_fetch_1(
            *_a: object, **_kw: object
        ) -> tuple[bool, dict[str, str], set[str], str]:
            fetch_called.append(True)
            return True, {}, set(), ""

        monkeypatch.setattr("src.scan.fetch_remote_refs", _fake_fetch_1)
        app = FakeApp(ssh_response=False)
        result = self._result(self.SSH_URL)
        _check_remotes(
            app, self.REPO, result, "~/repo", set(), set(), None, False
        )
        assert (
            result.remote_checks[0].skip_reason == RemoteSkipReason.SSH_DECLINED
        )
        assert not fetch_called

    def test_ssh_user_approves_proceeds_to_fetch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Approving SSH triggers ls-remote and marks the remote reachable."""
        monkeypatch.setattr(
            "src.scan.fetch_remote_refs",
            lambda *a, **kw: (True, {}, set(), ""),
        )
        app = FakeApp(ssh_response=True)
        result = self._result(self.SSH_URL)
        _check_remotes(
            app, self.REPO, result, "~/repo", set(), set(), None, False
        )
        assert result.remote_checks[0].reachable is True

    def test_ssh_already_declined_skips_fetch_immediately(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A host already in ssh_declined skips fetch without prompting."""
        fetch_called: list[bool] = []

        def _fake_fetch_2(
            *_a: object, **_kw: object
        ) -> tuple[bool, dict[str, str], set[str], str]:
            fetch_called.append(True)
            return True, {}, set(), ""

        monkeypatch.setattr("src.scan.fetch_remote_refs", _fake_fetch_2)
        app = FakeApp()
        result = self._result(self.SSH_URL)
        declined = {"git@github.com"}
        _check_remotes(
            app, self.REPO, result, "~/repo", set(), declined, None, False
        )
        assert not fetch_called
        assert (
            result.remote_checks[0].skip_reason == RemoteSkipReason.SSH_DECLINED
        )


# ──────────────────────────────────────────────────────────────| _scan_repo |──


class TestScanRepo:
    """Tests for the single-repository scan worker."""

    REPO = Path("/test/repo")

    def _patch_git_ops(
        self,
        monkeypatch: pytest.MonkeyPatch,
        remotes: dict[str, str] | None = None,
        uncommitted: list[str] | None = None,
        untracked: list[str] | None = None,
        stashes: list[str] | None = None,
    ) -> None:
        """Patch all git operations with safe defaults."""
        monkeypatch.setattr(
            "src.scan.get_remotes",
            lambda *a: remotes if remotes is not None else {},
        )
        monkeypatch.setattr(
            "src.scan.check_local_state",
            lambda *a: (uncommitted or [], untracked or [], stashes or []),
        )
        monkeypatch.setattr("src.scan.check_stale", lambda *a: (False, None))
        monkeypatch.setattr("src.scan.get_local_branches", lambda *a: [])
        monkeypatch.setattr("src.scan.get_local_tags", lambda *a: [])
        monkeypatch.setattr(
            "src.scan.fetch_remote_refs",
            lambda *a, **kw: (True, {}, set(), ""),
        )
        monkeypatch.setattr(
            "src.scan.analyse_branches_and_tags", lambda *a: ([], [])
        )

    def test_no_remote_returns_early_and_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Repo without a remote is flagged and returned without remote
        checks."""
        self._patch_git_ops(monkeypatch, remotes={})
        app = FakeApp()
        result = _scan_repo(app, self.REPO, 0, 1, set(), set(), None, False, 90)

        assert not result.has_remote
        assert any("No remote" in m for m in app.logs)

    def test_clean_repo_logs_ok_clean(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A repo with no issues logs 'OK  clean'."""
        self._patch_git_ops(
            monkeypatch, remotes={"origin": "https://github.com/u/r.git"}
        )
        app = FakeApp()
        _scan_repo(app, self.REPO, 0, 1, set(), set(), None, False, 90)
        assert any("OK  clean" in m for m in app.logs)

    def test_uncommitted_files_logged_in_summary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A repo with uncommitted files logs their count in the summary."""
        self._patch_git_ops(
            monkeypatch,
            remotes={"origin": "https://github.com/u/r.git"},
            uncommitted=["M  file.py", "A  new.py"],
        )
        app = FakeApp()
        _scan_repo(app, self.REPO, 0, 1, set(), set(), None, False, 90)
        assert any("2 uncommitted" in m for m in app.logs)

    def test_multiple_issue_types_all_appear_in_summary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All issue types are listed together in the summary line."""
        self._patch_git_ops(
            monkeypatch,
            remotes={"origin": "https://github.com/u/r.git"},
            uncommitted=["M  a.py"],
            untracked=["b.txt"],
            stashes=["stash@{0}: WIP"],
        )
        app = FakeApp()
        _scan_repo(app, self.REPO, 0, 1, set(), set(), None, False, 90)
        summary = next(m for m in app.logs if "uncommitted" in m)
        assert "1 untracked" in summary
        assert "1 stash(es)" in summary

    def test_progress_updated_per_repo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """set_progress is called once per repo within the stage-2 range."""
        self._patch_git_ops(monkeypatch, remotes={})
        app = FakeApp()
        _scan_repo(app, self.REPO, 4, 10, set(), set(), None, False, 90)
        assert any(5.0 < p < 85.0 for p in app.progresses)

    def test_result_path_matches_repo_argument(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The returned RepoResult carries the repo path passed in."""
        self._patch_git_ops(monkeypatch, remotes={})
        app = FakeApp()
        result = _scan_repo(app, self.REPO, 0, 1, set(), set(), None, False, 90)
        assert result.path == self.REPO

    def test_branch_and_tag_issues_logged_in_summary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Branch and tag issue counts appear in the summary log line."""
        self._patch_git_ops(
            monkeypatch, remotes={"origin": "https://github.com/u/r.git"}
        )
        bi = BranchIssue(
            branch="feature",
            remote="origin",
            reason=BranchIssueReason.NOT_IN_ORIGIN,
        )
        ti = TagIssue(tag="v1.0", remote="origin")
        monkeypatch.setattr(
            "src.scan.analyse_branches_and_tags", lambda *a: ([bi], [ti])
        )
        app = FakeApp()
        _scan_repo(app, self.REPO, 0, 1, set(), set(), None, False, 90)
        assert any("1 branch issue(s)" in m for m in app.logs)
        assert any("1 tag issue(s)" in m for m in app.logs)


# ────────────────────────────────────────────────────────────────────| scan |──


class TestScan:
    """Integration tests for the full three-stage scan pipeline."""

    def _patch_all(
        self,
        monkeypatch: pytest.MonkeyPatch,
        repos: list[Path] | None = None,
        remotes: dict[str, str] | None = None,
        uncommitted: list[str] | None = None,
    ) -> None:
        """Patch all git and report operations with safe no-op defaults."""
        monkeypatch.setattr("src.scan.find_git_repos", lambda *a: repos or [])
        monkeypatch.setattr(
            "src.scan.get_remotes",
            lambda *a: remotes if remotes is not None else {},
        )
        monkeypatch.setattr(
            "src.scan.check_local_state",
            lambda *a: (uncommitted or [], [], []),
        )
        monkeypatch.setattr("src.scan.check_stale", lambda *a: (False, None))
        monkeypatch.setattr("src.scan.get_local_branches", lambda *a: [])
        monkeypatch.setattr("src.scan.get_local_tags", lambda *a: [])
        monkeypatch.setattr(
            "src.scan.fetch_remote_refs",
            lambda *a, **kw: (True, {}, set(), ""),
        )
        monkeypatch.setattr(
            "src.scan.analyse_branches_and_tags", lambda *a: ([], [])
        )
        monkeypatch.setattr("src.scan.build_ssh_env", lambda *a: {})
        monkeypatch.setattr("src.scan.close_ssh_sockets", lambda: None)
        monkeypatch.setattr(
            "src.scan.load_previous_issue_keys", lambda *a: set()
        )
        monkeypatch.setattr("src.scan.manage_reports", lambda *a, **kw: None)

    def test_missing_git_root_logs_error_and_exits_early(
        self,
        fake_home: Path,
        cfg: configparser.ConfigParser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """scan() finishes with (0, None) when git_root does not exist."""
        self._patch_all(monkeypatch)
        app = FakeApp()
        scan(app, cfg)
        assert app.finish_call == (0, None)
        assert any("does not exist" in m for m in app.logs)

    def test_no_repos_found_finishes_clean(
        self,
        fake_home: Path,
        cfg: configparser.ConfigParser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """scan() finishes with no report when git_root exists but has no
        repos."""
        (fake_home / "git").mkdir()
        self._patch_all(monkeypatch, repos=[])
        app = FakeApp()
        scan(app, cfg)

        assert app.finish_call == (0, None)

    def test_clean_repo_produces_no_report_file(
        self,
        fake_home: Path,
        cfg: configparser.ConfigParser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A repo with no issues produces no report; finish receives None
        path."""
        (fake_home / "git").mkdir()
        repo = fake_home / "git" / "myrepo"
        self._patch_all(
            monkeypatch,
            repos=[repo],
            remotes={"origin": "https://github.com/u/r.git"},
        )
        app = FakeApp()
        scan(app, cfg)

        assert app.finish_call is not None
        assert app.finish_call[1] is None

    def test_repo_with_uncommitted_writes_report_file(
        self,
        fake_home: Path,
        cfg: configparser.ConfigParser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A repo with uncommitted changes causes a report file to be
        written."""
        (fake_home / "git").mkdir()
        repo = fake_home / "git" / "myrepo"
        self._patch_all(
            monkeypatch,
            repos=[repo],
            remotes={"origin": "https://github.com/u/r.git"},
            uncommitted=["M  file.py"],
        )
        app = FakeApp()
        scan(app, cfg)
        assert app.finish_call is not None
        report_path = app.finish_call[1]
        assert report_path is not None
        assert report_path.exists()
        assert report_path.suffix == ".log"

    def test_repo_without_remote_counted_as_issue(
        self,
        fake_home: Path,
        cfg: configparser.ConfigParser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """finish() receives issue_count=1 for a repo with no remote."""
        (fake_home / "git").mkdir()
        repo = fake_home / "git" / "norem"
        self._patch_all(monkeypatch, repos=[repo], remotes={})
        app = FakeApp()
        scan(app, cfg)
        assert app.finish_call is not None
        assert app.finish_call[0] == 1

    def test_all_three_stages_logged(
        self,
        fake_home: Path,
        cfg: configparser.ConfigParser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """All three stage banners appear in the log in the correct order."""
        (fake_home / "git").mkdir()
        self._patch_all(monkeypatch, repos=[])
        app = FakeApp()
        scan(app, cfg)
        stage_logs = [m for m in app.logs if "Stage" in m]
        assert len(stage_logs) >= 3
        assert "Stage 1" in stage_logs[0]
        assert "Stage 2" in stage_logs[1]
        assert "Stage 3" in stage_logs[2]

    def test_progress_reaches_100_at_end(
        self,
        fake_home: Path,
        cfg: configparser.ConfigParser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The final set_progress call is 100.0."""
        (fake_home / "git").mkdir()
        self._patch_all(monkeypatch, repos=[])
        app = FakeApp()
        scan(app, cfg)
        assert app.progresses[-1] == 100.0

    def test_singular_label_for_one_repo(
        self,
        fake_home: Path,
        cfg: configparser.ConfigParser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """'repository' (singular) is used when exactly one repo is found."""
        (fake_home / "git").mkdir()
        repo = fake_home / "git" / "r"
        self._patch_all(monkeypatch, repos=[repo], remotes={})
        app = FakeApp()
        scan(app, cfg)
        all_text = " ".join(app.logs + app.statuses)
        assert "1 repository" in all_text

    def test_windows_disables_control_master_and_logs_warning(
        self,
        fake_home: Path,
        cfg: configparser.ConfigParser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """On win32 with use_control_master=true, a NOTE is logged and the
        setting is silently forced off for the rest of the scan.

        The cfg fixture supplies a non-empty desktop_override so
        get_desktop_path() returns early and never touches the Windows registry.

        Args:
            fake_home (Path): Temporary HOME; git_root is created inside it.
            cfg (configparser.ConfigParser): Base scan config.
            monkeypatch (pytest.MonkeyPatch): Platform override + git op stubs.
        """
        (fake_home / "git").mkdir()
        cfg["ssh"]["use_control_master"] = "true"
        monkeypatch.setattr(sys, "platform", "win32")
        self._patch_all(monkeypatch, repos=[])
        app = FakeApp()
        scan(app, cfg)

        assert any(
            "ControlMaster is not supported on Windows" in m for m in app.logs
        )
